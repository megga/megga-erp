"""Logique pure du pilotage : le classement d'un impayé par âge.

Aucune dépendance Odoo. La vue d'analyse classe en SQL (pour que le
pivot et le graphe travaillent en base), le rapport imprimable classe
en Python : deux chemins, une seule règle — et un test compare les
deux verdicts sur toute la plage, pour qu'ils ne divergent jamais en
silence.
"""

# Bornes SUPERIEURES des tranches, en jours de retard. Au-dela de la
# derniere, tout tombe dans la queue de balance.
BORNES = (30, 60, 90)

TRANCHES = ('not_due', 'b30', 'b60', 'b90', 'b90p')

LIBELLES = {
    'not_due': "Non échu",
    'b30': "1 à 30 jours",
    'b60': "31 à 60 jours",
    'b90': "61 à 90 jours",
    'b90p': "Plus de 90 jours",
}


def tranche_age(jours_de_retard):
    """Tranche d'une facture selon ses jours de retard.

    Une facture échue AUJOURD'HUI (0 jour) n'est pas encore en retard :
    le débiteur a la journée pour payer. Le premier jour de retard est
    donc 1, et c'est aussi ce que dit le SQL de la vue d'analyse.
    """
    if jours_de_retard <= 0:
        return 'not_due'
    for borne, tranche in zip(BORNES, TRANCHES[1:]):
        if jours_de_retard <= borne:
            return tranche
    return TRANCHES[-1]


def ventiler(lignes):
    """Ventile des couples (tranche, montant) en un total par tranche,
    dans l'ordre des tranches — un tableau de balance âgée se lit du
    plus frais au plus vieux, jamais dans l'ordre d'un dictionnaire."""
    totaux = dict.fromkeys(TRANCHES, 0.0)
    for tranche, montant in lignes:
        totaux[tranche] = totaux.get(tranche, 0.0) + montant
    return totaux
