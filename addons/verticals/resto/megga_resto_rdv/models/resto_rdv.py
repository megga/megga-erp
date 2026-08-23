from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.megga_resto.resto_logic import intervals_overlap, slot_end

# Les états d'une réservation du carnet qui occupent réellement la table —
# la même paire que la contrainte anti-collision de megga_resto.
ETATS_ACTIFS = ('confirmed', 'seated')


class MeggaRdvType(models.Model):
    _inherit = 'megga.rdv.type'

    resto_reservation = fields.Boolean(
        "Réservation de table (restaurant)", default=False,
        help="Le formulaire public demande les couverts, le créneau "
             "n'occupe pas l'agenda (plusieurs tablées à la même heure) "
             "et chaque réservation prend la plus petite table suffisante "
             "du plan de salle — complet : refus propre.")


class MeggaRdvBooking(models.Model):
    _inherit = 'megga.rdv.booking'

    resto_party_size = fields.Integer("Couverts", copy=False)
    resto_reservation_id = fields.Many2one(
        'megga.resto.reservation', string="Entrée du carnet",
        readonly=True, copy=False)

    @api.model
    def _calendar_event_vals(self, rdv_type, start_utc, user, partner,
                             guest_name):
        vals = super()._calendar_event_vals(
            rdv_type, start_utc, user, partner, guest_name)
        if rdv_type.resto_reservation:
            # Non bloquant : la capacité, ce sont les tables — pas
            # l'agenda de l'intervenant.
            vals['show_as'] = 'free'
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        bookings = super().create(vals_list)
        bookings._resto_create_reservation()
        return bookings

    def _resto_find_table(self, start_utc, duration, party_size):
        """La plus petite table suffisante encore libre sur le créneau
        (égalité : plus petit identifiant). Une table est prise si une
        réservation active du carnet la chevauche — même règle stricte
        que la contrainte de megga_resto. Vide si complet."""
        end = slot_end(start_utc, duration)
        occupantes = self.env['megga.resto.reservation'].search([
            ('state', 'in', ETATS_ACTIFS),
            ('table_ids', '!=', False),
        ])
        prises = set()
        for reservation in occupantes:
            if intervals_overlap(
                    start_utc, end, reservation.start,
                    slot_end(reservation.start, reservation.duration)):
                prises.update(reservation.table_ids.ids)
        candidates = self.env['restaurant.table'].search([
            ('active', '=', True),
            ('seats', '>=', party_size),
            ('id', 'not in', list(prises) or [0]),
        ])
        if not candidates:
            return self.env['restaurant.table']
        return min(candidates, key=lambda t: (t.seats, t.id))

    def _resto_create_reservation(self):
        """Matérialise la réservation en ligne dans le carnet, table
        attribuée et entrée confirmée. Complet : UserError — dans le flux
        public, toute la réservation (événement compris) est annulée et
        le visiteur voit un refus propre.

        En sudo : la matérialisation est un effet système de la
        réservation (elle peut être saisie par un utilisateur sans droit
        sur les contacts ni sur le carnet) — comme les autres ponts."""
        Reservation = self.env['megga.resto.reservation'].sudo()
        for booking in self:
            rdv_type = booking.type_id
            booking_sudo = booking.sudo()
            if not rdv_type.resto_reservation \
                    or booking_sudo.resto_reservation_id:
                continue
            booking_sudo._ensure_partner()
            party = booking.resto_party_size or 2
            table = booking_sudo._resto_find_table(
                booking.start, rdv_type.duration, party)
            if not table:
                raise UserError(_(
                    "Plus de table libre pour %s couverts à cet horaire — "
                    "appelez-nous, on trouvera une solution.") % party)
            try:
                reservation = Reservation.create({
                    'guest_name': booking.guest_name,
                    'partner_id': booking_sudo.partner_id.id,
                    'phone': booking.phone or False,
                    'start': booking.start,
                    'duration': rdv_type.duration,
                    'party_size': party,
                    'table_ids': [(6, 0, table.ids)],
                    'notes': _("Réservation en ligne %s") % booking.name,
                    'rdv_booking_id': booking.id,
                })
                reservation.action_confirm()
            except ValidationError as exc:
                # Course entre deux visiteurs sur la même table : la
                # contrainte du carnet reste l'arbitre final.
                raise UserError(str(exc)) from exc
            booking_sudo.resto_reservation_id = reservation

    def action_cancel(self):
        res = super().action_cancel()
        for booking in self:
            reservation = booking.resto_reservation_id
            if reservation and reservation.state in ('draft', 'confirmed'):
                reservation.action_cancel()
        return res


class MeggaRestoReservation(models.Model):
    _inherit = 'megga.resto.reservation'

    rdv_booking_id = fields.Many2one(
        'megga.rdv.booking', string="Réservation en ligne",
        readonly=True, copy=False, index=True)

    def action_cancel(self):
        res = super().action_cancel()
        for reservation in self:
            booking = reservation.rdv_booking_id
            if booking and booking.state == 'confirmed':
                booking.action_cancel()
        return res
