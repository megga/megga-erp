from odoo.tests import TransactionCase

from odoo.addons.megga_dental_stock.dental_stock_logic import merge_needs


class TestDentalStockLogic(TransactionCase):
    """Logique pure : aucune base, aucun ORM — juste l'arithmétique
    d'agrégation des besoins, celle qui se trompe le plus facilement."""

    def test_agrege_par_cle(self):
        self.assertEqual(
            merge_needs([('compresse', 2.0), ('gant', 1.0),
                         ('compresse', 3.0)]),
            [('compresse', 5.0), ('gant', 1.0)])

    def test_ordre_de_premiere_apparition(self):
        """Le picking se lit dans l'ordre des actes, pas au hasard."""
        self.assertEqual(
            [cle for cle, _qty in merge_needs(
                [('c', 1.0), ('a', 1.0), ('b', 1.0), ('a', 1.0)])],
            ['c', 'a', 'b'])

    def test_liste_vide(self):
        self.assertEqual(merge_needs([]), [])

    def test_quantites_fractionnaires(self):
        """Les millilitres d'anesthésique ne s'arrondissent pas en
        route : l'addition se fait sur les valeurs reçues."""
        total = dict(merge_needs([('art', 1.7), ('art', 1.7), ('art', 1.7)]))
        self.assertAlmostEqual(total['art'], 5.1, places=9)
