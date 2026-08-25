"""Logique pure des rappels de factures impayées.

Aucune dépendance Odoo : ce fichier se teste seul, au même standard que
`camt_parser` (socle) et `dental_logic` (verticale dentaire).

Le cœur du sujet tient en une question : une facture échue depuis N
jours appelle QUEL rappel ? La réponse est le niveau le plus élevé dont
le délai est atteint — un client à 47 jours de retard reçoit la mise en
demeure, pas le premier rappel qu'il a déjà eu.
"""


def niveau_applicable(jours_de_retard, delais):
    """Position (index) du niveau dû pour `jours_de_retard`, parmi des
    `delais` (jours après échéance) donnés dans l'ordre croissant.

    Renvoie None si aucun délai n'est atteint : il est trop tôt pour
    relancer, et « trop tôt » n'est pas « niveau zéro » — l'appelant ne
    doit rien envoyer du tout.
    """
    atteints = [i for i, delai in enumerate(delais)
                if jours_de_retard >= delai]
    return atteints[-1] if atteints else None


def jours_de_retard(echeance, aujourdhui):
    """Jours écoulés depuis l'échéance. Négatif si la facture n'est pas
    encore échue — le signe porte l'information, l'appelant tranche."""
    return (aujourdhui - echeance).days
