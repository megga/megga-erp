from odoo import api, fields, models


class AccountMove(models.Model):
    """La facture client porte l'apporteur d'affaires : c'est lui qui
    fait entrer la facture dans le volume d'un décompte « à verser ».
    Proposé depuis le contact au choix du client, toujours ajustable —
    et conservé à la duplication comme à l'extourne, pour que l'avoir
    se déduise du même volume que sa facture."""
    _inherit = 'account.move'

    referrer_id = fields.Many2one(
        'res.partner', string="Apporteur d'affaires",
        compute='_compute_referrer_id', store=True, readonly=False,
        precompute=True, index='btree_not_null',
        help="Ce client a été amené par cet apporteur : la facture"
             " compte dans le volume de sa commission.")

    @api.depends('partner_id')
    def _compute_referrer_id(self):
        for move in self:
            if (not move.referrer_id
                    and move.move_type in ('out_invoice', 'out_refund')
                    and move.partner_id.referrer_id):
                move.referrer_id = move.partner_id.referrer_id
            else:
                move.referrer_id = move.referrer_id
