import base64

from odoo import Command
from odoo.tests import HttpCase, tagged

SIGNATURE = base64.b64encode(b"paraphe")


@tagged('post_install', '-at_install')
class TestDentalPortalHttp(HttpCase):
    """Les routes, en vrai : les pages listent le sien, le PDF du
    voisin est bloqué AVANT tout rendu."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_reset_password=True))
        Patient = cls.env['megga.dental.patient']
        Users = cls.env['res.users']
        portal_group = cls.env.ref('base.group_portal')
        produit = cls.env['product.product'].create({
            'name': "Contrôle", 'type': 'service', 'list_price': 120.0})

        def monte(nom, login):
            patient = Patient.create({'name': nom})
            Users.create({
                'name': nom, 'login': login,
                'email': '%s@exemple.ch' % login,
                'password': 'Portail-123!',
                'partner_id': patient.partner_id.id,
                'group_ids': [(6, 0, [portal_group.id])],
            })
            treatment = cls.env['megga.dental.treatment'].create({
                'patient_id': patient.id,
                'line_ids': [Command.create({
                    'product_id': produit.id, 'price_unit': 120.0})],
            })
            prescription = cls.env['megga.dental.prescription'].create({
                'patient_id': patient.id,
                'line_ids': [Command.create({
                    'name': "Amoxicilline", 'posology': "3 x par jour"})],
            })
            prescription.action_issue()
            return patient, treatment, prescription

        cls.patient_a, cls.trt_a, cls.ord_a = monte(
            "Alice Web", "web.alice")
        cls.patient_b, cls.trt_b, cls.ord_b = monte(
            "Bruno Web", "web.bruno")

    def test_les_pages_listent_le_sien(self):
        self.authenticate("web.alice", "Portail-123!")
        page = self.url_open('/my/traitements')
        self.assertEqual(page.status_code, 200)
        self.assertIn(self.trt_a.name, page.text)
        self.assertNotIn(self.trt_b.name, page.text)
        page = self.url_open('/my/ordonnances')
        self.assertEqual(page.status_code, 200)
        self.assertIn(self.ord_a.name, page.text)
        self.assertNotIn(self.ord_b.name, page.text)

    def test_le_pdf_du_voisin_est_bloque(self):
        self.authenticate("web.alice", "Portail-123!")
        reponse = self.url_open(
            '/my/ordonnances/%d/pdf' % self.ord_b.id)
        self.assertNotEqual(reponse.status_code, 200)

    def test_la_carte_d_accueil(self):
        self.authenticate("web.alice", "Portail-123!")
        page = self.url_open('/my')
        self.assertEqual(page.status_code, 200)
        self.assertIn("Mon dossier dentaire", page.text)
