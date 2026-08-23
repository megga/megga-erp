import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MeggaRdvType(models.Model):
    _inherit = 'megga.rdv.type'

    auto_vehicle_link = fields.Boolean(
        "Rattacher le véhicule du client", default=True,
        help="À la réservation, rattache d'office le véhicule du contact "
             "s'il n'en possède qu'un au parc. À décocher pour les "
             "rendez-vous qui ne concernent pas un véhicule.")


class MeggaRdvBooking(models.Model):
    _inherit = 'megga.rdv.booking'

    vehicle_id = fields.Many2one(
        'fleet.vehicle', string="Véhicule", copy=False, index=True)
    workorder_id = fields.Many2one(
        'megga.auto.workorder', string="Ordre de réparation",
        readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        bookings = super().create(vals_list)
        bookings._auto_link_vehicle()
        return bookings

    def _auto_link_vehicle(self):
        """Rattache d'office le véhicule quand il n'y a pas d'ambiguïté :
        le contact (garanti par e-mail) possède exactement UN véhicule au
        parc. Plusieurs ou aucun : le comptoir tranche à la réception.

        En sudo : le rattachement est un effet système de la réservation
        (elle peut être saisie par un utilisateur sans droit sur les
        contacts ni sur le parc) — comme le pont dentaire."""
        Vehicle = self.env['fleet.vehicle'].sudo()
        for booking in self:
            booking_sudo = booking.sudo()
            if booking_sudo.vehicle_id \
                    or not booking.type_id.auto_vehicle_link:
                continue
            booking_sudo._ensure_partner()
            vehicles = Vehicle.search(
                [('megga_owner_id', '=', booking_sudo.partner_id.id)])
            if len(vehicles) == 1:
                booking_sudo.vehicle_id = vehicles

    def action_create_workorder(self):
        """Ouvre l'atelier depuis la réservation : ordre de réparation en
        brouillon, pré-rempli — date LOCALE du rendez-vous (fuseau du
        type), mécanicien = intervenant réservé, compteur = dernier
        relevé du véhicule."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_(
                "Seule une réservation confirmée ouvre un ordre de "
                "réparation."))
        if self.workorder_id:
            raise UserError(_(
                "Cette réservation a déjà son ordre : %s.")
                % self.workorder_id.display_name)
        if not self.vehicle_id:
            raise UserError(_(
                "Renseignez d'abord le véhicule concerné."))
        if not self.partner_id:
            self._ensure_partner()
        tz = pytz.timezone(self.type_id.tz)
        local_date = pytz.utc.localize(self.start).astimezone(tz).date()
        order = self.env['megga.auto.workorder'].create({
            'vehicle_id': self.vehicle_id.id,
            'partner_id': self.partner_id.id,
            'date': local_date,
            'mechanic_id': (self.user_id or self.env.user).id,
            'odometer_in': self.vehicle_id.odometer,
            'diagnosis': _(
                "Réservation en ligne %(ref)s — %(prestation)s",
                ref=self.name, prestation=self.type_id.name),
        })
        self.workorder_id = order
        order.message_post(
            body=_("Créé depuis la réservation %s.") % self.name)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'megga.auto.workorder',
            'view_mode': 'form',
            'res_id': order.id,
        }


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    rdv_booking_ids = fields.One2many(
        'megga.rdv.booking', 'vehicle_id',
        string="Réservations en ligne")
    rdv_booking_count = fields.Integer(
        compute='_compute_rdv_booking_count')

    @api.depends('rdv_booking_ids')
    def _compute_rdv_booking_count(self):
        for vehicle in self:
            vehicle.rdv_booking_count = len(vehicle.rdv_booking_ids)

    def action_view_rdv_bookings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Réservations en ligne"),
            'res_model': 'megga.rdv.booking',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
        }
