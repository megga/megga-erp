from datetime import date, datetime, time

from odoo.tests import TransactionCase

from ..rdv_logic import (
    day_slots,
    float_to_time,
    format_jour_fr,
    in_window,
    slot_free,
)


class TestRdvLogic(TransactionCase):
    """Logique pure : aucune écriture en base."""

    def test_float_to_time(self):
        self.assertEqual(float_to_time(9.5), time(9, 30))
        self.assertEqual(float_to_time(9.25), time(9, 15))
        self.assertEqual(float_to_time(0), time(0, 0))
        # La borne 24.0 est écrêtée à la fin de journée.
        self.assertEqual(float_to_time(24.0), time(23, 59))
        for mauvaise in (-0.5, 24.5):
            with self.assertRaises(ValueError):
                float_to_time(mauvaise)

    def test_grille_de_creneaux(self):
        jour = date(2026, 9, 3)
        creneaux = day_slots(jour, [(9.0, 12.0)], 0.5)
        self.assertEqual(len(creneaux), 6)
        self.assertEqual(creneaux[0], datetime(2026, 9, 3, 9, 0))
        self.assertEqual(creneaux[-1], datetime(2026, 9, 3, 11, 30))

    def test_creneau_doit_tenir_dans_la_plage(self):
        jour = date(2026, 9, 3)
        # 9h-10h avec 45 min : 9:00 tient, 9:45 finirait à 10:30 -> exclu.
        creneaux = day_slots(jour, [(9.0, 10.0)], 0.75)
        self.assertEqual(creneaux, [datetime(2026, 9, 3, 9, 0)])
        # Deux plages (matin + après-midi) s'additionnent.
        creneaux = day_slots(jour, [(9.0, 10.0), (14.0, 15.0)], 1.0)
        self.assertEqual(creneaux, [datetime(2026, 9, 3, 9, 0),
                                    datetime(2026, 9, 3, 14, 0)])
        with self.assertRaises(ValueError):
            day_slots(jour, [(9.0, 10.0)], 0)

    def test_creneau_libre_chevauchement_strict(self):
        occupe = [(datetime(2026, 9, 3, 9, 0), datetime(2026, 9, 3, 10, 0))]
        self.assertFalse(
            slot_free(datetime(2026, 9, 3, 9, 30), 1.0, occupe))
        # Les bornes qui se touchent ne bloquent pas : 10:00 est libre.
        self.assertTrue(
            slot_free(datetime(2026, 9, 3, 10, 0), 1.0, occupe))
        self.assertTrue(
            slot_free(datetime(2026, 9, 3, 8, 0), 1.0, occupe))

    def test_fenetre_de_reservation(self):
        now = datetime(2026, 9, 2, 8, 0)
        # Trop tôt (préavis 24 h), dedans, trop loin (horizon 7 jours).
        self.assertFalse(
            in_window(datetime(2026, 9, 2, 18, 0), now, 24, 7))
        self.assertTrue(
            in_window(datetime(2026, 9, 4, 9, 0), now, 24, 7))
        self.assertFalse(
            in_window(datetime(2026, 9, 20, 9, 0), now, 24, 7))

    def test_sans_plage_pas_de_creneau(self):
        self.assertEqual(day_slots(date(2026, 9, 3), [], 0.5), [])

    def test_format_jour_francais(self):
        self.assertEqual(format_jour_fr(date(2026, 8, 24)),
                         "lundi 24 août 2026")
        self.assertEqual(format_jour_fr(date(2026, 1, 4)),
                         "dimanche 4 janvier 2026")
