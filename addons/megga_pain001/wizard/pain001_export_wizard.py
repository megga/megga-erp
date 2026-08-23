import base64
import re
from decimal import Decimal

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..pain001 import (
    CreditTransfer, Pain001Error, PaymentOrder,
    generate_pain001, sanitize_iban, valid_qrr, valid_scor,
)

# Jeu de caractères admis pour les identifiants (charset SEPA/SPS).
_ID_CHARSET = re.compile(r"[^A-Za-z0-9/\-?:().,'+ ]")


class MeggaPain001ExportWizard(models.TransientModel):
    _name = 'megga.pain001.export.wizard'
    _description = "Export pain.001.001.09.ch.03 des paiements fournisseurs"

    journal_id = fields.Many2one(
        'account.journal', string="Journal de banque", required=True,
        domain=[('type', '=', 'bank')])
    execution_date = fields.Date(
        string="Date d'exécution souhaitée", required=True,
        default=fields.Date.context_today)
    payment_ids = fields.Many2many(
        'account.payment', string="Paiements",
        domain=[('payment_type', '=', 'outbound')])
    force_reexport = fields.Boolean(
        string="Ré-exporter les paiements déjà envoyés",
        help="À n'utiliser que si le fichier précédent n'a pas été transmis "
             "à la banque.")

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'account.payment':
            payments = self.env['account.payment'].browse(
                self.env.context.get('active_ids', []))
            vals.setdefault('payment_ids', [(6, 0, payments.ids)])
            if len(payments.journal_id) == 1:
                vals.setdefault('journal_id', payments.journal_id.id)
        return vals

    # ------------------------------------------------------------- contrôles

    def _check_payments(self):
        payments = self.payment_ids
        if not payments:
            raise UserError(_("Aucun paiement sélectionné."))

        def names(records):
            return ', '.join(records.mapped('name'))

        wrong_type = payments.filtered(lambda p: p.payment_type != 'outbound')
        if wrong_type:
            raise UserError(_("Seuls les paiements sortants s'exportent en "
                              "pain.001 : %s") % names(wrong_type))
        wrong_state = payments.filtered(
            lambda p: p.state not in ('in_process', 'paid'))
        if wrong_state:
            raise UserError(_("Paiements non validés (brouillon, annulé ou "
                              "rejeté) : %s") % names(wrong_state))
        wrong_journal = payments.filtered(
            lambda p: p.journal_id != self.journal_id)
        if wrong_journal:
            raise UserError(_("Paiements d'un autre journal que « %s » : %s")
                            % (self.journal_id.display_name,
                               names(wrong_journal)))
        no_bank = payments.filtered(lambda p: not p.partner_bank_id)
        if no_bank:
            raise UserError(_("Compte bancaire du bénéficiaire manquant "
                              "sur : %s") % names(no_bank))
        if not self.force_reexport:
            sent = payments.filtered('megga_pain_msg_id')
            if sent:
                raise UserError(_(
                    "Déjà exportés (cochez « Ré-exporter » si le fichier "
                    "précédent n'a pas été transmis) : %s") % names(sent))

    # ------------------------------------------------------------ conversion

    def _to_transfer(self, payment):
        partner = payment.partner_id
        bank = payment.partner_bank_id
        memo = (payment.memo or '').strip()
        compact = memo.replace(' ', '')
        reference, message = '', memo
        if valid_qrr(compact) or valid_scor(compact):
            reference, message = compact, ''
        return CreditTransfer(
            amount=Decimal(str(payment.amount)),
            currency=payment.currency_id.name,
            creditor_name=bank.acc_holder_name or partner.name or '',
            creditor_iban=bank.acc_number or '',
            reference=reference,
            message=message,
            end_to_end_id=_ID_CHARSET.sub('-', payment.name or ''),
            creditor_street=partner.street or '',
            creditor_zip=partner.zip or '',
            creditor_city=partner.city or '',
            creditor_country=partner.country_id.code or '',
            creditor_bic=bank.bank_id.bic or '',
        )

    # ---------------------------------------------------------------- export

    def action_export(self):
        self.ensure_one()
        self._check_payments()
        journal = self.journal_id
        if not journal.bank_account_id:
            raise UserError(_("Le journal « %s » n'a pas de compte bancaire "
                              "configuré.") % journal.display_name)
        company = journal.company_id
        now = fields.Datetime.now()
        message_id = 'MEGGA-%s' % now.strftime('%Y%m%d%H%M%S')

        order = PaymentOrder(
            message_id=message_id,
            created_at=now.strftime('%Y-%m-%dT%H:%M:%S'),
            initiating_party=company.name,
            debtor_name=company.name,
            debtor_iban=sanitize_iban(journal.bank_account_id.acc_number),
            debtor_bic=journal.bank_account_id.bank_id.bic or '',
            execution_date=fields.Date.to_string(self.execution_date),
            transfers=[self._to_transfer(p) for p in self.payment_ids],
        )
        try:
            xml_bytes = generate_pain001(order)
        except Pain001Error as exc:
            raise UserError(str(exc))

        attachment = self.env['ir.attachment'].create({
            'name': '%s.xml' % message_id,
            'datas': base64.b64encode(xml_bytes),
            'mimetype': 'application/xml',
            'res_model': 'account.journal',
            'res_id': journal.id,
        })
        self.payment_ids.write({'megga_pain_msg_id': message_id})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
