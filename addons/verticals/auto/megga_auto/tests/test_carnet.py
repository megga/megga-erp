from odoo import Command
from odoo.tests import TransactionCase


class TestCarnet(TransactionCase):
    """Le carnet d'entretien imprimable : les interventions TERMINÉES,
    chronologiques, avec dates, compteur et travaux — et jamais les
    prix (le carnet se remet à l'acheteur, pas les tarifs du garage)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': "Subaru"})
        model = cls.env['fleet.vehicle.model'].create({
            'name': "Forester", 'brand_id': brand.id})
        cls.owner = cls.env['res.partner'].create({
            'name': "Chappuis Léon"})
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': model.id,
            'license_plate': "JU 55 731",
            'vin_sn': "JF1SH5LS5AG733012",
            'megga_owner_id': cls.owner.id,
            'megga_first_circulation': '2020-03-15',
        })
        cls.vidange = cls.env['product.product'].create({
            'name': "Service vidange", 'type': 'service',
            'list_price': 777.77})
        cls.Workorder = cls.env['megga.auto.workorder']

    def _order(self, date, km, description, state='done'):
        order = self.Workorder.create({
            'vehicle_id': self.vehicle.id,
            'partner_id': self.owner.id,
            'date': date,
            'odometer_in': km,
            'line_ids': [Command.create({
                'product_id': self.vidange.id,
                'description': description,
                'quantity': 1.0,
                'price_unit': 777.77,
            })],
        })
        if state != 'draft':
            order.action_confirm()
        if state == 'done':
            order.action_done()
        return order

    def _html(self):
        html, _kind = self.env['ir.actions.report']._render_qweb_html(
            'megga_auto.report_carnet', self.vehicle.ids)
        return html.decode()

    def test_seules_les_interventions_terminees(self):
        fait = self._order('2026-03-10', 61000, "Service annuel")
        self._order('2026-05-02', 63000, "Devis pneus", state='draft')
        self._order('2026-06-15', 64000, "Accepté non fait",
                    state='confirmed')
        self.assertEqual(self.vehicle._megga_carnet_workorders(), fait)

    def test_le_carnet_montre_l_essentiel(self):
        self._order('2026-03-10', 61000, "Service annuel + filtres")
        html = self._html()
        self.assertIn("Carnet d'entretien", html)
        self.assertIn("JU 55 731", html)
        self.assertIn("JF1SH5LS5AG733012", html)
        self.assertIn("Forester", html)
        self.assertIn("Chappuis Léon", html)
        self.assertIn("61000 km", html)
        self.assertIn("Service annuel + filtres", html)

    def test_jamais_les_prix(self):
        # « 777.77 » et pas « 777 » : le logo de l'en-tête, encodé en
        # base64, peut contenir « 777 » par hasard — mais jamais un
        # point (hors alphabet base64).
        self._order('2026-03-10', 61000, "Service annuel")
        html = self._html()
        self.assertNotIn("777.77", html,
                         "ni le prix unitaire ni le total ne figurent "
                         "au carnet")

    def test_ordre_chronologique(self):
        self._order('2026-02-01', 58000, "Deuxième intervention")
        self._order('2024-11-20', 41000, "Première intervention")
        html = self._html()
        self.assertLess(html.index("Première intervention"),
                        html.index("Deuxième intervention"),
                        "du plus ancien au plus récent, comme un carnet "
                        "papier")

    def test_vehicule_vierge(self):
        html = self._html()
        self.assertIn("Aucune intervention terminée", html)

    def test_reliure_au_vehicule(self):
        report = self.env['ir.actions.report'].search(
            [('report_name', '=', 'megga_auto.report_carnet')])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.binding_model_id.model, 'fleet.vehicle',
                         "le carnet s'imprime depuis la fiche véhicule")
