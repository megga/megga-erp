from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..afc import AggregationError, apply_subformula, parse_aggregation


def _trimestre_precedent(today):
    """Bornes du dernier trimestre civil échu."""
    premier_du_trimestre = date(today.year, 3 * ((today.month - 1) // 3) + 1, 1)
    fin = premier_du_trimestre - timedelta(days=1)
    debut = date(fin.year, 3 * ((fin.month - 1) // 3) + 1, 1)
    return debut, fin


class MeggaTvaDecompteWizard(models.TransientModel):
    _name = 'megga.tva.decompte.wizard'
    _description = "Décompte TVA suisse (formulaire AFC)"

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    date_from = fields.Date(
        string="Du", required=True,
        default=lambda self: _trimestre_precedent(fields.Date.context_today(self))[0])
    date_to = fields.Date(
        string="Au", required=True,
        default=lambda self: _trimestre_precedent(fields.Date.context_today(self))[1])

    # ------------------------------------------------------------ évaluation

    def _report(self):
        report = self.env.ref('l10n_ch.tax_report', raise_if_not_found=False)
        if not report:
            raise UserError(_("Le rapport de taxes suisse (l10n_ch.tax_report) "
                              "est introuvable — l10n_ch est-il installé ?"))
        return report

    def _tag_sum(self, formula, country_id):
        """Sémantique 19.0 vérifiée dans account_account_tag.py : un tag nommé
        formula.lstrip('-') ; négation si la formule commence par « - »."""
        tags = self.env['account.account.tag']._get_tax_tags(formula, country_id)
        if not tags:
            return 0.0
        [(total,)] = self.env['account.move.line']._read_group(
            domain=[
                ('tax_tag_ids', 'in', tags.ids),
                ('parent_state', '=', 'posted'),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('company_id', '=', self.company_id.id),
            ],
            aggregates=['balance:sum'],
        )
        total = total or 0.0
        return -total if formula.startswith('-') else total

    def _compute_rubriques(self):
        """-> (rows, values) : rows pour le rendu (dans l'ordre du rapport),
        values = {code de ligne: montant}."""
        self.ensure_one()
        report = self._report()
        country_id = report.country_id.id
        lines = report.line_ids.sorted('sequence')

        expression_by_code = {}
        for line in lines:
            expression = line.expression_ids[:1]
            if line.code and expression:
                expression_by_code[line.code] = expression

        values, resolving = {}, set()

        def resolve(code):
            if code in values:
                return values[code]
            if code in resolving:
                raise UserError(_("Cycle d'agrégation dans le rapport de "
                                  "taxes sur le code %s") % code)
            expression = expression_by_code.get(code)
            if expression is None:
                values[code] = 0.0
                return 0.0
            resolving.add(code)
            if expression.engine == 'tax_tags':
                value = self._tag_sum(expression.formula, country_id)
            elif expression.engine == 'aggregation':
                try:
                    terms = parse_aggregation(expression.formula)
                except AggregationError as exc:
                    raise UserError(_("Rubrique %s : %s") % (code, exc))
                value = sum(sign * resolve(term) for sign, term in terms)
            else:
                value = 0.0   # moteur non géré : ne jamais inventer un chiffre
            value = apply_subformula(value, expression.subformula)
            resolving.discard(code)
            values[code] = self.company_id.currency_id.round(value)
            return values[code]

        rows = []
        for line in lines:
            expression = line.expression_ids[:1]
            has_value = bool(expression)
            value = 0.0
            if has_value:
                if line.code:
                    value = resolve(line.code)
                elif expression.engine == 'tax_tags':
                    value = self.company_id.currency_id.round(apply_subformula(
                        self._tag_sum(expression.formula, country_id),
                        expression.subformula))
                elif expression.engine == 'aggregation':
                    try:
                        terms = parse_aggregation(expression.formula)
                    except AggregationError as exc:
                        raise UserError(_("Ligne « %s » : %s") % (line.name, exc))
                    value = self.company_id.currency_id.round(apply_subformula(
                        sum(sign * resolve(term) for sign, term in terms),
                        expression.subformula))
            rows.append({
                'name': line.name,
                'code': line.code or '',
                'value': value,
                'has_value': has_value,
                'is_total': has_value and expression.engine == 'aggregation',
                'level': int(line.hierarchy_level or 0),
            })
        return rows, values

    def action_print(self):
        self.ensure_one()
        return self.env.ref('megga_tva_ch.action_report_decompte') \
                   .report_action(self)
