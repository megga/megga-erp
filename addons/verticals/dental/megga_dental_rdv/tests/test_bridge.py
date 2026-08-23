from datetime import datetime

from odoo.tests import TransactionCase


class TestDentalRdvBridge(TransactionCase):
    """Le pont réservation → dossier patient : rattacher sans dupliquer,
    créer sans rien demander, et savoir s'effacer quand le type de
    rendez-vous n'est pas un soin."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff = cls.env['res.users'].create({
            'name': "Praticien Pont", 'login': "bridge_staff",
            'email': "bridge.staff@exemple.ch"})
        cls.rdv_type = cls.env['megga.rdv.type'].create({
            'name': "Contrôle",
            'duration': 0.5,
            'tz': 'Europe/Zurich',
            'min_notice_hours': 12,
            'horizon_days': 7,
            'user_ids': [(6, 0, cls.staff.ids)],
            'line_ids': [(0, 0, {'dayofweek': str(jour),
                                 'hour_from': 9.0, 'hour_to': 12.0})
                         for jour in range(5)],
        })
        cls.now = datetime(2026, 9, 2, 8, 0)
        cls.Booking = cls.env['megga.rdv.booking']
        cls.Patient = cls.env['megga.dental.patient']

    def _reserver(self, start, nom="Alice Dupont",
                  email="alice@exemple.ch"):
        return self.Booking._reserver(
            self.rdv_type, start, nom, email, now=self.now)

    def test_reservation_cree_le_patient(self):
        avant = self.Patient.search_count([])
        booking = self._reserver(datetime(2026, 9, 3, 7, 0))
        self.assertTrue(booking.patient_id)
        self.assertEqual(booking.patient_id.partner_id, booking.partner_id,
                         "le dossier délègue au même contact")
        self.assertTrue(booking.patient_id.code.startswith('PAT/'))
        self.assertEqual(self.Patient.search_count([]), avant + 1)

    def test_patient_existant_rattache(self):
        patient = self.Patient.create({
            'name': "Bob Martin", 'email': "bob@exemple.ch"})
        avant = self.Patient.search_count([])
        booking = self._reserver(datetime(2026, 9, 3, 7, 0),
                                 nom="Bob Martin", email="Bob@Exemple.ch")
        self.assertEqual(booking.patient_id, patient,
                         "même e-mail : même dossier, pas de doublon")
        self.assertEqual(self.Patient.search_count([]), avant)

    def test_deux_reservations_un_seul_dossier(self):
        premiere = self._reserver(datetime(2026, 9, 3, 7, 0))
        seconde = self._reserver(datetime(2026, 9, 3, 8, 0))
        self.assertEqual(premiere.patient_id, seconde.patient_id)

    def test_patient_archive_rattache_sans_doublon(self):
        patient = self.Patient.create({
            'name': "Carla Archivée", 'email': "carla@exemple.ch"})
        patient.active = False
        avant = self.Patient.with_context(active_test=False).search_count([])
        booking = self._reserver(datetime(2026, 9, 3, 7, 0),
                                 nom="Carla Archivée",
                                 email="carla@exemple.ch")
        self.assertEqual(booking.patient_id, patient)
        self.assertEqual(
            self.Patient.with_context(active_test=False).search_count([]),
            avant, "un dossier archivé est rattaché, jamais dupliqué")

    def test_type_sans_creation_de_dossier(self):
        self.rdv_type.dental_patient_creation = False
        avant = self.Patient.search_count([])
        booking = self._reserver(datetime(2026, 9, 3, 7, 0))
        self.assertFalse(booking.patient_id)
        self.assertEqual(self.Patient.search_count([]), avant)

    def test_saisie_interne_sans_contact(self):
        """Une réservation créée au comptoir sans contact : le pont crée
        le contact depuis l'e-mail puis le dossier."""
        booking = self.Booking.create({
            'type_id': self.rdv_type.id,
            'guest_name': "Daniel Comptoir",
            'email': "daniel@exemple.ch",
            'phone': "+41 21 555 33 22",
            'start': datetime(2026, 9, 4, 7, 0),
        })
        self.assertTrue(booking.partner_id)
        self.assertEqual(booking.partner_id.email, "daniel@exemple.ch")
        self.assertTrue(booking.patient_id)
        self.assertEqual(booking.patient_id.partner_id, booking.partner_id)

    def test_contact_existant_sans_dossier(self):
        """Un contact déjà connu (facturation, camt…) mais sans dossier
        patient : le dossier est créé SUR ce contact, pas un nouveau."""
        partner = self.env['res.partner'].create({
            'name': "Emma Connue", 'email': "emma@exemple.ch"})
        booking = self._reserver(datetime(2026, 9, 3, 7, 0),
                                 nom="Emma Connue", email="emma@exemple.ch")
        self.assertEqual(booking.partner_id, partner)
        self.assertEqual(booking.patient_id.partner_id, partner)

    def test_annulation_conserve_le_dossier(self):
        booking = self._reserver(datetime(2026, 9, 3, 7, 0))
        patient = booking.patient_id
        booking.action_cancel()
        self.assertEqual(booking.state, 'cancelled')
        self.assertTrue(patient.exists(), "annuler ne supprime rien")
        self.assertEqual(booking.patient_id, patient)
        self.assertIn(booking, patient.rdv_booking_ids)
        self.assertEqual(patient.rdv_booking_count, 1)
