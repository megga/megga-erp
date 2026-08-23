from datetime import datetime, timedelta

from odoo.tests import TransactionCase


class TestReminder(TransactionCase):
    """Le rappel de la veille : un e-mail par réservation confirmée dans
    la fenêtre, jamais deux, et les types qui n'en veulent pas sont
    respectés. `now` est injecté partout."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        staff = cls.env['res.users'].create({
            'name': "Praticien Rappel", 'login': "reminder_staff",
            'email': "reminder.staff@exemple.ch"})
        cls.rdv_type = cls.env['megga.rdv.type'].create({
            'name': "Contrôle rappelé",
            'duration': 0.5,
            'tz': 'Europe/Zurich',
            'user_ids': [(6, 0, staff.ids)],
            'line_ids': [(0, 0, {'dayofweek': '0',
                                 'hour_from': 9.0, 'hour_to': 12.0})],
        })
        cls.now = datetime(2026, 9, 2, 8, 0)
        cls.Booking = cls.env['megga.rdv.booking']

    def _booking(self, dans_heures, email="rappel@exemple.ch", **kw):
        vals = {
            'type_id': self.rdv_type.id,
            'guest_name': "Client Rappel",
            'email': email,
            'start': self.now + timedelta(hours=dans_heures),
        }
        vals.update(kw)
        return self.Booking.create(vals)

    def _mails(self, booking):
        return self.env['mail.mail'].search([
            ('model', '=', 'megga.rdv.booking'),
            ('res_id', '=', booking.id),
            ('subject', 'like', 'Rappel%'),
        ])

    def test_rappel_envoye_dans_la_fenetre(self):
        booking = self._booking(dans_heures=12)
        self.Booking._cron_rdv_reminders(now=self.now)
        self.assertTrue(booking.reminder_sent)
        mails = self._mails(booking)
        self.assertEqual(len(mails), 1)
        self.assertIn("rappel@exemple.ch", mails.email_to)
        self.assertIn(booking.access_token, mails.body_html,
                      "le rappel embarque le lien d'annulation")

    def test_idempotent(self):
        booking = self._booking(dans_heures=12)
        self.Booking._cron_rdv_reminders(now=self.now)
        self.Booking._cron_rdv_reminders(now=self.now)
        self.assertEqual(len(self._mails(booking)), 1,
                         "une réservation n'est rappelée qu'une fois")

    def test_hors_fenetre(self):
        trop_loin = self._booking(dans_heures=48)
        passee = self._booking(dans_heures=-2,
                               email="passee@exemple.ch")
        self.Booking._cron_rdv_reminders(now=self.now)
        self.assertFalse(trop_loin.reminder_sent,
                         "à 48 h, ce sera pour le prochain passage")
        self.assertFalse(passee.reminder_sent,
                         "on ne rappelle pas un rendez-vous passé")

    def test_annulee_pas_de_rappel(self):
        booking = self._booking(dans_heures=12)
        booking.action_cancel()
        self.Booking._cron_rdv_reminders(now=self.now)
        self.assertFalse(booking.reminder_sent)
        self.assertFalse(self._mails(booking))

    def test_type_sans_rappel(self):
        self.rdv_type.send_reminder = False
        booking = self._booking(dans_heures=12)
        self.Booking._cron_rdv_reminders(now=self.now)
        self.assertFalse(booking.reminder_sent)
        self.assertFalse(self._mails(booking))
