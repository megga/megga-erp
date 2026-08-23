from odoo import Command, _, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _megga_setup_takeaway_vat(self):
        """Câble la TVA suisse à l'emporter pour cette société.

        En 19, une position fiscale ne porte plus de table de
        correspondance : c'est la taxe de REMPLACEMENT qui déclare ce
        qu'elle remplace (original_tax_ids) et où (fiscal_position_ids)
        — même patron que l10n_be_pos_restaurant du cœur. On copie donc
        la TVA due à 2.6% (TR) en taxe « à l'emporter » dédiée : les
        grilles du décompte AFC (313a) suivent la copie, et les ventes à
        l'emporter restent distinguables des autres ventes au taux
        réduit.

        Idempotente (les enregistrements portent des xml_ids de société,
        comme le fait le plan comptable). Sans plan comptable suisse :
        ne fait rien et renvoie False. Le preset « À l'emporter » de la
        caisse est un enregistrement GLOBAL de pos_restaurant : il n'est
        relié qu'une fois, à la première société câblée (déploiements
        mono-société — le nôtre).
        """
        self.ensure_one()
        if not (self.chart_template or '').startswith('ch'):
            return False
        ChartTemplate = self.env['account.chart.template'].with_company(self)
        tax_81 = ChartTemplate.ref('vat_sale_81', raise_if_not_found=False)
        tax_26 = ChartTemplate.ref('vat_sale_26', raise_if_not_found=False)
        if not tax_81 or not tax_26:
            return False

        fp = ChartTemplate.ref('megga_takeaway_fp', raise_if_not_found=False)
        if not fp:
            fp = self.env['account.fiscal.position'].create({
                'name': _("Vente à l'emporter (TVA 2.6%)"),
                'company_id': self.id,
                'note': _(
                    "Livraison de denrées alimentaires au taux réduit "
                    "(art. 25 al. 2 LTVA). Suppose des tickets distincts "
                    "par mode de vente — c'est ce que fait la caisse via "
                    "le preset À l'emporter."),
            })
            self.env['ir.model.data']._update_xmlids([{
                'xml_id': ChartTemplate.company_xmlid(
                    'megga_takeaway_fp', self),
                'record': fp,
                'noupdate': True,
            }])

        takeaway_tax = ChartTemplate.ref(
            'megga_takeaway_tax', raise_if_not_found=False)
        if not takeaway_tax:
            takeaway_tax = tax_26.copy({
                'name': _("TVA due à 2.6% (TR) — à l'emporter"),
                'fiscal_position_ids': [Command.set(fp.ids)],
                'original_tax_ids': [Command.set(tax_81.ids)],
            })
            self.env['ir.model.data']._update_xmlids([{
                'xml_id': ChartTemplate.company_xmlid(
                    'megga_takeaway_tax', self),
                'record': takeaway_tax,
                'noupdate': True,
            }])

        # En sudo : relier le preset est un effet système du câblage —
        # l'appelant (un comptable, le hook d'installation) n'a pas
        # forcément les droits caisse sur pos.preset.
        preset = self.env.ref(
            'pos_restaurant.pos_takeout_preset', raise_if_not_found=False)
        if preset:
            preset = preset.sudo()
            if not preset.fiscal_position_id:
                preset.fiscal_position_id = fp
        return fp
