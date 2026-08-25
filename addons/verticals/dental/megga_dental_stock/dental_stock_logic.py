"""Logique metier pure du magasin dentaire.

Aucune dependance Odoo : ce fichier se teste seul, au meme standard que
dental_logic (verticale dentaire) et resto_logic (verticale
restaurant). Il couvre l'agregation des besoins en consommables — la
seule arithmetique du chantier, et celle qui se trompe le plus
facilement.
"""


def merge_needs(needs):
    """Agrege des besoins (cle, quantite) par cle.

    Deux actes de la meme seance qui consomment le meme produit font UN
    besoin, donc UN mouvement de stock : le magasin ne tient pas la
    comptabilite des actes, il compte des compresses.

    L'ordre de premiere apparition est preserve — le picking se lit
    dans l'ordre des actes de la seance, pas dans un ordre de hasard.
    Les quantites s'additionnent telles quelles : a l'appelant de les
    avoir converties dans la meme unite d'abord (lecon des fiches
    techniques resto : convertir APRES avoir somme, ou arrondir par
    ligne, fausse le total).
    """
    totals = {}
    order = []
    for key, qty in needs:
        if key not in totals:
            totals[key] = 0.0
            order.append(key)
        totals[key] += qty
    return [(key, totals[key]) for key in order]
