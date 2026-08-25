from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..dental_logic import next_recall_date

# Valeur du point de la convention des assurances sociales (AA/AI/AM),
# en vigueur depuis le tarif de 2018. Le champ reste modifiable sur le
# traitement si la convention évolue.
SOCIAL_POINT_VALUE = 1.0


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
    plan_id = fields.Many2one(
        'megga.dental.plan', string="Plan de traitement",
        compute='_compute_plan_id',
        help="Renseigné quand ce traitement est la phase d'un plan.")
    tariff_kind = fields.Selection([
        ('prive', "Privé"),
        ('social', "Assurances sociales (AA/AI/AM)"),
    ], string="Tarif", default='prive', required=True)
    # La valeur du point est FIGÉE sur le traitement (elle ne dépend pas
    # de la valeur du cabinet au moment où on relit le devis) : seule le
    # changement de tarif la recalcule.
    point_value = fields.Float(
        "Valeur du point", digits=(12, 2), tracking=True,
        compute='_compute_point_value', store=True, readonly=False,
        precompute=True)
    # Contenu clinique : réservé aux soins (LPD). Les actes et montants
    # restent visibles de la réception — ils figurent sur la facture.
    notes = fields.Text(
        "Notes cliniques", groups="megga_dental.group_dental_praticien")

    @api.depends('tariff_kind')
    def _compute_point_value(self):
        for treatment in self:
            if treatment.tariff_kind == 'social':
                treatment.point_value = SOCIAL_POINT_VALUE
            else:
                treatment.point_value = (
                    treatment.company_id.dental_point_value
                    or self.env.company.dental_point_value or 1.0)

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
            treatment._create_tooth_records()
            treatment._refresh_plan()
            patient = treatment.patient_id
            patient.write({
                'last_visit_date': treatment.date,
                'recall_date': next_recall_date(
                    treatment.date, patient.recall_months or 6),
            })

    def _create_tooth_records(self):
        """Inscrit sur l'odontogramme le constat porté par chaque acte
        (position avec constat + dents renseignées). En sudo : c'est un
        effet système du flux — la réception peut clore une séance sans
        détenir le moindre droit sur les constats ; la LECTURE, elle,
        reste gardée par les groupes (doctrine LPD du dépôt)."""
        Record = self.env['megga.dental.tooth.record'].sudo()
        for treatment in self:
            for line in treatment.line_ids:
                condition = line.position_id.condition
                if not condition or not line.tooth_ids:
                    continue
                Record.create([{
                    'patient_id': treatment.patient_id.id,
                    'tooth_id': tooth.id,
                    'condition': condition,
                    'date': treatment.date,
                    'dentist_id': treatment.dentist_id.id,
                    'line_id': line.id,
                    'note': line.description or line.position_id.name,
                } for tooth in line.tooth_ids])

    def action_cancel(self):
        for treatment in self:
            if treatment.invoice_id and treatment.invoice_id.state != 'cancel':
                raise UserError(
                    _("Annulez d'abord la facture %s.")
                    % treatment.invoice_id.display_name)
            treatment.state = 'cancelled'
            treatment._refresh_plan()

    def _compute_plan_id(self):
        phases = self.env['megga.dental.plan.phase'].search(
            [('treatment_id', 'in', self.ids)])
        par_traitement = {
            phase.treatment_id.id: phase.plan_id.id for phase in phases}
        for treatment in self:
            treatment.plan_id = par_traitement.get(treatment.id, False)

    def _refresh_plan(self):
        """Si ce traitement est la phase d'un plan, le plan reevalue son
        etat (achevement automatique quand tout est solde)."""
        phases = self.env['megga.dental.plan.phase'].search(
            [('treatment_id', 'in', self.ids)])
        phases.plan_id._refresh_state()

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
    # Un acte renvoie soit à une POSITION du tarif par points (la voie
    # suisse : montant = points × valeur du point du traitement), soit à
    # un produit du catalogue (forfaits, fournitures) — au moins l'un
    # des deux.
    position_id = fields.Many2one(
        'megga.dental.position', string="Position", index=True,
        ondelete='restrict')
    product_id = fields.Many2one(
        'product.product', string="Produit")
    description = fields.Char("Description")
    tooth_ids = fields.Many2many(
        'megga.dental.tooth', string="Dents")
    quantity = fields.Float("Quantité", default=1.0, required=True)
    points = fields.Float(
        "PT", digits=(12, 2),
        compute='_compute_points', store=True, readonly=False,
        precompute=True)
    price_unit = fields.Float(
        "Prix unitaire",
        compute='_compute_price_unit', store=True, readonly=False,
        precompute=True)
    currency_id = fields.Many2one(related='treatment_id.currency_id')
    subtotal = fields.Monetary(
        "Sous-total", compute='_compute_subtotal', store=True,
        currency_field='currency_id')

    # treatment_id figure dans les champs surveillés : un constrains ne
    # se déclenche à la création QUE si l'un de ses champs est fourni —
    # sans lui, une ligne créée sans produit ni position passerait.
    @api.constrains('product_id', 'position_id', 'treatment_id')
    def _check_act_source(self):
        for line in self:
            if not line.product_id and not line.position_id:
                raise ValidationError(_(
                    "Chaque acte renvoie à une position tarifaire ou à "
                    "un produit du catalogue."))

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.description = line.product_id.display_name
                if not line.position_id:
                    line.price_unit = line.product_id.list_price

    @api.onchange('position_id')
    def _onchange_position_id(self):
        for line in self:
            if line.position_id:
                line.description = line.position_id.name

    @api.depends('position_id')
    def _compute_points(self):
        for line in self:
            if line.position_id:
                line.points = line.position_id.points
            else:
                line.points = line.points

    @api.depends('position_id', 'points', 'treatment_id.point_value')
    def _compute_price_unit(self):
        for line in self:
            if line.position_id:
                value = line.points * line.treatment_id.point_value
                line.price_unit = (
                    line.currency_id.round(value)
                    if line.currency_id else value)
            else:
                line.price_unit = line.price_unit

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    def _invoice_line_name(self):
        self.ensure_one()
        name = self.description or (
            self.position_id.name if self.position_id
            else self.product_id.display_name)
        if self.position_id:
            name = "[%s] %s" % (self.position_id.code, name)
        teeth = self.tooth_ids.sorted('number')
        if teeth:
            prefixe = _("dent") if len(teeth) == 1 else _("dents")
            name = "%s — %s %s" % (
                name, prefixe, ", ".join(str(t.number) for t in teeth))
        return name
