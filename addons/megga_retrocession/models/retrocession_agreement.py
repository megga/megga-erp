from odoo import _, api, fields, models


class MeggaRetrocessionAgreement(models.Model):
    """L'accord fixe le partenaire, le sens et le taux — le cadre
    négocié. Les chiffres, eux, vivent dans les décomptes : l'accord peut
    évoluer (renégociation) sans réécrire l'historique, chaque décompte
    ayant figé le taux en vigueur à sa création."""
    _name = 'megga.retrocession.agreement'
    _description = "Accord de rétrocession"
    _inherit = ['mail.thread']
    _order = 'partner_id, id'

    name = fields.Char("Nom de l'accord", required=True, tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string="Partenaire", required=True, index=True,
        tracking=True,
        help="Qui reverse (laboratoire, pharmacie, clinique) ou qui est"
             " commissionné (apporteur d'affaires).")
    direction = fields.Selection([
        ('receivable', "À encaisser — le partenaire nous reverse"),
        ('payable', "À verser — nous commissionnons l'apporteur"),
    ], string="Sens", required=True, default='receivable', tracking=True)
    rate = fields.Float(
        "Taux (%)", required=True, digits=(5, 2), tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    active = fields.Boolean(default=True)
    notes = fields.Text("Notes")

    settlement_ids = fields.One2many(
        'megga.retrocession.settlement', 'agreement_id',
        string="Décomptes")
    settlement_count = fields.Integer(compute='_compute_settlement_count')

    _rate_range = models.Constraint(
        'CHECK (rate > 0 AND rate <= 100)',
        "Le taux de rétrocession est un pour-cent entre 0 exclu et 100.")

    @api.depends('settlement_ids')
    def _compute_settlement_count(self):
        for agreement in self:
            agreement.settlement_count = len(agreement.settlement_ids)

    def action_view_settlements(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Décomptes"),
            'res_model': 'megga.retrocession.settlement',
            'view_mode': 'list,form',
            'domain': [('agreement_id', '=', self.id)],
            'context': {'default_agreement_id': self.id},
        }
