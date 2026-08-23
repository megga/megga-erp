from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    megga_pain_msg_id = fields.Char(
        string="Message pain.001",
        index='btree_not_null',
        copy=False,
        readonly=True,
        help="MsgId du fichier pain.001 dans lequel ce paiement a été "
             "exporté. Protège contre un double envoi à la banque.",
    )
