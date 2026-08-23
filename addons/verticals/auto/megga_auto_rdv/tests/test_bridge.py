from datetime import date, datetime

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestAutoRdvBridge(TransactionCase):
    """Le pont réservation → véhicule → ordre de réparation : rattacher
    seulement quand il n'y a pas d'ambiguïté, et pré-remplir l'atelier
    depuis le rendez-vous."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff = cls.env['res.users'].create({
            'name': "Mécanicien Pont", 'login': "auto_bridge_staff",
            'email': "auto.bridge@exemple.ch"})
        cls.rdv_type = cls.env['megga.rdv.type'].create({
            'name': "Passage atelier",
            'duration': 0.5,
            'tz': 'Europe/Zurich',
            'min_notice_hours': 12,
            'horizon_days': 7,
            'user_ids': [(6, 0, cls.staff.ids)],
            'line_ids': [(0, 0, {'dayofweek': str(jour),
                                 'hour_from': 9.0, 'hour_to': 12.0})
                         for jour in range(5)],
        })
        brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': "Toyota"})
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': "Yaris", 'brand_id': brand.id})
        cls.client = cls.env['res.partner'].create({
            'name': "Morand Frédéric", 'email': "morand@exemple.ch"})
        cls.golf = cls.env['fleet.vehicle'].create({
            'model_id': cls.model.id, 'license_plate': "VD 214 780",
            'megga_owner_id': cls.client.id})
        cls.now = datetime(2026, 9, 2, 8, 0)
        cls.Booking = cls.env['megga.rdv.booking']

    def _reserver(self, start, nom="Morand Frédéric",
                  email="morand@exemple.ch"):
        return self.Booking._reserver(
            self.rdv_type, start, nom, email, now=self.now)

    def test_un_seul_vehicule_rattache(self):
        booking = self._reserver(datetime(2026, 9, 3, 7, 0))
        self.assertEqual(booking.vehicle_id, self.golf,
                         "un seul véhicule au parc : rattaché d'office")
        self.assertEqual(booking.partner_id, self.client)

    def test_plusieurs_vehicules_le_comptoir_tranche(self):
        self.env['fleet.vehicle'].create({
            'model_id': self.model.id, 'license_plate': "VD 999 111",
            'megga_owner_id': self.client.id})
        booking = self._reserver(datetime(2026, 9, 3, 7, 0))
        self.assertFalse(booking.vehicle_id,
                         "deux véhicules : aucune devinette")

    def test_client_inconnu_sans_vehicule(self):
        booking = self._reserver(datetime(2026, 9, 3, 7, 0),
                                 nom="Nadia Neuve",
                                 email="nadia@exemple.ch")
        self.assertFalse(booking.vehicle_id)
        self.assertEqual(booking.partner_id.email, "nadia@exemple.ch",
                         "le contact est tout de même garanti")

    def test_type_sans_rattachement(self):
        self.rdv_type.auto_vehicle_link = False
        booking = self._reserver(datetime(2026, 9, 3, 7, 0))
        self.assertFalse(booking.vehicle_id)

    def test_ordre_de_reparation_prerempli(self):
        self.env['fleet.vehicle.odometer'].create({
            'vehicle_id': self.golf.id, 'value': 48350.0})
        booking = self._reserver(datetime(2026, 9, 3, 7, 0))
        action = booking.action_create_workorder()
        order = booking.workorder_id
        self.assertTrue(order)
        self.assertEqual(action['res_id'], order.id)
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.vehicle_id, self.golf)
        self.assertEqual(order.partner_id, self.client)
        self.assertEqual(order.mechanic_id, self.staff,
                         "le mécanicien est l'intervenant réservé")
        self.assertEqual(order.date, date(2026, 9, 3))
        self.assertAlmostEqual(order.odometer_in, 48350.0)
        self.assertIn(booking.name, order.diagnosis)

    def test_date_locale_pas_utc(self):
        """22:30 UTC = minuit passé à Zurich : l'ordre porte la date
        LOCALE du rendez-vous, pas celle du fuseau serveur."""
        booking = self.Booking.create({
            'type_id': self.rdv_type.id,
            'guest_name': "Morand Frédéric",
            'email': "morand@exemple.ch",
            'start': datetime(2026, 9, 3, 22, 30),
        })
        booking.action_create_workorder()
        self.assertEqual(booking.workorder_id.date, date(2026, 9, 4))

    def test_ordre_unique_et_vehicule_requis(self):
        booking = self._reserver(datetime(2026, 9, 3, 7, 0))
        booking.action_create_workorder()
        with self.assertRaises(UserError):
            booking.action_create_workorder()
        sans_vehicule = self._reserver(datetime(2026, 9, 3, 8, 0),
                                       nom="Nadia Neuve",
                                       email="nadia@exemple.ch")
        with self.assertRaises(UserError):
            sans_vehicule.action_create_workorder()

    def test_vehicule_montre_ses_reservations(self):
        booking = self._reserver(datetime(2026, 9, 3, 7, 0))
        self.assertIn(booking, self.golf.rdv_booking_ids)
        self.assertEqual(self.golf.rdv_booking_count, 1)
