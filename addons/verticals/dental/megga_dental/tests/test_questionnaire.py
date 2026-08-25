import base64

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase

SIGNATURE = base64.b64encode(b"paraphe")


class TestQuestionnaire(TransactionCase):
    """Questionnaires et consentements : le gabarit engendre les
    lignes, la signature fige tout (doctrine de l'ordonnance émise),
    l'anamnèse se périme selon son gabarit et le dossier l'affiche.
    Données de santé : réponses ET gabarits fermés à la réception."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        cls.reception = Users.create({
            'name': "Réception Quest", 'login': "quest_reception",
            'email': "quest.reception@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        cls.soins = Users.create({
            'name': "Soins Quest", 'login': "quest_soins",
            'email': "quest.soins@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_praticien').id)],
        })
        cls.patient = cls.env['megga.dental.patient'].create({
            'name': "Quentin Interrogé",
        })
        cls.anamnese = cls.env.ref('megga_dental.questionnaire_anamnese')
        cls.consent = cls.env.ref('megga_dental.questionnaire_consent_lpd')

    def _answer(self, questionnaire, fill=None):
        answer = self.env['megga.dental.questionnaire.answer'].create({
            'patient_id': self.patient.id,
            'questionnaire_id': questionnaire.id,
        })
        if fill:
            answer.line_ids.write({'answer': fill})
        return answer

    def test_le_gabarit_engendre_les_lignes(self):
        answer = self._answer(self.anamnese)
        self.assertEqual(len(answer.line_ids), 8)
        questions = answer.line_ids.mapped('question')
        self.assertIn(
            "Prenez-vous des anticoagulants ou antiagrégants ?", questions)
        # Le drapeau « précision si oui » suit la question.
        anticoag = answer.line_ids.filtered(
            lambda line: "anticoagulants" in line.question)
        self.assertTrue(anticoag.note_on_yes)
        self.assertEqual(answer.state, 'draft')

    def test_signature_exigee(self):
        answer = self._answer(self.anamnese, fill='no')
        with self.assertRaises(UserError):
            answer.action_sign()

    def test_anamnese_exige_toutes_les_reponses(self):
        answer = self._answer(self.anamnese, fill='no')
        answer.line_ids[0].answer = False
        answer.signature = SIGNATURE
        with self.assertRaises(UserError):
            answer.action_sign()

    def test_signature_fige_tout(self):
        answer = self._answer(self.anamnese, fill='no')
        answer.signature = SIGNATURE
        answer.signed_by = "Quentin Interrogé"
        answer.action_sign()
        self.assertEqual(answer.state, 'signed')
        self.assertTrue(answer.signed_on)
        with self.assertRaises(UserError):
            answer.date = '2020-01-01'
        with self.assertRaises(UserError):
            answer.line_ids[0].answer = 'yes'
        with self.assertRaises(UserError):
            self.env['megga.dental.questionnaire.answer.line'].create({
                'answer_id': answer.id, 'question': "Ajout interdit"})
        with self.assertRaises(UserError):
            answer.line_ids.unlink()
        with self.assertRaises(UserError):
            answer.unlink()
        # Le rattachement administratif reste permis (traitement, plan).
        treatment = self.env['megga.dental.treatment'].create({
            'patient_id': self.patient.id})
        answer.treatment_id = treatment
        self.assertEqual(answer.treatment_id, treatment)

    def test_consentement_sans_questions(self):
        answer = self._answer(self.consent)
        self.assertFalse(answer.line_ids)
        answer.signature = SIGNATURE
        answer.action_sign()
        self.assertEqual(answer.state, 'signed')

    def test_copie_repart_en_brouillon(self):
        answer = self._answer(self.anamnese, fill='no')
        answer.signature = SIGNATURE
        answer.action_sign()
        copie = answer.copy()
        self.assertEqual(copie.state, 'draft')
        self.assertFalse(copie.signature)
        self.assertFalse(copie.signed_on)
        self.assertEqual(len(copie.line_ids), 8)
        self.assertEqual(set(copie.line_ids.mapped('answer')), {'no'})

    def test_indicateur_anamnese_du_dossier(self):
        self.assertEqual(self.patient.anamnesis_state, 'missing')
        answer = self._answer(self.anamnese, fill='no')
        answer.signature = SIGNATURE
        answer.action_sign()
        self.assertEqual(self.patient.anamnesis_state, 'ok')

    def test_peremption_de_bout_en_bout(self):
        answer = self._answer(self.anamnese, fill='no')
        answer.signature = SIGNATURE
        answer.action_sign()
        self.assertFalse(answer.expired)
        # Vieillir la signature au-dela des 24 mois du gabarit : la
        # garde d'ecriture protege les signes, on passe par SQL comme
        # le ferait le temps lui-meme.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE megga_dental_questionnaire_answer "
            "SET signed_on = (CURRENT_DATE - INTERVAL '25 months') "
            "WHERE id = %s", (answer.id,))
        # L'UPDATE brut echappe au suivi des dependances : tout le
        # cache doit etre invalide, les calcules compris.
        self.env.invalidate_all()
        self.assertTrue(answer.expired)
        self.assertEqual(self.patient.anamnesis_state, 'expired')

    def test_lpd_reception_aveugle(self):
        answer = self._answer(self.anamnese, fill='no')
        Answer = self.env['megga.dental.questionnaire.answer'].with_user(
            self.reception)
        with self.assertRaises(AccessError):
            Answer.search([])
        with self.assertRaises(AccessError):
            Answer.create({
                'patient_id': self.patient.id,
                'questionnaire_id': self.anamnese.id,
            })
        with self.assertRaises(AccessError):
            answer.line_ids.with_user(self.reception).read(['question'])
        with self.assertRaises(AccessError):
            self.anamnese.with_user(self.reception).read(['name'])
        with self.assertRaises(AccessError):
            self.patient.with_user(self.reception).read(['anamnesis_state'])

    def test_soins_et_rendu(self):
        answer = self.env['megga.dental.questionnaire.answer'].with_user(
            self.soins).create({
                'patient_id': self.patient.id,
                'questionnaire_id': self.consent.id,
            })
        answer.signature = SIGNATURE
        answer.signed_by = "Quentin Interrogé"
        answer.action_sign()
        html = self.env['ir.actions.report']._render_qweb_html(
            'megga_dental.report_questionnaire', answer.ids)[0]
        self.assertIn(b"Quentin Interrog", html)
        self.assertIn(b"nLPD", html)
        self.assertIn("aux seules fins de mes soins".encode(), html)
        self.assertIn(b"Signature", html)
