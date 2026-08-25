from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..dental_logic import anamnesis_expired


class ReportQuestionnaire(models.AbstractModel):
    """Rendu du rapport : injecte le titre DIN dans le contexte GLOBAL
    (meme mecanique que l'ordonnance — la mise en page DIN imprime son
    titre avant le corps et masque ceux du corps)."""
    _name = 'report.megga_dental.report_questionnaire'
    _description = "Rendu du questionnaire signé"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['megga.dental.questionnaire.answer'].browse(docids)
        kinds = set(docs.mapped('questionnaire_id.kind'))
        title = _("Consentement") if kinds == {'consent'} \
            else _("Questionnaire médical")
        return {
            'doc_ids': docids,
            'doc_model': 'megga.dental.questionnaire.answer',
            'docs': docs,
            'din5008_document_title': title,
        }


class MeggaDentalQuestionnaire(models.Model):
    """Gabarit de questionnaire du cabinet : l'anamnèse médicale (à
    refaire périodiquement — la validité se règle ici) ou un
    consentement (le texte à signer vit dans l'introduction). Les
    gabarits appartiennent au cabinet : chaque cabinet écrit les siens,
    les exemples livrés sont explicitement à adapter."""
    _name = 'megga.dental.questionnaire'
    _description = "Gabarit de questionnaire"
    _order = 'kind, name, id'

    name = fields.Char("Nom", required=True)
    kind = fields.Selection([
        ('anamnese', "Questionnaire médical (anamnèse)"),
        ('consent', "Consentement"),
    ], string="Type", required=True, default='anamnese')
    intro = fields.Text(
        "Introduction",
        help="Imprimée en tête. Pour un consentement : le texte même "
             "auquel le patient consent.")
    validity_months = fields.Integer(
        "Validité (mois)", default=0,
        help="0 : sans péremption. Une anamnèse signée il y a plus "
             "longtemps que cela est signalée périmée sur le dossier.")
    question_ids = fields.One2many(
        'megga.dental.questionnaire.question', 'questionnaire_id',
        string="Questions", copy=True)
    active = fields.Boolean(default=True)


