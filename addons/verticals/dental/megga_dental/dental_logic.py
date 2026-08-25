"""Logique métier pure de la verticale dentaire.

Aucune dépendance Odoo : ce fichier se teste seul, au même standard que
camt_parser (socle camt) et pain001. Il couvre :

- l'arithmétique des rappels de contrôle : ajout de mois avec écrêtage en
  fin de mois (31 août + 6 mois -> 28 ou 29 février) ;
- la numérotation dentaire FDI / ISO 3950 : quadrants 1-4 positions 1-8
  pour les dents définitives (11-48), quadrants 5-8 positions 1-5 pour
  les dents de lait (51-85) ;
- le calcul d'âge en années révolues.
"""

import calendar
from datetime import date

# Positions dans un quadrant. Tous ces noms sont féminins, ce qui permet
# d'accorder l'arcade et le côté une fois pour toutes.
_POSITIONS_DEFINITIVES = {
    1: "incisive centrale",
    2: "incisive latérale",
    3: "canine",
    4: "première prémolaire",
    5: "deuxième prémolaire",
    6: "première molaire",
    7: "deuxième molaire",
    8: "dent de sagesse",
}
_POSITIONS_LAIT = {
    1: "incisive centrale",
    2: "incisive latérale",
    3: "canine",
    4: "première molaire",
    5: "deuxième molaire",
}
# Quadrant FDI (ramené à 1-4) -> (arcade, côté), vus du praticien.
_QUADRANTS = {
    1: ("supérieure", "droite"),
    2: ("supérieure", "gauche"),
    3: ("inférieure", "gauche"),
    4: ("inférieure", "droite"),
}


def add_months(day, months):
    """`day` décalé de `months` mois, le jour écrêté à la fin du mois
    d'arrivée : 2026-08-31 + 6 -> 2027-02-28 (2024-08-31 + 6 -> 2025-02-28,
    et une arrivée en février bissextile donne le 29)."""
    total = day.year * 12 + (day.month - 1) + months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def next_recall_date(last_visit, months):
    """Prochaine date de rappel après une visite. `months` >= 1."""
    if months < 1:
        raise ValueError("intervalle de rappel invalide : %r mois" % (months,))
    return add_months(last_visit, months)


def age_years(birthdate, on_day):
    """Âge en années révolues au jour `on_day` (0 si date future)."""
    if birthdate > on_day:
        return 0
    return on_day.year - birthdate.year - (
        (on_day.month, on_day.day) < (birthdate.month, birthdate.day))


def fdi_valid(number):
    """Le numéro est-il une dent FDI valide (11-48 ou 51-85) ?"""
    if not isinstance(number, int) or isinstance(number, bool):
        return False
    quadrant, position = divmod(number, 10)
    if 1 <= quadrant <= 4:
        return 1 <= position <= 8
    if 5 <= quadrant <= 8:
        return 1 <= position <= 5
    return False


def fdi_deciduous(number):
    """La dent est-elle une dent de lait (quadrants 5-8) ?"""
    return fdi_valid(number) and number >= 51


def fdi_description(number):
    """16 -> « Première molaire supérieure droite » ; les quadrants 5-8
    intercalent « de lait ». ValueError sur un numéro invalide."""
    if not fdi_valid(number):
        raise ValueError("numéro FDI invalide : %r" % (number,))
    quadrant, position = divmod(number, 10)
    if quadrant >= 5:
        nom = _POSITIONS_LAIT[position] + " de lait"
        quadrant -= 4
    else:
        nom = _POSITIONS_DEFINITIVES[position]
    arcade, cote = _QUADRANTS[quadrant]
    texte = "%s %s %s" % (nom, arcade, cote)
    return texte[0].upper() + texte[1:]


def all_fdi_numbers():
    """Les 52 numéros FDI (32 définitives puis 20 de lait), ordonnés."""
    definitives = [q * 10 + p for q in (1, 2, 3, 4) for p in range(1, 9)]
    lait = [q * 10 + p for q in (5, 6, 7, 8) for p in range(1, 6)]
    return definitives + lait


# --- Odontogramme ------------------------------------------------------------

# Surfaces d'une dent (nomenclature clinique usuelle). Le bord incisal
# des dents antérieures partage le code O avec la face occlusale.
SURFACES = {
    'M': "mésiale",
    'D': "distale",
    'V': "vestibulaire",
    'L': "linguale / palatine",
    'O': "occlusale / incisale",
}

# Constats portés sur l'odontogramme, avec la couleur du schéma. Les
# couleurs vivent ici (source unique) : le widget SVG les reçoit dans la
# charge JSON et un futur rapport imprimé lira le même dictionnaire.
CONDITION_COLORS = {
    'carie': "#C0392B",
    'a_surveiller': "#D4AC0D",
    'obturation': "#2E6DA4",
    'devitalisee': "#B9770E",
    'couronne': "#7D3C98",
    'implant': "#148F77",
    'absente': "#909497",
    'saine': "#A9DFBF",
}


def merge_findings(findings):
    """Réduit un historique de constats à l'état ACTUEL de chaque dent.

    `findings` : itérable de (numéro FDI, surface ou '', constat, clé
    d'ordre) — la clé d'ordre est comparable ((date, id) en pratique) et
    le DERNIER constat gagne, surface par surface : une obturation posée
    par-dessus une carie remplace la carie sur cette surface, sans que
    l'histoire soit réécrite. Un constat sans surface porte sur la dent
    entière et vit à son propre niveau (une couronne n'efface pas le
    constat mésial qui suivra).

    Retourne {numéro: {'tooth': constat dent entière ou None,
                       'surfaces': {surface: constat}}}.
    """
    state = {}
    for number, surface, condition, order in sorted(
            findings, key=lambda finding: finding[3]):
        tooth = state.setdefault(number, {'tooth': None, 'surfaces': {}})
        if surface:
            tooth['surfaces'][surface] = condition
        else:
            tooth['tooth'] = condition
    return state
