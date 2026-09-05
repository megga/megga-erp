"""Logique métier pure de la déclaration légale d'un restaurant.

Aucune dépendance Odoo : ce fichier se teste seul, au même standard que
resto_logic (créneaux et coût matière), dental_logic (le cabinet) et le
parseur camt du socle.

Le droit alimentaire suisse impose au restaurateur deux informations sur
ce qu'il sert : les ALLERGÈNES, et — pour la viande et le poisson — le
PAYS DE PRODUCTION. Ce fichier ne connaît le détail d'aucun des deux :
il tient LA RÈGLE DE COMPLÉTUDE, c'est-à-dire la différence entre « cet
ingrédient n'apporte aucun allergène » et « personne n'a encore
regardé ». Cette différence est tout l'objet d'une déclaration : une
liste vide ne se signe pas.
"""

from collections import namedtuple

Ingredient = namedtuple('Ingredient', (
    'name',               # le libellé de l'ingrédient, tel qu'il paraîtra
    'allergens_checked',  # quelqu'un a REGARDÉ l'étiquette
    'allergen_count',     # combien d'allergènes y ont été trouvés
    'origin_required',    # viande ou poisson : provenance obligatoire
    'origin_known',       # le pays de production est renseigné
))


def is_declared(ingredient):
    """Un ingrédient est déclaré dès que quelqu'un s'est prononcé : soit
    la case « vérifié » est cochée — y compris pour dire « aucun
    allergène » —, soit au moins un allergène y figure : en cocher un,
    c'est avoir regardé l'étiquette."""
    return bool(ingredient.allergens_checked) or ingredient.allergen_count > 0


def missing_declarations(ingredients):
    """Ce qui manque pour signer la déclaration, en clair, dans l'ordre
    de la fiche. Un même ingrédient répété (le beurre de la sauce et
    celui du dressage) ne se plaint qu'une fois — dédoublonnage à ordre
    stable, même patron que merge_needs pour la liste de courses.

    Une fiche SANS ingrédient n'est jamais complète : on ne déclare pas
    un plat dont on ignore la composition. C'est le cas qu'un « rien à
    signaler » laisserait passer.
    """
    if not ingredients:
        return ["aucun ingrédient à la fiche"]
    manques = []
    for ingredient in ingredients:
        if not is_declared(ingredient):
            manques.append(
                "%s : allergènes non vérifiés" % ingredient.name)
        if ingredient.origin_required and not ingredient.origin_known:
            manques.append(
                "%s : provenance manquante" % ingredient.name)
    vus = set()
    uniques = []
    for manque in manques:
        if manque not in vus:
            vus.add(manque)
            uniques.append(manque)
    return uniques


def declaration_state(ingredients):
    """« complete » quand plus rien ne manque, « incomplete » sinon."""
    return 'incomplete' if missing_declarations(ingredients) else 'complete'
