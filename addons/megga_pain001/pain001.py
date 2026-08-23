"""Générateur pain.001.001.09.ch.03 — ordres de virement Swiss Payment Standards.

Bibliothèque pure (stdlib uniquement, aucune dépendance Odoo), testable hors
serveur. Le XML produit est destiné au e-banking : namespace ISO
urn:iso:std:iso:20022:tech:xsd:pain.001.001.09, restrictions suisses .ch.03.

Règles métier appliquées (Pain001Error sinon) :
- le compte débiteur doit être un IBAN CH/LI ;
- un créancier en QR-IBAN (IID 30000-31999) exige une référence QRR valide
  (27 chiffres, checksum mod10r), et réciproquement ;
- une référence RF (SCOR) doit satisfaire ISO 11649 (mod 97) ;
- montants strictement positifs, arrondis au centime.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

NS = 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.09'


class Pain001Error(ValueError):
    """Donnée de paiement invalide au regard des Swiss Payment Standards."""


# ---------------------------------------------------------------- utilitaires

def _clean(text, maxlen):
    text = ' '.join((text or '').split())
    return text[:maxlen]


def sanitize_iban(iban):
    return (iban or '').replace(' ', '').upper()


def is_qr_iban(iban):
    iban = sanitize_iban(iban)
    return (iban[:2] in ('CH', 'LI') and len(iban) >= 9
            and iban[4:9].isdigit() and 30000 <= int(iban[4:9]) <= 31999)


def valid_qrr(reference):
    reference = (reference or '').replace(' ', '')
    if len(reference) != 27 or not reference.isdigit():
        return False
    table = [0, 9, 4, 6, 8, 2, 7, 1, 3, 5]
    carry = 0
    for char in reference[:26]:
        carry = table[(carry + int(char)) % 10]
    return str((10 - carry) % 10) == reference[26]


def valid_scor(reference):
    reference = (reference or '').replace(' ', '').upper()
    if not (5 <= len(reference) <= 25 and reference.startswith('RF')
            and reference.isalnum()):
        return False
    rearranged = reference[4:] + reference[:4]
    number = ''.join(str(int(char, 36)) for char in rearranged)
    return int(number) % 97 == 1


# ------------------------------------------------------------------- données

@dataclass
class CreditTransfer:
    amount: Decimal
    currency: str
    creditor_name: str
    creditor_iban: str
    reference: str = ''          # QRR (27 chiffres) ou SCOR (RFxx…) ou vide
    message: str = ''            # communication non structurée
    end_to_end_id: str = ''
    creditor_street: str = ''
    creditor_building: str = ''
    creditor_zip: str = ''
    creditor_city: str = ''
    creditor_country: str = ''
    creditor_bic: str = ''


@dataclass
class PaymentOrder:
    message_id: str
    created_at: str              # ISO : AAAA-MM-JJTHH:MM:SS
    initiating_party: str
    debtor_name: str
    debtor_iban: str
    execution_date: str          # AAAA-MM-JJ
    debtor_bic: str = ''
    transfers: list = field(default_factory=list)


# ---------------------------------------------------------------- validation

def _classify_reference(transfer, position):
    reference = (transfer.reference or '').replace(' ', '')
    qr_creditor = is_qr_iban(transfer.creditor_iban)
    if qr_creditor:
        if not valid_qrr(reference):
            raise Pain001Error(
                "Paiement %s (%s) : le compte créancier est un QR-IBAN, une "
                "référence QRR valide (27 chiffres, mod10r) est obligatoire — "
                "reçu : %r" % (position, transfer.creditor_name, reference))
        return 'QRR', reference
    if reference:
        if valid_qrr(reference):
            raise Pain001Error(
                "Paiement %s (%s) : référence QRR fournie mais le compte "
                "créancier %s n'est pas un QR-IBAN."
                % (position, transfer.creditor_name, transfer.creditor_iban))
        if not valid_scor(reference):
            raise Pain001Error(
                "Paiement %s (%s) : référence %r invalide — ni QRR ni "
                "référence créancier ISO 11649 (RF…)."
                % (position, transfer.creditor_name, transfer.reference))
        return 'SCOR', reference
    return None, ''


def _validate(order):
    debtor_iban = sanitize_iban(order.debtor_iban)
    if debtor_iban[:2] not in ('CH', 'LI'):
        raise Pain001Error(
            "Le compte débiteur %r doit être un IBAN suisse ou "
            "liechtensteinois." % order.debtor_iban)
    if not order.transfers:
        raise Pain001Error("Aucun paiement à exporter.")
    for position, transfer in enumerate(order.transfers, start=1):
        if transfer.amount <= 0:
            raise Pain001Error("Paiement %s (%s) : montant %s invalide."
                               % (position, transfer.creditor_name,
                                  transfer.amount))
        if not sanitize_iban(transfer.creditor_iban):
            raise Pain001Error("Paiement %s (%s) : IBAN créancier manquant."
                               % (position, transfer.creditor_name))
        if not _clean(transfer.creditor_name, 70):
            raise Pain001Error("Paiement %s : nom du créancier manquant."
                               % position)


# --------------------------------------------------------------- génération

def _element(parent, tag, text=None, **attrs):
    node = ET.SubElement(parent, '{%s}%s' % (NS, tag),
                         {key: value for key, value in attrs.items()})
    if text is not None:
        node.text = text
    return node


def _decimal(value):
    """Coercition sure : l'ORM d'Odoo fournit des float, l'API des Decimal."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _money(value):
    return str(_decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _postal_address(parent, transfer):
    if not (transfer.creditor_country
            and (transfer.creditor_city or transfer.creditor_street)):
        return
    address = _element(parent, 'PstlAdr')
    if transfer.creditor_street:
        _element(address, 'StrtNm', _clean(transfer.creditor_street, 70))
    if transfer.creditor_building:
        _element(address, 'BldgNb', _clean(transfer.creditor_building, 16))
    if transfer.creditor_zip:
        _element(address, 'PstCd', _clean(transfer.creditor_zip, 16))
    if transfer.creditor_city:
        _element(address, 'TwnNm', _clean(transfer.creditor_city, 35))
    _element(address, 'Ctry', transfer.creditor_country.strip().upper()[:2])


def generate_pain001(order):
    """PaymentOrder -> bytes XML pain.001.001.09.ch.03. Pain001Error sinon."""
    _validate(order)
    ET.register_namespace('', NS)

    control_sum = _money(sum((_decimal(t.amount) for t in order.transfers),
                             Decimal('0')))
    count = str(len(order.transfers))

    document = ET.Element('{%s}Document' % NS)
    initiation = _element(document, 'CstmrCdtTrfInitn')

    header = _element(initiation, 'GrpHdr')
    _element(header, 'MsgId', _clean(order.message_id, 35))
    _element(header, 'CreDtTm', order.created_at)
    _element(header, 'NbOfTxs', count)
    _element(header, 'CtrlSum', control_sum)
    initiating = _element(header, 'InitgPty')
    _element(initiating, 'Nm', _clean(order.initiating_party, 70))

    payment_info = _element(initiation, 'PmtInf')
    _element(payment_info, 'PmtInfId', _clean(order.message_id, 33) + '-1')
    _element(payment_info, 'PmtMtd', 'TRF')
    _element(payment_info, 'BtchBookg', 'true')
    _element(payment_info, 'NbOfTxs', count)
    _element(payment_info, 'CtrlSum', control_sum)
    execution = _element(payment_info, 'ReqdExctnDt')
    _element(execution, 'Dt', order.execution_date)
    debtor = _element(payment_info, 'Dbtr')
    _element(debtor, 'Nm', _clean(order.debtor_name, 70))
    debtor_account = _element(payment_info, 'DbtrAcct')
    _element(_element(debtor_account, 'Id'), 'IBAN',
             sanitize_iban(order.debtor_iban))
    debtor_agent = _element(payment_info, 'DbtrAgt')
    agent_id = _element(debtor_agent, 'FinInstnId')
    if order.debtor_bic:
        _element(agent_id, 'BICFI', order.debtor_bic.replace(' ', '').upper())

    for position, transfer in enumerate(order.transfers, start=1):
        ref_type, reference = _classify_reference(transfer, position)

        transaction = _element(payment_info, 'CdtTrfTxInf')
        payment_id = _element(transaction, 'PmtId')
        _element(payment_id, 'InstrId', 'INSTR-%s' % position)
        _element(payment_id, 'EndToEndId',
                 _clean(transfer.end_to_end_id, 35) or 'NOTPROVIDED')
        amount = _element(transaction, 'Amt')
        _element(amount, 'InstdAmt', _money(transfer.amount),
                 Ccy=transfer.currency.strip().upper())
        if transfer.creditor_bic:
            creditor_agent = _element(transaction, 'CdtrAgt')
            _element(_element(creditor_agent, 'FinInstnId'), 'BICFI',
                     transfer.creditor_bic.replace(' ', '').upper())
        creditor = _element(transaction, 'Cdtr')
        _element(creditor, 'Nm', _clean(transfer.creditor_name, 70))
        _postal_address(creditor, transfer)
        creditor_account = _element(transaction, 'CdtrAcct')
        _element(_element(creditor_account, 'Id'), 'IBAN',
                 sanitize_iban(transfer.creditor_iban))

        message = _clean(transfer.message, 140)
        if ref_type:
            remittance = _element(transaction, 'RmtInf')
            structured = _element(remittance, 'Strd')
            reference_info = _element(structured, 'CdtrRefInf')
            reference_type = _element(reference_info, 'Tp')
            code_or_proprietary = _element(reference_type, 'CdOrPrtry')
            if ref_type == 'QRR':
                _element(code_or_proprietary, 'Prtry', 'QRR')
            else:
                _element(code_or_proprietary, 'Cd', 'SCOR')
            _element(reference_info, 'Ref', reference)
            if message:
                _element(structured, 'AddtlRmtInf', message)
        elif message:
            remittance = _element(transaction, 'RmtInf')
            _element(remittance, 'Ustrd', message)

    ET.indent(document)
    return ET.tostring(document, encoding='UTF-8', xml_declaration=True)
