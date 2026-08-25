from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MeggaDentalMedicament(models.Model):
    """Référentiel de médicaments DU CABINET, pour l'autocomplétion des
    ordonnances. Comme le catalogue des positions tarifaires (œuvre
    SSO), le compendium officiel est sous licence : il n'est PAS
    embarqué — chaque cabinet saisit les quelques médicaments qu'il
    prescrit vraiment, ou écrit librement sur la ligne (le référentiel
    est facultatif)."""
    _name = 'megga.dental.medicament'
    _description = "Médicament (référentiel du cabinet)"
    _order = 'name, id'

    name = fields.Char("Nom", required=True)
    dosage = fields.Char("Dosage", help="500 mg, 1 g…")
    form = fields.Char("Forme", help="Comprimés, sirop, bain de bouche…")
    default_posology = fields.Char(
        "Posologie habituelle",
        help="Pré-remplit la ligne d'ordonnance ; toujours modifiable.")
    active = fields.Boolean(default=True)

    @api.depends('name', 'dosage')
    def _compute_display_name(self):
        for medicament in self:
            medicament.display_name = " ".join(
                part for part in (medicament.name, medicament.dosage) if part)


class MeggaDentalPrescription(models.Model):
    """Ordonnance du cabinet. Données de santé pures (art. 5 nLPD) : le
    modèle entier est réservé au groupe Soins, comme les constats —
    aucune ligne ir.model.access pour la réception.

    Une ordonnance ÉMISE ne se modifie plus (le papier remis au patient
    fait foi) : on la renouvelle — copie neuve, chaînée à l'originale —
    ou on l'annule ; une émise ne se supprime pas non plus, l'histoire
    reste."""
    _name = 'megga.dental.prescription'
    _description = "Ordonnance"
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char("Référence", readonly=True, copy=False, default='/')
    patient_id = fields.Many2one(
        'megga.dental.patient', string="Patient", required=True,
        ondelete='restrict', index=True)
    dentist_id = fields.Many2one(
        'res.users', string="Prescripteur", required=True,
        default=lambda self: self.env.user)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    date = fields.Date(
        "Date", required=True, default=fields.Date.context_today)
    date_issued = fields.Date("Émise le", readonly=True, copy=False)
    state = fields.Selection([
        ('draft', "Brouillon"),
        ('issued', "Émise"),
        ('cancelled', "Annulée"),
    ], string="État", default='draft', required=True, copy=False,
        tracking=True)
    treatment_id = fields.Many2one(
        'megga.dental.treatment', string="Traitement", ondelete='set null',
        help="La séance dont cette ordonnance découle, le cas échéant.")
    # copy=True : le renouvellement EST une copie — sans lui les lignes
    # ne suivraient pas (One2many ne copie pas par defaut ; le traitement
    # porte le meme drapeau pour la meme raison).
    line_ids = fields.One2many(
        'megga.dental.prescription.line', 'prescription_id',
        string="Médicaments", copy=True)
    note = fields.Char("Remarque au pharmacien")
    renewal_of_id = fields.Many2one(
        'megga.dental.prescription', string="Renouvelle", readonly=True,
        copy=False, ondelete='set null')
    renewal_ids = fields.One2many(
        'megga.dental.prescription', 'renewal_of_id',
        string="Renouvellements")
    renewal_count = fields.Integer(compute='_compute_renewal_count')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'megga.dental.prescription') or '/'
        return super().create(vals_list)

    @api.depends('renewal_ids')
    def _compute_renewal_count(self):
        for prescription in self:
            prescription.renewal_count = len(prescription.renewal_ids)

    def write(self, vals):
        # Le contenu d'une ordonnance emise est fige : seuls l'etat (
        # annulation) et les liens de renouvellement bougent encore.
        figees = self.filtered(lambda p: p.state != 'draft')
        if figees and set(vals) - {'state', 'renewal_ids'}:
            raise UserError(_(
                "L'ordonnance %s est émise : son contenu ne se modifie "
                "plus. Renouvelez-la ou annulez-la.")
                % figees[0].display_name)
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_draft_only(self):
        for prescription in self:
            if prescription.state != 'draft':
                raise UserError(_(
                    "Une ordonnance émise ou annulée ne se supprime "
                    "pas — l'histoire reste."))

    def action_issue(self):
        for prescription in self:
            if prescription.state != 'draft':
                raise UserError(
                    _("Seul un brouillon peut être émis."))
            if not prescription.line_ids:
                raise UserError(
                    _("Ajoutez au moins un médicament avant d'émettre."))
            # Un seul write, pendant que l'etat est encore brouillon :
            # la garde de write controle AVANT d'ecrire.
            prescription.write({
                'state': 'issued',
                'date_issued': fields.Date.context_today(prescription),
            })

    def action_cancel(self):
        for prescription in self:
            if prescription.state == 'cancelled':
                continue
            prescription.write({'state': 'cancelled'})

    def action_renew(self):
        """Renouvelle l'ordonnance : copie neuve en brouillon, datée du
        jour, chaînée à l'originale — les lignes suivent."""
        self.ensure_one()
        if self.state != 'issued':
            raise UserError(_("Seule une ordonnance émise se renouvelle."))
        copie = self.copy({
            'date': fields.Date.context_today(self),
            'renewal_of_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'megga.dental.prescription',
            'view_mode': 'form',
            'res_id': copie.id,
        }

    def action_view_renewals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Renouvellements"),
            'res_model': 'megga.dental.prescription',
            'view_mode': 'list,form',
            'domain': [('renewal_of_id', '=', self.id)],
        }


class MeggaDentalPrescriptionLine(models.Model):
    _name = 'megga.dental.prescription.line'
    _description = "Ligne d'ordonnance"
    _order = 'prescription_id, sequence, id'

    prescription_id = fields.Many2one(
        'megga.dental.prescription', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(default=10)
    medicament_id = fields.Many2one(
        'megga.dental.medicament', string="Référentiel",
        ondelete='restrict')
    name = fields.Char(
        "Médicament", required=True,
        compute='_compute_name', store=True, readonly=False,
        precompute=True)
    posology = fields.Char(
        "Posologie", required=True,
        compute='_compute_posology', store=True, readonly=False,
        precompute=True,
        help="3 × par jour pendant 5 jours, après les repas…")
    quantity = fields.Integer("Quantité", default=1, required=True)
    note = fields.Char("Remarque")

    @api.depends('medicament_id')
    def _compute_name(self):
        for line in self:
            if line.medicament_id:
                medicament = line.medicament_id
                parts = [medicament.name, medicament.dosage, medicament.form]
                line.name = " ".join(part for part in parts if part)
            else:
                line.name = line.name

    @api.depends('medicament_id')
    def _compute_posology(self):
        for line in self:
            if line.medicament_id and line.medicament_id.default_posology:
                line.posology = line.medicament_id.default_posology
            else:
                line.posology = line.posology

    def _guard_frozen(self):
        for line in self:
            if line.prescription_id.state != 'draft':
                raise UserError(_(
                    "L'ordonnance %s est émise : ses lignes ne bougent "
                    "plus.") % line.prescription_id.display_name)

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
