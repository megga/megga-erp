from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestRecipeUom(TransactionCase):
    """La conversion d'unités des fiches techniques : la cuisine pèse en
    grammes ce que l'économat achète en kilos — le coût est converti par
    l'arbre d'unités du cœur (19 : racines communes, plus de
    catégories)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kg = cls.env.ref('uom.product_uom_kgm')
        cls.g = cls.env.ref('uom.product_uom_gram')
        cls.litre = cls.env.ref('uom.product_uom_litre')
        Product = cls.env['product.product']
        cls.boeuf = Product.create({
            'name': "Entrecôte", 'type': 'consu',
            'uom_id': cls.kg.id, 'standard_price': 38.0})
        cls.huile = Product.create({
            'name': "Huile d'olive", 'type': 'consu',
            'uom_id': cls.litre.id, 'standard_price': 30.0})
        cls.plat = Product.create({
            'name': "Entrecôte, huile vierge", 'type': 'consu',
            'list_price': 44.0})
        cls.Recipe = cls.env['megga.resto.recipe']

    def _recette(self, lines):
        return self.Recipe.create({
            'product_id': self.plat.id, 'line_ids': lines})

    def test_defaut_l_unite_de_l_ingredient(self):
        recette = self._recette(
            [(0, 0, {'product_id': self.boeuf.id, 'quantity': 0.3})])
        ligne = recette.line_ids
        self.assertEqual(ligne.uom_id, self.kg,
                         "sans choix, l'unité de l'ingrédient")
        self.assertAlmostEqual(ligne.cost, 11.4)   # 0.3 kg × 38

    def test_conversion_g_vers_kg(self):
        recette = self._recette([(0, 0, {
            'product_id': self.boeuf.id,
            'quantity': 300.0, 'uom_id': self.g.id})])
        self.assertAlmostEqual(recette.line_ids.cost, 11.4,
                               msg="300 g d'un article au kilo : 0.3 × 38")
        self.assertAlmostEqual(recette.cost_total, 11.4)

    def test_pas_d_arrondi_parasite(self):
        """1 g d'un article au kilo : l'arrondi par défaut du cœur (à
        l'arrondi de l'unité cible, vers le haut) donnerait 0.01 kg — un
        coût multiplié par dix."""
        truffe = self.env['product.product'].create({
            'name': "Truffe noire", 'type': 'consu',
            'uom_id': self.kg.id, 'standard_price': 1000.0})
        recette = self._recette([(0, 0, {
            'product_id': truffe.id,
            'quantity': 1.0, 'uom_id': self.g.id})])
        self.assertAlmostEqual(recette.line_ids.cost, 1.0)

    def test_unite_maison(self):
        """Le cœur ne livre pas le centilitre : un établissement crée la
        sienne (0.01 litre) et la fiche la convertit comme les autres."""
        cl = self.env['uom.uom'].create({
            'name': "cl (maison)",
            'relative_uom_id': self.litre.id,
            'relative_factor': 0.01,
        })
        recette = self._recette([(0, 0, {
            'product_id': self.huile.id,
            'quantity': 5.0, 'uom_id': cl.id})])
        self.assertAlmostEqual(recette.line_ids.cost, 1.5,
                               msg="5 cl × 30 CHF/litre")

    def test_famille_incompatible_refusee(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._recette([(0, 0, {
                'product_id': self.huile.id,
                'quantity': 100.0, 'uom_id': self.g.id})])

    def test_changer_d_ingredient_reprend_son_unite(self):
        recette = self._recette([(0, 0, {
            'product_id': self.boeuf.id,
            'quantity': 300.0, 'uom_id': self.g.id})])
        ligne = recette.line_ids
        ligne.product_id = self.huile
        self.assertEqual(ligne.uom_id, self.litre,
                         "changer d'ingrédient reprend SON unité — pas "
                         "de grammes d'huile hérités par accident")
        self.assertAlmostEqual(ligne.cost, 9000.0)   # 300 litres × 30

    def test_report_du_cout_converti(self):
        recette = self._recette([
            (0, 0, {'product_id': self.boeuf.id,
                    'quantity': 300.0, 'uom_id': self.g.id}),
            (0, 0, {'product_id': self.huile.id, 'quantity': 0.02}),
        ])
        self.assertAlmostEqual(recette.cost_total, 12.0)   # 11.4 + 0.6
        recette.action_apply_cost()
        self.assertAlmostEqual(self.plat.standard_price, 12.0)