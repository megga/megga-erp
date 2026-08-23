"""Parseur camt.053 / camt.054 (et camt.052) — ISO 20022, variantes suisses.

Bibliothèque pure (stdlib uniquement, aucune dépendance Odoo) : testable hors
serveur. Lecture par nom local, indépendante de l'espace de noms, donc
tolérante aux versions de schéma (.001.02 / .04 / .08, suffixe .ch.02 des
Swiss Payment Standards compris). La référence structurée QRR/SCOR est lue
dans RmtInf/Strd/CdtrRefInf/Ref — c'est elle qui permet le rapprochement
automatique des encaissements de QR-factures.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


class CamtParseError(ValueError):
    """Fichier illisible, ou qui n'est pas un camt.052/053/054."""


_KINDS = {
    'BkToCstmrStmt': ('053', 'Stmt'),
    'BkToCstmrDbtCdtNtfctn': ('054', 'Ntfctn'),
    'BkToCstmrAcctRpt': ('052', 'Rpt'),
}


def _local(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _children(node, name):
    if node is None:
        return []
    return [child for child in node if _local(child.tag) == name]


def _find(node, *path):
    for name in path:
        if node is None:
            return None
        found = _children(node, name)
        node = found[0] if found else None
    return node


def _text(node, *path, default=''):
    found = _find(node, *path) if path else node
    if found is None or found.text is None:
        return default
    return found.text.strip() or default


@dataclass
class CamtTransaction:
    amount: Decimal          # signé : crédit positif, débit négatif
    currency: str
    date: str                # AAAA-MM-JJ (BookgDt, repli ValDt)
    reference: str           # référence structurée QRR/SCOR, repli EndToEndId
    label: str
    partner_name: str
    partner_account: str
    unique_ref: str          # identifiant de déduplication


@dataclass
class CamtStatement:
    kind: str                # '052' | '053' | '054'
    name: str
    account_iban: str
    currency: str
    balance_start: Decimal | None
    balance_end: Decimal | None
    transactions: list = field(default_factory=list)


def _amount_of(node):
    amt = _find(node, 'Amt')
    if amt is None:
        raise CamtParseError("Montant absent (élément Amt)")
    try:
        value = Decimal(_text(amt))
    except InvalidOperation as exc:
        raise CamtParseError("Montant illisible : %r" % _text(amt)) from exc
    return value, (amt.get('Ccy') or '')


def _signed(node, value, inherited=''):
    indicator = _text(node, 'CdtDbtInd') or inherited
    signed = value if indicator == 'CRDT' else -value
    if _text(node, 'RvslInd').lower() == 'true':
        signed = -signed
    return signed


def _date_of(node):
    for holder in ('BookgDt', 'ValDt'):
        for leaf in ('Dt', 'DtTm'):
            value = _text(node, holder, leaf)
            if value:
                return value[:10]
    return ''


def _party_name(txdtls, role):
    party = _find(txdtls, 'RltdPties', role)
    if party is None:
        return ''
    # .02/.04 : Dbtr/Nm — .08 : Dbtr/Pty/Nm
    return _text(party, 'Nm') or _text(party, 'Pty', 'Nm')


def _party_account(txdtls, role):
    acct = _find(txdtls, 'RltdPties', role + 'Acct')
    if acct is None:
        return ''
    return _text(acct, 'Id', 'IBAN') or _text(acct, 'Id', 'Othr', 'Id')


def _unstructured(txdtls):
    rmtinf = _find(txdtls, 'RmtInf')
    parts = [_text(node) for node in _children(rmtinf, 'Ustrd')]
    return ' '.join(part for part in parts if part)


def _reference(txdtls):
    ref = _text(txdtls, 'RmtInf', 'Strd', 'CdtrRefInf', 'Ref') \
        or _text(txdtls, 'Refs', 'EndToEndId')
    return '' if ref.upper() == 'NOTPROVIDED' else ref


def _build_transaction(amount, currency, date, txdtls, stmt_name, fallback_unique):
    role = 'Dbtr' if amount >= 0 else 'Cdtr'
    reference = _reference(txdtls) if txdtls is not None else ''
    partner = _party_name(txdtls, role) if txdtls is not None else ''
    label = (_unstructured(txdtls) if txdtls is not None else '') \
        or ' — '.join(part for part in (partner, reference) if part) \
        or 'Transaction camt %s' % stmt_name
    unique = ''
    if txdtls is not None:
        unique = _text(txdtls, 'Refs', 'AcctSvcrRef')
        if not unique:
            end_to_end = _text(txdtls, 'Refs', 'EndToEndId')
            unique = '' if end_to_end.upper() == 'NOTPROVIDED' else end_to_end
    return CamtTransaction(
        amount=amount,
        currency=currency,
        date=date,
        reference=reference,
        label=label,
        partner_name=partner,
        partner_account=_party_account(txdtls, role) if txdtls is not None else '',
        unique_ref=unique or fallback_unique,
    )


def _entry_transactions(entry, stmt_name, entry_index):
    entry_value, entry_ccy = _amount_of(entry)
    entry_indicator = _text(entry, 'CdtDbtInd')
    entry_amount = _signed(entry, entry_value)
    entry_date = _date_of(entry)
    entry_ref = _text(entry, 'NtryRef') or str(entry_index)

    txdtls_list = []
    for details in _children(entry, 'NtryDtls'):
        txdtls_list.extend(_children(details, 'TxDtls'))

    # Éclatement par TxDtls uniquement si chaque détail porte son montant
    # (lot d'encaissements QR typique des camt.054 suisses).
    if txdtls_list and all(_find(tx, 'Amt') is not None for tx in txdtls_list):
        transactions = []
        for j, txdtls in enumerate(txdtls_list):
            value, ccy = _amount_of(txdtls)
            amount = _signed(txdtls, value, inherited=entry_indicator)
            fallback = '%s/%s/%s' % (stmt_name, entry_ref, j)
            transactions.append(_build_transaction(
                amount, ccy or entry_ccy, entry_date, txdtls, stmt_name, fallback))
        return transactions

    txdtls = txdtls_list[0] if txdtls_list else None
    fallback = _text(entry, 'AcctSvcrRef') or '%s/%s' % (stmt_name, entry_ref)
    return [_build_transaction(
        entry_amount, entry_ccy, entry_date, txdtls, stmt_name, fallback)]


def _balances(stmt_node):
    start = end = None
    for bal in _children(stmt_node, 'Bal'):
        code = _text(bal, 'Tp', 'CdOrPrtry', 'Cd')
        value, _ccy = _amount_of(bal)
        signed = value if _text(bal, 'CdtDbtInd') == 'CRDT' else -value
        if code == 'OPBD':
            start = signed
        elif code == 'CLBD':
            end = signed
    return start, end


def parse_camt(content):
    """bytes ou str -> list[CamtStatement]. CamtParseError si illisible."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise CamtParseError("XML illisible : %s" % exc) from exc
    if _local(root.tag) != 'Document' or len(root) == 0:
        raise CamtParseError("Racine %r inattendue : pas un document ISO 20022"
                             % _local(root.tag))
    head = _local(root[0].tag)
    if head not in _KINDS:
        raise CamtParseError(
            "Document ISO 20022 de type %r : seuls camt.052/053/054 sont admis "
            "(un pain.001 est un fichier de paiement, pas un relevé)" % head)
    kind, stmt_tag = _KINDS[head]

    statements = []
    for stmt_node in _children(root[0], stmt_tag):
        name = _text(stmt_node, 'Id') or 'camt-%s' % kind
        start, end = _balances(stmt_node)
        acct = _find(stmt_node, 'Acct')
        statement = CamtStatement(
            kind=kind,
            name=name,
            account_iban=_text(acct, 'Id', 'IBAN') or _text(acct, 'Id', 'Othr', 'Id'),
            currency=_text(acct, 'Ccy'),
            balance_start=start,
            balance_end=end,
        )
        for index, entry in enumerate(_children(stmt_node, 'Ntry')):
            statement.transactions.extend(
                _entry_transactions(entry, name, index))
        statements.append(statement)
    if not statements:
        raise CamtParseError("Aucun relevé (%s) dans ce document camt.%s"
                             % (stmt_tag, kind))
    return statements
