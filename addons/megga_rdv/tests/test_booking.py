from datetime import datetime, timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestBooking(TransactionCase):
    """La réservation : re-vérification du créneau, choix de
    l'intervenant le moins chargé, contact par e-mail, événement
    d'agenda, annulation qui libère le créneau."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff1 = cls.env['res.users'].create({
            'name': "Praticien Un", 'login': "book_staff1",
            'email': "bstaff1@exemple.ch"})
        cls.staff2 = cls.env['res.users'].create({
            'name': "Praticien Deux", 'login': "book_staff2",
            'email': "bstaff2@exemple.ch"})
        cls.rdv_type = cls.env['megga.rdv.type'].create({
            'name': "Contrôle",
            'duration': 0.5,
            'tz': 'Europe/Zurich',
            'min_notice_hours': 12,
            'horizon_days': 7,
            'user_ids': [(6, 0, cls.staff1.ids)],
            'line_ids': [(0, 0, {'dayofweek': str(jour),
                                 'hour_from': 9.0, 'hour_to': 12.0})
                         for jour in range(5)],
        })
        cls.now = datetime(2026, 9, 2, 8, 0)
        cls.jeudi_9h = datetime(2026, 9, 3, 7, 0)   # 09:00 locale

    def _reserver(self, start, nom="Alice Dupont",
                  email="alice@exemple.ch", **kw):
        return self.env['megga.rdv.booking']._reserver(
            self.rdv_type, start, nom, email,
            phone=kw.get('phone', "+41 21 555 00 11"), now=self.now)

    def test_reservation_complete(self):
        booking = self._reserver(self.jeudi_9h)
        self.assertTrue(booking.name.startswith('RDV/'))
        self.assertEqual(booking.state, 'confirmed')
        self.assertEqual(booking.stop, self.jeudi_9h + timedelta(minutes=30))
        self.assertTrue(booking.access_token)
        # Le contact est créé depuis l'e-mail…
        self.assertEqual(booking.partner_id.email, "alice@exemple.ch")
        # …et l'événement d'agenda matérialise le rendez-vous.
        event = booking.event_id
        self.assertTrue(event)
        self.assertEqual(event.start, self.jeudi_9h)
        self.assertEqual(event.user_id, self.staff1)
        self.assertIn(booking.partner_id, event.partner_ids)
        self.assertIn(self.staff1.partner_id, event.partner_ids)

    def test_contact_reutilise_par_email(self):
        premiere = self._reserver(self.jeudi_9h)
        seconde = self._reserver(
            datetime(2026, 9, 3, 8, 0),   # 10:00 locale
            email="Alice@Exemple.ch")     # casse différente
        self.assertEqual(premiere.partner_id, seconde.partner_id,
                         "même e-mail : même contact, pas de doublon")

    def test_creneau_pris_refuse(self):
        self._reserver(self.jeudi_9h)
        with self.assertRaises(UserError):
            self._reserver(self.jeudi_9h, nom="Bob Martin",
                           email="bob@exemple.ch")

    def test_moins_charge_choisi(self):
        self.rdv_type.user_ids = [(4, self.staff2.id)]
        premiere = self._reserver(self.jeudi_9h)
        self.assertEqual(premiere.user_id, self.staff1,
                         "à charge égale : le plus petit identifiant")
        seconde = self._reserver(datetime(2026, 9, 3, 8, 0),
                                 email="bob@exemple.ch", nom="Bob Martin")
        self.assertEqual(seconde.user_id, self.staff2,
                         "le second créneau du jour va au moins chargé")

    def test_annulation_libere_le_creneau(self):
        booking = self._reserver(self.jeudi_9h)
        slots = self.rdv_type._available_slots(now=self.now)
        self.assertNotIn(self.jeudi_9h, [s['start'] for s in slots],
                         "réservé : le créneau a disparu")
        booking.action_cancel()
        self.assertEqual(booking.state, 'cancelled')
        self.assertFalse(booking.event_id,
                         "l'événement d'agenda est supprimé")
        slots = self.rdv_type._available_slots(now=self.now)
        self.assertIn(self.jeudi_9h, [s['start'] for s in slots],
                      "annulé : le créneau est de nouveau proposé")
        booking.action_cancel()   # idempotent
        self.assertEqual(booking.state, 'cancelled')
