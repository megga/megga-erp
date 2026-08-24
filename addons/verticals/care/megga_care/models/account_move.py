from odoo import _, api, fields, models


class AccountMove(models.Model):
    """Depuis la facture fournisseur, voir les événements de mandat
    qu'elle couvre : le geste quotidien de la conciergerie — la pièce
    arrive par e-mail, on la saisit, on la rattache à l'événement — se
    vérifie dans les deux sens."""
    _inherit = 'account.move'

    care_event_ids = fields.One2many(
        'megga.care.event', 'supplier_invoice_id',
        string="Événements de mandat couverts")
    care_event_count = fields.Integer(
        compute='_compute_care_event_count')

    @api.depends('care_event_ids')
    def _compute_care_event_count(self):
        for move in self:
            move.care_event_count = len(move.care_event_ids)

    def action_view_care_events(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Événements de mandat"),
            'res_model': 'megga.care.event',
            'view_mode': 'list,form',
            'domain': [('supplier_invoice_id', '=', self.id)],
        }
