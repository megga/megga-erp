"""Helpers purs du décompte TVA AFC (stdlib uniquement, testables hors Odoo).

Évaluation des formules d'agrégation du rapport de taxes suisse de l10n_ch
(engine « aggregation » : « tax_ch_A.balance + tax_ch_B.balance - … »)
et de la sous-formule de plancher « if_above(CHF(0)) » des rubriques 500/510.
"""
import re

_TERM = re.compile(r'\s*(?P<op>[+-])?\s*(?P<code>[A-Za-z0-9_]+)\.balance\s*')


class AggregationError(ValueError):
    """Formule d'agrégation non reconnue."""


def parse_aggregation(formula):
    """'a.balance + b.balance - c.balance' -> [(1,'a'), (1,'b'), (-1,'c')].

    Refuse toute formule qui ne se réduit pas exactement à cette grammaire :
    mieux vaut échouer bruyamment que publier un décompte faux.
    """
    terms, position = [], 0
    while position < len(formula):
        match = _TERM.match(formula, position)
        if not match:
            raise AggregationError(
                "Formule d'agrégation non reconnue à la position %s : %r"
                % (position, formula))
        operator = match.group('op')
        if operator is None and terms:
            raise AggregationError("Opérateur manquant dans %r" % formula)
        terms.append((-1 if operator == '-' else 1, match.group('code')))
        position = match.end()
    if not terms:
        raise AggregationError("Formule vide")
    return terms


def apply_subformula(value, subformula):
    """Applique la sous-formule d'une expression (500/510 : if_above(CHF(0)))."""
    if subformula and 'if_above' in subformula:
        return value if value > 0 else 0.0
    return value


def montant_suisse(value):
    """-1234.5 -> « -1'234.50 » (séparateur de milliers suisse)."""
    return format(value, ',.2f').replace(',', "'")
