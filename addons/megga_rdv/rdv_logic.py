"""Logique pure de la prise de rendez-vous en ligne.

Aucune dépendance Odoo : ce fichier se teste seul, au même standard que
les logiques des verticales et le parseur camt du socle. Il couvre :

- la grille de créneaux d'une journée à partir de plages d'ouverture
  exprimées en heures décimales (9.5 = 09:30), au pas de la durée du
  rendez-vous ;
- la disponibilité d'un créneau face à des occupations (chevauchement
  STRICT : un rendez-vous qui finit à 10:00 n'empêche pas celui de
  10:00) ;
- la fenêtre de réservation (préavis minimal, horizon maximal) ;
- des libellés de dates en français, sans dépendre de la locale du
  système.

Tout ici travaille en datetimes NAÏFS : l'appelant choisit le fuseau
(les plages sont en heure locale du cabinet/garage, les occupations du
calendrier sont en UTC — c'est le modèle qui convertit, pas cette
logique).
"""

from datetime import datetime, time, timedelta

FR_JOURS = ["lundi", "mardi", "mercredi", "jeudi",
            "vendredi", "samedi", "dimanche"]
FR_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin",
           "juillet", "août", "septembre", "octobre", "novembre",
           "décembre"]


def float_to_time(value):
    """9.5 -> 09:30. ValueError hors de [0, 24]. La borne 24.0 exacte est
    écrêtée à 23:59 (fin de journée) pour rester dans le même jour."""
    if not 0 <= value <= 24:
        raise ValueError("heure décimale invalide : %r" % (value,))
    hour = int(value)
    minute = int(round((value - hour) * 60))
    if minute == 60:
        hour, minute = hour + 1, 0
    if hour >= 24:
        return time(23, 59)
    return time(hour, minute)


def day_slots(day, openings, duration_hours):
    """Créneaux d'une journée : pour chaque plage (de, à) en heures
    décimales, une grille au pas de la durée, dont chaque créneau tient
    ENTIÈREMENT dans la plage. Datetimes naïfs (heure locale)."""
    if duration_hours <= 0:
        raise ValueError(
            "durée de rendez-vous invalide : %r" % (duration_hours,))
    step = timedelta(hours=duration_hours)
    slots = []
    for hour_from, hour_to in openings:
        cursor = datetime.combine(day, float_to_time(hour_from))
        end = datetime.combine(day, float_to_time(hour_to))
        while cursor + step <= end:
            slots.append(cursor)
            cursor += step
    return slots


def overlaps(start1, end1, start2, end2):
    """Chevauchement STRICT : les bornes qui se touchent ne comptent pas."""
    return start1 < end2 and start2 < end1


def slot_free(start, duration_hours, busy):
    """Le créneau [start, start+durée) est-il libre face à la liste
    d'occupations [(début, fin), …] ?"""
    end = start + timedelta(hours=duration_hours)
    return not any(overlaps(start, end, b_start, b_end)
                   for b_start, b_end in busy)


def in_window(start, now, min_notice_hours, horizon_days):
    """Le créneau respecte-t-il le préavis minimal et l'horizon maximal ?"""
    return (start >= now + timedelta(hours=min_notice_hours)
            and start <= now + timedelta(days=horizon_days))


def format_jour_fr(day):
    """date(2026, 8, 24) -> « lundi 24 août 2026 », sans locale système."""
    return "%s %d %s %d" % (
        FR_JOURS[day.weekday()], day.day, FR_MOIS[day.month - 1], day.year)
