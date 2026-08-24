from odoo.exceptions import AccessError
from odoo.tests import TransactionCase


class TestLpd(TransactionCase):
    """Les groupes LPD du dossier client : l'assistance travaille
    (identité, mandats, facturation) sans jamais voir le parcours de
    santé ; la coordination voit tout ; sans groupe conciergerie, rien
    du tout. La protection du champ est portée par l'ORM (groups= sur le
    champ), pas par les vues."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        cls.assistance = Users.create({
            'name': "Assistance Test", 'login': "lpd_care_assistance",
            'email': "lpd.assistance@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_care.group_care_assistance').id)],
        })
        cls.coordination = Users.create({
            'name': "Coordination Test", 'login': "lpd_care_coordination",
            'email': "lpd.coordination@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_care.group_care_coordination').id)],
        })
        cls.autre = Users.create({
            'name': "Interne Sans Groupe", 'login': "lpd_care_autre",
            'email': "lpd.autre@exemple.ch",
        })
        cls.patient = cls.env['megga.care.patient'].create({
            'name': "Rania Sensible",
            'phone': "+41 22 555 10 10",
            'medical_notes': "Suivi oncologique, ne pas évoquer par e-mail.",
        })

    def test_assistance_travaille_sur_l_identite(self):
        patient = self.patient.with_user(self.assistance)
        self.assertEqual(patient.name, "Rania Sensible")
        patient.phone = "+41 22 555 20 20"   # mise à jour d'identité : oui
        self.assertEqual(patient.phone, "+41 22 555 20 20")
        # Le cœur du métier de l'assistance : tenir les mandats.
        mandat = self.env['megga.care.mandate'].with_user(
            self.assistance).create({'patient_id': patient.id})
        self.assertTrue(mandat.name.startswith('MAN/'))

    def test_assistance_ne_voit_pas_le_parcours_de_sante(self):
        patient = self.patient.with_user(self.assistance)
        with self.assertRaises(AccessError):
            patient.read(['medical_notes'])
        with self.assertRaises(AccessError):
            patient.write({'medical_notes': "Intrusion"})

    def test_coordination_tient_le_dossier(self):
        patient = self.patient.with_user(self.coordination)
        self.assertIn("oncologique", patient.medical_notes)
        patient.medical_notes = "Suivi clos."
        self.assertEqual(patient.medical_notes, "Suivi clos.")

    def test_suppression_reservee_a_la_coordination(self):
        jetable = self.env['megga.care.patient'].create({
            'name': "Dossier Jetable"})
        with self.assertRaises(AccessError):
            jetable.with_user(self.assistance).unlink()
        jetable.with_user(self.coordination).unlink()
        self.assertFalse(jetable.exists())

    def test_sans_groupe_aucun_acces(self):
        with self.assertRaises(AccessError):
            self.patient.with_user(self.autre).read(['name'])
        with self.assertRaises(AccessError):
            self.env['megga.care.patient'].with_user(
                self.autre).create({'name': "Intrus"})
