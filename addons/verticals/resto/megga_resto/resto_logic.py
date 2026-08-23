"""Logique métier pure de la verticale restaurant.

Aucune dépendance Odoo : ce fichier se teste seul, au même standard que
dental_logic (verticale dentaire) et camt_parser (socle). Il couvre :

- l'arithmétique des créneaux de réservation : fin de créneau et
  chevauchement STRICT (deux services qui se touchent — 18h-20h puis
  20h-22h — ne se chevauchent pas) ;
- le coût matière (food cost) : part du coût dans le prix de vente,
  marge brute et taux de marge.
"""

from datetime import timedelta


def slot_end(start, duration_hours):
    """Fin d'un créneau commençant à `start` et durant `duration_hours`
    heures (fractions permises : 1.5 = 90 minutes). ValueError si la
    durée n'est pas strictement positive."""
    if duration_hours <= 0:
        raise ValueError(
            "durée de créneau invalide : %r heure(s)" % (duration_hours,))
    return start + timedelta(hours=duration_hours)


def intervals_overlap(start1, end1, start2, end2):
    """Chevauchement STRICT de deux intervalles : les bornes qui se
    touchent (end1 == start2) ne comptent pas comme un conflit, sans quoi
    on ne pourrait jamais enchaîner deux services sur la même table."""
    return start1 < end2 and start2 < end1


def food_cost_pct(cost, price):
    """Part du coût matière dans le prix de vente, en pour cent.
    None si le prix n'est pas strictement positif (fiche incomplète) :
    l'appelant décide de l'affichage, pas de division par zéro cachée."""
    if price <= 0:
        return None
    return cost / price * 100.0


def margin(cost, price):
    """Marge brute en valeur absolue (prix - coût matière)."""
    return price - cost


def margin_pct(cost, price):
    """Taux de marge brute en pour cent du prix de vente.
    None si le prix n'est pas strictement positif."""
    if price <= 0:
        return None
    return (price - cost) / price * 100.0
