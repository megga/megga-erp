from odoo.tests import TransactionCase

from ..pilotage_logic import LIBELLES, TRANCHES, tranche_age, ventiler


class TestPilotageLogic(TransactionCase):
    """La règle de classement, seule et nue."""

    def test_pas_encore_echu(self):
        self.assertEqual(tranche_age(-5), 'not_due')

    def test_le_jour_de_l_echeance_n_est_pas_un_retard(self):
        """Le débiteur a la journée pour payer."""
        self.assertEqual(tranche_age(0), 'not_due')

    def test_premier_jour_de_retard(self):
        self.assertEqual(tranche_age(1), 'b30')

    def test_les_bornes(self):
        self.assertEqual(tranche_age(30), 'b30')
        self.assertEqual(tranche_age(31), 'b60')
        self.assertEqual(tranche_age(60), 'b60')
        self.assertEqual(tranche_age(61), 'b90')
        self.assertEqual(tranche_age(90), 'b90')
        self.assertEqual(tranche_age(91), 'b90p')

    def test_la_queue_de_balance(self):
        self.assertEqual(tranche_age(900), 'b90p')

    def test_toutes_les_tranches_ont_un_libelle(self):
        for tranche in TRANCHES:
            self.assertIn(tranche, LIBELLES)

    def test_ventilation_ordonnee_et_complete(self):
        totaux = ventiler([('b30', 100.0), ('b90p', 50.0), ('b30', 25.0)])
        self.assertEqual(list(totaux), list(TRANCHES),
                         "une balance se lit du plus frais au plus vieux")
        self.assertAlmostEqual(totaux['b30'], 125.0)
        self.assertAlmostEqual(totaux['b90p'], 50.0)
        self.assertAlmostEqual(totaux['not_due'], 0.0,
                               msg="une tranche vide vaut zéro, pas rien")
