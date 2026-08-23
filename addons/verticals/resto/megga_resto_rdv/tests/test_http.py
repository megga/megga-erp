import re

from odoo import fields
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestRestoRdvHttp(HttpCase):
    """Le parcours public complet d'une réservation de table : le
    formulaire demande les couverts, et la valeur postée arrive jusqu'à
    l'entrée du carnet."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        staff = cls.env['res.users'].create({
            'name': "Maître d'hôtel Web", 'login': "resto_web_staff",
            'email': "resto.web@exemple.ch"})
        floor = cls.env['restaurant.floor'].create({'name': "Salle web"})
        cls.env['restaurant.table'].create({
            'floor_id': floor.id, 'table_number': 401, 'seats': 6})
        cls.rdv_type = cls.env['megga.rdv.type'].create({
            'name': "Table en ligne",
            'duration': 1.5,
            'tz': 'Europe/Zurich',
            'min_notice_hours': 0,
            'horizon_days': 2,
            'resto_reservation': True,
            'user_ids': [(6, 0, staff.ids)],
            'line_ids': [(0, 0, {'dayofweek': str(jour),
                                 'hour_from': 0.0, 'hour_to': 23.5})
                         for jour in range(7)],
        })

    def test_couverts_de_bout_en_bout(self):
        creneau = fields.Datetime.to_string(
            self.rdv_type._available_slots()[0]['start'])
        formulaire = self.url_open(
            '/rdv/%d/formulaire?creneau=%s'
            % (self.rdv_type.id, creneau.replace(' ', '%20')))
        self.assertEqual(formulaire.status_code, 200)
        self.assertIn("Couverts", formulaire.text,
                      "le formulaire d'un type restaurant demande les "
                      "couverts")
        jeton = re.search(
            r'name="csrf_token"\s+value="([^"]+)"', formulaire.text)
        self.assertTrue(jeton)
        reponse = self.url_open(
            '/rdv/%d/reserver' % self.rdv_type.id,
            data={
                'csrf_token': jeton.group(1),
                'creneau': creneau,
                'nom': "Tablée Web",
                'email': "tablee.web@exemple.ch",
                'telephone': "+41 21 555 44 55",
                'couverts': "4",
            })
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("Rendez-vous confirmé", reponse.text)
        booking = self.env['megga.rdv.booking'].search(
            [('email', '=', "tablee.web@exemple.ch")], limit=1)
        self.assertTrue(booking)
        entree = booking.resto_reservation_id
        self.assertTrue(entree, "l'entrée du carnet existe")
        self.assertEqual(entree.party_size, 4,
                         "les couverts postés arrivent jusqu'au carnet")
        self.assertEqual(entree.state, 'confirmed')