class MeggaDentalQuestionnaireQuestion(models.Model):
    _name = 'megga.dental.questionnaire.question'
    _description = "Question d'un gabarit"
    _order = 'questionnaire_id, sequence, id'

    questionnaire_id = fields.Many2one(
        'megga.dental.questionnaire', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char("Question", required=True)
    note_on_yes = fields.Boolean(
        "Précision si oui",
        help="Rappelle au praticien de demander un détail quand la "
             "réponse est oui (lequel, depuis quand, quel dosage…).")


class MeggaDentalQuestionnaireAnswer(models.Model):
    """Questionnaire REMPLI par un patient : données de santé pures
    (art. 5 nLPD), modèle entièrement fermé à la réception, comme les
    constats et les ordonnances.

    Un questionnaire signé ne se modifie plus — c'est sa raison d'être
    (la doctrine de l'ordonnance émise) : on en refait un."""
    _name = 'megga.dental.questionnaire.answer'
    _description = "Questionnaire signé"
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    patient_id = fields.Many2one(
        'megga.dental.patient', string="Patient", required=True,
        ondelete='cascade', index=True)
    questionnaire_id = fields.Many2one(
        'megga.dental.questionnaire', string="Gabarit", required=True,
        ondelete='restrict')
    kind = fields.Selection(related='questionnaire_id.kind', store=True)
    dentist_id = fields.Many2one(
        'res.users', string="Recueilli par",
        default=lambda self: self.env.user)
    date = fields.Date(
        "Date", required=True, default=fields.Date.context_today)
    state = fields.Selection([
        ('draft', "En cours"),
        ('signed', "Signé"),
    ], string="État", default='draft', required=True, copy=False,
        tracking=True)
    treatment_id = fields.Many2one(
        'megga.dental.treatment', string="Traitement", ondelete='set null')
    plan_id = fields.Many2one(
        'megga.dental.plan', string="Plan de traitement",
        ondelete='set null')
    line_ids = fields.One2many(
        'megga.dental.questionnaire.answer.line', 'answer_id',
        string="Réponses", copy=True)
    signature = fields.Binary("Signature", attachment=True, copy=False)
    signed_by = fields.Char("Signé par (nom)", copy=False)
    signed_on = fields.Date("Signé le", readonly=True, copy=False)
    expired = fields.Boolean(
        "Périmé", compute='_compute_expired',
        help="Anamnèse plus vieille que la validité de son gabarit.")

    @api.depends('patient_id.name', 'questionnaire_id.name', 'date')
    def _compute_display_name(self):
        for answer in self:
            answer.display_name = "%s — %s (%s)" % (
                answer.questionnaire_id.name or "?",
                answer.patient_id.name or "?", answer.date or "")

    @api.model_create_multi
    def create(self, vals_list):
        answers = super().create(vals_list)
        # Les questions du gabarit deviennent les lignes de reponse —
        # sauf si l'appelant a fourni les siennes (copie, import).
        for answer in answers:
            if not answer.line_ids:
                answer.line_ids = [
                    (0, 0, {
                        'question': question.name,
                        'note_on_yes': question.note_on_yes,
                        'sequence': question.sequence,
                    })
                    for question in answer.questionnaire_id.question_ids
                ]
        return answers

    @api.depends('kind', 'signed_on',
                 'questionnaire_id.validity_months')
    def _compute_expired(self):
        today = fields.Date.context_today(self)
        for answer in self:
            answer.expired = (
                answer.kind == 'anamnese'
                and answer.state == 'signed'
                and anamnesis_expired(
                    answer.signed_on,
                    answer.questionnaire_id.validity_months, today))

    def write(self, vals):
        signees = self.filtered(lambda a: a.state == 'signed')
        if signees and set(vals) - {'treatment_id', 'plan_id'}:
            raise UserError(_(
                "Le questionnaire « %s » est signé : il ne se modifie "
                "plus — refaites-en un.") % signees[0].display_name)
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_draft_only(self):
        for answer in self:
            if answer.state == 'signed':
                raise UserError(_(
                    "Un questionnaire signé ne se supprime pas — "
                    "l'histoire reste."))

    def action_sign(self):
        for answer in self:
            if answer.state != 'draft':
                raise UserError(_("Déjà signé."))
            if not answer.signature:
                raise UserError(_(
                    "La signature du patient manque."))
            if answer.kind == 'anamnese':
                vides = answer.line_ids.filtered(
                    lambda line: not line.answer)
                if vides:
                    raise UserError(_(
                        "Répondez à toutes les questions avant de "
                        "signer (%s restante(s)).") % len(vides))
            # Un seul write, pendant que l'etat est encore brouillon.
            answer.write({
                'state': 'signed',
                'signed_on': fields.Date.context_today(answer),
            })


class MeggaDentalQuestionnaireAnswerLine(models.Model):
    _name = 'megga.dental.questionnaire.answer.line'
    _description = "Réponse à une question"
    _order = 'answer_id, sequence, id'

    answer_id = fields.Many2one(
        'megga.dental.questionnaire.answer', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    question = fields.Char("Question", required=True)
    note_on_yes = fields.Boolean("Précision si oui")
    answer = fields.Selection([
        ('yes', "Oui"),
        ('no', "Non"),
        ('na', "Sans objet"),
    ], string="Réponse")
    note = fields.Char("Précision")

    def _guard_frozen(self):
        for line in self:
            if line.answer_id.state == 'signed':
                raise UserError(_(
                    "Le questionnaire « %s » est signé : ses réponses "
                    "ne bougent plus.") % line.answer_id.display_name)

    def write(self, vals):
        self._guard_frozen()
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._guard_frozen()
        return lines

    @api.ondelete(at_uninstall=False)
    def _unlink_guard(self):
        self._guard_frozen()
