from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..resto_logic import intervals_overlap, slot_end


class MeggaRestoReservation(models.Model):
    """Réservation de tables sur le plan de salle du cœur
    (restaurant.floor / restaurant.table de pos_restaurant) : la brique
    Community fournit les tables, la surcouche apporte ce qui n'existe
    qu'en Enterprise — le carnet de réservations."""
    _name = 'megga.resto.reservation'
    _description = "Réservation de table"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start desc, id desc'

    name = fields.Char(
        "Référence", readonly=True, copy=False, default='/')
    guest_name = fields.Char("Nom du client", required=True)
    partner_id = fields.Many2one('res.partner', string="Contact")
    phone = fields.Char("Téléphone")
    start = fields.Datetime("Arrivée", required=True, tracking=True)
    duration = fields.Float(
        "Durée (heures)", required=True, default=2.0)
    stop = fields.Datetime(
        "Fin du créneau", compute='_compute_stop', store=True)
    party_size = fields.Integer("Couverts", required=True, default=2)
    table_ids = fields.Many2many(
        'restaurant.table', string="Tables",
        domain=[('active', '=', True)])
    seats_total = fields.Integer(
        "Places aux tables", compute='_compute_seats_total')
    state = fields.Selection([
        ('draft', "Demande"),
        ('confirmed', "Confirmée"),
        ('seated', "Installés"),
        ('done', "Terminée"),
        ('no_show', "Non venus"),
        ('cancelled', "Annulée"),
    ], string="État", default='draft', required=True, copy=False,
        tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    # groups= : note de SERVICE. Le client y a donne des informations
    # (allergies, occasion), mais la salle y ecrit aussi ses propres
    # remarques — elle ne redescend donc pas au portail, et l'ORM le
    # garantit (meme patron que le dossier medical du dentaire), pas
    # seulement l'absence de la note dans un gabarit.
    notes = fields.Text(
        "Notes (allergies, occasion, chaise haute…)",
        groups="base.group_user")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'megga.resto.reservation') or '/'
        return super().create(vals_list)

    @api.depends('guest_name', 'party_size')
    def _compute_display_name(self):
        """Sur le calendrier de service, on veut lire « Famille Rochat (4) »,
        pas une référence RSV/… — la référence reste le champ name."""
        for reservation in self:
            if reservation.guest_name:
                reservation.display_name = "%s (%s)" % (
                    reservation.guest_name, reservation.party_size)
            else:
                reservation.display_name = reservation.name

    @api.depends('start', 'duration')
    def _compute_stop(self):
        for reservation in self:
            if reservation.start and reservation.duration > 0:
                reservation.stop = slot_end(
                    reservation.start, reservation.duration)
            else:
                reservation.stop = reservation.start

    @api.depends('table_ids.seats')
    def _compute_seats_total(self):
        for reservation in self:
            reservation.seats_total = sum(
                reservation.table_ids.mapped('seats'))

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for reservation in self:
            if reservation.partner_id:
                reservation.guest_name = reservation.partner_id.name
                reservation.phone = (reservation.partner_id.phone
                                     or reservation.phone)

    @api.constrains('party_size')
    def _check_party_size(self):
        for reservation in self:
            if reservation.party_size <= 0:
                raise ValidationError(
                    _("Le nombre de couverts doit être positif."))

    @api.constrains('duration')
    def _check_duration(self):
        for reservation in self:
            if reservation.duration <= 0:
                raise ValidationError(
                    _("La durée du créneau doit être positive."))

    @api.constrains('table_ids', 'party_size')
    def _check_capacity(self):
        for reservation in self:
            if (reservation.table_ids
                    and reservation.seats_total < reservation.party_size):
                raise ValidationError(_(
                    "%(nom)s : %(couverts)s couverts pour %(places)s places "
                    "aux tables choisies. Ajoutez une table ou réduisez le "
                    "nombre de couverts.",
                    nom=reservation.name, couverts=reservation.party_size,
                    places=reservation.seats_total))

    @api.constrains('table_ids', 'start', 'duration', 'state')
    def _check_table_overlap(self):
        """Aucune table ne peut porter deux réservations actives
        (confirmée ou installés) qui se chevauchent. Chevauchement
        strict : enchaîner 18h-20h puis 20h-22h est permis."""
        actifs = ('confirmed', 'seated')
        for reservation in self:
            if reservation.state not in actifs or not reservation.table_ids:
                continue
            end = slot_end(reservation.start, reservation.duration)
            others = self.search([
                ('id', '!=', reservation.id),
                ('state', 'in', actifs),
                ('table_ids', 'in', reservation.table_ids.ids),
            ])
            for other in others:
                if intervals_overlap(
                        reservation.start, end,
                        other.start, slot_end(other.start, other.duration)):
                    tables = ", ".join(
                        (reservation.table_ids & other.table_ids)
                        .mapped('display_name'))
                    raise ValidationError(_(
                        "Conflit de tables entre %(a)s et %(b)s sur : "
                        "%(tables)s.",
                        a=reservation.name, b=other.name, tables=tables))

    def action_confirm(self):
        for reservation in self:
            if reservation.state != 'draft':
                raise UserError(
                    _("Seule une demande peut être confirmée."))
            reservation.state = 'confirmed'

    def action_seat(self):
        for reservation in self:
            if reservation.state != 'confirmed':
                raise UserError(
                    _("Seule une réservation confirmée peut être installée."))
            reservation.state = 'seated'

    def action_done(self):
        for reservation in self:
            if reservation.state != 'seated':
                raise UserError(
                    _("Seule une table installée peut être clôturée."))
            reservation.state = 'done'

    def action_no_show(self):
        for reservation in self:
            if reservation.state != 'confirmed':
                raise UserError(
                    _("Seule une réservation confirmée peut être marquée "
                      "« non venus »."))
            reservation.state = 'no_show'

    def action_cancel(self):
        for reservation in self:
            if reservation.state not in ('draft', 'confirmed'):
                raise UserError(
                    _("Une réservation %s ne peut plus être annulée.")
                    % dict(reservation._fields['state'].selection)[
                        reservation.state])
            reservation.state = 'cancelled'

    @api.model
    def _cron_resto_no_show(self, grace_hours=2):
        """Chaque jour : les réservations restées « confirmée » bien après
        l'heure d'arrivée (délai de grâce) passent en « non venus ».
        Idempotent par construction — l'état change au premier passage."""
        limite = fields.Datetime.now() - timedelta(hours=grace_hours)
        retardataires = self.search([
            ('state', '=', 'confirmed'),
            ('start', '<', limite),
        ])
        for reservation in retardataires:
            reservation.state = 'no_show'
            reservation.message_post(body=_(
                "Marquée « non venus » automatiquement : arrivée prévue à "
                "%(heure)s, aucun passage en salle après %(grace)s h de "
                "délai.", heure=reservation.start, grace=grace_hours))
        return True
