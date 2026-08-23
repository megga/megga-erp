import base64

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..camt_parser import CamtParseError, parse_camt


class MeggaCamtImportWizard(models.TransientModel):
    _name = 'megga.camt.import.wizard'
    _description = "Import de relevés camt.053 et d'avis camt.054"

    journal_id = fields.Many2one(
        'account.journal', string="Journal de banque", required=True,
        domain=[('type', '=', 'bank')])
    attachment_ids = fields.Many2many(
        'ir.attachment', string="Fichiers camt", required=True)

    def action_import(self):
        self.ensure_one()
        if not self.attachment_ids:
            raise UserError(_("Aucun fichier fourni."))

        journal = self.journal_id
        journal_currency = journal.currency_id or journal.company_id.currency_id
        journal_iban = ''
        if journal.bank_account_id:
            journal_iban = (journal.bank_account_id.sanitized_acc_number or '').upper()

        Statement = self.env['account.bank.statement']
        Line = self.env['account.bank.statement.line']
        created = Statement
        skipped = []

        for attachment in self.attachment_ids:
            raw = base64.b64decode(attachment.datas or b'')
            try:
                camt_statements = parse_camt(raw)
            except CamtParseError as exc:
                raise UserError("%s : %s" % (attachment.name, exc))

            for camt in camt_statements:
                # Garde devise : tout le fichier doit être dans la devise du journal.
                currencies = {camt.currency} | {t.currency for t in camt.transactions}
                currencies.discard('')
                foreign = currencies - {journal_currency.name}
                if foreign:
                    raise UserError(_(
                        "%s : devise(s) %s alors que le journal « %s » est en %s. "
                        "Importez ce fichier dans un journal de la bonne devise."
                    ) % (attachment.name, ', '.join(sorted(foreign)),
                         journal.display_name, journal_currency.name))

                # Garde IBAN : le relevé doit viser le compte du journal.
                camt_iban = (camt.account_iban or '').replace(' ', '').upper()
                if journal_iban and camt_iban and camt_iban != journal_iban:
                    raise UserError(_(
                        "%s : le relevé « %s » porte sur le compte %s, mais le "
                        "journal « %s » est relié au compte %s."
                    ) % (attachment.name, camt.name, camt_iban,
                         journal.display_name, journal_iban))

                # Déduplication au niveau du relevé…
                if Statement.search_count([('name', '=', camt.name),
                                           ('journal_id', '=', journal.id)]):
                    skipped.append(_("%s : relevé déjà importé") % camt.name)
                    continue

                # …et au niveau des transactions (ré-imports partiels,
                # recouvrement camt.053 / camt.054).
                unique_refs = [t.unique_ref for t in camt.transactions]
                already = set(Line.search([
                    ('journal_id', '=', journal.id),
                    ('megga_import_ref', 'in', unique_refs),
                ]).mapped('megga_import_ref'))

                line_vals = []
                for transaction in camt.transactions:
                    if transaction.unique_ref in already:
                        continue
                    line_vals.append({
                        'journal_id': journal.id,
                        'date': transaction.date or fields.Date.context_today(self),
                        'payment_ref': transaction.label,
                        'ref': transaction.reference or False,
                        'partner_name': transaction.partner_name or False,
                        'account_number': transaction.partner_account or False,
                        'amount': float(transaction.amount),
                        'transaction_type': 'camt.%s' % camt.kind,
                        'megga_import_ref': transaction.unique_ref,
                    })
                if not line_vals:
                    skipped.append(_("%s : transactions déjà toutes importées")
                                   % camt.name)
                    continue

                statement_vals = {'name': camt.name, 'reference': attachment.name}
                if camt.balance_start is not None:
                    statement_vals['balance_start'] = float(camt.balance_start)
                if camt.balance_end is not None:
                    statement_vals['balance_end_real'] = float(camt.balance_end)
                statement = Statement.create(statement_vals)
                for vals in line_vals:
                    vals['statement_id'] = statement.id
                Line.create(line_vals)
                statement.attachment_ids = [(4, attachment.id)]
                created |= statement

        if not created:
            raise UserError(_("Rien à importer.\n%s")
                            % ('\n'.join(skipped) or _("Aucun relevé nouveau.")))

        action = {
            'name': _("Relevés importés"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created.ids)],
        }
        if len(created) == 1:
            action.update({'view_mode': 'form', 'res_id': created.id, 'domain': []})
        return action
