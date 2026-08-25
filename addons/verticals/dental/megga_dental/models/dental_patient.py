import json

from odoo import _, api, fields, models

from ..dental_logic import (
    CONDITION_COLORS, age_years, merge_findings, next_recall_date)


class MeggaDentalPatient(models.Model):
    """Le patient délègue son identité à res.partner (_inherits) : il a
    d'emblée nom, adresse, téléphone, e-mail — et surtout il est facturable
    tel quel, donc la chaîne du socle (facture -> QR-facture -> encaissement
    camt) s'applique sans pont supplémentaire."""
    _name = 'megga.dental.patient'
    _description = "Patient du cabinet dentaire"
    _inherits = {'res.partner': 'partner_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code desc'

    partner_id = fields.Many2one(
        'res.partner', string="Contact lié", required=True,
        ondelete='cascade', index=True)
    code = fields.Char(
        "N° de patient", readonly=True, copy=False, default='/')
    # `active` propre au patient : archiver un dossier ne doit pas archiver
    # le contact, qui peut rester débiteur de factures ouvertes.
    active = fields.Boolean(default=True)
    birthdate = fields.Date("Date de naissance")
    age = fields.Integer("Âge", compute='_compute_age')
    dentist_id = fields.Many2one(
        'res.users', string="Praticien référent",
        default=lambda self: self.env.user)
    insurance_name = fields.Char("Assurance complémentaire")
    insurance_policy = fields.Char("N° de police")
    # Dossier médical : données personnelles SENSIBLES (art. 5 nLPD).
    # groups= sur le champ = protection par l'ORM lui-même — la
    # réception ne peut ni les lire ni les écrire, quelles que soient
    # les vues.
    allergies = fields.Text(
        "Allergies", groups="megga_dental.group_dental_praticien")
    medical_history = fields.Text(
        "Antécédents médicaux",
        groups="megga_dental.group_dental_praticien")
    medications = fields.Text(
        "Médication en cours",
        groups="megga_dental.group_dental_praticien")

    recall_months = fields.Integer("Intervalle de rappel (mois)", default=6)
    recall_date = fields.Date("Prochain rappel")
    recall_notified_date = fields.Date(
        "Rappel déjà notifié", readonly=True, copy=False,
        help="Date de rappel pour laquelle une activité a déjà été créée ;"
             " garantit qu'un même rappel ne génère qu'une seule activité.")
    last_visit_date = fields.Date("Dernière visite", readonly=True, copy=False)

    treatment_ids = fields.One2many(
        'megga.dental.treatment', 'patient_id', string="Traitements")
    tooth_record_ids = fields.One2many(
        'megga.dental.tooth.record', 'patient_id',
        string="Constats dentaires",
        groups="megga_dental.group_dental_praticien")
    odontogram_json = fields.Text(
        "Odontogramme", compute='_compute_odontogram_json',
        groups="megga_dental.group_dental_praticien")
    treatment_count = fields.Integer(compute='_compute_treatment_count')
    plan_ids = fields.One2many(
        'megga.dental.plan', 'patient_id', string="Plans de traitement")
    plan_count = fields.Integer(compute='_compute_plan_count')
    prescription_ids = fields.One2many(
        'megga.dental.prescription', 'patient_id', string="Ordonnances",
        groups="megga_dental.group_dental_praticien")
    prescription_count = fields.Integer(
        compute='_compute_prescription_count',
        groups="megga_dental.group_dental_praticien")
    questionnaire_answer_ids = fields.One2many(
        'megga.dental.questionnaire.answer', 'patient_id',
        string="Questionnaires",
        groups="megga_dental.group_dental_praticien")
    questionnaire_count = fields.Integer(
        compute='_compute_questionnaire_count',
        groups="megga_dental.group_dental_praticien")
    anamnesis_state = fields.Selection([
        ('missing', "Anamnèse manquante"),
        ('ok', "Anamnèse à jour"),
        ('expired', "Anamnèse périmée"),
    ], compute='_compute_anamnesis_state', string="Anamnèse",
        groups="megga_dental.group_dental_praticien",
        help="État de la DERNIÈRE anamnèse signée, au regard de la "
             "validité de son gabarit.")

    _code_uniq = models.Constraint(
        'unique(code)', "Ce numéro de patient existe déjà.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') or vals['code'] == '/':
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'megga.dental.patient') or '/'
        return super().create(vals_list)

    @api.depends('birthdate')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for patient in self:
            patient.age = (
                age_years(patient.birthdate, today) if patient.birthdate else 0)

    @api.depends('tooth_record_ids.tooth_id', 'tooth_record_ids.surface',
                 'tooth_record_ids.condition', 'tooth_record_ids.date')
    def _compute_odontogram_json(self):
        """Charge JSON du widget : l'état ACTUEL de chaque dent (dernier
        constat par surface, dernier constat dent entière), plus la
        légende — libellés traduits et couleurs de dental_logic, pour
        que le JS ne porte aucune constante métier."""
        teeth = self.env['megga.dental.tooth'].search([])
        Record = self.env['megga.dental.tooth.record']
        legend = [
            {'code': code, 'label': label,
             'color': CONDITION_COLORS.get(code, '#999999')}
            for code, label
            in Record._fields['condition']._description_selection(self.env)
        ]
        for patient in self:
            findings = [
                (record.tooth_id.number, record.surface or '',
                 record.condition, (record.date, record.id))
                for record in patient.tooth_record_ids
            ]
            state = merge_findings(findings)
            payload = {
                'legend': legend,
                'deciduous': any(
                    record.tooth_id.deciduous
                    for record in patient.tooth_record_ids),
                'teeth': {
                    str(tooth.number): {
                        'id': tooth.id,
                        'name': tooth.name,
                        'tooth': state.get(tooth.number, {}).get('tooth'),
                        'surfaces': state.get(
                            tooth.number, {}).get('surfaces', {}),
                    }
                    for tooth in teeth
                },
            }
            patient.odontogram_json = json.dumps(payload, ensure_ascii=False)

    @api.depends('treatment_ids')
    def _compute_treatment_count(self):
        for patient in self:
            patient.treatment_count = len(patient.treatment_ids)

    @api.depends('plan_ids')
    def _compute_plan_count(self):
        for patient in self:
            patient.plan_count = len(patient.plan_ids)

    @api.depends('prescription_ids')
    def _compute_prescription_count(self):
        for patient in self:
            patient.prescription_count = len(patient.prescription_ids)

    @api.depends('questionnaire_answer_ids')
    def _compute_questionnaire_count(self):
        for patient in self:
            patient.questionnaire_count = len(
                patient.questionnaire_answer_ids)

    @api.depends('questionnaire_answer_ids.state',
                 'questionnaire_answer_ids.signed_on')
    def _compute_anamnesis_state(self):
        for patient in self:
            signees = patient.questionnaire_answer_ids.filtered(
                lambda answer: answer.kind == 'anamnese'
                and answer.state == 'signed')
            if not signees:
                patient.anamnesis_state = 'missing'
                continue
            derniere = signees.sorted(
                key=lambda answer: (answer.signed_on, answer.id))[-1]
            patient.anamnesis_state = (
                'expired' if derniere.expired else 'ok')

    def action_view_questionnaires(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Questionnaires"),
            'res_model': 'megga.dental.questionnaire.answer',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }

    def action_view_prescriptions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Ordonnances"),
            'res_model': 'megga.dental.prescription',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }

    def action_view_plans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Plans de traitement"),
            'res_model': 'megga.dental.plan',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }

    def action_view_treatments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Traitements"),
            'res_model': 'megga.dental.treatment',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }

    def action_plan_recall(self):
        """Planifie manuellement le prochain rappel à aujourd'hui + intervalle."""
        today = fields.Date.context_today(self)
        for patient in self:
            patient.recall_date = next_recall_date(
                today, patient.recall_months or 6)

    @api.model
    def _cron_dental_recalls(self, horizon_days=14):
        """Chaque jour : crée une activité « Rappel de contrôle » pour tout
        patient dont le rappel tombe dans l'horizon. Idempotent : un même
        rappel (recall_notified_date == recall_date) n'est notifié qu'une fois ;
        une nouvelle date de rappel relance naturellement la notification."""
        today = fields.Date.today()
        limite = fields.Date.add(today, days=horizon_days)
        patients = self.search([
            ('recall_date', '!=', False),
            ('recall_date', '<=', limite),
        ])
        for patient in patients:
            if patient.recall_notified_date == patient.recall_date:
                continue
            patient.activity_schedule(
                'megga_dental.mail_activity_dental_recall',
                date_deadline=patient.recall_date,
                summary=_("Rappel de contrôle : %s") % patient.name,
                note=_("Contrôle périodique à planifier (intervalle : %s mois)."
                       ) % (patient.recall_months or 6),
                user_id=patient.dentist_id.id or self.env.uid,
            )
            patient.recall_notified_date = patient.recall_date
        return True
