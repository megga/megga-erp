from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class MeggaAutoWorkorder(models.Model):
    """L'ordre de réparation atelier : devis -> accepté -> terminé, puis
    facture en un clic (le même moule éprouvé que le traitement dentaire).
    À la clôture, le kilométrage relevé alimente le journal de compteur du
    cœur (fleet.vehicle.odometer) — l'historique du véhicule est unique.

    NOTE : le module `repair` du cœur répare un PRODUIT tenu en stock
    (product_id + lot) — inadapté au véhicule d'un client. D'où ce modèle
    métier propre, adossé à fleet."""
    _name = 'megga.auto.workorder'
    _description = "Ordre de réparation"
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(
        "Référence", readonly=True, copy=False, default='/')
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string="Véhicule", required=True,
        ondelete='restrict', index=True)
    partner_id = fields.Many2one(
        'res.partner', string="Client facturé", required=True)
    mechanic_id = fields.Many2one(
        'res.users', string="Mécanicien",
        default=lambda self: self.env.user)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    date = fields.Date(
        "Date", required=True, default=fields.Date.context_today)
    odometer_in = fields.Float(
        "Compteur à la réception (km)",
        help="Relevé à l'entrée en atelier ; reporté dans le journal de "
             "compteur du véhicule à la clôture de l'ordre.")
    state = fields.Selection([
        ('draft', "Devis"),
        ('confirmed', "Accepté"),
        ('done', "Terminé"),
        ('cancelled', "Annulé"),
    ], string="État", default='draft', required=True, copy=False,
        tracking=True)
    line_ids = fields.One2many(
        'megga.auto.workorder.line', 'workorder_id',
        string="Travaux et pièces", copy=True)
    amount_total = fields.Monetary(
        "Total", compute='_compute_amount_total', store=True,
        currency_field='currency_id')
    invoice_id = fields.Many2one(
        'account.move', string="Facture", readonly=True, copy=False)
    diagnosis = fields.Text("Diagnostic / travaux effectués")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'megga.auto.workorder') or '/'
        return super().create(vals_list)

    @api.depends('line_ids.subtotal')
    def _compute_amount_total(self):
        for order in self:
            order.amount_total = sum(order.line_ids.mapped('subtotal'))

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        for order in self:
            if order.vehicle_id:
                if order.vehicle_id.megga_owner_id:
                    order.partner_id = order.vehicle_id.megga_owner_id
                if not order.odometer_in:
                    order.odometer_in = order.vehicle_id.odometer

    def action_confirm(self):
        for order in self:
            if order.state != 'draft':
                raise UserError(_("Seul un devis peut être accepté."))
            if not order.line_ids:
                raise UserError(
                    _("Ajoutez au moins une ligne avant d'accepter."))
            order.state = 'confirmed'

    def action_done(self):
        """Clôt l'ordre et reporte le relevé de compteur dans le journal
        du cœur — le kilométrage du véhicule reste une seule histoire."""
        for order in self:
            if order.state != 'confirmed':
                raise UserError(
                    _("Seul un ordre accepté peut être terminé."))
            order.state = 'done'
            if order.odometer_in > 0:
                self.env['fleet.vehicle.odometer'].create({
                    'vehicle_id': order.vehicle_id.id,
                    'value': order.odometer_in,
                    'date': order.date,
                })

    def action_cancel(self):
        for order in self:
            if order.invoice_id and order.invoice_id.state != 'cancel':
                raise UserError(
                    _("Annulez d'abord la facture %s.")
                    % order.invoice_id.display_name)
            order.state = 'cancelled'

    def action_create_invoice(self):
        self.ensure_one()
        if self.state != 'done':
            raise UserError(_("Seul un ordre terminé peut être facturé."))
        if self.invoice_id:
            raise UserError(
                _("Cet ordre est déjà facturé (%s).")
                % self.invoice_id.display_name)
        origin = self.name
        if self.vehicle_id.license_plate:
            origin = "%s — %s" % (self.name, self.vehicle_id.license_plate)
        move = self.env['account.move'].with_company(self.company_id).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_origin': origin,
            'invoice_line_ids': [Command.create({
                'product_id': line.product_id.id,
                'name': line.description or line.product_id.display_name,
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


class MeggaAutoWorkorderLine(models.Model):
    _name = 'megga.auto.workorder.line'
    _description = "Ligne d'ordre de réparation"
    _order = 'workorder_id, sequence, id'

    workorder_id = fields.Many2one(
        'megga.auto.workorder', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product', string="Pièce / forfait", required=True)
    # Compute store readonly=False : la designation est TOUJOURS posee
    # cote serveur, jamais laissee vide. Le portail client peut alors
    # afficher les travaux sans lire le catalogue du garage — un libelle
    # ne vaut pas d'ouvrir product.product au groupe portail.
    description = fields.Char(
        "Description", compute='_compute_description', store=True,
        readonly=False, precompute=True)
    quantity = fields.Float("Quantité", required=True, default=1.0)
    price_unit = fields.Float("Prix unitaire")
    currency_id = fields.Many2one(related='workorder_id.currency_id')
    subtotal = fields.Monetary(
        "Sous-total", compute='_compute_subtotal', store=True,
        currency_field='currency_id')

    @api.depends('product_id')
    def _compute_description(self):
        for line in self:
            if line.product_id and not line.description:
                line.description = line.product_id.display_name

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.price_unit = line.product_id.list_price

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit
