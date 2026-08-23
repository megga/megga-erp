from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestTakeawayVat(AccountTestInvoicingCommon):
    """La dualité suisse de la restauration : sur place 8.1 % (TN),
    à l'emporter 2.6 % (TR, art. 25 LTVA) — portée par une taxe de
    remplacement dédiée et le preset À l'emporter de la caisse."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.ChartTemplate = cls.env['account.chart.template'].with_company(
            cls.company)
        cls.tax_81 = cls.ChartTemplate.ref('vat_sale_81')
        cls.tax_26 = cls.ChartTemplate.ref('vat_sale_26')
        cls.fp = cls.company._megga_setup_takeaway_vat()
        cls.takeaway_tax = cls.ChartTemplate.ref('megga_takeaway_tax')
        cls.pizza = cls.env['product.product'].create({
            'name': "Pizza margherita", 'type': 'consu',
            'list_price': 20.0,
            'taxes_id': [Command.set(cls.tax_81.ids)]})

    def _facture(self, **kw):
        vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2026-09-10',
            'invoice_line_ids': [Command.create({
                'product_id': self.pizza.id,
                'quantity': 1.0,
                'price_unit': 20.0,
            })],
        }
        vals.update(kw)
        return self.env['account.move'].create(vals)

    def test_position_et_taxe_creees(self):
        self.assertTrue(self.fp)
        self.assertEqual(self.fp.company_id, self.company)
        self.assertAlmostEqual(self.takeaway_tax.amount, 2.6)
        self.assertEqual(self.takeaway_tax.type_tax_use, 'sale')
        self.assertEqual(self.takeaway_tax.fiscal_position_ids, self.fp,
                         "la taxe de remplacement est scellée à la "
                         "position à l'emporter")
        self.assertEqual(self.takeaway_tax.original_tax_ids, self.tax_81,
                         "elle remplace la TVA due à 8.1% (TN)")

    def test_idempotente(self):
        taxes_avant = self.env['account.tax'].search_count(
            [('company_id', '=', self.company.id)])
        fp2 = self.company._megga_setup_takeaway_vat()
        self.assertEqual(fp2, self.fp, "pas de doublon de position")
        self.assertEqual(
            self.env['account.tax'].search_count(
                [('company_id', '=', self.company.id)]),
            taxes_avant, "pas de doublon de taxe")

    def test_correspondance(self):
        self.assertEqual(self.fp.map_tax(self.tax_81), self.takeaway_tax)

    def test_facture_sur_place_puis_emporter(self):
        sur_place = self._facture()
        self.assertAlmostEqual(sur_place.amount_untaxed, 20.0)
        self.assertAlmostEqual(sur_place.amount_tax, 1.62)   # 8.1 %
        emporter = self._facture(fiscal_position_id=self.fp.id)
        self.assertEqual(
            emporter.invoice_line_ids.tax_ids, self.takeaway_tax)
        self.assertAlmostEqual(emporter.amount_tax, 0.52)    # 2.6 %
        self.assertAlmostEqual(emporter.amount_total, 20.52)

    def test_grilles_du_decompte_conservees(self):
        """La copie garde les grilles AFC du taux réduit : les ventes à
        l'emporter tombent en 313a du décompte, comme toute vente au
        taux réduit."""
        def grilles(tax):
            return sorted(tax.invoice_repartition_line_ids
                          .mapped('tag_ids.name'))
        self.assertEqual(grilles(self.takeaway_tax), grilles(self.tax_26))
        self.assertTrue(any('313' in nom
                            for nom in grilles(self.takeaway_tax)))

    def test_preset_de_caisse_relie(self):
        preset = self.env.ref('pos_restaurant.pos_takeout_preset').sudo()
        self.assertEqual(preset.fiscal_position_id, self.fp,
                         "le mode À l'emporter de la caisse applique la "
                         "position fiscale")

    def test_societe_sans_plan_suisse(self):
        autre = self.env['res.company'].sudo().create(
            {'name': "Sans plan comptable"})
        self.assertFalse(autre._megga_setup_takeaway_vat(),
                         "sans plan suisse : ne fait rien, ne casse rien")
