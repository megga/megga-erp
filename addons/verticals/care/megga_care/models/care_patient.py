from odoo import _, api, fields, models


class MeggaCarePatient(models.Model):
    """Le client VIP délègue son identité à res.partner (_inherits) : il a
    d'emblée nom, pays, téléphone, e-mail — et surtout il est facturable
    tel quel, donc la chaîne du socle (facture -> QR-facture, y compris
    pour un débiteur domicilié à l'étranger -> encaissement camt)
    s'applique sans pont supplémentaire. Le pays du contact porte aussi le
    régime TVA (position fiscale : étranger hors TVA, Suisse avec)."""
    _name = 'megga.care.patient'
    _description = "Client de la conciergerie médicale"
    _inherits = {'res.partner': 'partner_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code desc'

    partner_id = fields.Many2one(
        'res.partner', string="Contact lié", required=True,
        ondelete='cascade', index=True)
    code = fields.Char(
        "N° de client", readonly=True, copy=False, default='/')
    # `active` propre au client : archiver un dossier ne doit pas archiver
    # le contact, qui peut rester débiteur de factures ouvertes.
    active = fields.Boolean(default=True)
    user_id = fields.Many2one(
        'res.users', string="Responsable",
        default=lambda self: self.env.user)
    # Parcours de santé : données personnelles SENSIBLES (art. 5 nLPD).
    # groups= sur le champ = protection par l'ORM lui-même — l'assistance
    # ne peut ni les lire ni les écrire, quelles que soient les vues.
    medical_notes = fields.Text(
        "Parcours de santé", groups="megga_care.group_care_coordination")

    mandate_ids = fields.One2many(
        'megga.care.mandate', 'patient_id', string="Mandats")
    mandate_count = fields.Integer(compute='_compute_mandate_count')

    _code_uniq = models.Constraint(
        'unique(code)', "Ce numéro de client existe déjà.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') or vals['code'] == '/':
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'megga.care.patient') or '/'
        return super().create(vals_list)

    @api.depends('mandate_ids')
    def _compute_mandate_count(self):
        for patient in self:
            patient.mandate_count = len(patient.mandate_ids)

    def action_view_mandates(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Mandats"),
            'res_model': 'megga.care.mandate',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }
