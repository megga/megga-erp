from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    """L'apporteur d'affaires se note UNE fois, sur le contact : chaque
    facture client de ce contact le propose ensuite d'elle-même — c'est
    ce qui rend le décompte « à verser » exhaustif sans discipline de
    saisie au quotidien."""
    _inherit = 'res.partner'

    referrer_id = fields.Many2one(
        'res.partner', string="Apporteur d'affaires",
        index='btree_not_null',
        help="Qui a amené ce client. Proposé automatiquement sur ses"
             " factures ; la commission se décompte dans"
             " Comptabilité > Rétrocessions.")

    @api.constrains('referrer_id')
    def _check_referrer(self):
        for partner in self:
            if partner.referrer_id == partner:
                raise ValidationError(
                    _("Un contact ne peut pas être son propre apporteur."))
