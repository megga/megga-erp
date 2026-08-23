from datetime import date

from odoo.tests import TransactionCase

from ..dental_logic import (
    add_months,
    age_years,
    all_fdi_numbers,
    fdi_deciduous,
    fdi_description,
    fdi_valid,
    next_recall_date,
)


class TestDentalLogic(TransactionCase):
    """Logique pure : aucune écriture en base, comme les tests du parseur
    camt et du générateur pain.001 dans le socle."""

    def test_add_months_ecretage_fin_de_mois(self):
        # Le cas métier central : contrôle du 31 août + 6 mois de rappel.
        self.assertEqual(add_months(date(2026, 8, 31), 6), date(2027, 2, 28))
        # Arrivée en février d'une année bissextile : le 29 est conservé.
        self.assertEqual(add_months(date(2023, 8, 31), 6), date(2024, 2, 29))
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(add_months(date(2026, 3, 31), 1), date(2026, 4, 30))

    def test_add_months_cas_courants(self):
        self.assertEqual(add_months(date(2026, 3, 15), 6), date(2026, 9, 15))
        self.assertEqual(add_months(date(2026, 8, 23), 12), date(2027, 8, 23))
        # Passage d'année dans les deux sens, y compris en négatif.
        self.assertEqual(add_months(date(2026, 11, 5), 3), date(2027, 2, 5))
        self.assertEqual(add_months(date(2026, 2, 5), -3), date(2025, 11, 5))
        self.assertEqual(add_months(date(2026, 8, 23), -6), date(2026, 2, 23))

    def test_next_recall_date(self):
        self.assertEqual(
            next_recall_date(date(2026, 8, 31), 6), date(2027, 2, 28))
        with self.assertRaises(ValueError):
            next_recall_date(date(2026, 8, 31), 0)

    def test_fdi_valid(self):
        pour = [11, 18, 21, 28, 31, 38, 41, 48, 51, 55, 61, 65, 71, 75, 81, 85]
        contre = [0, 1, 10, 19, 29, 40, 49, 50, 56, 66, 76, 86, 90, 111, -11]
        for numero in pour:
            self.assertTrue(fdi_valid(numero), "%s devrait être valide" % numero)
        for numero in contre:
            self.assertFalse(fdi_valid(numero), "%s devrait être rejeté" % numero)
        self.assertFalse(fdi_valid("16"))
        self.assertFalse(fdi_valid(True))
        self.assertEqual(len(all_fdi_numbers()), 52)
        self.assertTrue(all(fdi_valid(n) for n in all_fdi_numbers()))

    def test_fdi_description(self):
        self.assertEqual(
            fdi_description(11), "Incisive centrale supérieure droite")
        self.assertEqual(
            fdi_description(16), "Première molaire supérieure droite")
        self.assertEqual(
            fdi_description(36), "Première molaire inférieure gauche")
        self.assertEqual(
            fdi_description(48), "Dent de sagesse inférieure droite")
        self.assertEqual(
            fdi_description(55), "Deuxième molaire de lait supérieure droite")
        self.assertTrue(fdi_deciduous(55))
        self.assertFalse(fdi_deciduous(16))
        with self.assertRaises(ValueError):
            fdi_description(19)

    def test_age_years(self):
        naissance = date(1988, 4, 12)
        self.assertEqual(age_years(naissance, date(2026, 4, 11)), 37)
        self.assertEqual(age_years(naissance, date(2026, 4, 12)), 38)
        self.assertEqual(age_years(date(2030, 1, 1), date(2026, 1, 1)), 0)
        # Naissance un 29 février : l'anniversaire compte au 1er mars
        # les années non bissextiles.
        bissextile = date(2000, 2, 29)
        self.assertEqual(age_years(bissextile, date(2026, 2, 28)), 25)
        self.assertEqual(age_years(bissextile, date(2026, 3, 1)), 26)
