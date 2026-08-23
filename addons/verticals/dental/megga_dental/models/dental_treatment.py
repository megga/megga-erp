from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from ..dental_logic import next_recall_date


class MeggaDentalTreatment(models.Model):
    """Un traitement regroupe les actes d'une séance ou d'un plan de soins :
    devis -> planifié -> terminé, puis facturation en un clic. La facture est
    une account.move ordinaire : la QR-facture (megga_qr_export) et
    l'encaissement camt (megga_camt) du socle prennent le relais."""
    _name = 'megga.dental.treatment'
    _description = "Traitement dentaire"
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(
        "Référence", readonly=True, copy=False, default='/')
    patient_id = fields.Many2one(
        'megga.dental.patient', string="Patient", required=True,
        ondelete='restrict', index=True)
    partner_id = fields.Many2one(
        related='patient_id.partner_id', store=True)
    dentist_id = fields.Many2one(
        'res.users', string="Praticien",
        default=lambda self: self.env.user)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    date = fields.Date(
        "Date du traitement", required=True,
        default=fields.Date.context_today)
    state = fields.Selection([
        ('draft', "Devis"),
        ('confirmed', "Planifié"),
        ('done', "Terminé"),
        ('cancelled', "Annulé"),
    ], string="État", default='draft', required=True, copy=False,
        tracking=True)
    line_ids = fields.One2many(
        'megga.dental.treatment.line', 'treatment_id',
        string="Actes", copy=True)
    amount_total = fields.Monetary(
        "Total", compute='_compute_amount_total', store=True,
        currency_field='currency_id')
    invoice_id = fields.Many2one(
        'account.move', string="Facture", readonly=True, copy=False)
    # Contenu clinique : réservé aux soins (LPD). Les actes et montants
    # restent visibles de la réception — ils figurent sur la facture.
    notes = fields.Text(
        "Notes cliniques", groups="megga_dental.group_dental_praticien")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'megga.dental.treatment') or '/'
        return super().create(vals_list)

    @api.depends('line_ids.subtotal')
    def _compute_amount_total(self):
        for treatment in self:
            treatment.amount_total = sum(treatment.line_ids.mapped('subtotal'))

    def action_confirm(self):
        for treatment in self:
            if treatment.state != 'draft':
                raise UserError(_("Seul un devis peut être planifié."))
            if not treatment.line_ids:
                raise UserError(
                    _("Ajoutez au moins un acte avant de planifier."))
            treatment.state = 'confirmed'

    def action_done(self):
        """Clôt la séance et arme le rappel de contrôle du patient."""
        for treatment in self:
            if treatment.state != 'confirmed':
                raise UserError(
                    _("Seul un traitement planifié peut être terminé."))
            treatment.state = 'done'
            patient = treatment.patient_id
            patient.write({
                'last_visit_date': treatment.date,
                'recall_date': next_recall_date(
                    treatment.date, patient.recall_months or 6),
            })

    def action_cancel(self):
        for treatment in self:
            if treatment.invoice_id and treatment.invoice_id.state != 'cancel':
                raise UserError(
                    _("Annulez d'abord la facture %s.")
                    % treatment.invoice_id.display_name)
            treatment.state = 'cancelled'

    def action_create_invoice(self):
        self.ensure_one()
        if self.state != 'done':
            raise UserError(_("Seul un traitement terminé peut être facturé."))
        if self.invoice_id:
            raise UserError(
                _("Ce traitement est déjà facturé (%s).")
                % self.invoice_id.display_name)
        move = self.env['account.move'].with_company(self.company_id).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_origin': self.name,
            'invoice_line_ids': [Command.create({
                'product_id': line.product_id.id,
                'name': line._invoice_line_name(),
                'quantity': line.quantity,
                'price_unit': line.price_unit,
            }) for line in self.line_ids],
        })
        self.invoice_id = move
        self.message_post(body=_("Facture %s créée.") % move.display_name)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
        }


class MeggaDentalTreatmentLine(models.Model):
    _name = 'megga.dental.treatment.line'
    _description = "Acte de soin"
    _order = 'treatment_id, sequence, id'

    treatment_id = fields.Many2one(
        'megga.dental.treatment', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product', string="Acte", required=True)
    description = fields.Char("Description")
    tooth_ids = fields.Many2many(
        'megga.dental.tooth', string="Dents")
    quantity = fields.Float("Quantité", default=1.0, required=True)
    price_unit = fields.Float("Prix unitaire")
    currency_id = fields.Many2one(related='treatment_id.currency_id')
    subtotal = fields.Monetary(
        "Sous-total", compute='_compute_subtotal', store=True,
        currency_field='currency_id')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.description = line.product_id.display_name
                line.price_unit = line.product_id.list_price

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    def _invoice_line_name(self):
        self.ensure_one()
        name = self.description or self.product_id.display_name
        teeth = self.tooth_ids.sorted('number')
        if teeth:
            prefixe = _("dent") if len(teeth) == 1 else _("dents")
            name = "%s — %s %s" % (
                name, prefixe, ", ".join(str(t.number) for t in teeth))
        return name
