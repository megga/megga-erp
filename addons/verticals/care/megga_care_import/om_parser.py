"""Parseur pur des exports texte Office Maker.

Aucune dépendance Odoo : ce fichier se teste seul, au même standard que
camt_parser (socle camt), pain001 et qr_parser. Office Maker (bâti sur
4D) exporte ses fiches en texte dont l'encodage et le séparateur varient
selon la machine et l'époque ; ce parseur couvre :

- le décodage : BOM UTF-8/UTF-16 honorés, essai UTF-8 strict, repli
  cp1252 (qui décode tout octet — Mac Roman reste disponible en choix
  explicite, indiscernable de cp1252 à l'aveugle) ;
- la détection du séparateur : tabulation, puis point-virgule, puis
  virgule — surchargeable ;
- les formats suisses : dates 31.12.2019 (siècle déduit sous 70),
  heures 08:00 / 8h30, montants 1'949.75 ou 1 949,75.

Une valeur illisible lève ValueError avec l'original : c'est à
l'appelant de rejeter la ligne avec sa raison, jamais de deviner.
"""

import re
import unicodedata
from datetime import date, time

_DATE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})$")
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_TIME_RE = re.compile(r"^(\d{1,2})[:hH](\d{2})?$")
_AMOUNT_CLEAN_RE = re.compile(r"[\s'’  ]|CHF|EUR", re.I)


def decode_text(raw, encoding=None):
    """Octets d'un export -> texte. `encoding` explicite prioritaire ;
    sinon BOM, puis UTF-8 strict, puis cp1252 (jamais d'échec)."""
    if encoding and encoding != 'auto':
        return raw.decode(encoding)
    if raw.startswith(b'\xef\xbb\xbf'):
        return raw.decode('utf-8-sig')
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16')
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('cp1252')


def sniff_delimiter(text, delimiter=None):
    """Séparateur de colonnes, décidé sur la ligne d'en-tête."""
    if delimiter and delimiter != 'auto':
        return '\t' if delimiter == 'tab' else delimiter
    header = text.split('\n', 1)[0]
    for candidate in ('\t', ';', ','):
        if candidate in header:
            return candidate
    return '\t'


def norm(text):
    """Forme de comparaison : minuscules, accents retirés, tout ce qui
    n'est pas alphanumérique réduit à une espace simple. Sert à
    rapprocher les en-têtes de leurs alias et à bâtir des clés."""
    text = unicodedata.normalize('NFD', text or '')
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def slug(text):
    """`norm` en clé stable : « Petit laboratoire » -> petit-laboratoire."""
    return norm(text).replace(' ', '-')


def parse_table(text, delimiter=None):
    """Export -> (en-têtes normalisés, lignes en dicts).

    La première ligne nomme les colonnes ; les lignes vides sont
    sautées ; une ligne plus courte que l'en-tête est complétée de
    vides, une plus longue voit son excédent ignoré (les exports 4D
    traînent parfois un séparateur final). La validation du CONTENU
    appartient à l'appelant, champ par champ."""
    sep = sniff_delimiter(text, delimiter)
    lines = [line for line in text.replace('\r\n', '\n').replace(
        '\r', '\n').split('\n') if line.strip()]
    if not lines:
        return [], []
    headers = [norm(cell) for cell in lines[0].split(sep)]
    rows = []
    for line in lines[1:]:
        cells = [cell.strip() for cell in line.split(sep)]
        cells += [''] * (len(headers) - len(cells))
        rows.append(dict(zip(headers, cells)))
    return headers, rows


def parse_swiss_date(text):
    """31.12.2019, 5.1.24 (siècle déduit : < 70 -> 2000+) ou ISO
    2019-12-31. Vide -> None ; illisible -> ValueError."""
    text = (text or '').strip()
    if not text:
        return None
    match = _ISO_DATE_RE.match(text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return date(year, month, day)
    match = _DATE_RE.match(text)
    if not match:
        raise ValueError("date illisible : %r" % (text,))
    day, month, year = (int(part) for part in match.groups())
    if year < 100:
        year += 2000 if year < 70 else 1900
    try:
        return date(year, month, day)
    except ValueError:
        raise ValueError("date impossible : %r" % (text,))


def parse_swiss_time(text):
    """08:00, 8h30, 14H — vide -> None ; illisible -> ValueError."""
    text = (text or '').strip()
    if not text:
        return None
    match = _TIME_RE.match(text)
    if not match:
        raise ValueError("heure illisible : %r" % (text,))
    hour, minute = int(match.group(1)), int(match.group(2) or 0)
    if hour > 23 or minute > 59:
        raise ValueError("heure impossible : %r" % (text,))
    return time(hour, minute)


def parse_swiss_amount(text):
    """1'949.75, 1 949,75, CHF 500.00 -> float. Vide -> None ;
    illisible -> ValueError. Le DERNIER point ou virgule fait la
    décimale, l'autre disparaît en séparateur de milliers."""
    original = text
    text = _AMOUNT_CLEAN_RE.sub('', (text or ''))
    if not text:
        return None
    if ',' in text and '.' in text:
        decimal = max(text.rfind(','), text.rfind('.'))
        text = (text[:decimal].replace(',', '').replace('.', '')
                + '.' + text[decimal + 1:])
    else:
        text = text.replace(',', '.')
    try:
        return float(text)
    except ValueError:
        raise ValueError("montant illisible : %r" % (original,))
