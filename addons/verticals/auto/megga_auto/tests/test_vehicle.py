from datetime import date

from odoo import fields
from odoo.tests import TransactionCase

from ..auto_logic import next_inspection_date


class TestVehicle(TransactionCase):
    """L'extension garage de fleet.vehicle : expertise et VIN."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': "Volkswagen"})
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': "Golf 8", 'brand_id': brand.id})

    def _vehicle(self, **kw):
        vals = {'model_id': self.model.id, 'license_plate': "VD 214 780"}
        vals.update(kw)
        return self.env['fleet.vehicle'].create(vals)

    def test_prochaine_expertise_calculee(self):
        vehicle = self._vehicle(megga_first_circulation='2022-06-15')
        self.assertEqual(vehicle.megga_next_inspection, date(2026, 6, 15))
        vehicle.write({'megga_last_inspection': '2026-07-01',
                       'megga_inspections_done': 1})
        self.assertEqual(vehicle.megga_next_inspection, date(2029, 7, 1))
        sans_date = self._vehicle()
        self.assertFalse(sans_date.megga_next_inspection)

    def test_enregistrer_expertise(self):
        vehicle = self._vehicle(megga_first_circulation='2022-06-15')
        vehicle.action_megga_register_inspection()
        today = fields.Date.context_today(vehicle)
        self.assertEqual(vehicle.megga_last_inspection, today)
        self.assertEqual(vehicle.megga_inspections_done, 1)
        self.assertEqual(vehicle.megga_next_inspection,
                         next_inspection_date(date(2022, 6, 15), today, 1))

    def test_vin_plausible(self):
        bon = self._vehicle(vin_sn="WVWZZZAUZLW000123")
        self.assertTrue(bon.megga_vin_ok)
        mauvais = self._vehicle(vin_sn="ABC123")
        self.assertFalse(mauvais.megga_vin_ok)
        vide = self._vehicle()
        self.assertFalse(vide.megga_vin_ok)
