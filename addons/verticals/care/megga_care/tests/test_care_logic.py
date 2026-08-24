from odoo.tests import TransactionCase

from ..care_logic import (
    fee_total,
    margin,
    margin_rate,
    unbilled_indexes,
    uncovered_cost_indexes,
)


class TestCareLogic(TransactionCase):
    """Logique pure : aucune écriture en base, comme les tests du parseur
    camt et du générateur pain.001 dans le socle."""

    def test_margin(self):
        # Le cas métier fondateur : labo facturé 500 au client, coût 450.
        self.assertAlmostEqual(margin(500.0, 450.0), 50.0)
        # Refacturation à l'identique (consultation) : marge nulle.
        self.assertAlmostEqual(margin(800.0, 800.0), 0.0)
        # Vente à perte : le chiffre reste visible, jamais écrêté.
        self.assertAlmostEqual(margin(400.0, 450.0), -50.0)

    def test_margin_rate(self):
        self.assertAlmostEqual(margin_rate(500.0, 450.0), 0.10)
        self.assertAlmostEqual(margin_rate(800.0, 800.0), 0.0)
        # Coût sans prix client : pas de taux, pas de division par zéro.
        self.assertAlmostEqual(margin_rate(0.0, 450.0), 0.0)

    def test_fee_total(self):
        self.assertAlmostEqual(fee_total('forfait', flat_amount=1500.0), 1500.0)
        self.assertAlmostEqual(
            fee_total('horaire', hourly_rate=180.0, hours=12.5), 2250.0)
        # Le forfait ignore les paramètres horaires, et réciproquement.
        self.assertAlmostEqual(
            fee_total('forfait', flat_amount=1500.0,
                      hourly_rate=180.0, hours=10.0), 1500.0)
        with self.assertRaises(ValueError):
            fee_total('gratuit')

    def test_unbilled_indexes(self):
        events = [
            (500.0, True),    # facturé -> rien à signaler
            (1000.0, False),  # à facturer
            (0.0, False),     # gratuit -> jamais « oublié »
            (800.0, False),   # à facturer
        ]
        self.assertEqual(unbilled_indexes(events), [1, 3])
        self.assertEqual(unbilled_indexes([]), [])

    def test_uncovered_cost_indexes(self):
        events = [
            (450.0, True),   # pièce reçue
            (900.0, False),  # coût sans pièce
            (0.0, False),    # pas de coût -> rien à couvrir
        ]
        self.assertEqual(uncovered_cost_indexes(events), [1])
        self.assertEqual(uncovered_cost_indexes([]), [])
