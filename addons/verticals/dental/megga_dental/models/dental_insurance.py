from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Régimes de prise en charge des soins dentaires en Suisse. Les trois
# assurances sociales (accident LAA, invalidité AI, militaire AM) paient
# le cabinet DIRECTEMENT au tarif de la convention (tiers payant de
# droit) ; la LAMal (art. 31 : maladies graves du système de la
# mastication) et les complémentaires LCA passent par une garantie de
# prise en charge — sans garantie écrite, le patient avance les frais
# (tiers garant).
REGIME_SELECTION = [
    ('aa', "Accident (LAA)"),
    ('ai', "Invalidité (AI)"),
    ('am', "Assurance militaire (AM)"),
    ('lamal', "Maladie (LAMal art. 31)"),
    ('lca', "Complémentaire (LCA)"),
]
SOCIAL_REGIMES = ('aa', 'ai', 'am')


class MeggaDentalInsurer(models.Model):
    """L'assureur délègue son identité à res.partner (même patron que le
    patient) : il est facturable tel quel — c'est tout l'objet du tiers
    payant — et la chaîne du socle (QR-facture, encaissement camt) suit."""
    _name = 'megga.dental.insurer'
    _description = "Assureur"
    _inherits = {'res.partner': 'partner_id'}
    _order = 'id'

    partner_id = fields.Many2one(
        'res.partner', string="Contact lié", required=True,
        ondelete='cascade', index=True)
    # `active` propre : radier un assureur du référentiel ne doit pas
    # archiver le contact, qui reste débiteur de factures ouvertes.
    active = fields.Boolean(default=True)
    note = fields.Text("Remarques")
    case_ids = fields.One2many(
        'megga.dental.insurance.case', 'insurer_id', string="Dossiers")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Un assureur est une organisation, pas une personne.
            vals.setdefault('is_company', True)
        return super().create(vals_list)


class MeggaDentalInsuranceCase(models.Model):
    """Le dossier d'assurance d'un patient : un sinistre (accident), une
    décision (AI/AM) ou une garantie de prise en charge (LAMal/LCA). Les
    traitements s'y rattachent ; en tiers payant, leur facture part chez
    l'assureur avec la référence du dossier."""
    _name = 'megga.dental.insurance.case'
    _description = "Dossier d'assurance"
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(
        "Référence", readonly=True, copy=False, default='/')
    patient_id = fields.Many2one(
        'megga.dental.patient', string="Patient", required=True,
        ondelete='restrict', index=True)
    insurer_id = fields.Many2one(
        'megga.dental.insurer', string="Assureur", required=True,
        ondelete='restrict', index=True)
    regime = fields.Selection(
        REGIME_SELECTION, string="Régime", required=True, default='aa')
    # Le mode découle du régime (AA/AI/AM : tiers payant de droit ;
    # LAMal/LCA : tiers garant tant que l'assureur n'a rien garanti)
    # mais reste modifiable : une complémentaire qui délivre une
    # garantie se facture en direct.
    payment_mode = fields.Selection([
        ('payant', "Tiers payant (l'assureur paie le cabinet)"),
        ('garant', "Tiers garant (le patient avance et se fait rembourser)"),
    ], string="Mode", compute='_compute_payment_mode', store=True,
        readonly=False, required=True, precompute=True, tracking=True)
    claim_number = fields.Char(
        "N° de sinistre / décision",
        help="Référence de l'assureur : numéro de sinistre LAA, de "
             "décision AI/AM ou de garantie. Reportée sur les factures.")
    event_date = fields.Date(
        "Date de l'événement",
        help="Date de l'accident ou de la décision de prise en charge.")
    guarantee_amount = fields.Monetary(
        "Garantie de prise en charge", currency_field='currency_id',
        help="Montant garanti par écrit par l'assureur (LAMal/LCA).")
    guarantee_date = fields.Date("Garantie reçue le")
    state = fields.Selection([
        ('draft', "Ouvert"),
        ('active', "Prise en charge confirmée"),
        ('closed', "Clos"),
    ], string="État", default='draft', required=True, copy=False,
        tracking=True)
    note = fields.Text("Remarques")
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    treatment_ids = fields.One2many(
        'megga.dental.treatment', 'insurance_case_id',
        string="Traitements")
    treatment_count = fields.Integer(compute='_compute_amounts')
    amount_invoiced = fields.Monetary(
        "Facturé", compute='_compute_amounts',
        currency_field='currency_id',
        help="Total des factures (hors annulées) des traitements du dossier.")

    _claim_number_insurer_uniq = models.Constraint(
        'UNIQUE(insurer_id, claim_number)',
        "Ce numéro de sinistre existe déjà chez cet assureur.")

    @api.depends('regime')
    def _compute_payment_mode(self):
        for case in self:
            case.payment_mode = (
                'payant' if case.regime in SOCIAL_REGIMES else 'garant')

    def _compute_amounts(self):
        for case in self:
            case.treatment_count = len(case.treatment_ids)
            moves = case.treatment_ids.invoice_id.filtered(
                lambda m: m.state != 'cancel')
            case.amount_invoiced = sum(moves.mapped('amount_total'))

    @api.depends('name', 'patient_id', 'insurer_id', 'regime')
    def _compute_display_name(self):
        libelles = dict(
            self._fields['regime']._description_selection(self.env))
        for case in self:
            case.display_name = "%s — %s (%s)" % (
                case.name, case.patient_id.display_name,
                libelles.get(case.regime, case.regime))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'megga.dental.insurance.case') or '/'
        return super().create(vals_list)

    def action_activate(self):
        """Confirme la prise en charge. Les gardes disent le droit : un
        sinistre social sans numéro n'est pas traité par l'assureur, et
        « pas de garantie écrite, pas de tiers payant » en LAMal/LCA."""
        for case in self:
            if case.regime in SOCIAL_REGIMES and not case.claim_number:
                raise UserError(_(
                    "Renseignez le n° de sinistre ou de décision de "
                    "l'assureur avant de confirmer un dossier %s.")
                    % dict(REGIME_SELECTION)[case.regime])
            if case.regime not in SOCIAL_REGIMES \
                    and case.payment_mode == 'payant' \
                    and not (case.guarantee_amount > 0
                             and case.guarantee_date):
                raise UserError(_(
                    "Pas de garantie écrite, pas de tiers payant : "
                    "renseignez le montant garanti et sa date, ou "
                    "repassez le dossier en tiers garant."))
            case.state = 'active'

    def action_close(self):
        self.write({'state': 'closed'})

    @api.ondelete(at_uninstall=False)
    def _unlink_only_untied(self):
        for case in self:
            if case.treatment_ids:
                raise UserError(_(
                    "Le dossier %s porte des traitements — clôturez-le "
                    "au lieu de le supprimer.") % case.name)
