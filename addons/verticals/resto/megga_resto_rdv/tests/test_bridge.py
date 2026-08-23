from datetime import datetime

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestRestoRdvBridge(TransactionCase):
    """Le pont réservation en ligne → carnet de tables : l'agenda ne
    bloque plus (plusieurs tablées par créneau), la capacité vient des
    tables, et complet veut dire refus propre."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff = cls.env['res.users'].create({
            'name': "Maître d'hôtel", 'login': "resto_bridge_staff",
            'email': "resto.bridge@exemple.ch"})
        cls.rdv_type = cls.env['megga.rdv.type'].create({
            'name': "Table au restaurant",
            'duration': 2.0,
            'tz': 'Europe/Zurich',
            'min_notice_hours': 12,
            'horizon_days': 7,
            'resto_reservation': True,
            'user_ids': [(6, 0, cls.staff.ids)],
            'line_ids': [(0, 0, {'dayofweek': str(jour),
                                 'hour_from': 18.0, 'hour_to': 22.0})
                         for jour in range(5)],
        })
        floor = cls.env['restaurant.floor'].create({'name': "Salle pont"})
        Table = cls.env['restaurant.table']
        cls.t2 = Table.create({
            'floor_id': floor.id, 'table_number': 301, 'seats': 2})
        cls.t4 = Table.create({
            'floor_id': floor.id, 'table_number': 302, 'seats': 4})
        cls.t6 = Table.create({
            'floor_id': floor.id, 'table_number': 303, 'seats': 6})
        cls.now = datetime(2026, 9, 2, 8, 0)
        # Jeudi 3 septembre, 18h locale (Europe/Zurich, été) = 16:00 UTC.
        cls.jeudi_18h = datetime(2026, 9, 3, 16, 0)
        cls.Booking = cls.env['megga.rdv.booking']

    def _reserver(self, start, party=2, nom="Client Pont", email=None):
        email = email or "%s@exemple.ch" % nom.lower().replace(' ', '.')
        return self.Booking._reserver(
            self.rdv_type, start, nom, email, now=self.now,
            extra_vals={'resto_party_size': party})

    def test_reservation_cree_l_entree_du_carnet(self):
        booking = self._reserver(self.jeudi_18h, party=2)
        entree = booking.resto_reservation_id
        self.assertTrue(entree)
        self.assertEqual(entree.state, 'confirmed')
        self.assertEqual(entree.table_ids, self.t2,
                         "deux couverts : la table de deux, pas plus")
        self.assertEqual(entree.party_size, 2)
        self.assertEqual(entree.start, self.jeudi_18h)
        self.assertEqual(entree.duration, 2.0)
        self.assertEqual(entree.rdv_booking_id, booking)
        self.assertEqual(booking.event_id.show_as, 'free',
                         "l'agenda ne bloque pas : la capacité, ce sont "
                         "les tables")

    def test_plus_petite_table_suffisante(self):
        booking = self._reserver(self.jeudi_18h, party=3)
        self.assertEqual(booking.resto_reservation_id.table_ids, self.t4)

    def test_type_non_marque(self):
        self.rdv_type.resto_reservation = False
        booking = self._reserver(self.jeudi_18h)
        self.assertFalse(booking.resto_reservation_id)
        self.assertEqual(booking.event_id.show_as, 'busy')

    def test_plusieurs_tablees_meme_creneau(self):
        premiere = self._reserver(self.jeudi_18h, party=2,
                                  nom="Tablee Une")
        seconde = self._reserver(self.jeudi_18h, party=4,
                                 nom="Tablee Deux")
        self.assertEqual(premiere.resto_reservation_id.table_ids, self.t2)
        self.assertEqual(seconde.resto_reservation_id.table_ids, self.t4,
                         "le même créneau accepte une deuxième tablée")

    def test_complet_refus_propre(self):
        self._reserver(self.jeudi_18h, party=2, nom="Un")
        self._reserver(self.jeudi_18h, party=4, nom="Deux")
        self._reserver(self.jeudi_18h, party=6, nom="Trois")
        avant = self.Booking.search_count([])
        with self.assertRaises(UserError), self.cr.savepoint():
            self._reserver(self.jeudi_18h, party=2, nom="Quatre")
        self.assertEqual(self.Booking.search_count([]), avant,
                         "refus : rien ne reste, ni réservation ni entrée")

    def test_grande_tablee_refusee(self):
        with self.assertRaises(UserError), self.cr.savepoint():
            self._reserver(self.jeudi_18h, party=8)

    def test_annulation_libere_la_table(self):
        premiere = self._reserver(self.jeudi_18h, party=2, nom="Un")
        premiere.action_cancel()
        self.assertEqual(premiere.resto_reservation_id.state, 'cancelled',
                         "l'annulation publique annule l'entrée du carnet")
        seconde = self._reserver(self.jeudi_18h, party=2, nom="Deux")
        self.assertEqual(seconde.resto_reservation_id.table_ids, self.t2,
                         "la table est libérée pour la tablée suivante")

    def test_annulation_depuis_le_carnet(self):
        booking = self._reserver(self.jeudi_18h, party=2)
        booking.resto_reservation_id.action_cancel()
        self.assertEqual(booking.state, 'cancelled')
        self.assertFalse(booking.event_id,
                         "l'événement d'agenda est parti avec")

    def test_couverts_par_defaut(self):
        booking = self.Booking._reserver(
            self.rdv_type, self.jeudi_18h, "Sans Couverts",
            "sans.couverts@exemple.ch", now=self.now)
        self.assertEqual(booking.resto_reservation_id.party_size, 2)

    def test_sans_droit_contact_le_pont_fonctionne(self):
        """Un utilisateur interne SANS droit sur les contacts prend une
        réservation au comptoir : la matérialisation au carnet (contact
        créé par e-mail compris) est un effet système, en sudo — comme
        pour les autres ponts."""
        operateur = self.env['res.users'].create({
            'name': "Opérateur Comptoir", 'login': "resto_operateur",
            'email': "operateur.resto@exemple.ch"})
        booking = self.Booking.with_user(operateur).create({
            'type_id': self.rdv_type.id,
            'guest_name': "Tablée Comptoir",
            'email': "tablee.comptoir@exemple.ch",
            'start': self.jeudi_18h,
            'resto_party_size': 2,
        })
        entree = booking.resto_reservation_id
        self.assertTrue(entree, "l'entrée du carnet est créée quand même")
        self.assertEqual(entree.state, 'confirmed')
        self.assertEqual(entree.partner_id.email,
                         "tablee.comptoir@exemple.ch")
