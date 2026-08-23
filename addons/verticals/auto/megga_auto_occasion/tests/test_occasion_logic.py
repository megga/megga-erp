from odoo.tests import TransactionCase

from ..occasion_logic import fictive_input_tax, margin_vat, vat_from_gross


class TestOccasionLogic(TransactionCase):
    """L'arithmétique des deux régimes, au centime."""

    def test_part_de_tva_dans_un_ttc(self):
        # 108.10 TTC contiennent exactement 8.10 de TVA.
        self.assertAlmostEqual(vat_from_gross(108.10, 8.1), 8.10)
        self.assertAlmostEqual(vat_from_gross(10000.0, 8.1), 749.31)

    def test_impot_prealable_fictif(self):
        self.assertAlmostEqual(fictive_input_tax(10000.0, 8.1), 749.31)
        self.assertEqual(fictive_input_tax(0.0, 8.1), 0.0)
        self.assertEqual(fictive_input_tax(-5.0, 8.1), 0.0)

    def test_tva_sur_marge(self):
        self.assertAlmostEqual(margin_vat(30000.0, 36000.0, 8.1), 449.58)

    def test_marge_negative_sans_credit(self):
        self.assertEqual(margin_vat(30000.0, 25000.0, 8.1), 0.0)
        self.assertEqual(margin_vat(30000.0, 30000.0, 8.1), 0.0)

    def test_la_charge_nette_est_la_tva_de_la_marge(self):
        """La voie fictive taxe la marge par construction : TVA due à la
        revente moins impôt fictif = TVA extraite de la marge."""
        buy, sale, rate = 10000.0, 12900.0, 8.1
        nette = vat_from_gross(sale, rate) - fictive_input_tax(buy, rate)
        self.assertAlmostEqual(nette, 217.29)
        self.assertAlmostEqual(
            nette, vat_from_gross(sale - buy, rate), places=1,
            msg="au centime d'arrondi près, c'est la TVA de la marge")
