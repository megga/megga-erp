from odoo import _, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _megga_setup_occasion_taxes(self):
        """Les deux taxes du commerce d'occasion, pour cette société.

        - « TVA due à 8.1% (TN) — incluse » : copie de la TVA de vente
          au taux normal, incluse dans le prix (les occasions s'affichent
          et se vendent TTC) ;
        - « Impôt préalable fictif 8.1% (art. 28a LTVA) » : copie de la
          TVA d'achat au taux normal, incluse dans le prix — posée sur
          la facture de reprise d'un particulier, elle extrait la part
          déductible du prix payé et la porte aux grilles d'impôt
          préalable du décompte, comme la pratique AFC le prévoit.

        Idempotente (xml_ids de société, comme le plan comptable) ;
        renvoie (taxe_vente_ttc, taxe_fictive), ou False sans plan
        comptable suisse. Même patron que megga_resto_tva.
        """
        self.ensure_one()
        if not (self.chart_template or '').startswith('ch'):
            return False
        ChartTemplate = self.env['account.chart.template'].with_company(self)
        tax_sale = ChartTemplate.ref('vat_sale_81', raise_if_not_found=False)
        tax_purchase = ChartTemplate.ref(
            'vat_purchase_81', raise_if_not_found=False)
        if not tax_sale or not tax_purchase:
            return False

        sale_ttc = ChartTemplate.ref(
            'megga_occasion_sale_ttc', raise_if_not_found=False)
        if not sale_ttc:
            sale_ttc = tax_sale.copy({
                'name': _("TVA due à 8.1% (TN) — incluse"),
                'price_include_override': 'tax_included',
            })
            self.env['ir.model.data']._update_xmlids([{
                'xml_id': ChartTemplate.company_xmlid(
                    'megga_occasion_sale_ttc', self),
                'record': sale_ttc,
                'noupdate': True,
            }])

        fictive = ChartTemplate.ref(
            'megga_occasion_fictive', raise_if_not_found=False)
        if not fictive:
            fictive = tax_purchase.copy({
                'name': _("Impôt préalable fictif 8.1% (art. 28a LTVA)"),
                'price_include_override': 'tax_included',
            })
            self.env['ir.model.data']._update_xmlids([{
                'xml_id': ChartTemplate.company_xmlid(
                    'megga_occasion_fictive', self),
                'record': fictive,
                'noupdate': True,
            }])
        return sale_ttc, fictive
