"""Parseur pur de la QR-facture suisse (charge utile Swiss Payment Code).

Aucune dépendance Odoo : ce fichier se teste seul, au même standard que
camt_parser (socle camt) et pain001. Il lit la charge utile SPC version
0200 des Swiss Implementation Guidelines QR-bill et REFUSE toute charge
non conforme plutôt que de deviner :

- en-tête SPC / 0200 / codage 1 ;
- IBAN CH/LI contrôlé (mod 97, ISO 7064) ;
- cohérence stricte type de référence <-> compte : QRR exige un QR-IBAN
  (IID 30000-31999) et une référence à 27 chiffres au mod 10 récursif ;
  SCOR exige un IBAN ordinaire et une référence ISO 11649 ; NON exige un
  IBAN ordinaire et aucune référence ;
- montant à deux décimales, devise CHF ou EUR, trailer EPD présent.
"""

import re

_AMOUNT_RE = re.compile(r"^\d{1,9}\.\d{2}$")
_SCOR_RE = re.compile(r"^RF\d{2}[0-9A-Za-z]{1,21}$")


def _base36(text):
    """« A » -> 10 … « Z » -> 35, chiffres inchangés — l'arithmétique
    commune aux contrôles ISO 7064 (IBAN) et ISO 11649 (SCOR)."""
    return "".join(str(int(char, 36)) for char in text)


def iban_valid(iban):
    """Contrôle mod 97 (ISO 7064) d'un IBAN sans espaces, en majuscules."""
    if len(iban) < 5 or not iban[:2].isalpha() or not iban.isalnum():
        return False
    try:
        return int(_base36(iban[4:] + iban[:4])) % 97 == 1
    except ValueError:
        return False


def is_qr_iban(iban):
    """Le compte est-il un QR-IBAN (IID 30000-31999) ? Seul un QR-IBAN
    porte des références QRR, et réciproquement."""
    try:
        return 30000 <= int(iban[4:9]) <= 31999
    except (ValueError, IndexError):
        return False


def mod10r(digits):
    """Chiffre de contrôle « modulo 10 récursif » des références QRR
    (l'héritier du BVR). Retourne le chiffre attendu après `digits`."""
    table = (0, 9, 4, 6, 8, 2, 7, 1, 3, 5)
    report = 0
    for char in digits:
        report = table[(report + int(char)) % 10]
    return str((10 - report) % 10)


def qrr_valid(reference):
    """Référence QRR : 27 chiffres, le dernier étant le chiffre de
    contrôle mod 10 récursif des 26 premiers."""
    return (len(reference) == 27 and reference.isdigit()
            and mod10r(reference[:26]) == reference[26])


def scor_valid(reference):
    """Référence créancier ISO 11649 : « RF » + 2 chiffres de contrôle +
    jusqu'à 21 caractères, mod 97 sur la chaîne réarrangée."""
    if not _SCOR_RE.match(reference):
        return False
    return int(_base36((reference[4:] + reference[:4]).upper())) % 97 == 1


def _address(lines):
    """Un bloc adresse SPC de 7 lignes -> dict, ou None s'il est vide.
    Type S (structuré) : rue, numéro, NPA, localité séparés ; type K
    (combiné) : deux lignes libres — la seconde porte « NPA Localité »."""
    addr_type, name, line1, line2, zip_code, city, country = lines
    if not name:
        return None
    if addr_type == 'K':
        return {'name': name, 'street': line1, 'house': '',
                'zip': '', 'city': line2, 'country': country}
    return {'name': name, 'street': line1, 'house': line2,
            'zip': zip_code, 'city': city, 'country': country}


def parse_spc(payload):
    """Charge utile SPC -> dict {iban, creditor, amount, currency,
    debtor, ref_type, reference, message, billing_info}. ValueError,
    avec la raison, sur toute charge non conforme."""
    lines = [line.strip() for line in payload.replace('\r\n', '\n').split('\n')]
    if len(lines) < 31:
        raise ValueError(
            "charge utile tronquée : %d ligne(s), 31 au minimum"
            % len(lines))
    if lines[0] != 'SPC':
        raise ValueError("en-tête inattendu : %r" % (lines[0],))
    if lines[1] != '0200':
        raise ValueError("version non gérée : %r" % (lines[1],))
    if lines[2] != '1':
        raise ValueError("codage non géré : %r" % (lines[2],))

    iban = lines[3].replace(' ', '').upper()
    if iban[:2] not in ('CH', 'LI') or len(iban) != 21:
        raise ValueError("IBAN hors CH/LI : %r" % (lines[3],))
    if not iban_valid(iban):
        raise ValueError("IBAN au contrôle mod 97 invalide : %r" % (iban,))

    creditor = _address(lines[4:11])
    if creditor is None:
        raise ValueError("créancier absent de la charge utile")
    if len(creditor['country']) != 2 or not creditor['country'].isalpha():
        raise ValueError(
            "pays du créancier invalide : %r" % (creditor['country'],))

    amount_text = lines[18]
    if amount_text and not _AMOUNT_RE.match(amount_text):
        raise ValueError("montant illisible : %r" % (amount_text,))
    amount = float(amount_text) if amount_text else None

    currency = lines[19]
    if currency not in ('CHF', 'EUR'):
        raise ValueError("devise hors CHF/EUR : %r" % (currency,))

    ref_type = lines[27]
    reference = lines[28].replace(' ', '')
    if ref_type == 'QRR':
        if not is_qr_iban(iban):
            raise ValueError(
                "référence QRR sur un IBAN ordinaire : %r" % (iban,))
        if not qrr_valid(reference):
            raise ValueError("référence QRR invalide : %r" % (reference,))
    elif ref_type == 'SCOR':
        if is_qr_iban(iban):
            raise ValueError(
                "référence SCOR sur un QR-IBAN : %r" % (iban,))
        if not scor_valid(reference):
            raise ValueError("référence SCOR invalide : %r" % (reference,))
    elif ref_type == 'NON':
        if is_qr_iban(iban):
            raise ValueError("IBAN de type QR sans référence QRR")
        if reference:
            raise ValueError(
                "référence inattendue avec le type NON : %r" % (reference,))
    else:
        raise ValueError("type de référence inconnu : %r" % (ref_type,))

    if lines[30] != 'EPD':
        raise ValueError("trailer EPD absent : %r" % (lines[30],))

    return {
        'iban': iban,
        'creditor': creditor,
        'amount': amount,
        'currency': currency,
        'debtor': _address(lines[20:27]),
        'ref_type': ref_type,
        'reference': reference,
        'message': lines[29],
        'billing_info': lines[31] if len(lines) > 31 else '',
    }
