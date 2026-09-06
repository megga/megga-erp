from odoo.tests import TransactionCase

from ..declaration_logic import (
    Ingredient,
    declaration_state,
    is_declared,
    missing_declarations,
)


def ingredient(name, verifies=False, allergenes=0,
               provenance_exigee=False, provenance_connue=False):
    """Raccourci de lecture : les tests parlent de ce qu'ils changent,
    pas des cinq champs à chaque fois."""
    return Ingredient(name, verifies, allergenes,
                      provenance_exigee, provenance_connue)


class TestDeclarationLogic(TransactionCase):
    """Logique pure : aucune écriture en base, comme resto_logic et le
    parseur camt du socle."""

    def test_verifie_a_vide_vaut_declaration(self):
        """« J'ai regardé, il n'y a rien » EST une déclaration — c'est
        toute la raison d'être de la case."""
        self.assertTrue(is_declared(ingredient("Frites", verifies=True)))

    def test_vide_sans_la_case_ne_vaut_rien(self):
        self.assertFalse(is_declared(ingredient("Frites")))

    def test_cocher_un_allergene_vaut_verification(self):
        """Personne ne coche « lait » sans avoir lu l'étiquette."""
        self.assertTrue(is_declared(ingredient("Beurre", allergenes=1)))

    def test_fiche_sans_ingredient(self):
        """On ne déclare pas un plat dont on ignore la composition : le
        cas qu'un « rien à signaler » laisserait passer."""
        self.assertEqual(missing_declarations([]),
                         ["aucun ingrédient à la fiche"])
        self.assertEqual(declaration_state([]), 'incomplete')

    def test_fiche_complete(self):
        fiche = [
            ingredient("Beurre", allergenes=1),
            ingredient("Entrecôte", verifies=True,
                       provenance_exigee=True, provenance_connue=True),
        ]
        self.assertEqual(missing_declarations(fiche), [])
        self.assertEqual(declaration_state(fiche), 'complete')

    def test_les_manques_sont_nommes_dans_l_ordre_de_la_fiche(self):
        fiche = [
            ingredient("Beurre"),
            ingredient("Entrecôte", verifies=True, provenance_exigee=True),
        ]
        self.assertEqual(missing_declarations(fiche), [
            "Beurre : allergènes non vérifiés",
            "Entrecôte : provenance manquante",
        ])
        self.assertEqual(declaration_state(fiche), 'incomplete')

    def test_un_ingredient_peut_porter_les_deux_manques(self):
        fiche = [ingredient("Cabillaud", provenance_exigee=True)]
        self.assertEqual(missing_declarations(fiche), [
            "Cabillaud : allergènes non vérifiés",
            "Cabillaud : provenance manquante",
        ])

    def test_un_ingredient_repete_ne_se_plaint_qu_une_fois(self):
        """Le beurre de la sauce et celui du dressage : un seul manque
        à corriger, pas deux lignes identiques."""
        fiche = [ingredient("Beurre"), ingredient("Beurre")]
        self.assertEqual(missing_declarations(fiche),
                         ["Beurre : allergènes non vérifiés"])

    def test_provenance_non_exigee_ne_manque_jamais(self):
        """Le sel n'a pas de pays à déclarer."""
        fiche = [ingredient("Sel", verifies=True)]
        self.assertEqual(missing_declarations(fiche), [])
