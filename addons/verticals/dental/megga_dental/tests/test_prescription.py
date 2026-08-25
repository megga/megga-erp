from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase


class TestPrescription(TransactionCase):
    """Ordonnances : référentiel facultatif, émission qui FIGE le
    contenu (le papier remis fait foi), renouvellement chaîné,
    impression. Données de santé : le modèle entier est fermé à la
    réception, et c'est testé."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        cls.reception = Users.create({
            'name': "Réception Ord", 'login': "ord_reception",
            'email': "ord.reception@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        cls.soins = Users.create({
            'name': "Soins Ord", 'login': "ord_soins",
            'email': "ord.soins@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_praticien').id)],
        })
        cls.patient = cls.env['megga.dental.patient'].create({
            'name': "Odile Prescrite",
            'birthdate': '1979-02-03',
        })
        cls.amoxicilline = cls.env['megga.dental.medicament'].create({
            'name': "Amoxicilline",
            'dosage': "750 mg",
            'form': "comprimés",
            'default_posology': "3 × par jour pendant 5 jours",
        })

    def _prescription(self, lines):
        return self.env['megga.dental.prescription'].create({
            'patient_id': self.patient.id,
            'line_ids': lines,
        })

    def test_sequence_et_referentiel(self):
        prescription = self._prescription([
            Command.create({'medicament_id': self.amoxicilline.id}),
        ])
        self.assertTrue(prescription.name.startswith("ORD/"))
        line = prescription.line_ids
        # precompute : le referentiel remplit nom et posologie, tous
        # deux modifiables ensuite.
        self.assertEqual(line.name, "Amoxicilline 750 mg comprimés")
        self.assertEqual(line.posology, "3 × par jour pendant 5 jours")

    def test_ligne_libre_sans_referentiel(self):
        prescription = self._prescription([
            Command.create({
                'name': "Bain de bouche chlorhexidine 0.2%",
                'posology': "2 rinçages par jour, 7 jours",
            }),
        ])
        line = prescription.line_ids
        self.assertFalse(line.medicament_id)
        self.assertEqual(line.quantity, 1)

    def test_emission_exige_une_ligne(self):
        prescription = self._prescription([])
        with self.assertRaises(UserError):
            prescription.action_issue()

    def test_emission_fige_le_contenu(self):
        prescription = self._prescription([
            Command.create({'medicament_id': self.amoxicilline.id}),
        ])
        prescription.action_issue()
        self.assertEqual(prescription.state, 'issued')
        self.assertTrue(prescription.date_issued)
        with self.assertRaises(UserError):
            prescription.note = "changement apres coup"
        with self.assertRaises(UserError):
            prescription.line_ids.posology = "autre chose"
        with self.assertRaises(UserError):
            self.env['megga.dental.prescription.line'].create({
                'prescription_id': prescription.id,
                'name': "Ajout interdit", 'posology': "n/a",
            })
        with self.assertRaises(UserError):
            prescription.line_ids.unlink()

    def test_annulation(self):
        prescription = self._prescription([
            Command.create({'medicament_id': self.amoxicilline.id}),
        ])
        prescription.action_issue()
        prescription.action_cancel()
        self.assertEqual(prescription.state, 'cancelled')
        with self.assertRaises(UserError):
            prescription.action_renew()

    def test_renouvellement_chaine(self):
        originale = self._prescription([
            Command.create({'medicament_id': self.amoxicilline.id}),
            Command.create({
                'name': "Ibuprofène 400 mg",
                'posology': "au besoin, max 3 par jour",
            }),
        ])
        with self.assertRaises(UserError):
            originale.action_renew()     # un brouillon ne se renouvelle pas
        originale.action_issue()
        originale.action_renew()
        copie = originale.renewal_ids
        self.assertEqual(len(copie), 1)
        self.assertEqual(copie.state, 'draft')
        self.assertEqual(copie.renewal_of_id, originale)
        self.assertEqual(originale.renewal_count, 1)
        self.assertNotEqual(copie.name, originale.name)
        self.assertEqual(
            copie.line_ids.mapped('name'), originale.line_ids.mapped('name'))

    def test_suppression_gardee(self):
        prescription = self._prescription([
            Command.create({'medicament_id': self.amoxicilline.id}),
        ])
        prescription.action_issue()
        with self.assertRaises(UserError):
            prescription.unlink()
        brouillon = self._prescription([])
        brouillon.unlink()
        self.assertFalse(brouillon.exists())

    def test_depuis_le_traitement(self):
        treatment = self.env['megga.dental.treatment'].create({
            'patient_id': self.patient.id,
        })
        action = treatment.action_new_prescription()
        contexte = action['context']
        self.assertEqual(contexte['default_patient_id'], self.patient.id)
        self.assertEqual(contexte['default_treatment_id'], treatment.id)
        self.assertEqual(
            contexte['default_dentist_id'], treatment.dentist_id.id)

    def test_lpd_reception_aveugle(self):
        prescription = self._prescription([
            Command.create({'medicament_id': self.amoxicilline.id}),
        ])
        Prescription = self.env['megga.dental.prescription'].with_user(
            self.reception)
        with self.assertRaises(AccessError):
            Prescription.search([])
        with self.assertRaises(AccessError):
            Prescription.create({'patient_id': self.patient.id})
        with self.assertRaises(AccessError):
            prescription.line_ids.with_user(self.reception).read(['name'])
        with self.assertRaises(AccessError):
            self.amoxicilline.with_user(self.reception).read(['name'])
        with self.assertRaises(AccessError):
            self.patient.with_user(self.reception).read(
                ['prescription_count'])

    def test_soins_et_rapport(self):
        prescription = self.env['megga.dental.prescription'].with_user(
            self.soins).create({
                'patient_id': self.patient.id,
                'line_ids': [Command.create({
                    'medicament_id': self.amoxicilline.id})],
            })
        prescription.action_issue()
        html = self.env['ir.actions.report']._render_qweb_html(
            'megga_dental.report_prescription', prescription.ids)[0]
        self.assertIn(b"Odile Prescrite", html)
        self.assertIn(b"Amoxicilline 750 mg", html)
        self.assertIn("3 × par jour pendant 5 jours".encode(), html)
        self.assertIn(b"Signature et timbre", html)
