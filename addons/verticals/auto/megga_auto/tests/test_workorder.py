from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWorkorder(AccountTestInvoicingCommon):
    """Cycle devis -> accepté -> terminé -> facture sur plan comptable
    suisse, et report du compteur dans le journal fleet du cœur."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        # Décor en sudo : marques et modèles sont réservés à
        # Fleet/Administrateur (lecture seule pour les internes, comme en
        # production). Le reste du test tourne sous droits normaux.
        brand = cls.env['fleet.vehicle.model.brand'].sudo().create({
            'name': "Škoda"})
        model = cls.env['fleet.vehicle.model'].sudo().create({
            'name': "Octavia", 'brand_id': brand.id})
        cls.client = cls.env['res.partner'].create({
            'name': "Morand Frédéric"})
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': model.id,
            'license_plate': "VD 214 780",
            'megga_owner_id': cls.client.id,
        })
        cls.forfait = cls.env['product.product'].create({
            'name': "Service annuel (forfait)", 'type': 'service',
            'list_price': 420.0})
        cls.plaquettes = cls.env['product.product'].create({
            'name': "Plaquettes avant (jeu)", 'type': 'consu',
            'list_price': 260.0})

    def _order(self, **kw):
        vals = {
            'vehicle_id': self.vehicle.id,
            'partner_id': self.client.id,
            'date': '2026-08-23',
            'odometer_in': 48350.0,
            'line_ids': [
                Command.create({
                    'product_id': self.forfait.id,
                    'description': "Service annuel (forfait)",
                    'quantity': 1.0, 'price_unit': 420.0,
                }),
                Command.create({
                    'product_id': self.plaquettes.id,
                    'description': "Plaquettes avant (jeu)",
                    'quantity': 1.0, 'price_unit': 260.0,
                }),
            ],
        }
        vals.update(kw)
        return self.env['megga.auto.workorder'].create(vals)

    def test_sequence_et_montants(self):
        order = self._order()
        self.assertTrue(order.name.startswith('OR/'))
        self.assertAlmostEqual(order.amount_total, 680.0)

    def test_accepter_exige_des_lignes(self):
        vide = self._order(line_ids=[])
        with self.assertRaises(UserError):
            vide.action_confirm()

    def test_cloture_reporte_le_compteur(self):
        """Terminer l'ordre écrit le relevé dans le journal de compteur du
        cœur — et le compteur du véhicule (max des relevés) suit."""
        Odometer = self.env['fleet.vehicle.odometer']
        avant = Odometer.search_count(
            [('vehicle_id', '=', self.vehicle.id)])
        order = self._order()
        order.action_confirm()
        order.action_done()
        releves = Odometer.search(
            [('vehicle_id', '=', self.vehicle.id)])
        self.assertEqual(len(releves), avant + 1)
        self.assertAlmostEqual(max(releves.mapped('value')), 48350.0)
        self.assertAlmostEqual(self.vehicle.odometer, 48350.0)

    def test_facturation(self):
        order = self._order()
        order.action_confirm()
        order.action_done()
        action = order.action_create_invoice()
        facture = order.invoice_id
        self.assertTrue(facture)
        self.assertEqual(action['res_id'], facture.id)
        self.assertEqual(facture.move_type, 'out_invoice')
        self.assertEqual(facture.partner_id, self.client)
        self.assertAlmostEqual(facture.amount_untaxed, 680.0)
        self.assertTrue(facture.invoice_origin.startswith(order.name))
        self.assertIn("VD 214 780", facture.invoice_origin,
                      "la plaque doit suivre sur le document d'origine")

    def test_double_facturation_bloquee(self):
        order = self._order()
        order.action_confirm()
        order.action_done()
        order.action_create_invoice()
        with self.assertRaises(UserError):
            order.action_create_invoice()

    def test_facturation_exige_termine(self):
        order = self._order()
        with self.assertRaises(UserError):
            order.action_create_invoice()

    def test_designation_posee_a_la_source(self):
        """Sans passer par l'interface : une ligne creee par script ou
        par un forfait porte quand meme sa designation (le portail
        client s'appuie dessus)."""
        order = self._order(line_ids=[Command.create({
            'product_id': self.plaquettes.id, 'price_unit': 260.0})])
        self.assertEqual(order.line_ids.description,
                         self.plaquettes.display_name)

    def test_designation_saisie_est_respectee(self):
        order = self._order(line_ids=[Command.create({
            'product_id': self.plaquettes.id,
            'description': "Plaquettes + rectification disques",
            'price_unit': 320.0})])
        self.assertEqual(order.line_ids.description,
                         "Plaquettes + rectification disques")
