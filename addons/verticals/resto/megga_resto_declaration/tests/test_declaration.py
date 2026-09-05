from odoo.exceptions import AccessError
from odoo.tests import TransactionCase


class TestDeclaration(TransactionCase):
    """La déclaration se déduit des ingrédients : rien ne se saisit sur
    la fiche, et un ingrédient corrigé met à jour tous les plats qui
    l'emploient."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lait = cls.env.ref('megga_resto_declaration.allergen_lait')
        cls.moutarde = cls.env.ref('megga_resto_declaration.allergen_moutarde')
        cls.poissons = cls.env.ref('megga_resto_declaration.allergen_poissons')
        cls.suisse = cls.env.ref('base.ch')

        Product = cls.env['product.product']
        cls.boeuf = Product.create({
            'name': "Entrecôte (kg)", 'type': 'consu',
            'standard_price': 38.0})
        cls.beurre = Product.create({
            'name': "Beurre café de Paris (kg)", 'type': 'consu',
            'standard_price': 24.0})
        cls.plat = Product.create({
            'name': "Entrecôte café de Paris", 'type': 'consu',
            'list_price': 42.0})
        cls.recette = cls.env['megga.resto.recipe'].create({
            'product_id': cls.plat.id,
            'line_ids': [
                (0, 0, {'product_id': cls.boeuf.id, 'quantity': 0.3}),
                (0, 0, {'product_id': cls.beurre.id, 'quantity': 0.05}),
            ],
        })

    # ---------------------------------------------------------- référentiel

    def test_le_referentiel_est_livre(self):
        """Les quatorze allergènes à déclaration obligatoire arrivent
        avec le module : un restaurant n'a pas à taper la loi."""
        allergenes = self.env['megga.resto.allergen'].search([])
        self.assertEqual(len(allergenes), 14)
        self.assertEqual(self.lait.name, "Lait")

    def test_le_referentiel_se_lit_mais_ne_s_ecrit_pas(self):
        """Tout employé doit pouvoir lire les allergènes au service ;
        la liste est fixée par la loi, elle se règle en configuration."""
        serveur = self.env['res.users'].create({
            'name': "Serveuse", 'login': 'resto_declaration_salle',
            'email': "salle@exemple.ch",
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        vu = self.env['megga.resto.allergen'].with_user(serveur).search([])
        self.assertEqual(len(vu), 14)
        with self.assertRaises(AccessError):
            self.lait.with_user(serveur).write({'name': "Lactose"})

    # ------------------------------------------------------- les allergènes

    def test_les_allergenes_remontent_au_plat(self):
        self.beurre.megga_allergen_ids = [(6, 0, (
            self.lait + self.moutarde + self.poissons).ids)]
        self.assertEqual(self.recette.allergen_ids,
                         self.lait + self.moutarde + self.poissons)

    def test_un_allergene_ajoute_se_propage_a_toute_la_carte(self):
        """Le nerf du module : la farine devient allergène une fois, et
        chaque plat qui l'emploie le dit."""
        autre_plat = self.env['product.product'].create({
            'name': "Beurre maison en accompagnement", 'type': 'consu',
            'list_price': 4.0})
        autre_fiche = self.env['megga.resto.recipe'].create({
            'product_id': autre_plat.id,
            'line_ids': [(0, 0, {
                'product_id': self.beurre.id, 'quantity': 0.02})],
        })
        self.beurre.megga_allergen_ids = [(4, self.lait.id)]
        self.assertIn(self.lait, self.recette.allergen_ids)
        self.assertIn(self.lait, autre_fiche.allergen_ids)

    def test_un_allergene_partage_ne_parait_qu_une_fois(self):
        self.boeuf.megga_allergen_ids = [(4, self.lait.id)]
        self.beurre.megga_allergen_ids = [(4, self.lait.id)]
        self.assertEqual(self.recette.allergen_ids, self.lait)

    def test_chercher_les_plats_par_allergene(self):
        """La question du service : « qu'est-ce qui contient du lait ? »
        Le champ n'est pas stocké — c'est la méthode de recherche qui
        traduit la question en requête sur les lignes."""
        self.beurre.megga_allergen_ids = [(4, self.lait.id)]
        Recipe = self.env['megga.resto.recipe']
        avec = Recipe.search([('allergen_ids', 'in', self.lait.ids)])
        self.assertIn(self.recette, avec)
        self.assertNotIn(
            self.recette,
            Recipe.search([('allergen_ids', 'in', self.moutarde.ids)]))

    def test_chercher_les_plats_SANS_un_allergene(self):
        """La négation s'inverse au bon niveau : un plat au lait a aussi
        des ingrédients sans lait — ce n'est pas un plat sans lait."""
        self.beurre.megga_allergen_ids = [(4, self.lait.id)]
        sans_lait = self.env['megga.resto.recipe'].search(
            [('allergen_ids', 'not in', self.lait.ids)])
        self.assertNotIn(self.recette, sans_lait)

    # ------------------------------------------------------- la complétude

    def test_une_fiche_neuve_est_a_completer(self):
        """Aucun ingrédient n'a été regardé : la fiche le dit, et elle
        nomme lesquels."""
        self.assertEqual(self.recette.declaration_state, 'incomplete')
        self.assertIn("Entrecôte (kg) : allergènes non vérifiés",
                      self.recette.declaration_missing)
        self.assertIn(
            "Beurre café de Paris (kg) : allergènes non vérifiés",
            self.recette.declaration_missing)

    def test_verifier_les_ingredients_rend_la_fiche_declarable(self):
        self.boeuf.megga_allergens_checked = True
        self.beurre.megga_allergen_ids = [(4, self.lait.id)]
        self.assertEqual(self.recette.declaration_state, 'complete')
        self.assertFalse(self.recette.declaration_missing)

    def test_la_provenance_manquante_retient_la_fiche(self):
        """La viande demande un pays ; tant qu'il manque, la fiche n'est
        pas déclarable — même si les allergènes, eux, sont réglés."""
        self.boeuf.megga_allergens_checked = True
        self.beurre.megga_allergens_checked = True
        self.boeuf.megga_origin_required = True
        self.assertEqual(self.recette.declaration_state, 'incomplete')
        self.assertEqual(self.recette.declaration_missing,
                         "Entrecôte (kg) : provenance manquante")
        self.boeuf.megga_origin_country_id = self.suisse
        self.assertEqual(self.recette.declaration_state, 'complete')

    def test_une_fiche_sans_ingredient_n_est_pas_declarable(self):
        vide = self.env['megga.resto.recipe'].create({
            'product_id': self.env['product.product'].create({
                'name': "Plat du jour", 'type': 'consu'}).id,
        })
        self.assertEqual(vide.declaration_state, 'incomplete')
        self.assertEqual(vide.declaration_missing,
                         "aucun ingrédient à la fiche")

    def test_la_declaration_ne_bloque_jamais_la_fiche(self):
        """Doctrine de la maison : on signale, on ne barre pas la route.
        Une fiche incomplète se modifie et se sauve comme une autre."""
        self.assertEqual(self.recette.declaration_state, 'incomplete')
        self.recette.notes = "Cuisson au gril."
        self.recette.line_ids[0].quantity = 0.35
        self.assertEqual(self.recette.line_ids[0].quantity, 0.35)

    # -------------------------------------------------------- les provenances

    def test_les_provenances_gardent_l_ordre_et_montrent_les_trous(self):
        """Un ingrédient à déclarer sans pays paraît quand même : le trou
        doit se voir sur le papier, pas disparaître de la liste."""
        self.boeuf.megga_origin_required = True
        self.boeuf.megga_origin_country_id = self.suisse
        self.beurre.megga_origin_required = True
        origines = self.recette._declaration_origins()
        self.assertEqual([o['product'] for o in origines],
                         [self.boeuf, self.beurre])
        self.assertEqual(origines[0]['country'], self.suisse)
        self.assertFalse(origines[1]['country'])

    def test_un_ingredient_repete_n_a_qu_une_provenance(self):
        self.boeuf.megga_origin_required = True
        self.boeuf.megga_origin_country_id = self.suisse
        self.recette.write({'line_ids': [
            (0, 0, {'product_id': self.boeuf.id, 'quantity': 0.05})]})
        origines = self.recette._declaration_origins()
        self.assertEqual(len(origines), 1)
