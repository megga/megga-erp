from datetime import datetime

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestReservation(TransactionCase):
    """Le carnet de réservations adossé aux tables du plan de salle du
    cœur (restaurant.table de pos_restaurant)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.floor = cls.env['restaurant.floor'].create({
            'name': "Salle test"})
        Table = cls.env['restaurant.table']
        cls.t2 = Table.create({
            'floor_id': cls.floor.id, 'table_number': 201, 'seats': 2})
        cls.t4 = Table.create({
            'floor_id': cls.floor.id, 'table_number': 202, 'seats': 4})

    def _reservation(self, **kw):
        vals = {
            'guest_name': "Client Test",
            'start': datetime(2026, 9, 1, 18, 0),
            'duration': 2.0,
            'party_size': 2,
        }
        vals.update(kw)
        return self.env['megga.resto.reservation'].create(vals)

    def test_sequence_et_creneau(self):
        reservation = self._reservation()
        self.assertTrue(reservation.name.startswith('RSV/'))
        self.assertEqual(reservation.state, 'draft')
        self.assertEqual(reservation.stop, datetime(2026, 9, 1, 20, 0))

    def test_couverts_positifs(self):
        with self.assertRaises(ValidationError):
            self._reservation(party_size=0)

    def test_duree_positive(self):
        with self.assertRaises(ValidationError):
            self._reservation(duration=0)

    def test_capacite_des_tables(self):
        with self.assertRaises(ValidationError):
            self._reservation(party_size=4, table_ids=[(6, 0, self.t2.ids)])
        deux_tables = self._reservation(
            party_size=6, table_ids=[(6, 0, (self.t2 | self.t4).ids)])
        self.assertEqual(deux_tables.seats_total, 6)

    def test_conflit_meme_table(self):
        premiere = self._reservation(table_ids=[(6, 0, self.t2.ids)])
        premiere.action_confirm()
        seconde = self._reservation(
            start=datetime(2026, 9, 1, 19, 0),
            table_ids=[(6, 0, self.t2.ids)])
        with self.assertRaises(ValidationError):
            seconde.action_confirm()

    def test_tables_differentes_ok(self):
        premiere = self._reservation(table_ids=[(6, 0, self.t2.ids)])
        premiere.action_confirm()
        seconde = self._reservation(
            start=datetime(2026, 9, 1, 19, 0),
            table_ids=[(6, 0, self.t4.ids)])
        seconde.action_confirm()
        self.assertEqual(seconde.state, 'confirmed')

    def test_services_qui_s_enchainent(self):
        """18h-20h puis 20h-22h sur la même table : permis (chevauchement
        strict, cohérent avec resto_logic)."""
        premier = self._reservation(table_ids=[(6, 0, self.t2.ids)])
        premier.action_confirm()
        second = self._reservation(
            start=datetime(2026, 9, 1, 20, 0),
            table_ids=[(6, 0, self.t2.ids)])
        second.action_confirm()
        self.assertEqual(second.state, 'confirmed')

    def test_annulee_ne_bloque_pas(self):
        premiere = self._reservation(table_ids=[(6, 0, self.t2.ids)])
        premiere.action_confirm()
        premiere.action_cancel()
        seconde = self._reservation(table_ids=[(6, 0, self.t2.ids)])
        seconde.action_confirm()
        self.assertEqual(seconde.state, 'confirmed')

    def test_workflow(self):
        reservation = self._reservation()
        reservation.action_confirm()
        reservation.action_seat()
        reservation.action_done()
        self.assertEqual(reservation.state, 'done')
        installee = self._reservation()
        installee.action_confirm()
        installee.action_seat()
        with self.assertRaises(UserError):
            installee.action_cancel()
        with self.assertRaises(UserError):
            self._reservation().action_no_show()
