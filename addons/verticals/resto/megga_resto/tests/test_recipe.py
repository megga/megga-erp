from odoo.tests import TransactionCase


class TestRecipe(TransactionCase):
    """Fiches techniques : coût matière depuis le prix de revient des
    ingrédients, marges face au prix de carte, report du coût."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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

    def test_cout_matiere(self):
        couts = self.recette.line_ids.mapped('cost')
        self.assertAlmostEqual(sum(couts), 12.6)   # 0.3×38 + 0.05×24
        self.assertAlmostEqual(self.recette.cost_total, 12.6)

    def test_marges(self):
        self.assertAlmostEqual(self.recette.margin, 29.4)
        self.assertAlmostEqual(self.recette.margin_pct, 70.0)
        self.assertAlmostEqual(self.recette.food_cost, 30.0)

    def test_prix_de_carte_zero(self):
        self.plat.list_price = 0.0
        self.assertEqual(self.recette.margin_pct, 0.0)
        self.assertEqual(self.recette.food_cost, 0.0)

    def test_report_du_cout(self):
        self.recette.action_apply_cost()
        self.assertAlmostEqual(self.plat.standard_price, 12.6)

    def test_le_cout_suit_le_prix_des_ingredients(self):
        """Changer le prix de revient d'un ingrédient recalcule la fiche
        (dépendance sur une propriété par société — le piège classique)."""
        self.beurre.standard_price = 30.0
        ligne_beurre = self.recette.line_ids.filtered(
            lambda l: l.product_id == self.beurre)
        self.assertAlmostEqual(ligne_beurre.cost, 1.5)
        self.assertAlmostEqual(self.recette.cost_total, 12.9)
