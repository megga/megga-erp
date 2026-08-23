from datetime import timedelta

import pytz

from odoo import _, api, fields, models
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import ValidationError

from ..rdv_logic import day_slots, in_window, slot_free


class MeggaRdvType(models.Model):
    """Une prestation réservable en ligne : durée, plages hebdomadaires,
    intervenants. Les créneaux libres se calculent contre le calendrier
    du cœur (calendar.event) — l'agenda reste l'unique source de vérité
    de l'occupation."""
    _name = 'megga.rdv.type'
    _description = "Type de rendez-vous en ligne"
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    name = fields.Char("Prestation", required=True, translate=True)
    description = fields.Text(
        "Description publique",
        help="Affichée sur la page de réservation.")
    duration = fields.Float(
        "Durée (heures)", required=True, default=0.5)
    tz = fields.Selection(
        _tz_get, string="Fuseau horaire", required=True,
        default=lambda self: self.env.user.tz or 'Europe/Zurich',
        help="Les plages d'ouverture sont exprimées dans ce fuseau.")
    min_notice_hours = fields.Integer(
        "Préavis minimal (heures)", default=24,
        help="Un créneau plus proche que ce préavis n'est pas proposé.")
    horizon_days = fields.Integer(
        "Réservable jusqu'à (jours)", default=21)
    user_ids = fields.Many2many(
        'res.users', string="Intervenants",
        domain=[('share', '=', False)],
        help="Le rendez-vous est planifié chez l'un d'eux (le moins "
             "chargé du jour parmi les libres).")
    line_ids = fields.One2many(
        'megga.rdv.type.line', 'type_id',
        string="Plages hebdomadaires", copy=True)
    active = fields.Boolean(default=True)
    booking_count = fields.Integer(compute='_compute_booking_count')

    @api.constrains('duration')
    def _check_duration(self):
        for rdv_type in self:
            if rdv_type.duration <= 0:
                raise ValidationError(_("La durée doit être positive."))

    @api.constrains('min_notice_hours', 'horizon_days')
    def _check_window(self):
        for rdv_type in self:
            if rdv_type.min_notice_hours < 0:
                raise ValidationError(_("Le préavis ne peut être négatif."))
            if rdv_type.horizon_days < 1:
                raise ValidationError(
                    _("L'horizon doit être d'au moins un jour."))

    def _compute_booking_count(self):
        for rdv_type in self:
            rdv_type.booking_count = self.env['megga.rdv.booking'] \
                .search_count([('type_id', '=', rdv_type.id)])

    def _openings_for_weekday(self, weekday):
        self.ensure_one()
        return [(line.hour_from, line.hour_to)
                for line in self.line_ids
                if int(line.dayofweek) == weekday]

    def _busy_intervals(self, user, start_utc, stop_utc):
        """Occupations d'un intervenant sur la fenêtre, en UTC naïf.
        En sudo : l'agenda des intervenants n'est pas lisible du public,
        mais seuls des couples (début, fin) en sortent — jamais le
        contenu des événements."""
        events = self.env['calendar.event'].sudo().search([
            ('show_as', '=', 'busy'),
            ('stop', '>', start_utc),
            ('start', '<', stop_utc),
            '|', ('user_id', '=', user.id),
            ('partner_ids', 'in', user.partner_id.id),
        ])
        return [(event.start, event.stop) for event in events]

    def _available_slots(self, now=None):
        """Les créneaux réservables, triés : liste de dicts
        {'start': datetime UTC naïf, 'day': date locale,
         'label': 'HH:MM' local, 'user_ids': [intervenants libres]}.
        `now` est injectable pour des tests déterministes."""
        self.ensure_one()
        now = now or fields.Datetime.now()
        if not self.user_ids or not self.line_ids:
            return []
        tz = pytz.timezone(self.tz)
        horizon_end = now + timedelta(days=self.horizon_days + 1)
        busy_by_user = {
            user.id: self._busy_intervals(user, now, horizon_end)
            for user in self.user_ids
        }
        local_today = pytz.utc.localize(now).astimezone(tz).date()
        slots = []
        for offset in range(self.horizon_days + 1):
            day = local_today + timedelta(days=offset)
            openings = self._openings_for_weekday(day.weekday())
            for local_start in day_slots(day, openings, self.duration):
                start_utc = tz.localize(local_start).astimezone(pytz.utc) \
                    .replace(tzinfo=None)
                if not in_window(start_utc, now,
                                 self.min_notice_hours, self.horizon_days):
                    continue
                free = [user.id for user in self.user_ids
                        if slot_free(start_utc, self.duration,
                                     busy_by_user[user.id])]
                if free:
                    slots.append({
                        'start': start_utc,
                        'day': day,
                        'label': local_start.strftime('%H:%M'),
                        'user_ids': free,
                    })
        slots.sort(key=lambda slot: slot['start'])
        return slots


class MeggaRdvTypeLine(models.Model):
    _name = 'megga.rdv.type.line'
    _description = "Plage hebdomadaire de rendez-vous"
    _order = 'type_id, dayofweek, hour_from'

    type_id = fields.Many2one(
        'megga.rdv.type', required=True, ondelete='cascade', index=True)
    dayofweek = fields.Selection([
        ('0', "Lundi"), ('1', "Mardi"), ('2', "Mercredi"), ('3', "Jeudi"),
        ('4', "Vendredi"), ('5', "Samedi"), ('6', "Dimanche"),
    ], string="Jour", required=True, default='0')
    hour_from = fields.Float("De", required=True)
    hour_to = fields.Float("À", required=True)

    @api.constrains('hour_from', 'hour_to')
    def _check_hours(self):
        for line in self:
            if not (0 <= line.hour_from < line.hour_to <= 24):
                raise ValidationError(_(
                    "Plage invalide : « de » doit précéder « à », "
                    "entre 0 et 24 heures."))
