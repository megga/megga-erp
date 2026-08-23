"""Logique métier pure de la verticale automobile.

Aucune dépendance Odoo : ce fichier se teste seul, au même standard que
dental_logic, resto_logic et le parseur camt du socle. Il couvre :

- le rythme fédéral d'expertise périodique des voitures (art. 33 OETV) :
  première expertise 4 ans après la première mise en circulation, la
  suivante 3 ans plus tard, puis tous les 2 ans — les convocations
  cantonales peuvent s'en écarter, le calcul sert de rappel ;
- la plausibilité d'un numéro de châssis VIN (ISO 3779) : forme sur
  17 caractères sans I/O/Q, et clé de contrôle en position 9 — la clé
  n'est obligatoire qu'en Amérique du Nord, elle reste donc un signal
  informatif et jamais une contrainte bloquante.

`add_months` est volontairement recopié de dental_logic (5 lignes) :
chaque verticale reste installable seule, sans dépendre d'une autre.
"""

import calendar
from datetime import date

# Translittération ISO 3779 (I, O et Q n'existent pas dans un VIN).
_VIN_VALEURS = {
    'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8,
    'J': 1, 'K': 2, 'L': 3, 'M': 4, 'N': 5, 'P': 7, 'R': 9,
    'S': 2, 'T': 3, 'U': 4, 'V': 5, 'W': 6, 'X': 7, 'Y': 8, 'Z': 9,
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4,
    '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
}
_VIN_POIDS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)


def add_months(day, months):
    """`day` + `months` mois, le jour écrêté à la fin du mois d'arrivée
    (29 février -> 28 février les années non bissextiles)."""
    total = day.year * 12 + (day.month - 1) + months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def next_inspection_date(first_circulation, last_inspection=None,
                         inspections_done=0):
    """Prochaine expertise selon le rythme fédéral 4-3-2 (art. 33 OETV).

    - jamais expertisée : première mise en circulation + 4 ans ;
    - une expertise passée : dernière expertise + 3 ans ;
    - deux ou plus : dernière expertise + 2 ans.

    Si le compteur annonce des expertises mais que la date de la dernière
    manque, on retombe prudemment sur première circulation + 4 ans.
    """
    if inspections_done < 0:
        raise ValueError(
            "nombre d'expertises invalide : %r" % (inspections_done,))
    if inspections_done == 0 or not last_inspection:
        return add_months(first_circulation, 48)
    if inspections_done == 1:
        return add_months(last_inspection, 36)
    return add_months(last_inspection, 24)


def vin_well_formed(vin):
    """Le VIN a-t-il la forme ISO 3779 : 17 caractères, chiffres et
    lettres sans I, O ni Q ? La casse est ignorée."""
    if not isinstance(vin, str):
        return False
    vin = vin.strip().upper()
    return len(vin) == 17 and all(c in _VIN_VALEURS for c in vin)


def vin_check_digit_ok(vin):
    """La clé de contrôle (position 9) est-elle correcte ? Somme pondérée
    des valeurs translittérées, modulo 11, où 10 s'écrit « X ».
    False si le VIN n'est même pas bien formé. Indicatif seulement :
    beaucoup de VIN européens n'implémentent pas la clé."""
    if not vin_well_formed(vin):
        return False
    vin = vin.strip().upper()
    somme = sum(_VIN_VALEURS[c] * p for c, p in zip(vin, _VIN_POIDS))
    reste = somme % 11
    attendu = 'X' if reste == 10 else str(reste)
    return vin[8] == attendu
