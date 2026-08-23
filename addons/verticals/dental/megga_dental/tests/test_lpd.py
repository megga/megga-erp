from odoo.exceptions import AccessError
from odoo.tests import TransactionCase


class TestLpd(TransactionCase):
    """Les groupes LPD du dossier médical : la réception travaille
    (identité, rendez-vous, facturation) sans jamais voir les données de
    santé ; les soins voient tout ; sans groupe dentaire, rien du tout.
    La protection des champs est portée par l'ORM (groups= sur le
    champ), pas par les vues."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        cls.reception = Users.create({
            'name': "Réception Test", 'login': "lpd_reception",
            'email': "lpd.reception@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        cls.soins = Users.create({
            'name': "Soins Test", 'login': "lpd_soins",
            'email': "lpd.soins@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_praticien').id)],
        })
        cls.autre = Users.create({
            'name': "Interne Sans Groupe", 'login': "lpd_autre",
            'email': "lpd.autre@exemple.ch",
        })
        cls.patient = cls.env['megga.dental.patient'].create({
            'name': "Paul Sensible",
            'phone': "+41 21 555 10 10",
            'allergies': "Pénicilline",
            'medical_history': "Antécédent cardiaque",
        })

    def test_reception_travaille_sur_l_identite(self):
        patient = self.patient.with_user(self.reception)
        self.assertEqual(patient.name, "Paul Sensible")
        self.assertEqual(patient.phone, "+41 21 555 10 10")
        patient.phone = "+41 21 555 20 20"   # mise à jour d'identité : oui
        self.assertEqual(patient.phone, "+41 21 555 20 20")

    def test_reception_ne_voit_pas_le_medical(self):
        patient = self.patient.with_user(self.reception)
        with self.assertRaises(AccessError):
            patient.read(['allergies'])
        with self.assertRaises(AccessError):
            patient.read(['medical_history'])
        with self.assertRaises(AccessError):
            patient.write({'medications': "Aspirine"})

    def test_soins_voient_et_tiennent_le_dossier(self):
        patient = self.patient.with_user(self.soins)
        self.assertEqual(patient.allergies, "Pénicilline")
        patient.medications = "Amoxicilline 1g"
        self.assertEqual(patient.medications, "Amoxicilline 1g")

    def test_suppression_reservee_aux_soins(self):
        jetable = self.env['megga.dental.patient'].create({
            'name': "Dossier Jetable"})
        with self.assertRaises(AccessError):
            jetable.with_user(self.reception).unlink()
        jetable.with_user(self.soins).unlink()
        self.assertFalse(jetable.exists())

    def test_sans_groupe_aucun_acces(self):
        with self.assertRaises(AccessError):
            self.patient.with_user(self.autre).read(['name'])
        with self.assertRaises(AccessError):
            self.env['megga.dental.patient'].with_user(
                self.autre).create({'name': "Intrus"})

    def test_notes_cliniques_reservees_aux_soins(self):
        traitement = self.env['megga.dental.treatment'].create({
            'patient_id': self.patient.id,
            'notes': "Carie distale 16, à surveiller.",
        })
        cote_reception = traitement.with_user(self.reception)
        # La facturation reste possible : état et montant sont lisibles…
        self.assertEqual(cote_reception.state, 'draft')
        self.assertEqual(cote_reception.amount_total, 0.0)
        # …mais jamais le contenu clinique.
        with self.assertRaises(AccessError):
            cote_reception.read(['notes'])
        self.assertIn("Carie", traitement.with_user(self.soins).notes)
