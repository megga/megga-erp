from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class MeggaDentalPlan(models.Model):
    """Plan de traitement par phases : l'assainissement avant la prothèse,
    la chirurgie avant l'implant. Le plan CHAPEAUTE des traitements
    existants — chaque phase porte le sien (créé en devis dès l'ajout de
    la phase) : la facturation, le tarif par points et les constats
    d'odontogramme restent portés par le traitement ; le plan apporte
    l'ordre clinique (une phase ne se lance que quand les précédentes
    sont soldées), le devis d'ensemble et l'avancement."""
    _name = 'megga.dental.plan'
    _description = "Plan de traitement"
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char("Référence", readonly=True, copy=False, default='/')
    patient_id = fields.Many2one(
        'megga.dental.patient', string="Patient", required=True,
        ondelete='restrict', index=True)
    dentist_id = fields.Many2one(
        'res.users', string="Praticien",
        default=lambda self: self.env.user)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    date = fields.Date(
        "Date de proposition", required=True,
        default=fields.Date.context_today)
    state = fields.Selection([
        ('draft', "Proposé"),
        ('accepted', "Accepté"),
        ('done', "Achevé"),
        ('cancelled', "Abandonné"),
    ], string="État", default='draft', required=True, copy=False,
        tracking=True)
    # Le tarif du plan est PROPAGÉ aux traitements créés par ses phases
    # (chaque traitement fige ensuite sa valeur du point, chantier
    # tarif) : un plan aux assurances sociales se chiffre au point de la
    # convention d'un bout à l'autre.
    tariff_kind = fields.Selection([
        ('prive', "Privé"),
        ('social', "Assurances sociales (AA/AI/AM)"),
    ], string="Tarif", default='prive', required=True)
    insurance_case_id = fields.Many2one(
        'megga.dental.insurance.case', string="Dossier d'assurance",
        ondelete='restrict', index=True,
        help="Propagé aux traitements des phases : tout le plan se "
             "facture sur le même dossier de prise en charge.")

    @api.constrains('insurance_case_id', 'patient_id', 'tariff_kind')
    def _check_insurance_case(self):
        for plan in self:
            case = plan.insurance_case_id
            if not case:
                continue
            if case.patient_id != plan.patient_id:
                raise ValidationError(_(
                    "Le dossier d'assurance %(dossier)s appartient à "
                    "%(titulaire)s, pas à %(patient)s.") % {
                        'dossier': case.name,
                        'titulaire': case.patient_id.display_name,
                        'patient': plan.patient_id.display_name})
            if case.regime in ('aa', 'ai', 'am') \
                    and plan.tariff_kind != 'social':
                raise ValidationError(_(
                    "Un dossier %s se chiffre au tarif des assurances "
                    "sociales — passez le plan au tarif conventionnel.")
                    % case.name)

    # Pourquoi ce plan : donnée clinique (art. 5 nLPD) — réservé aux
    # Soins, comme les notes cliniques du traitement. La réception voit
    # le plan, ses montants et son avancement : elle encaisse.
    diagnosis = fields.Text(
        "Diagnostic et objectif",
        groups="megga_dental.group_dental_praticien")
    phase_ids = fields.One2many(
        'megga.dental.plan.phase', 'plan_id', string="Phases", copy=False)
    amount_total = fields.Monetary(
        "Devis du plan", compute='_compute_amount_total', store=True,
        currency_field='currency_id')
    progress = fields.Integer(
        "Avancement (%)", compute='_compute_progress')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'megga.dental.plan') or '/'
        return super().create(vals_list)

    @api.depends('phase_ids.treatment_id.amount_total',
                 'phase_ids.treatment_id.state')
    def _compute_amount_total(self):
        for plan in self:
            plan.amount_total = sum(
                phase.treatment_id.amount_total
                for phase in plan.phase_ids
                if phase.state != 'cancelled')

    @api.depends('phase_ids.state')
    def _compute_progress(self):
        for plan in self:
            actives = plan.phase_ids.filtered(
                lambda phase: phase.state != 'cancelled')
            done = actives.filtered(lambda phase: phase.state == 'done')
            plan.progress = round(100 * len(done) / len(actives)) \
                if actives else 0

    def action_accept(self):
        for plan in self:
            if plan.state != 'draft':
                raise UserError(_("Seul un plan proposé peut être accepté."))
            if not plan.phase_ids:
                raise UserError(
                    _("Ajoutez au moins une phase avant d'accepter."))
            plan.state = 'accepted'

    def action_cancel(self):
        """Abandonne le plan : les traitements non commencés (devis,
        planifiés) sont annulés ; une phase déjà terminée reste acquise —
        les soins prodigués ne se dé-prodiguent pas."""
        for plan in self:
            if plan.state == 'done':
                raise UserError(_("Un plan achevé ne s'abandonne plus."))
            plan.phase_ids.treatment_id.filtered(
                lambda treatment: treatment.state in ('draft', 'confirmed')
            ).action_cancel()
            plan.state = 'cancelled'

    def _refresh_state(self):
        """Achève le plan tout seul quand toutes ses phases sont soldées
        (terminées ou annulées) et qu'au moins une a été menée au bout.
        Appelé par le traitement à chaque clôture ou annulation."""
        for plan in self:
            if plan.state != 'accepted' or not plan.phase_ids:
                continue
            states = plan.phase_ids.mapped('state')
            if all(s in ('done', 'cancelled') for s in states) \
                    and 'done' in states:
                plan.state = 'done'
                plan.message_post(body=_(
                    "Plan achevé : toutes les phases sont soldées."))

    @api.ondelete(at_uninstall=False)
    def _unlink_only_untouched(self):
        for plan in self:
            if plan.state not in ('draft', 'cancelled'):
                raise UserError(_(
                    "Un plan accepté ou achevé ne se supprime pas — "
                    "abandonnez-le, l'histoire reste."))


