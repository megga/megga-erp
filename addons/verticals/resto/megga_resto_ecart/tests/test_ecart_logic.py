from odoo.tests import TransactionCase

from ..ecart_logic import (
    consommation_reelle,
    ecart,
    ecart_pct,
    perte,
    valorisation,
)


class TestEcartLogic(TransactionCase):
    """Logique pure : aucune écriture en base, comme resto_logic et le
    parseur camt du socle."""

    def test_consommation_reelle(self):
        """Ce qu'il y avait, plus ce qui est entré, moins ce qui reste."""
        self.assertAlmostEqual(consommation_reelle(10.0, 5.0, 3.0), 12.0)
        self.assertAlmostEqual(consommation_reelle(0.0, 0.0, 0.0), 0.0)

    def test_ecart_positif_est_une_perte(self):
        """La convention de signe dont tout le module dépend."""
        self.assertAlmostEqual(ecart(12.0, 10.0), 2.0)
        self.assertAlmostEqual(ecart(9.0, 10.0), -1.0)
        self.assertAlmostEqual(ecart(10.0, 10.0), 0.0)

    def test_ecart_pct(self):
        self.assertAlmostEqual(ecart_pct(12.0, 10.0), 20.0)
        self.assertAlmostEqual(ecart_pct(9.0, 10.0), -10.0)
        self.assertAlmostEqual(ecart_pct(10.0, 10.0), 0.0)

    def test_pas_de_pourcentage_sans_theorie(self):
        """Sans consommation attendue, un écart n'a pas de pourcentage —
        et surtout pas de division par zéro cachée."""
        self.assertIsNone(ecart_pct(5.0, 0.0))
        self.assertIsNone(ecart_pct(5.0, -1.0))

    def test_valorisation(self):
        """2.2 kg d'entrecôte à 38.00 : CHF 83.60 partis en fumée."""
        self.assertAlmostEqual(valorisation(2.2, 38.0), 83.6)
        self.assertAlmostEqual(valorisation(-1.0, 38.0), -38.0)

    def test_une_sous_consommation_n_est_pas_une_perte(self):
        """Sommer les écarts signés donnerait un total rassurant et
        faux : le beurre gaspillé effacerait la farine sous-consommée."""
        self.assertAlmostEqual(perte(83.6), 83.6)
        self.assertAlmostEqual(perte(-40.0), 0.0)
        self.assertAlmostEqual(perte(0.0), 0.0)

    def test_le_total_des_pertes_ne_se_compense_pas(self):
        valeurs = [83.6, -40.0, 12.0]
        self.assertAlmostEqual(sum(valeurs), 55.6)          # écart net
        self.assertAlmostEqual(sum(perte(v) for v in valeurs), 95.6)
