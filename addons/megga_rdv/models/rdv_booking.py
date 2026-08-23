import uuid
from datetime import timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..rdv_logic import format_jour_fr


class MeggaRdvBooking(models.Model):
    """Une réservation prise en ligne. Elle matérialise le rendez-vous en
    calendar.event chez l'intervenant : l'agenda du cœur reste l'unique
    vérité, et bloque naturellement le créneau pour les suivants."""
    _name = 'megga.rdv.booking'
    _description = "Réservation en ligne"
    _inherit = ['mail.thread']
    _order = 'start desc, id desc'

    name = fields.Char(
        "Référence", readonly=True, copy=False, default='/')
    type_id = fields.Many2one(
        'megga.rdv.type', string="Prestation", required=True,
        ondelete='restrict', index=True)
    guest_name = fields.Char("Nom", required=True)
    email = fields.Char("E-mail", required=True)
    phone = fields.Char("Téléphone")
    partner_id = fields.Many2one('res.partner', string="Contact")
    start = fields.Datetime("Début", required=True)
    stop = fields.Datetime(
        "Fin", compute='_compute_stop', store=True)
    user_id = fields.Many2one('res.users', string="Intervenant")
    event_id = fields.Many2one(
        'calendar.event', string="Événement d'agenda",
        readonly=True, copy=False, ondelete='set null')
    state = fields.Selection([
        ('confirmed', "Confirmée"),
        ('cancelled', "Annulée"),
    ], string="État", default='confirmed', required=True, copy=False,
        tracking=True)
    access_token = fields.Char(
        "Jeton d'annulation", readonly=True, copy=False, index=True,
        default=lambda self: uuid.uuid4().hex)
    reminder_sent = fields.Datetime(
        "Rappel envoyé le", readonly=True, copy=False,
        help="Horodatage du rappel de la veille ; garantit qu'une même "
             "réservation n'est rappelée qu'une fois.")
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'megga.rdv.booking') or '/'
        return super().create(vals_list)

    @api.depends('start', 'type_id.duration')
    def _compute_stop(self):
        for booking in self:
            if booking.start and booking.type_id.duration > 0:
                booking.stop = booking.start + timedelta(
                    hours=booking.type_id.duration)
            else:
                booking.stop = booking.start

    def _ensure_partner(self):
        """Garantit un contact sur la réservation : rattache par e-mail
        (insensible à la casse) ou le crée depuis les champs saisis.
        Utilisé par les modules-ponts (dentaire, garage) pour les
        réservations saisies au comptoir sans contact."""
        Partner = self.env['res.partner']
        for booking in self:
            if booking.partner_id:
                continue
            partner = Partner.search(
                [('email', '=ilike', booking.email)], limit=1)
            if not partner:
                partner = Partner.create({
                    'name': booking.guest_name,
                    'email': booking.email,
                    'phone': booking.phone or False,
                })
            booking.partner_id = partner
        return True

    def _local_label(self):
        """« jeudi 3 septembre 2026 à 09:00 », dans le fuseau du type."""
        self.ensure_one()
        tz = pytz.timezone(self.type_id.tz)
        local = pytz.utc.localize(self.start).astimezone(tz)
        return _("%(jour)s à %(heure)s",
                 jour=format_jour_fr(local.date()),
                 heure=local.strftime('%H:%M'))

    @api.model
    def _calendar_event_vals(self, rdv_type, start_utc, user, partner,
                             guest_name):
        """Valeurs de l'événement d'agenda matérialisant la réservation.
        Point d'extension pour les modules-ponts (le pont restaurant le
        rend non bloquant : plusieurs tablées partagent un créneau)."""
        return {
            'name': "%s — %s" % (rdv_type.name, guest_name),
            'start': start_utc,
            'stop': start_utc + timedelta(hours=rdv_type.duration),
            'user_id': user.id,
            'partner_ids': [(4, user.partner_id.id), (4, partner.id)],
        }

    @api.model
    def _reserver(self, rdv_type, start_utc, guest_name, email,
                  phone=False, now=None, extra_vals=None):
        """Réserve un créneau APRÈS re-vérification serveur (le créneau
        affiché a pu être pris entre-temps). Choisit l'intervenant le
        moins chargé du jour parmi les libres, rattache ou crée le
        contact par e-mail, matérialise l'événement d'agenda et envoie
        la confirmation. Lève UserError si le créneau n'est plus libre.
        `extra_vals` : champs supplémentaires posés sur la réservation
        par les modules-ponts (ex. les couverts du pont restaurant)."""
        slots = rdv_type._available_slots(now=now)
        slot = next((s for s in slots if s['start'] == start_utc), None)
        if slot is None:
            raise UserError(_(
                "Ce créneau vient d'être pris ou n'est plus disponible — "
                "choisissez-en un autre."))

        users = self.env['res.users'].browse(slot['user_ids'])
        tz = pytz.timezone(rdv_type.tz)
        local_day = pytz.utc.localize(start_utc).astimezone(tz).date()
        day_start = tz.localize(
            fields.Datetime.to_datetime(str(local_day))) \
            .astimezone(pytz.utc).replace(tzinfo=None)
        day_end = day_start + timedelta(days=1)
        charge = {
            user.id: self.search_count([
                ('user_id', '=', user.id),
                ('state', '=', 'confirmed'),
                ('start', '>=', day_start), ('start', '<', day_end),
            ]) for user in users
        }
        user = min(users, key=lambda u: (charge[u.id], u.id))

        Partner = self.env['res.partner']
        partner = Partner.search([('email', '=ilike', email)], limit=1)
        if not partner:
            partner = Partner.create({
                'name': guest_name, 'email': email, 'phone': phone or False})

        event = self.env['calendar.event'].create(
            self._calendar_event_vals(
                rdv_type, start_utc, user, partner, guest_name))
        vals = {
            'type_id': rdv_type.id,
            'guest_name': guest_name,
            'email': email,
            'phone': phone or False,
            'partner_id': partner.id,
            'start': start_utc,
            'user_id': user.id,
            'event_id': event.id,
        }
        vals.update(extra_vals or {})
        booking = self.create(vals)
        template = self.env.ref(
            'megga_rdv.mail_template_rdv_confirmation',
            raise_if_not_found=False)
        if template:
            template.send_mail(booking.id)
        return booking

    @api.model
    def _cron_rdv_reminders(self, lead_hours=24, now=None):
        """Chaque jour : un e-mail de rappel aux réservations confirmées
        qui démarrent dans la fenêtre (les prochaines `lead_hours`
        heures). Idempotent : le marqueur reminder_sent garantit un seul
        rappel par réservation, quel que soit le rythme du cron. `now`
        est injectable pour des tests déterministes."""
        now = now or fields.Datetime.now()
        template = self.env.ref(
            'megga_rdv.mail_template_rdv_rappel',
            raise_if_not_found=False)
        if not template:
            return True
        bookings = self.search([
            ('state', '=', 'confirmed'),
            ('reminder_sent', '=', False),
            ('start', '>', now),
            ('start', '<=', now + timedelta(hours=lead_hours)),
            ('type_id.send_reminder', '=', True),
        ])
        for booking in bookings:
            if booking.email:
                template.send_mail(booking.id)
            # Marqué même sans e-mail : inutile de rebalayer sans fin
            # une réservation qu'on ne peut de toute façon pas joindre.
            booking.reminder_sent = now
        return True

    def action_cancel(self):
        """Annulation (bouton interne ou lien public par jeton) :
        idempotente, et libère le créneau en supprimant l'événement."""
        for booking in self:
            if booking.state == 'cancelled':
                continue
            event = booking.event_id
            booking.state = 'cancelled'
            if event:
                event.unlink()
        return True