class MeggaDentalPlanPhase(models.Model):
    _name = 'megga.dental.plan.phase'
    _description = "Phase d'un plan de traitement"
    _order = 'plan_id, sequence, id'

    plan_id = fields.Many2one(
        'megga.dental.plan', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(
        "Phase", required=True,
        help="Assainissement, chirurgie, prothèse… le libellé clinique "
             "de l'étape.")
    # Chaque phase porte SON traitement, créé en devis dès l'ajout de la
    # phase (voir create) : les actes se saisissent dedans, au tarif par
    # points, comme n'importe quelle séance.
    treatment_id = fields.Many2one(
        'megga.dental.treatment', string="Traitement", readonly=True,
        copy=False, ondelete='set null')
    state = fields.Selection([
        ('todo', "À préparer"),
        ('draft', "Devis"),
        ('confirmed', "En cours"),
        ('done', "Terminée"),
        ('cancelled', "Annulée"),
    ], compute='_compute_state', string="État")
    currency_id = fields.Many2one(related='plan_id.currency_id')
    amount = fields.Monetary(
        related='treatment_id.amount_total', string="Montant",
        currency_field='currency_id')

    @api.depends('treatment_id.state')
    def _compute_state(self):
        for phase in self:
            phase.state = phase.treatment_id.state \
                if phase.treatment_id else 'todo'

    @api.model_create_multi
    def create(self, vals_list):
        phases = super().create(vals_list)
        Treatment = self.env['megga.dental.treatment']
        for phase in phases:
            if not phase.treatment_id:
                phase.treatment_id = Treatment.create({
                    'patient_id': phase.plan_id.patient_id.id,
                    'dentist_id': phase.plan_id.dentist_id.id,
                    'company_id': phase.plan_id.company_id.id,
                    'tariff_kind': phase.plan_id.tariff_kind,
                    'insurance_case_id':
                        phase.plan_id.insurance_case_id.id,
                })
        return phases

    @api.ondelete(at_uninstall=False)
    def _unlink_only_unstarted(self):
        for phase in self:
            if phase.state in ('confirmed', 'done'):
                raise UserError(_(
                    "La phase « %s » est engagée : elle ne se supprime "
                    "plus.") % phase.name)

    def action_start(self):
        """Lance la phase : son traitement passe en Planifié. Garde
        d'ordre clinique : toutes les phases PRÉCÉDENTES (séquence
        inférieure) doivent être soldées — on ne pose pas la prothèse
        avant la fin de l'assainissement."""
        for phase in self:
            plan = phase.plan_id
            if plan.state != 'accepted':
                raise UserError(_(
                    "Le plan %s n'est pas accepté.") % plan.name)
            if not phase.treatment_id or phase.state != 'draft':
                raise UserError(_(
                    "Seule une phase au stade du devis se lance."))
            avant = plan.phase_ids.filtered(
                lambda autre: (autre.sequence, autre.id)
                < (phase.sequence, phase.id))
            bloquantes = avant.filtered(
                lambda autre: autre.state not in ('done', 'cancelled'))
            if bloquantes:
                raise UserError(_(
                    "Les phases précédentes ne sont pas soldées : %s.")
                    % ", ".join(bloquantes.mapped('name')))
            phase.treatment_id.action_confirm()

    def action_open_treatment(self):
        self.ensure_one()
        if not self.treatment_id:
            raise UserError(_("Cette phase n'a pas encore de traitement."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'megga.dental.treatment',
            'view_mode': 'form',
            'res_id': self.treatment_id.id,
        }
