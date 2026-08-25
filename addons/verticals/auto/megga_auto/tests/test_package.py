from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPackage(AccountTestInvoicingCommon):
    """Les forfaits d'atelier : un gabarit (heures + pièces) posé sur
    l'ordre au prix du jour — main-d'œuvre au taux horaire de la
    société, figé sur la ligne ; pièces au prix de vente courant."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.sudo().megga_labor_rate = 156.0
        brand = cls.env['fleet.vehicle.model.brand'].sudo().create({
            'name': "Toyota"})
        model = cls.env['fleet.vehicle.model'].sudo().create({
            'name': "Corolla", 'brand_id': brand.id})
        cls.client = cls.env['res.partner'].create({
            'name': "Bochud Anne"})
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': model.id,
            'license_plate': "FR 33 214",
            'megga_owner_id': cls.client.id,
        })
        Product = cls.env['product.product']
        cls.filtre = Product.create({
            'name': "Filtre à huile", 'type': 'consu',
            'list_price': 24.0})
        cls.huile = Product.create({
            'name': "Huile 5W-30 (litre)", 'type': 'consu',
            'list_price': 15.0})
        cls.forfait = cls.env['megga.auto.package'].create({
            'name': "Vidange complète",
            'line_ids': [
                Command.create({'kind': 'labor', 'hours': 0.5,
                                'description': "Main-d'œuvre vidange"}),
                Command.create({'kind': 'part',
                                'product_id': cls.filtre.id}),
                Command.create({'kind': 'part',
                                'product_id': cls.huile.id,
                                'quantity': 4.0}),
            ]})

    def _order(self, **kw):
        vals = {
            'vehicle_id': self.vehicle.id,
            'partner_id': self.client.id,
        }
        vals.update(kw)
        return self.env['megga.auto.workorder'].create(vals)

    def test_nom_unique(self):
        """La garde d'unicité nommément, pas n'importe quelle exception :
        un assertRaises(Exception) passerait pour une faute de frappe."""
        with self.assertRaises(ValidationError) as erreur:
            self.env['megga.auto.package'].create({
                'name': "Vidange complète"})
        self.assertIn("existe déjà", str(erreur.exception))

    def test_taux_horaire_atteignable_a_l_ecran(self):
        """Le refus renvoie l'utilisateur vers la fiche Société : le
        champ doit y être, sinon le message envoie dans le vide."""
        arch = self.env['res.company'].get_view(view_type='form')['arch']
        self.assertIn('megga_labor_rate', arch)

    def test_homonyme_archive_dit_qu_il_est_archive(self):
        """Un refus qui désigne un enregistrement invisible est un
        refus incompréhensible."""
        self.forfait.active = False
        with self.assertRaises(ValidationError) as erreur:
            self.env['megga.auto.package'].create({
                'name': "Vidange complète"})
        self.assertIn("archivé", str(erreur.exception))

    def test_bascule_piece_vers_mo_ne_garde_pas_la_designation(self):
        """Sinon la facture porte « Filtre à huile » à 156.- de
        l'heure : le montant est juste, le libellé ment."""
        ligne = self.forfait.line_ids.filtered(
            lambda l: l.product_id == self.filtre)
        self.assertEqual(ligne.description, "Filtre à huile")
        ligne.write({'kind': 'labor', 'hours': 1.0})
        self.assertEqual(ligne.description, "Main-d'œuvre")

    def test_designation_saisie_a_la_main_est_respectee(self):
        ligne = self.forfait.line_ids.filtered(
            lambda l: l.kind == 'labor')
        ligne.description = "Diagnostic électronique"
        ligne.hours = 2.0
        self.assertEqual(ligne.description, "Diagnostic électronique")

    def test_forfait_vide_refuse_au_lieu_de_ne_rien_faire(self):
        """Le sélecteur qui se vide sans rien poser ferait croire au
        mécanicien que le service est facturé."""
        vide = self.env['megga.auto.package'].create({
            'name': "Service 60'000 km (à compléter)"})
        order = self._order(package_to_add_id=vide.id)
        with self.assertRaises(UserError):
            order.action_add_package()
        self.assertFalse(order.line_ids)

    def test_article_d_un_forfait_ne_se_supprime_pas(self):
        """Le vidage silencieux fausserait le prix indicatif et ferait
        échouer la pose."""
        with self.assertRaises(Exception):
            with self.cr.savepoint():
                self.filtre.unlink()

    def test_prix_indicatif_arrondi_a_la_devise(self):
        tiers = self.env['product.product'].create({
            'name': "Joint (au tiers)", 'type': 'consu',
            'list_price': 0.3333})
        forfait = self.env['megga.auto.package'].create({
            'name': "Arrondi",
            'line_ids': [Command.create({
                'kind': 'part', 'product_id': tiers.id,
                'quantity': 1.0})]})
        self.assertEqual(
            forfait.price_estimate,
            forfait.currency_id.round(0.3333),
            "un Monetary se lit arrondi à sa devise")

    def test_ligne_labor_exige_des_heures(self):
        with self.assertRaises(ValidationError):
            self.env['megga.auto.package'].create({
                'name': "Cassé — heures",
                'line_ids': [Command.create({'kind': 'labor',
                                             'hours': 0.0})]})

    def test_ligne_piece_exige_un_article(self):
        with self.assertRaises(ValidationError):
            self.env['megga.auto.package'].create({
                'name': "Cassé — pièce",
                'line_ids': [Command.create({'kind': 'part'})]})

    def test_prix_indicatif(self):
        # 0.5 h × 156 + 24 + 4 × 15 = 78 + 24 + 60
        self.assertAlmostEqual(self.forfait.price_estimate, 162.0)

    def test_pose_copie_les_lignes_au_prix_du_jour(self):
        order = self._order(package_to_add_id=self.forfait.id)
        order.action_add_package()
        self.assertEqual(len(order.line_ids), 3)
        self.assertFalse(order.package_to_add_id,
                         "le champ se vide après la pose")
        mo = order.line_ids.filtered(
            lambda l: l.product_id == self.env.ref(
                'megga_auto.product_labor'))
        self.assertEqual(mo.description, "Main-d'œuvre vidange")
        self.assertAlmostEqual(mo.quantity, 0.5)
        self.assertAlmostEqual(mo.price_unit, 156.0)
        huile = order.line_ids.filtered(
            lambda l: l.product_id == self.huile)
        self.assertAlmostEqual(huile.quantity, 4.0)
        self.assertAlmostEqual(huile.price_unit, 15.0)
        self.assertAlmostEqual(order.amount_total, 162.0)

    def test_taux_fige_sur_la_ligne(self):
        order = self._order(package_to_add_id=self.forfait.id)
        order.action_add_package()
        self.env.company.sudo().megga_labor_rate = 999.0
        mo = order.line_ids.filtered(
            lambda l: l.product_id == self.env.ref(
                'megga_auto.product_labor'))
        self.assertAlmostEqual(mo.price_unit, 156.0,
                               msg="le taux du jour de la pose fait foi")

    def test_poses_cumulatives(self):
        order = self._order(package_to_add_id=self.forfait.id)
        order.action_add_package()
        order.package_to_add_id = self.forfait
        order.action_add_package()
        self.assertEqual(len(order.line_ids), 6)
        self.assertAlmostEqual(order.amount_total, 324.0)

    def test_sans_forfait_choisi_refuse(self):
        order = self._order()
        with self.assertRaises(UserError):
            order.action_add_package()

    def test_ordre_termine_refuse(self):
        order = self._order(package_to_add_id=self.forfait.id)
        order.action_add_package()
        order.action_confirm()
        order.action_done()
        order.package_to_add_id = self.forfait
        with self.assertRaises(UserError):
            order.action_add_package()

    def test_taux_horaire_manquant_refuse(self):
        self.env.company.sudo().megga_labor_rate = 0.0
        order = self._order(package_to_add_id=self.forfait.id)
        with self.assertRaises(UserError):
            order.action_add_package()

    def test_forfait_sans_mo_passe_sans_taux(self):
        self.env.company.sudo().megga_labor_rate = 0.0
        pieces = self.env['megga.auto.package'].create({
            'name': "Pièces seules",
            'line_ids': [Command.create({'kind': 'part',
                                         'product_id': self.filtre.id})]})
        order = self._order(package_to_add_id=pieces.id)
        order.action_add_package()
        self.assertEqual(len(order.line_ids), 1)

    def test_facture_avec_forfait(self):
        order = self._order(package_to_add_id=self.forfait.id)
        order.action_add_package()
        order.action_confirm()
        order.action_done()
        order.action_create_invoice()
        facture = order.invoice_id
        self.assertAlmostEqual(facture.amount_untaxed, 162.0)
        libelles = facture.invoice_line_ids.mapped('name')
        self.assertIn("Main-d'œuvre vidange", libelles)
