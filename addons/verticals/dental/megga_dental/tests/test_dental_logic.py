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


class TestMergeFindings(TransactionCase):
    """Réduction de l'historique des constats à l'état actuel : le
    dernier constat gagne, surface par surface, la dent entière vit à
    son propre niveau."""

    def test_dernier_constat_gagne_par_surface(self):
        from ..dental_logic import merge_findings
        state = merge_findings([
            (16, 'M', 'carie', (date(2026, 1, 10), 1)),
            (16, 'D', 'carie', (date(2026, 1, 10), 2)),
            (16, 'M', 'obturation', (date(2026, 3, 1), 3)),
        ])
        self.assertEqual(state[16]['surfaces']['M'], 'obturation')
        self.assertEqual(state[16]['surfaces']['D'], 'carie')
        self.assertIsNone(state[16]['tooth'])

    def test_meme_jour_le_dernier_cree_gagne(self):
        from ..dental_logic import merge_findings
        state = merge_findings([
            (26, 'V', 'a_surveiller', (date(2026, 5, 2), 7)),
            (26, 'V', 'carie', (date(2026, 5, 2), 8)),
        ])
        self.assertEqual(state[26]['surfaces']['V'], 'carie')

    def test_dent_entiere_niveau_independant(self):
        from ..dental_logic import merge_findings
        state = merge_findings([
            (36, '', 'couronne', (date(2025, 11, 20), 1)),
            (36, 'M', 'carie', (date(2026, 6, 1), 2)),
        ])
        self.assertEqual(state[36]['tooth'], 'couronne')
        self.assertEqual(state[36]['surfaces']['M'], 'carie')


class TestAnamnesisExpired(TransactionCase):
    """Péremption d'une anamnèse : signée + validité du gabarit,
    écrêtage de fin de mois compris (réutilise add_months)."""

    def test_fraiche(self):
        from ..dental_logic import anamnesis_expired
        self.assertFalse(anamnesis_expired(
            date(2026, 1, 15), 24, date(2026, 8, 25)))
        # Le jour meme de l'echeance : encore valable.
        self.assertFalse(anamnesis_expired(
            date(2024, 8, 25), 24, date(2026, 8, 25)))

    def test_perimee(self):
        from ..dental_logic import anamnesis_expired
        self.assertTrue(anamnesis_expired(
            date(2024, 8, 24), 24, date(2026, 8, 25)))
        # Fin de mois ecretee : signee le 31.12.2023, 2 mois -> echeance
        # 29.02.2024 (bissextile), perimee au 01.03.2024.
        self.assertTrue(anamnesis_expired(
            date(2023, 12, 31), 2, date(2024, 3, 1)))
        self.assertFalse(anamnesis_expired(
            date(2023, 12, 31), 2, date(2024, 2, 29)))

    def test_sans_peremption(self):
        from ..dental_logic import anamnesis_expired
        self.assertFalse(anamnesis_expired(date(2000, 1, 1), 0, date(2026, 8, 25)))
        self.assertFalse(anamnesis_expired(None, 24, date(2026, 8, 25)))
