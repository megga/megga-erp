import re

from odoo import fields
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestRdvHttp(HttpCase):
    """Les pages publiques, de bout en bout : liste, créneaux, et une
    réservation complète soumise par HTTP (CSRF compris)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        staff = cls.env['res.users'].create({
            'name': "Praticien Web", 'login': "rdv_web_staff",
            'email': "web.staff@exemple.ch"})
        # Ouvert tous les jours, préavis nul : il existe toujours un
        # créneau réel, quel que soit le moment où la suite tourne.
        cls.rdv_type = cls.env['megga.rdv.type'].create({
            'name': "Contrôle en ligne",
            'duration': 0.5,
            'tz': 'Europe/Zurich',
            'min_notice_hours': 0,
            'horizon_days': 2,
            'user_ids': [(6, 0, staff.ids)],
            'line_ids': [(0, 0, {'dayofweek': str(jour),
                                 'hour_from': 0.0, 'hour_to': 23.5})
                         for jour in range(7)],
        })

    def test_page_des_prestations(self):
        page = self.url_open('/rdv')
        self.assertEqual(page.status_code, 200)
        self.assertIn("Contrôle en ligne", page.text)

    def test_page_des_creneaux(self):
        page = self.url_open('/rdv/%d' % self.rdv_type.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn("/formulaire?creneau=", page.text,
                      "au moins un créneau cliquable est proposé")
        inconnu = self.url_open('/rdv/999999')
        self.assertEqual(inconnu.status_code, 404)

    def test_reservation_de_bout_en_bout(self):
        creneau = fields.Datetime.to_string(
            self.rdv_type._available_slots()[0]['start'])
        formulaire = self.url_open(
            '/rdv/%d/formulaire?creneau=%s'
            % (self.rdv_type.id, creneau.replace(' ', '%20')))
        self.assertEqual(formulaire.status_code, 200)
        jeton = re.search(
            r'name="csrf_token"\s+value="([^"]+)"', formulaire.text)
        self.assertTrue(jeton, "le formulaire embarque un jeton CSRF")
        reponse = self.url_open(
            '/rdv/%d/reserver' % self.rdv_type.id,
            data={
                'csrf_token': jeton.group(1),
                'creneau': creneau,
                'nom': "Client Web",
                'email': "client.web@exemple.ch",
                'telephone': "+41 21 555 99 88",
            })
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("Rendez-vous confirmé", reponse.text)
        booking = self.env['megga.rdv.booking'].search(
            [('email', '=', "client.web@exemple.ch")], limit=1)
        self.assertTrue(booking)
        self.assertEqual(booking.state, 'confirmed')
        self.assertTrue(booking.event_id)
