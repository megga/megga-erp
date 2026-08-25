import base64

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase

SIGNATURE = base64.b64encode(b"paraphe")


class TestDentalPortal(TransactionCase):
    """L'étanchéité du portail : le patient connecté lit LE SIEN ET RIEN
    QUE LE SIEN, jamais un brouillon, jamais le clinique profond, et
    n'écrit rien nulle part."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_reset_password=True))
        Patient = cls.env['megga.dental.patient']
        Users = cls.env['res.users']
        portal_group = cls.env.ref('base.group_portal')

        def monte(nom, login):
            patient = Patient.create({'name': nom})
            user = Users.create({
                'name': nom, 'login': login,
                'email': '%s@exemple.ch' % login,
                'password': 'Portail-123!',
                'partner_id': patient.partner_id.id,
                'group_ids': [(6, 0, [portal_group.id])],
            })
            treatment = cls.env['megga.dental.treatment'].create({
                'patient_id': patient.id,
                'line_ids': [Command.create({
                    'description': "Contrôle",
                    'product_id': cls.produit.id,
                    'price_unit': 120.0})],
            })
            emise = cls.env['megga.dental.prescription'].create({
                'patient_id': patient.id,
                'line_ids': [Command.create({
                    'name': "Amoxicilline 750 mg",
                    'posology': "3 x par jour"})],
            })
            emise.action_issue()
            brouillon = cls.env['megga.dental.prescription'].create({
                'patient_id': patient.id,
                'line_ids': [Command.create({
                    'name': "Brouillon secret", 'posology': "n/a"})],
            })
            signe = cls.env['megga.dental.questionnaire.answer'].create({
                'patient_id': patient.id,
                'questionnaire_id': cls.env.ref(
                    'megga_dental.questionnaire_consent_lpd').id,
                'signature': SIGNATURE,
            })
            signe.action_sign()
            en_cours = cls.env['megga.dental.questionnaire.answer'].create({
                'patient_id': patient.id,
                'questionnaire_id': cls.env.ref(
                    'megga_dental.questionnaire_anamnese').id,
            })
            return patient, user, treatment, emise, brouillon, signe, en_cours

        cls.produit = cls.env['product.product'].create({
            'name': "Contrôle", 'type': 'service', 'list_price': 120.0})
        (cls.patient_a, cls.user_a, cls.trt_a, cls.ord_a, cls.brouillon_a,
         cls.quest_a, cls.encours_a) = monte("Alice Portail", "portail.alice")
        (cls.patient_b, cls.user_b, cls.trt_b, cls.ord_b, cls.brouillon_b,
         cls.quest_b, cls.encours_b) = monte("Bruno Portail", "portail.bruno")

    def test_voit_ses_traitements_et_montants(self):
        Treatment = self.env['megga.dental.treatment'].with_user(self.user_a)
        siens = Treatment.search([])
        self.assertEqual(siens, self.trt_a.with_user(self.user_a))
        self.assertEqual(siens.amount_total, 120.0)
        self.assertEqual(siens.line_ids.description, "Contrôle")

    def test_pas_ceux_du_voisin(self):
        with self.assertRaises(AccessError):
            self.trt_b.with_user(self.user_a).read(['name'])
        with self.assertRaises(AccessError):
            self.trt_b.line_ids.with_user(self.user_a).read(['description'])

    def test_ordonnances_emises_seulement(self):
        Prescription = self.env['megga.dental.prescription'].with_user(
            self.user_a)
        visibles = Prescription.search([])
        self.assertEqual(visibles, self.ord_a.with_user(self.user_a))
        with self.assertRaises(AccessError):
            self.brouillon_a.with_user(self.user_a).read(['name'])
        with self.assertRaises(AccessError):
            self.ord_b.with_user(self.user_a).read(['name'])

    def test_questionnaires_signes_seulement(self):
        Answer = self.env['megga.dental.questionnaire.answer'].with_user(
            self.user_a)
        visibles = Answer.search([])
        self.assertEqual(visibles, self.quest_a.with_user(self.user_a))
        with self.assertRaises(AccessError):
            self.encours_a.with_user(self.user_a).read(['state'])
        # Le gabarit, lui, se lit (il porte le nom affiché) — ce n'est
        # pas une donnée patient.
        self.assertTrue(
            self.quest_a.questionnaire_id.with_user(self.user_a).name)

    def test_les_lignes_suivent_les_regles(self):
        lignes = self.env['megga.dental.prescription.line'].with_user(
            self.user_a).search([])
        self.assertEqual(
            lignes.mapped('name'), ["Amoxicilline 750 mg"])
        with self.assertRaises(AccessError):
            self.brouillon_a.line_ids.with_user(self.user_a).read(['name'])
        with self.assertRaises(AccessError):
            self.ord_b.line_ids.with_user(self.user_a).read(['name'])

    def test_lecture_seule_partout(self):
        with self.assertRaises(AccessError):
            self.trt_a.with_user(self.user_a).write({'date': '2020-01-01'})
        with self.assertRaises(AccessError):
            self.env['megga.dental.prescription'].with_user(
                self.user_a).create({'patient_id': self.patient_a.id})
        with self.assertRaises(AccessError):
            self.quest_a.with_user(self.user_a).unlink()

    def test_le_clinique_profond_reste_ferme(self):
        for model in ('megga.dental.tooth.record', 'megga.dental.imaging',
                      'megga.dental.clinical.note', 'megga.dental.plan',
                      'megga.dental.medicament'):
            with self.assertRaises(AccessError, msg=model):
                self.env[model].with_user(self.user_a).search([])
        # Et sur son propre traitement, le champ clinique reste hors
        # de portée (groups= sur le champ).
        with self.assertRaises(AccessError):
            self.trt_a.with_user(self.user_a).read(['notes'])

    def test_le_dossier_patient_lui_meme_reste_ferme(self):
        # Le portail lit des DOCUMENTS (traitements, ordonnances...),
        # jamais le dossier megga.dental.patient : aucune ACL.
        with self.assertRaises(AccessError):
            self.env['megga.dental.patient'].with_user(
                self.user_a).search([])
