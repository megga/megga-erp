from odoo.tests import TransactionCase


class TestDeclarationReport(TransactionCase):
    """Le papier qui s'affiche en salle. Il doit dire la vérité — y
    compris quand elle est incomplète."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lait = cls.env.ref('megga_resto_declaration.allergen_lait')
        Product = cls.env['product.product']
        cls.beurre = Product.create({
            'name': "Beurre café de Paris (kg)", 'type': 'consu',
            'standard_price': 24.0})
        cls.boeuf = Product.create({
            'name': "Entrecôte (kg)", 'type': 'consu',
            'standard_price': 38.0})
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

    def _rendu(self, recettes=None):
        html = self.env['ir.actions.report']._render_qweb_html(
            'megga_resto_declaration.report_declaration',
            (recettes or self.recette).ids)[0]
        return html.decode()

    def test_le_rapport_porte_les_allergenes(self):
        self.boeuf.megga_allergens_checked = True
        self.beurre.megga_allergen_ids = [(4, self.lait.id)]
        texte = self._rendu()
        self.assertIn("Déclaration de la carte", texte)
        self.assertIn("Entrecôte café de Paris", texte)
        self.assertIn("Lait", texte)

    def test_un_plat_incomplet_porte_son_avertissement(self):
        """Une déclaration qui passe sous silence ce qu'elle ignore est
        pire que pas de déclaration : le plat sort barré."""
        texte = self._rendu()
        self.assertIn("Déclaration incomplète", texte)
        self.assertIn("allergènes non vérifiés", texte)

    def test_aucun_allergene_se_dit_autrement_que_non_renseigne(self):
        """« Aucun » et « non renseignés » ne veulent pas dire la même
        chose au client : le rapport ne les confond pas."""
        self.assertIn("non renseignés", self._rendu())
        self.boeuf.megga_allergens_checked = True
        self.beurre.megga_allergens_checked = True
        texte = self._rendu()
        self.assertIn("aucun", texte)
        self.assertNotIn("non renseignés", texte)

    def test_la_provenance_manquante_se_voit_sur_le_papier(self):
        self.boeuf.megga_allergens_checked = True
        self.beurre.megga_allergens_checked = True
        self.boeuf.megga_origin_required = True
        texte = self._rendu()
        self.assertIn("Provenance", texte)
        self.assertIn("à compléter", texte)
        # Le libellé du pays vient du cœur, donc de la langue de la base
        # (« Switzerland » sur une base de test en anglais) : on assère
        # sur le nom réel, jamais sur une traduction supposée.
        suisse = self.env.ref('base.ch')
        self.boeuf.megga_origin_country_id = suisse
        self.assertIn(suisse.name, self._rendu())
