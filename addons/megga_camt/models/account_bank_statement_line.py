from odoo import fields, models


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    megga_import_ref = fields.Char(
        string="Référence d'import camt",
        index='btree_not_null',
        copy=False,
        readonly=True,
        help="Identifiant unique de la transaction dans le fichier camt "
             "(AcctSvcrRef, EndToEndId ou clé de repli), utilisé pour la "
             "déduplication lors des ré-imports.",
    )
