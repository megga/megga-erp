from datetime import datetime

from odoo.tests import TransactionCase


class TestSlots(TransactionCase):
    """Le calcul des créneaux disponibles contre le calendrier du cœur.
    `now` est injecté partout : les tests sont déterministes.

    Décor : plages lundi-vendredi 9h-12h, Europe/Zurich (UTC+2 en été,
    donc 9h locale = 07:00 UTC), durée 30 min, préavis 12 h, horizon
    7 jours, `now` = mercredi 2 septembre 2026 08:00 UTC."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff1 = cls.env['res.users'].create({
            'name': "Praticien Un", 'login': "rdv_staff1",
            'email': "staff1@exemple.ch"})
        cls.staff2 = cls.env['res.users'].create({
            'name': "Praticien Deux", 'login': "rdv_staff2",
            'email': "staff2@exemple.ch"})
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
        cls.now = datetime(2026, 9, 2, 8, 0)   # mercredi, 10h locale

    def test_grille_et_fenetre(self):
        slots = self.rdv_type._available_slots(now=self.now)
        self.assertTrue(slots)
        # Préavis 12 h : le premier créneau est jeudi 09:00 locale,
        # soit 07:00 UTC.
        self.assertEqual(slots[0]['start'], datetime(2026, 9, 3, 7, 0))
        self.assertEqual(slots[0]['label'], "09:00")
        jeudi = [s for s in slots if s['start'].date() == datetime(
            2026, 9, 3).date()]
        self.assertEqual(len(jeudi), 6)   # 9h-12h au pas de 30 min
        # Pas de créneau le week-end (aucune plage samedi/dimanche).
        weekends = [s for s in slots if s['day'].weekday() >= 5]
        self.assertFalse(weekends)

    def test_occupation_retire_les_creneaux(self):
        self.env['calendar.event'].create({
            'name': "Occupé",
            'start': datetime(2026, 9, 3, 7, 0),    # jeudi 9h-10h locale
            'stop': datetime(2026, 9, 3, 8, 0),
            'user_id': self.staff1.id,
            'partner_ids': [(4, self.staff1.partner_id.id)],
        })
        slots = self.rdv_type._available_slots(now=self.now)
        jeudi = [s['label'] for s in slots
                 if s['start'].date() == datetime(2026, 9, 3).date()]
        self.assertEqual(len(jeudi), 4)
        self.assertNotIn("09:00", jeudi)
        self.assertNotIn("09:30", jeudi)
        self.assertIn("10:00", jeudi, "chevauchement strict : 10:00 reste libre")

    def test_deuxieme_intervenant_garde_le_creneau(self):
        self.env['calendar.event'].create({
            'name': "Occupé",
            'start': datetime(2026, 9, 3, 7, 0),
            'stop': datetime(2026, 9, 3, 8, 0),
            'user_id': self.staff1.id,
            'partner_ids': [(4, self.staff1.partner_id.id)],
        })
        self.rdv_type.user_ids = [(4, self.staff2.id)]
        slots = self.rdv_type._available_slots(now=self.now)
        neuf_heures = next(
            s for s in slots if s['start'] == datetime(2026, 9, 3, 7, 0))
        self.assertEqual(neuf_heures['user_ids'], [self.staff2.id],
                         "seul l'intervenant libre est proposé")

    def test_preavis_trop_grand_aucun_creneau(self):
        self.rdv_type.min_notice_hours = 24 * 8   # au-delà de l'horizon
        self.assertEqual(
            self.rdv_type._available_slots(now=self.now), [])
