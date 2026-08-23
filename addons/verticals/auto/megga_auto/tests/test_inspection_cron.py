from odoo import fields
from odoo.tests import TransactionCase

from ..auto_logic import add_months


class TestInspectionCron(TransactionCase):
    """Le cron de rappels d'expertise : une activité par échéance due,
    jamais deux pour la même, et l'horizon est respecté."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': "Audi"})
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': "A3", 'brand_id': brand.id})
        cls.admin = cls.env.ref('base.user_admin')
        cls.type_expertise = cls.env.ref(
            'megga_auto.mail_activity_auto_inspection')

    def _vehicle_due_dans(self, jours):
        """Un véhicule jamais expertisé dont l'échéance (première
        circulation + 48 mois) tombe dans `jours` jours."""
        echeance = fields.Date.add(fields.Date.today(), days=jours)
        return self.env['fleet.vehicle'].create({
            'model_id': self.model.id,
            'manager_id': self.admin.id,
            'megga_first_circulation': add_months(echeance, -48),
        })

    def _activities(self, vehicle):
        return self.env['mail.activity'].search([
            ('res_model', '=', 'fleet.vehicle'),
            ('res_id', '=', vehicle.id),
            ('activity_type_id', '=', self.type_expertise.id),
        ])

    def test_cron_cree_une_activite(self):
        vehicle = self._vehicle_due_dans(10)
        self.env['fleet.vehicle']._cron_megga_inspections()
        activites = self._activities(vehicle)
        self.assertEqual(len(activites), 1)
        self.assertEqual(activites.user_id, self.admin,
                         "l'activité revient au gestionnaire du véhicule")
        self.assertEqual(activites.date_deadline,
                         vehicle.megga_next_inspection)

    def test_cron_idempotent(self):
        vehicle = self._vehicle_due_dans(10)
        self.env['fleet.vehicle']._cron_megga_inspections()
        self.env['fleet.vehicle']._cron_megga_inspections()
        self.assertEqual(len(self._activities(vehicle)), 1)

    def test_cron_respecte_horizon(self):
        vehicle = self._vehicle_due_dans(90)
        self.env['fleet.vehicle']._cron_megga_inspections()  # horizon 30 j
        self.assertFalse(self._activities(vehicle))
        self.env['fleet.vehicle']._cron_megga_inspections(horizon_days=120)
        self.assertEqual(len(self._activities(vehicle)), 1)
