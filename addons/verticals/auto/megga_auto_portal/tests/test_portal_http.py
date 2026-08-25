from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestAutoPortalHttp(HttpCase):
    """Les routes, en vrai : les pages listent le sien, le carnet du
    véhicule du voisin est bloqué AVANT tout rendu."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context,
                                       no_reset_password=True))
        Users = cls.env['res.users']
        portal_group = cls.env.ref('base.group_portal')
        brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': "Renault"})
        modele = cls.env['fleet.vehicle.model'].create({
            'name': "Clio", 'brand_id': brand.id})
        piece = cls.env['product.product'].create({
            'name': "Filtre habitacle", 'type': 'consu',
            'list_price': 45.0})

        def monte(nom, login, plaque):
            partner = cls.env['res.partner'].create({'name': nom})
            Users.create({
                'name': nom, 'login': login,
                'email': '%s@exemple.ch' % login,
                'password': 'Portail-123!',
                'partner_id': partner.id,
                'group_ids': [(6, 0, [portal_group.id])],
            })
            vehicle = cls.env['fleet.vehicle'].create({
                'model_id': modele.id,
                'license_plate': plaque,
                'megga_owner_id': partner.id,
            })
            ordre = cls.env['megga.auto.workorder'].create({
                'vehicle_id': vehicle.id,
                'partner_id': partner.id,
                'line_ids': [Command.create({
                    'product_id': piece.id, 'price_unit': 45.0})],
            })
            ordre.action_confirm()
            return vehicle, ordre

        cls.veh_a, cls.ord_a = monte(
            "Web Client A", "web.autoa", "VD 111 111")
        cls.veh_b, cls.ord_b = monte(
            "Web Client B", "web.autob", "VD 222 222")

    def test_les_pages_listent_le_sien(self):
        self.authenticate("web.autoa", "Portail-123!")
        page = self.url_open('/my/vehicules')
        self.assertEqual(page.status_code, 200)
        self.assertIn("VD 111 111", page.text)
        self.assertNotIn("VD 222 222", page.text)
        page = self.url_open('/my/reparations')
        self.assertEqual(page.status_code, 200)
        self.assertIn(self.ord_a.name, page.text)
        self.assertNotIn(self.ord_b.name, page.text)

    def test_le_carnet_du_voisin_est_bloque(self):
        self.authenticate("web.autoa", "Portail-123!")
        reponse = self.url_open(
            '/my/vehicules/%d/carnet' % self.veh_b.id)
        self.assertNotEqual(reponse.status_code, 200)

    def test_la_carte_d_accueil(self):
        self.authenticate("web.autoa", "Portail-123!")
        page = self.url_open('/my')
        self.assertEqual(page.status_code, 200)
        self.assertIn("Mon garage", page.text)
