from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase


class TestNoShow(TransactionCase):
    """Le cron quotidien qui marque « non venus » : après le délai de
    grâce seulement, et jamais une table déjà installée."""

    def _confirmee(self, il_y_a_heures):
        reservation = self.env['megga.resto.reservation'].create({
            'guest_name': "Client Retard",
            'start': fields.Datetime.now() - timedelta(hours=il_y_a_heures),
            'duration': 2.0,
            'party_size': 2,
        })
        reservation.action_confirm()
        return reservation

    def test_cron_marque_les_retardataires(self):
        reservation = self._confirmee(il_y_a_heures=5)
        self.env['megga.resto.reservation']._cron_resto_no_show(grace_hours=2)
        self.assertEqual(reservation.state, 'no_show')

    def test_cron_respecte_le_delai_de_grace(self):
        reservation = self._confirmee(il_y_a_heures=1)
        self.env['megga.resto.reservation']._cron_resto_no_show(grace_hours=2)
        self.assertEqual(reservation.state, 'confirmed',
                         "à 1 h de retard sur 2 h de grâce, rien ne bouge")

    def test_cron_ignore_les_installes(self):
        reservation = self._confirmee(il_y_a_heures=5)
        reservation.action_seat()
        self.env['megga.resto.reservation']._cron_resto_no_show(grace_hours=2)
        self.assertEqual(reservation.state, 'seated',
                         "des clients installés ne sont pas des non-venus")
