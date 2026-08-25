from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase

from ..resto_logic import merge_needs


class TestMergeNeeds(TransactionCase):
    """L'agrégateur pur de la liste de courses : additionne par clé,
    ordre de première apparition préservé."""

    def test_agregation_et_ordre(self):
        self.assertEqual(
            merge_needs([('beurre', 0.2), ('sel', 0.01), ('beurre', 0.3)]),
            [('beurre', 0.5), ('sel', 0.01)])

    def test_cles_distinctes_ne_fusionnent_pas(self):
        self.assertEqual(
            merge_needs([('kg-farine', 1.0), ('kg-sucre', 1.0)]),
            [('kg-farine', 1.0), ('kg-sucre', 1.0)])

    def test_vide(self):
        self.assertEqual(merge_needs([]), [])


class TestProduction(TransactionCase):
    """La production de cuisine : plats × portions → liste de courses
    agrégée, convertie dans l'unité de l'économat, coût prévisionnel."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kg = cls.env.ref('uom.product_uom_kgm')
        cls.g = cls.env.ref('uom.product_uom_gram')
        Product = cls.env['product.product']
        cls.boeuf = Product.create({
            'name': "Entrecôte", 'type': 'consu',
            'uom_id': cls.kg.id, 'standard_price': 38.0})
        cls.beurre = Product.create({
            'name': "Beurre de cuisine", 'type': 'consu',
            'uom_id': cls.kg.id, 'standard_price': 12.0})
        cls.plat_viande = Product.create({
            'name': "Entrecôte café de Paris", 'type': 'consu',
            'list_price': 46.0})
        cls.plat_puree = Product.create({
            'name': "Purée maison", 'type': 'consu',
            'list_price': 9.0})
        cls.sans_fiche = Product.create({
            'name': "Plat improvisé", 'type': 'consu'})
        Recipe = cls.env['megga.resto.recipe']
        # 200 g de boeuf + 30 g de beurre par portion.
        cls.recette_viande = Recipe.create({
            'product_id': cls.plat_viande.id,
            'line_ids': [
                (0, 0, {'product_id': cls.boeuf.id,
                        'quantity': 200.0, 'uom_id': cls.g.id}),
                (0, 0, {'product_id': cls.beurre.id,
                        'quantity': 30.0, 'uom_id': cls.g.id}),
            ]})
        # 50 g de beurre par portion.
        cls.recette_puree = Recipe.create({
            'product_id': cls.plat_puree.id,
            'line_ids': [
                (0, 0, {'product_id': cls.beurre.id,
                        'quantity': 50.0, 'uom_id': cls.g.id}),
            ]})
        cls.Production = cls.env['megga.resto.production']

    def _production(self, lines, **kw):
        vals = {'label': "Banquet d'essai", 'line_ids': lines}
        vals.update(kw)
        return self.Production.create(vals)

    def test_sequence_et_affichage(self):
        production = self._production(
            [(0, 0, {'product_id': self.plat_viande.id, 'portions': 4})])
        self.assertTrue(production.name.startswith("PROD/"))
        self.assertIn("Banquet d'essai", production.display_name)

    def test_subtotal_du_plat(self):
        production = self._production(
            [(0, 0, {'product_id': self.plat_viande.id, 'portions': 10})])
        ligne = production.line_ids
        self.assertEqual(ligne.recipe_id, self.recette_viande)
        # (0.2 × 38 + 0.03 × 12) × 10 = (7.6 + 0.36) × 10
        self.assertAlmostEqual(ligne.subtotal, 79.6)

    def test_portions_positives(self):
        with self.assertRaises(ValidationError):
            self._production(
                [(0, 0, {'product_id': self.plat_viande.id,
                         'portions': 0})])

    def test_confirmer_sans_plat_refuse(self):
        production = self._production([])
        with self.assertRaises(UserError):
            production.action_confirm()

    def test_plat_sans_fiche_refuse_nominativement(self):
        production = self._production(
            [(0, 0, {'product_id': self.sans_fiche.id, 'portions': 5})])
        with self.assertRaises(UserError) as erreur:
            production.action_confirm()
        self.assertIn("Plat improvisé", str(erreur.exception))

    def test_courses_converties_et_agregees(self):
        """20 entrecôtes + 30 purées : le boeuf en kilos, et le beurre
        des DEUX fiches sur UNE ligne (0.03 × 20 + 0.05 × 30)."""
        production = self._production([
            (0, 0, {'product_id': self.plat_viande.id, 'portions': 20}),
            (0, 0, {'product_id': self.plat_puree.id, 'portions': 30}),
        ])
        production.action_confirm()
        self.assertEqual(production.state, 'confirmed')
        courses = {l.product_id: l for l in production.shopping_ids}
        self.assertEqual(len(courses), 2, "deux ingrédients, deux lignes")
        boeuf = courses[self.boeuf]
        self.assertAlmostEqual(boeuf.quantity, 4.0,
                               msg="200 g × 20 portions = 4 kg")
        self.assertEqual(boeuf.uom_id, self.kg,
                         "la liste parle l'unité de l'économat")
        beurre = courses[self.beurre]
        self.assertAlmostEqual(beurre.quantity, 2.1,
                               msg="0.6 kg (viande) + 1.5 kg (purée)")
        self.assertAlmostEqual(boeuf.cost, 152.0)
        self.assertAlmostEqual(beurre.cost, 25.2)
        self.assertAlmostEqual(production.cost_total, 177.2)

    def test_cout_courses_egale_cout_plats(self):
        production = self._production([
            (0, 0, {'product_id': self.plat_viande.id, 'portions': 20}),
            (0, 0, {'product_id': self.plat_puree.id, 'portions': 30}),
        ])
        production.action_confirm()
        self.assertAlmostEqual(
            production.cost_total,
            sum(production.line_ids.mapped('subtotal')),
            msg="l'agrégation ne perd ni n'invente un centime")

    def test_recalcul_suit_les_portions(self):
        production = self._production(
            [(0, 0, {'product_id': self.plat_puree.id, 'portions': 10})])
        production.action_confirm()
        self.assertAlmostEqual(production.shopping_ids.quantity, 0.5)
        production.line_ids.portions = 40
        production.action_refresh_shopping()
        self.assertAlmostEqual(production.shopping_ids.quantity, 2.0)

    def test_produite_fige_la_liste(self):
        production = self._production(
            [(0, 0, {'product_id': self.plat_puree.id, 'portions': 10})])
        production.action_confirm()
        production.action_done()
        with self.assertRaises(UserError):
            production.action_refresh_shopping()

    def test_engagee_ne_se_supprime_pas(self):
        production = self._production(
            [(0, 0, {'product_id': self.plat_puree.id, 'portions': 10})])
        production.action_confirm()
        with self.assertRaises(UserError):
            production.unlink()
        production.action_cancel()
        production.unlink()

    def test_rapport_liste_de_courses(self):
        production = self._production(
            [(0, 0, {'product_id': self.plat_viande.id, 'portions': 8})])
        production.action_confirm()
        html = self.env['ir.actions.report']._render_qweb_html(
            'megga_resto.report_shopping', production.ids)[0]
        texte = html.decode()
        self.assertIn("Liste de courses", texte)
        self.assertIn("Entrecôte", texte)
        self.assertIn("Beurre de cuisine", texte)
        self.assertIn(production.name, texte)
