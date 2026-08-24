"""Logique métier pure des rétrocessions.

Aucune dépendance Odoo : ce fichier se teste seul, au même standard que
camt_parser (socle camt), pain001, dental_logic et care_logic. Il couvre :

- le volume signé d'une période : les factures s'ajoutent, les avoirs se
  déduisent ;
- le montant de la rétrocession : un taux en pour-cent, strictement entre
  0 exclu et 100 inclus — tout autre taux est une erreur, pas un cas
  silencieux ;
- le chevauchement de périodes : la règle qui interdit de compter deux
  fois la même facture dans deux décomptes d'un même accord.
"""


def signed_volume(entries):
    """Volume d'une période : couples (montant, est_un_avoir). Les
    factures s'ajoutent, les avoirs se déduisent — un volume peut donc
    être négatif, et le chiffre doit rester visible tel quel."""
    return sum(-amount if is_refund else amount
               for amount, is_refund in entries)


def retrocession_amount(volume, rate):
    """Montant de la rétrocession : `rate` est un pour-cent dans
    ]0 ; 100]. 10 % de 50 000 -> 5 000. Hors bornes, ValueError : un taux
    nul ou au-delà du volume entier est une erreur de saisie, jamais un
    zéro silencieux."""
    if not 0 < rate <= 100:
        raise ValueError("taux de rétrocession invalide : %r %%" % (rate,))
    return volume * rate / 100.0


def periods_overlap(from_a, to_a, from_b, to_b):
    """Les deux périodes (bornes INCLUSES) se recouvrent-elles ? Deux
    décomptes d'un même accord ne peuvent pas partager un seul jour :
    une facture datée de ce jour serait comptée deux fois."""
    return from_a <= to_b and from_b <= to_a
