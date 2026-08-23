from odoo import api, models

from ..afc import montant_suisse


class DecompteReport(models.AbstractModel):
    _name = 'report.megga_tva_ch.decompte_template'
    _description = "Rendu du décompte TVA AFC"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['megga.tva.decompte.wizard'].browse(docids)
        wizard.ensure_one()
        rows, _values = wizard._compute_rubriques()
        return {
            'doc_ids': docids,
            'doc_model': 'megga.tva.decompte.wizard',
            'docs': wizard,
            'wizard': wizard,
            'rows': rows,
            'fmt': montant_suisse,
        }
