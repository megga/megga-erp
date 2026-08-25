from datetime import date

from odoo.tests import TransactionCase

from ..relance_logic import jours_de_retard, niveau_applicable


class TestRelanceLogic(TransactionCase):
    """La logique pure : quel cran pour quel retard, et depuis quand."""

    DELAIS = [10, 30, 45]

    def test_trop_tot_ne_vaut_pas_niveau_zero(self):
        self.assertIsNone(niveau_applicable(0, self.DELAIS))
        self.assertIsNone(niveau_applicable(9, self.DELAIS))

    def test_le_jour_dit_compte(self):
        self.assertEqual(niveau_applicable(10, self.DELAIS), 0)
        self.assertEqual(niveau_applicable(30, self.DELAIS), 1)
        self.assertEqual(niveau_applicable(45, self.DELAIS), 2)

    def test_le_cran_le_plus_eleve_gagne(self):
        """Un client à 47 jours reçoit la mise en demeure, pas le
        premier rappel qu'il a déjà eu."""
        self.assertEqual(niveau_applicable(47, self.DELAIS), 2)
        self.assertEqual(niveau_applicable(29, self.DELAIS), 0)

    def test_bien_au_dela_du_dernier_cran(self):
        self.assertEqual(niveau_applicable(900, self.DELAIS), 2)

    def test_sans_niveau_configure(self):
        self.assertIsNone(niveau_applicable(120, []))

    def test_jours_de_retard_signes(self):
        echeance = date(2026, 8, 10)
        self.assertEqual(jours_de_retard(echeance, date(2026, 8, 20)), 10)
        self.assertEqual(jours_de_retard(echeance, date(2026, 8, 10)), 0)
        self.assertEqual(
            jours_de_retard(echeance, date(2026, 8, 5)), -5,
            "pas encore échue : le signe porte l'information")
