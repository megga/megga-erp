from datetime import date

from odoo.tests import TransactionCase

from ..retrocession_logic import (
    periods_overlap,
    retrocession_amount,
    signed_volume,
)


class TestRetrocessionLogic(TransactionCase):
    """Logique pure : aucune écriture en base, comme les tests du parseur
    camt et du générateur pain.001 dans le socle."""

    def test_signed_volume(self):
        # Le cas de négociation du transcript : 50 000 de volume sur une
        # pharmacie, avoirs déduits.
        self.assertAlmostEqual(signed_volume([
            (30000.0, False), (22000.0, False), (2000.0, True)]), 50000.0)
        self.assertAlmostEqual(signed_volume([]), 0.0)
        # Une période à avoirs majoritaires : le volume négatif reste
        # visible tel quel.
        self.assertAlmostEqual(
            signed_volume([(100.0, False), (300.0, True)]), -200.0)

    def test_retrocession_amount(self):
        self.assertAlmostEqual(retrocession_amount(50000.0, 10.0), 5000.0)
        self.assertAlmostEqual(retrocession_amount(9000.0, 8.0), 720.0)
        # 100 % est un taux valide (reversement intégral), 0 et au-delà
        # de 100 sont des erreurs de saisie.
        self.assertAlmostEqual(retrocession_amount(1000.0, 100.0), 1000.0)
        with self.assertRaises(ValueError):
            retrocession_amount(1000.0, 0.0)
        with self.assertRaises(ValueError):
            retrocession_amount(1000.0, 101.0)

    def test_periods_overlap(self):
        janvier = (date(2026, 1, 1), date(2026, 1, 31))
        fevrier = (date(2026, 2, 1), date(2026, 2, 28))
        trimestre = (date(2026, 1, 1), date(2026, 3, 31))
        self.assertFalse(periods_overlap(*janvier, *fevrier))
        self.assertTrue(periods_overlap(*janvier, *trimestre))
        self.assertTrue(periods_overlap(*trimestre, *fevrier))
        # Un seul jour partagé suffit : une facture datée de ce jour
        # serait comptée deux fois.
        self.assertTrue(periods_overlap(
            date(2026, 1, 1), date(2026, 1, 31),
            date(2026, 1, 31), date(2026, 2, 28)))
