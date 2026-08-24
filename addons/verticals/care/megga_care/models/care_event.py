from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..care_logic import margin


class MeggaCareEvent(models.Model):
    """Un événement du mandat : une prestation chez un prestataire (labo,
    radiologie, spécialiste, pharmacie…) à une date donnée, portant DEUX
    prix — le prix facturé au client et le coût réel payé au prestataire.
    La marge (rétrocession comprise) se lit ici, événement par événement ;
    la facture fournisseur se rattache ici aussi, pas seulement au mandat.
    C'est la ligne d'analyse des statistiques : par mandat, par client,
    par type de prestation, par fournisseur (vues pivot et graphique)."""
    _name = 'megga.care.event'
    _description = "Événement de mandat"
    _order = 'date, id'

    mandate_id = fields.Many2one(
        'megga.care.mandate', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='mandate_id.company_id', store=True)
    currency_id = fields.Many2one(related='mandate_id.currency_id')
    # Stocké pour servir d'axe de regroupement (pivot « par client »).
    patient_id = fields.Many2one(
        related='mandate_id.patient_id', store=True)
    name = fields.Char("Description", required=True)
    service_type_id = fields.Many2one(
        'megga.care.service.type', string="Type de prestation",
        required=True, ondelete='restrict', index=True)
    retrocession = fields.Boolean(
        related='service_type_id.retrocession', store=True)
    provider_id = fields.Many2one(
        'res.partner', string="Prestataire", index=True)
    date = fields.Datetime(
        "Début", required=True, default=fields.Datetime.now)
    duration = fields.Float("Durée (h)", default=1.0)

    price_client = fields.Monetary(
        "Prix client", currency_field='currency_id')
    # Coût réel : proposé depuis la pièce fournisseur au rattachement
    # (montant HT), mais TOUJOURS ajustable — une même pièce peut couvrir
    # plusieurs événements.
    cost_price = fields.Monetary(
        "Coût réel", currency_field='currency_id',
        compute='_compute_cost_price', store=True, readonly=False,
        precompute=True)
    margin = fields.Monetary(
        "Marge", compute='_compute_margin', store=True,
        currency_field='currency_id',
        help="Prix client − coût réel : la rétrocession d'un laboratoire"
             " ou d'une pharmacie se lit ici.")

    supplier_invoice_id = fields.Many2one(
        'account.move', string="Facture fournisseur", copy=False,
        ondelete='set null', index='btree_not_null')
    client_invoice_line_id = fields.Many2one(
        'account.move.line', string="Ligne de facture client",
        readonly=True, copy=False, ondelete='set null',
        index='btree_not_null')
    client_invoice_id = fields.Many2one(
        related='client_invoice_line_id.move_id', string="Facture client",
        store=True)
    billing_state = fields.Selection([
        ('free', "Sans prix"),
        ('to_invoice', "À facturer"),
        ('invoiced', "Facturé"),
    ], string="Facturation client", compute='_compute_billing_state',
        store=True)
    cost_state = fields.Selection([
        ('none', "Sans coût"),
        ('awaiting', "Pièce attendue"),
        ('covered', "Pièce reçue"),
    ], string="Pièce fournisseur", compute='_compute_cost_state',
        store=True)

    calendar_event_id = fields.Many2one(
        'calendar.event', string="Rendez-vous d'agenda", readonly=True,
        copy=False, ondelete='set null')

    _amounts_positive = models.Constraint(
        'CHECK (price_client >= 0 AND cost_price >= 0)',
        "Prix client et coût réel ne peuvent pas être négatifs.")

    @api.constrains('supplier_invoice_id')
    def _check_supplier_invoice(self):
        for event in self:
            move = event.supplier_invoice_id
            if move and move.move_type not in ('in_invoice', 'in_refund'):
                raise ValidationError(_(
                    "%(piece)s n'est pas une facture fournisseur : seule "
                    "une pièce d'achat se rattache à un événement.",
                    piece=move.display_name))

    @api.depends('supplier_invoice_id')
    def _compute_cost_price(self):
        for event in self:
            if event.supplier_invoice_id and not event.cost_price:
                event.cost_price = event.supplier_invoice_id.amount_untaxed
            else:
                event.cost_price = event.cost_price

    @api.depends('price_client', 'cost_price')
    def _compute_margin(self):
        for event in self:
            event.margin = margin(event.price_client, event.cost_price)

    @api.depends('price_client', 'client_invoice_line_id',
                 'client_invoice_line_id.parent_state')
    def _compute_billing_state(self):
        for event in self:
            line = event.client_invoice_line_id
            if not event.price_client:
                event.billing_state = 'free'
            elif line and line.parent_state != 'cancel':
                event.billing_state = 'invoiced'
            else:
                event.billing_state = 'to_invoice'

    @api.depends('cost_price', 'supplier_invoice_id',
                 'supplier_invoice_id.state')
    def _compute_cost_state(self):
        for event in self:
            move = event.supplier_invoice_id
            if not event.cost_price:
                event.cost_state = 'none'
            elif move and move.state != 'cancel':
                event.cost_state = 'covered'
            else:
                event.cost_state = 'awaiting'

    def write(self, vals):
        result = super().write(vals)
        # Parité Office Maker : l'événement du mandat EST l'agenda. Tout
        # déplacement se propage au rendez-vous lié, jamais l'inverse.
        if {'date', 'duration', 'name'} & set(vals):
            for event in self.filtered('calendar_event_id'):
                event.calendar_event_id.write(event._calendar_values())
        return result

    def unlink(self):
        billed = self.filtered(lambda e: e.billing_state == 'invoiced')
        if billed:
            raise UserError(_(
                "%(evenements)s : un événement facturé au client ne se "
                "supprime pas — annulez d'abord la facture. Le garde-fou "
                "« rien d'oublié » n'a de sens que si l'historique "
                "facturé reste en place.",
                evenements=", ".join(billed.mapped('name'))))
        self.calendar_event_id.unlink()
        return super().unlink()

    def _calendar_values(self):
        self.ensure_one()
        return {
            'name': "%s — %s" % (self.patient_id.name, self.name),
            'start': self.date,
            'stop': self.date + timedelta(hours=self.duration or 1.0),
            'user_id': self.mandate_id.user_id.id,
        }

    def action_open_calendar_event(self):
        """Crée le rendez-vous d'agenda lié (s'il manque) et l'ouvre. Le
        détail médical reste dans le mandat : l'agenda ne porte que le
        client et l'intitulé de la prestation."""
        self.ensure_one()
        if not self.calendar_event_id:
            self.calendar_event_id = self.env['calendar.event'].create(
                self._calendar_values())
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'view_mode': 'form',
            'res_id': self.calendar_event_id.id,
        }

    def _invoice_line_name(self):
        self.ensure_one()
        name = "[%s] %s" % (self.service_type_id.code, self.name)
        jour = fields.Datetime.context_timestamp(self, self.date)
        name = "%s — %s" % (name, jour.strftime('%d.%m.%Y'))
        if self.provider_id:
            name = "%s — %s" % (name, self.provider_id.name)
        return name
