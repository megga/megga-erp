from datetime import date

from odoo.tests import TransactionCase

from ..auto_logic import (
    add_months,
    next_inspection_date,
    vin_check_digit_ok,
    vin_well_formed,
)


class TestAutoLogic(TransactionCase):
    """Logique pure : aucune écriture en base, comme dental_logic,
    resto_logic et le parseur camt du socle."""

    def test_add_months_ecretage(self):
        self.assertEqual(add_months(date(2026, 8, 31), 6), date(2027, 2, 28))
        self.assertEqual(add_months(date(2024, 2, 29), 48), date(2028, 2, 29))
        self.assertEqual(add_months(date(2024, 2, 29), 12), date(2025, 2, 28))

    def test_rythme_expertise_4_3_2(self):
        premiere = date(2022, 6, 15)
        # Jamais expertisée : première mise en circulation + 4 ans.
        self.assertEqual(next_inspection_date(premiere),
                         date(2026, 6, 15))
        # Une expertise passée : dernière + 3 ans.
        self.assertEqual(
            next_inspection_date(premiere, date(2026, 7, 1), 1),
            date(2029, 7, 1))
        # Deux et plus : dernière + 2 ans.
        self.assertEqual(
            next_inspection_date(premiere, date(2029, 8, 1), 2),
            date(2031, 8, 1))
        self.assertEqual(
            next_inspection_date(premiere, date(2033, 9, 1), 5),
            date(2035, 9, 1))

    def test_expertise_entrees_degradees(self):
        premiere = date(2022, 6, 15)
        # Compteur incohérent (des expertises sans date) : repli prudent
        # sur première circulation + 4 ans.
        self.assertEqual(next_inspection_date(premiere, None, 2),
                         date(2026, 6, 15))
        with self.assertRaises(ValueError):
            next_inspection_date(premiere, None, -1)

    def test_vin_bien_forme(self):
        self.assertTrue(vin_well_formed("11111111111111111"))
        self.assertTrue(vin_well_formed("1M8GDM9AXKP042788"))
        self.assertTrue(vin_well_formed("wvwzzzauzlw000123"),
                        "la casse doit être ignorée")
        self.assertFalse(vin_well_formed("1M8GDM9AXKP04278"))    # 16
        self.assertFalse(vin_well_formed("1M8GDM9AXKP0427888"))  # 18
        self.assertFalse(vin_well_formed("1M8GDM9AXKP04278I"))   # I interdit
        self.assertFalse(vin_well_formed("1M8GDM9AXKP04278O"))   # O interdit
        self.assertFalse(vin_well_formed("1M8GDM9AXKP04278Q"))   # Q interdit
        self.assertFalse(vin_well_formed(None))

    def test_vin_cle_de_controle(self):
        # Les deux VIN de référence de la littérature ISO 3779.
        self.assertTrue(vin_check_digit_ok("11111111111111111"))
        self.assertTrue(vin_check_digit_ok("1M8GDM9AXKP042788"))
        # Un caractère muté invalide la clé.
        self.assertFalse(vin_check_digit_ok("1M8GDM9AXKP042787"))
        # Mal formé -> False, jamais d'exception.
        self.assertFalse(vin_check_digit_ok("TROPCOURT"))
