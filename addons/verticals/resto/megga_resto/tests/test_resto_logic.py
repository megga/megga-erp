from datetime import datetime

from odoo.tests import TransactionCase

from ..resto_logic import (
    food_cost_pct,
    intervals_overlap,
    margin,
    margin_pct,
    slot_end,
)


class TestRestoLogic(TransactionCase):
    """Logique pure : aucune écriture en base, comme dental_logic et le
    parseur camt du socle."""

    def test_slot_end(self):
        debut = datetime(2026, 9, 1, 18, 0)
        self.assertEqual(slot_end(debut, 2), datetime(2026, 9, 1, 20, 0))
        # Les fractions d'heure comptent : 1.5 = 90 minutes.
        self.assertEqual(slot_end(debut, 1.5), datetime(2026, 9, 1, 19, 30))
        for mauvaise in (0, -1):
            with self.assertRaises(ValueError):
                slot_end(debut, mauvaise)

    def test_chevauchement_partiel(self):
        a1, a2 = datetime(2026, 9, 1, 18, 0), datetime(2026, 9, 1, 20, 0)
        b1, b2 = datetime(2026, 9, 1, 19, 0), datetime(2026, 9, 1, 21, 0)
        self.assertTrue(intervals_overlap(a1, a2, b1, b2))
        self.assertTrue(intervals_overlap(b1, b2, a1, a2))

    def test_bornes_qui_se_touchent(self):
        """18h-20h puis 20h-22h : PAS un conflit — on doit pouvoir
        enchaîner deux services sur la même table."""
        a1, a2 = datetime(2026, 9, 1, 18, 0), datetime(2026, 9, 1, 20, 0)
        b1, b2 = datetime(2026, 9, 1, 20, 0), datetime(2026, 9, 1, 22, 0)
        self.assertFalse(intervals_overlap(a1, a2, b1, b2))
        c1, c2 = datetime(2026, 9, 1, 12, 0), datetime(2026, 9, 1, 14, 0)
        self.assertFalse(intervals_overlap(a1, a2, c1, c2))

    def test_intervalle_contenu(self):
        a1, a2 = datetime(2026, 9, 1, 18, 0), datetime(2026, 9, 1, 22, 0)
        b1, b2 = datetime(2026, 9, 1, 19, 0), datetime(2026, 9, 1, 20, 0)
        self.assertTrue(intervals_overlap(a1, a2, b1, b2))
        self.assertTrue(intervals_overlap(a1, a2, a1, a2))

    def test_food_cost(self):
        self.assertAlmostEqual(food_cost_pct(14.0, 42.0), 33.3333, places=3)
        self.assertEqual(food_cost_pct(14.0, 0.0), None)
        self.assertEqual(food_cost_pct(0.0, 42.0), 0.0)

    def test_marges(self):
        self.assertAlmostEqual(margin(14.0, 42.0), 28.0)
        self.assertAlmostEqual(margin_pct(14.0, 42.0), 66.6667, places=3)
        self.assertEqual(margin_pct(14.0, 0.0), None)
