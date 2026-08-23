from odoo import fields
from odoo.tests import TransactionCase


class TestRecall(TransactionCase):
    """Le cron quotidien de rappels : une activité par rappel dû, jamais
    deux pour la même échéance, et l'horizon est respecté."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env['megga.dental.patient']
        cls.admin = cls.env.ref('base.user_admin')
        cls.type_rappel = cls.env.ref(
            'megga_dental.mail_activity_dental_recall')

    def _patient(self, recall_date):
        return self.Patient.create({
            'name': "Patient Rappel",
            'dentist_id': self.admin.id,
            'recall_date': recall_date,
        })

    def _activities(self, patient):
        return self.env['mail.activity'].search([
            ('res_model', '=', 'megga.dental.patient'),
            ('res_id', '=', patient.id),
            ('activity_type_id', '=', self.type_rappel.id),
        ])

    def test_cron_cree_une_activite(self):
        patient = self._patient(fields.Date.today())
        self.Patient._cron_dental_recalls()
        activites = self._activities(patient)
        self.assertEqual(len(activites), 1)
        self.assertEqual(activites.user_id, self.admin,
                         "l'activité doit revenir au praticien référent")
        self.assertEqual(activites.date_deadline, patient.recall_date)
        self.assertEqual(patient.recall_notified_date, patient.recall_date)

    def test_cron_idempotent(self):
        patient = self._patient(fields.Date.today())
        self.Patient._cron_dental_recalls()
        self.Patient._cron_dental_recalls()
        self.assertEqual(len(self._activities(patient)), 1,
                         "un même rappel ne doit être notifié qu'une fois")

    def test_cron_respecte_horizon(self):
        loin = fields.Date.add(fields.Date.today(), days=30)
        patient = self._patient(loin)
        self.Patient._cron_dental_recalls()  # horizon par défaut : 14 jours
        self.assertFalse(self._activities(patient))
        self.Patient._cron_dental_recalls(horizon_days=60)
        self.assertEqual(len(self._activities(patient)), 1)

    def test_nouvelle_echeance_renotifie(self):
        patient = self._patient(fields.Date.today())
        self.Patient._cron_dental_recalls()
        patient.recall_date = fields.Date.add(fields.Date.today(), days=3)
        self.Patient._cron_dental_recalls()
        self.assertEqual(len(self._activities(patient)), 2,
                         "une nouvelle échéance doit produire un nouveau rappel")
