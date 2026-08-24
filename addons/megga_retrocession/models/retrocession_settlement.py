from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..retrocession_logic import (
    periods_overlap,
    retrocession_amount,
    signed_volume,
)

REFUND_TYPES = ('in_refund', 'out_refund')


class MeggaRetrocessionSettlement(models.Model):
    """Le décompte d'une période : il compte les factures validées, fige
    volume, taux et montant, puis génère la pièce comptable. Les factures
    comptées restent attachées : le chiffre se justifie ligne à ligne —
    y compris face au partenaire, en négociation."""
    _name = 'megga.retrocession.settlement'
    _description = "Décompte de rétrocession"
    _inherit = ['mail.thread']
    _order = 'date_from desc, id desc'

    name = fields.Char(
        "Référence", readonly=True, copy=False, default='/')
    agreement_id = fields.Many2one(
        'megga.retrocession.agreement', string="Accord", required=True,
        ondelete='restrict', index=True)
    partner_id = fields.Many2one(
        related='agreement_id.partner_id', store=True)
    direction = fields.Selection(
        related='agreement_id.direction', store=True)
    company_id = fields.Many2one(
        related='agreement_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    # Le taux est FIGÉ sur le décompte à sa création : une renégociation
    # de l'accord ne réécrit jamais un décompte passé — seul le choix
    # d'un autre accord le recalcule.
    rate = fields.Float(
        "Taux (%)", digits=(5, 2), tracking=True,
        compute='_compute_rate', store=True, readonly=False,
        precompute=True)
    date_from = fields.Date("Du", required=True)
    date_to = fields.Date("Au", required=True)
    state = fields.Selection([
        ('draft', "Brouillon"),
        ('confirmed', "Confirmé"),
        ('invoiced', "Facturé"),
    ], string="État", default='draft', required=True, copy=False,
        tracking=True)
    move_ids = fields.Many2many(
        'account.move', 'megga_retrocession_settlement_move_rel',
        string="Factures comptées", readonly=True, copy=False)
    move_count = fields.Integer(compute='_compute_move_count')
    volume = fields.Monetary(
        "Volume de la période", readonly=True, copy=False,
        currency_field='currency_id',
        help="Somme HT des factures comptées, avoirs déduits.")
    amount = fields.Monetary(
        "Rétrocession", compute='_compute_amount', store=True,
        currency_field='currency_id')
    invoice_id = fields.Many2one(
        'account.move', string="Pièce de rétrocession", readonly=True,
        copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'megga.retrocession.settlement') or '/'
        return super().create(vals_list)

    @api.depends('agreement_id')
    def _compute_rate(self):
        for settlement in self:
            if settlement.agreement_id:
                settlement.rate = settlement.agreement_id.rate
            else:
                settlement.rate = settlement.rate

    @api.depends('volume', 'rate')
    def _compute_amount(self):
        for settlement in self:
            if settlement.rate > 0:
                value = retrocession_amount(
                    settlement.volume, settlement.rate)
            else:
                value = 0.0
            settlement.amount = (
                settlement.currency_id.round(value)
                if settlement.currency_id else value)

    @api.depends('move_ids')
    def _compute_move_count(self):
        for settlement in self:
            settlement.move_count = len(settlement.move_ids)

    @api.constrains('date_from', 'date_to', 'agreement_id')
    def _check_periods(self):
        for settlement in self:
            if settlement.date_to < settlement.date_from:
                raise ValidationError(
                    _("La fin de la période précède son début."))
            autres = self.search([
                ('agreement_id', '=', settlement.agreement_id.id),
                ('id', '!=', settlement.id),
            ])
            for autre in autres:
                if periods_overlap(
                        settlement.date_from, settlement.date_to,
                        autre.date_from, autre.date_to):
                    raise ValidationError(_(
                        "La période chevauche le décompte %(autre)s "
                        "(%(du)s — %(au)s) : une facture serait comptée "
                        "deux fois.",
                        autre=autre.name, du=autre.date_from,
                        au=autre.date_to))

    def _counted_moves_domain(self):
        """Ce qui compte : les factures VALIDÉES de la période — celles
        du partenaire quand on encaisse (son volume chez nous), celles
        marquées de l'apporteur quand on verse (le volume qu'il nous a
        amené). Avoirs compris, en déduction."""
        self.ensure_one()
        domain = [
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
        ]
        if self.direction == 'receivable':
            domain += [
                ('partner_id', '=', self.partner_id.id),
                ('move_type', 'in', ('in_invoice', 'in_refund')),
            ]
        else:
            domain += [
                ('referrer_id', '=', self.partner_id.id),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
            ]
        return domain

    def action_refresh(self):
        """Recompte la période. Ceinture en plus des périodes sans
        chevauchement : une facture déjà attachée à un autre décompte du
        même accord (une date corrigée après coup, par exemple) n'est
        jamais recomptée ici."""
        for settlement in self:
            if settlement.state != 'draft':
                raise UserError(
                    _("Seul un décompte en brouillon se recalcule."))
            deja = self.search([
                ('agreement_id', '=', settlement.agreement_id.id),
                ('id', '!=', settlement.id),
            ]).move_ids
            moves = self.env['account.move'].search(
                settlement._counted_moves_domain()) - deja
            settlement.write({
                'move_ids': [Command.set(moves.ids)],
                'volume': signed_volume([
                    (move.amount_untaxed, move.move_type in REFUND_TYPES)
                    for move in moves]),
            })

    def action_confirm(self):
        """Confirme sur des chiffres frais : le recompte fait partie de
        la confirmation, pas un préalable qu'on peut oublier."""
        for settlement in self:
            if settlement.state != 'draft':
                raise UserError(
                    _("Seul un décompte en brouillon se confirme."))
            settlement.action_refresh()
            settlement.state = 'confirmed'

    def action_reset_to_draft(self):
        for settlement in self:
            if settlement.state != 'confirmed':
                raise UserError(
                    _("Seul un décompte confirmé revient en brouillon."))
            settlement.state = 'draft'

    def action_create_invoice(self):
        """Génère la pièce : facture client au partenaire quand on
        encaisse, facture fournisseur provisionnée au nom de l'apporteur
        quand on verse — dans les deux cas en brouillon, à valider par
        la comptabilité."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(
                _("Seul un décompte confirmé se facture."))
        if self.invoice_id and self.invoice_id.state != 'cancel':
            raise UserError(
                _("Ce décompte est déjà facturé (%s).")
                % self.invoice_id.display_name)
        if self.currency_id.is_zero(self.amount):
            raise UserError(
                _("Rien à facturer : le volume de la période est nul."))
        move_type = (
            'out_invoice' if self.direction == 'receivable'
            else 'in_invoice')
        move = self.env['account.move'].with_company(self.company_id).create({
            'move_type': move_type,
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_origin': self.name,
            'invoice_line_ids': [Command.create({
                'name': self._invoice_line_name(),
                'quantity': 1.0,
                'price_unit': self.amount,
            })],
        })
        self.write({'invoice_id': move.id, 'state': 'invoiced'})
        self.message_post(body=_("Pièce %s créée.") % move.display_name)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
        }

    def _invoice_line_name(self):
        self.ensure_one()
        return _(
            "Rétrocession %(accord)s — période du %(du)s au %(au)s — "
            "%(taux).2f %% d'un volume de %(volume).2f",
            accord=self.agreement_id.name,
            du=self.date_from.strftime('%d.%m.%Y'),
            au=self.date_to.strftime('%d.%m.%Y'),
            taux=self.rate, volume=self.volume)
