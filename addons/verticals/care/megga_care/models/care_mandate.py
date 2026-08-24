from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..care_logic import fee_total


class MeggaCareMandate(models.Model):
    """Le mandat est l'objet central du métier : il lie le calendrier, les
    contacts et les factures en un seul flux. Offre -> en cours (les
    événements s'accumulent, la facturation client peut être progressive)
    -> clôturé. La clôture est le garde-fou « rien d'oublié » : elle
    refuse tant qu'un événement à prix n'est pas facturé au client ou
    qu'un coût n'est pas couvert par une pièce fournisseur. La facture
    émise est une account.move ordinaire : la QR-facture (megga_qr_export,
    débiteur à l'étranger compris) et l'encaissement camt (megga_camt) du
    socle prennent le relais."""
    _name = 'megga.care.mandate'
    _description = "Mandat de conciergerie médicale"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(
        "Référence", readonly=True, copy=False, default='/')
    patient_id = fields.Many2one(
        'megga.care.patient', string="Client", required=True,
        ondelete='restrict', index=True)
    partner_id = fields.Many2one(
        related='patient_id.partner_id', store=True)
    user_id = fields.Many2one(
        'res.users', string="Responsable",
        default=lambda self: self.env.user)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    kind = fields.Selection([
        ('ambulatoire', "Ambulatoire (check-up)"),
        ('hospitalise', "Hospitalisé"),
    ], string="Type de mandat", default='ambulatoire', required=True,
        tracking=True)
    date_start = fields.Date(
        "Début", required=True, default=fields.Date.context_today)
    date_end = fields.Date("Fin")
    state = fields.Selection([
        ('draft', "Offre"),
        ('confirmed', "En cours"),
        ('done', "Clôturé"),
        ('cancelled', "Annulé"),
    ], string="État", default='draft', required=True, copy=False,
        tracking=True)
    event_ids = fields.One2many(
        'megga.care.event', 'mandate_id', string="Événements", copy=True)

    # Honoraires de coordination : au forfait (check-up) ou au taux
    # horaire (longs séjours). Ils s'ajoutent aux prestations refacturées
    # et partent sur la première facture client qui suit.
    fee_mode = fields.Selection([
        ('forfait', "Forfait"),
        ('horaire', "Taux horaire"),
    ], string="Honoraires", default='forfait', required=True)
    fee_flat = fields.Monetary(
        "Forfait", currency_field='currency_id')
    fee_hourly_rate = fields.Monetary(
        "Taux horaire", currency_field='currency_id')
    fee_hours = fields.Float("Heures")
    fee_total = fields.Monetary(
        "Total honoraires", compute='_compute_fee_total', store=True,
        currency_field='currency_id')
    fee_invoice_line_id = fields.Many2one(
        'account.move.line', string="Ligne d'honoraires facturée",
        readonly=True, copy=False)

    amount_client = fields.Monetary(
        "Total client", compute='_compute_amounts', store=True,
        currency_field='currency_id',
        help="Prestations facturées au client + honoraires.")
    amount_cost = fields.Monetary(
        "Total coûts", compute='_compute_amounts', store=True,
        currency_field='currency_id')
    amount_margin = fields.Monetary(
        "Marge", compute='_compute_amounts', store=True,
        currency_field='currency_id')

    # Stockés : le tableau de bord filtre dessus (« À facturer »,
    # « Pièces attendues ») — un compute volatil ne se cherche pas.
    unbilled_event_count = fields.Integer(
        "Événements à facturer", compute='_compute_watchdog_counts',
        store=True)
    uncovered_cost_count = fields.Integer(
        "Coûts sans pièce", compute='_compute_watchdog_counts',
        store=True)

    invoice_ids = fields.Many2many(
        'account.move', 'megga_care_mandate_invoice_rel',
        string="Factures client", readonly=True, copy=False)
    invoice_count = fields.Integer(compute='_compute_invoice_count')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'megga.care.mandate') or '/'
        return super().create(vals_list)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for mandate in self:
            if mandate.date_end and mandate.date_end < mandate.date_start:
                raise ValidationError(
                    _("La fin du mandat précède son début."))

    @api.depends('fee_mode', 'fee_flat', 'fee_hourly_rate', 'fee_hours')
    def _compute_fee_total(self):
        for mandate in self:
            mandate.fee_total = fee_total(
                mandate.fee_mode, mandate.fee_flat,
                mandate.fee_hourly_rate, mandate.fee_hours)

    @api.depends('event_ids.price_client', 'event_ids.cost_price',
                 'fee_total')
    def _compute_amounts(self):
        for mandate in self:
            prices = sum(mandate.event_ids.mapped('price_client'))
            costs = sum(mandate.event_ids.mapped('cost_price'))
            mandate.amount_client = prices + mandate.fee_total
            mandate.amount_cost = costs
            mandate.amount_margin = mandate.amount_client - costs

    @api.depends('event_ids.billing_state', 'event_ids.cost_state')
    def _compute_watchdog_counts(self):
        for mandate in self:
            events = mandate.event_ids
            mandate.unbilled_event_count = len(events.filtered(
                lambda e: e.billing_state == 'to_invoice'))
            mandate.uncovered_cost_count = len(events.filtered(
                lambda e: e.cost_state == 'awaiting'))

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for mandate in self:
            mandate.invoice_count = len(mandate.invoice_ids)

    def _fee_to_invoice(self):
        """Les honoraires restent à facturer tant qu'aucune ligne vivante
        ne les porte (une ligne sur facture annulée ne compte pas)."""
        self.ensure_one()
        line = self.fee_invoice_line_id
        return bool(self.fee_total) and (
            not line or line.parent_state == 'cancel')

    def action_confirm(self):
        for mandate in self:
            if mandate.state != 'draft':
                raise UserError(_("Seule une offre peut être lancée."))
            mandate.state = 'confirmed'

    def action_close(self):
        """LE garde-fou : rien ne se clôture tant que tout n'est pas
        facturé au client et couvert par les pièces fournisseurs."""
        for mandate in self:
            if mandate.state != 'confirmed':
                raise UserError(
                    _("Seul un mandat en cours peut être clôturé."))
            if mandate.unbilled_event_count:
                raise UserError(_(
                    "%(mandat)s : %(nombre)s événement(s) restent à "
                    "facturer au client. Créez la facture (ou mettez le "
                    "prix client à zéro) avant de clôturer.",
                    mandat=mandate.name,
                    nombre=mandate.unbilled_event_count))
            if mandate.uncovered_cost_count:
                raise UserError(_(
                    "%(mandat)s : %(nombre)s coût(s) sans facture "
                    "fournisseur rattachée. Liez chaque pièce à son "
                    "événement avant de clôturer.",
                    mandat=mandate.name,
                    nombre=mandate.uncovered_cost_count))
            if mandate._fee_to_invoice():
                raise UserError(_(
                    "%(mandat)s : les honoraires de coordination ne sont "
                    "pas encore facturés.", mandat=mandate.name))
            mandate.write({
                'state': 'done',
                'date_end': mandate.date_end
                or fields.Date.context_today(mandate),
            })

    def action_cancel(self):
        for mandate in self:
            vivantes = mandate.invoice_ids.filtered(
                lambda move: move.state != 'cancel')
            if vivantes:
                raise UserError(
                    _("Annulez d'abord les factures %s.")
                    % ", ".join(vivantes.mapped('display_name')))
            mandate.state = 'cancelled'

    def action_create_invoice(self):
        """Facture au client tout ce qui reste à facturer : les événements
        sans ligne client vivante, plus les honoraires s'ils ne sont pas
        encore partis. Appelable plusieurs fois — les longs mandats se
        facturent au fil de l'eau, c'est précisément ce qui évite les
        oublis."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(
                _("Seul un mandat en cours peut être facturé."))
        events = self.event_ids.filtered(
            lambda e: e.billing_state == 'to_invoice').sorted('date')
        fee_needed = self._fee_to_invoice()
        if not events and not fee_needed:
            raise UserError(
                _("Rien à facturer : tout est déjà parti au client."))
        line_commands = [Command.create({
            'name': event._invoice_line_name(),
            'quantity': 1.0,
            'price_unit': event.price_client,
            'sequence': index * 10,
        }) for index, event in enumerate(events)]
        if fee_needed:
            line_commands.append(Command.create({
                'name': self._fee_line_name(),
                'quantity': 1.0,
                'price_unit': self.fee_total,
                'sequence': len(events) * 10,
            }))
        move = self.env['account.move'].with_company(self.company_id).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_origin': self.name,
            'invoice_line_ids': line_commands,
        })
        # Les lignes ressortent dans l'ordre des commandes : les
        # événements d'abord, les honoraires en dernier.
        lines = move.invoice_line_ids.sorted('sequence')
        for event, line in zip(events, lines):
            event.client_invoice_line_id = line
        if fee_needed:
            self.fee_invoice_line_id = lines[-1]
        self.invoice_ids = [Command.link(move.id)]
        self.message_post(body=_("Facture %s créée.") % move.display_name)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
        }

    def _fee_line_name(self):
        self.ensure_one()
        if self.fee_mode == 'horaire':
            return _("Honoraires de coordination — %(heures)s h × %(taux).2f",
                     heures=self.fee_hours, taux=self.fee_hourly_rate)
        return _("Honoraires de coordination — forfait")

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Factures client"),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
        }

    @api.model
    def _cron_care_unbilled(self, horizon_days=7):
        """Chaque jour : crée une activité « Facturation à compléter » sur
        tout mandat en cours dont un événement passé depuis l'horizon
        reste à facturer. Une seule activité ouverte à la fois par mandat :
        le rappel revient si elle est close alors que l'oubli demeure —
        c'est le comportement voulu, il insiste jusqu'à la facture."""
        limite = fields.Datetime.subtract(
            fields.Datetime.now(), days=horizon_days)
        type_activite = self.env.ref('megga_care.activity_care_unbilled')
        mandates = self.search([('state', '=', 'confirmed')])
        for mandate in mandates:
            en_retard = mandate.event_ids.filtered(
                lambda e: e.billing_state == 'to_invoice'
                and e.date and e.date <= limite)
            if not en_retard:
                continue
            deja = mandate.activity_ids.filtered(
                lambda a: a.activity_type_id == type_activite)
            if deja:
                continue
            mandate.activity_schedule(
                'megga_care.activity_care_unbilled',
                summary=_("Facturation à compléter : %s") % mandate.name,
                note=_("%(nombre)s événement(s) passé(s) depuis plus de "
                       "%(jours)s jours ne sont pas facturés au client.",
                       nombre=len(en_retard), jours=horizon_days),
                user_id=mandate.user_id.id or self.env.uid,
            )
        return True
