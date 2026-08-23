from odoo import _, api, fields, models

from ..auto_logic import next_inspection_date, vin_well_formed


class FleetVehicle(models.Model):
    """Le parc n'est plus celui de l'entreprise mais celui des CLIENTS du
    garage : on étend fleet.vehicle du cœur (marques, modèles, plaques,
    journal de compteur — tout est déjà là) avec le propriétaire, le
    suivi d'expertise OETV et la plausibilité du VIN."""
    _inherit = 'fleet.vehicle'

    megga_owner_id = fields.Many2one(
        'res.partner', string="Propriétaire (client)", index=True,
        tracking=True)
    megga_first_circulation = fields.Date("Première mise en circulation")
    megga_last_inspection = fields.Date("Dernière expertise")
    megga_inspections_done = fields.Integer(
        "Expertises passées", default=0)
    megga_next_inspection = fields.Date(
        "Prochaine expertise", compute='_compute_megga_next_inspection',
        store=True,
        help="Rythme fédéral (art. 33 OETV) : 4 ans après la première mise "
             "en circulation, puis 3 ans, puis tous les 2 ans. Les "
             "convocations cantonales peuvent varier — ceci sert de rappel.")
    megga_inspection_notified = fields.Date(
        "Expertise déjà notifiée", readonly=True, copy=False,
        help="Échéance pour laquelle une activité a déjà été créée ; "
             "garantit qu'une même échéance n'est notifiée qu'une fois.")
    megga_vin_ok = fields.Boolean(
        "VIN plausible", compute='_compute_megga_vin_ok',
        help="17 caractères, alphabet ISO 3779 (sans I, O, Q). Indicatif : "
             "la clé de contrôle n'est obligatoire qu'en Amérique du Nord.")
    megga_workorder_ids = fields.One2many(
        'megga.auto.workorder', 'vehicle_id', string="Ordres de réparation")
    megga_workorder_count = fields.Integer(
        compute='_compute_megga_workorder_count')

    @api.depends('megga_first_circulation', 'megga_last_inspection',
                 'megga_inspections_done')
    def _compute_megga_next_inspection(self):
        for vehicle in self:
            if vehicle.megga_first_circulation:
                vehicle.megga_next_inspection = next_inspection_date(
                    vehicle.megga_first_circulation,
                    vehicle.megga_last_inspection,
                    vehicle.megga_inspections_done)
            else:
                vehicle.megga_next_inspection = False

    @api.depends('vin_sn')
    def _compute_megga_vin_ok(self):
        for vehicle in self:
            vehicle.megga_vin_ok = vin_well_formed(vehicle.vin_sn or '')

    @api.depends('megga_workorder_ids')
    def _compute_megga_workorder_count(self):
        for vehicle in self:
            vehicle.megga_workorder_count = len(vehicle.megga_workorder_ids)

    def action_megga_register_inspection(self):
        """Expertise passée aujourd'hui : le rythme 4-3-2 repart d'ici."""
        today = fields.Date.context_today(self)
        for vehicle in self:
            vehicle.write({
                'megga_last_inspection': today,
                'megga_inspections_done': vehicle.megga_inspections_done + 1,
            })

    def action_megga_view_workorders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Ordres de réparation"),
            'res_model': 'megga.auto.workorder',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }

    @api.model
    def _cron_megga_inspections(self, horizon_days=30):
        """Chaque jour : une activité au gestionnaire pour tout véhicule
        dont l'expertise tombe dans l'horizon. Idempotent : une même
        échéance (megga_inspection_notified) n'est notifiée qu'une fois ;
        passer l'expertise déplace l'échéance et réarme le rappel."""
        today = fields.Date.today()
        limite = fields.Date.add(today, days=horizon_days)
        vehicles = self.search([
            ('megga_next_inspection', '!=', False),
            ('megga_next_inspection', '<=', limite),
        ])
        for vehicle in vehicles:
            if vehicle.megga_inspection_notified == vehicle.megga_next_inspection:
                continue
            vehicle.activity_schedule(
                'megga_auto.mail_activity_auto_inspection',
                date_deadline=vehicle.megga_next_inspection,
                summary=_("Expertise à préparer : %s") % vehicle.display_name,
                note=_("Contrôle périodique (rythme OETV 4-3-2). Proposer "
                       "au client la préparation à l'expertise."),
                user_id=vehicle.manager_id.id or self.env.uid,
            )
            vehicle.megga_inspection_notified = vehicle.megga_next_inspection
        return True
