from datetime import date

from odoo import fields
from odoo.tests import TransactionCase

from ..dental_logic import age_years, fdi_description


class TestPatient(TransactionCase):

    def test_creation_code_et_partner(self):
        """La délégation vers res.partner et la séquence PAT/ fonctionnent."""
        Patient = self.env['megga.dental.patient']
        alice = Patient.create({'name': "Alice Dupont",
                                'birthdate': '1990-05-01'})
        self.assertTrue(alice.code.startswith('PAT/'),
                        "code attendu PAT/…, obtenu %r" % alice.code)
        self.assertTrue(alice.partner_id.exists())
        self.assertEqual(alice.partner_id.name, "Alice Dupont")
        bob = Patient.create({'name': "Bob Martin"})
        self.assertNotEqual(alice.code, bob.code)

    def test_age_calcule(self):
        patient = self.env['megga.dental.patient'].create({
            'name': "Alice Dupont", 'birthdate': '1990-05-01'})
        today = fields.Date.context_today(patient)
        self.assertEqual(patient.age, age_years(date(1990, 5, 1), today))
        patient.birthdate = False
        self.assertEqual(patient.age, 0)

    def test_referentiel_dents(self):
        """Les 52 dents FDI sont chargées et cohérentes avec dental_logic
        (le CSV est généré depuis la même source)."""
        Tooth = self.env['megga.dental.tooth']
        teeth = Tooth.search([])
        self.assertEqual(len(teeth), 52)
        self.assertEqual(len(set(teeth.mapped('number'))), 52)
        seize = Tooth.search([('number', '=', 16)])
        self.assertEqual(seize.name, fdi_description(16))
        self.assertFalse(seize.deciduous)
        self.assertEqual(seize.display_name, "16 — %s" % fdi_description(16))
        lait = Tooth.search([('number', '=', 55)])
        self.assertTrue(lait.deciduous)
