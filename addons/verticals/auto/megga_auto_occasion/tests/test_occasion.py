from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestOccasion(AccountTestInvoicingCommon):
    """Reprise -> stock -> revente sur plan comptable suisse : l'impôt
    préalable fictif de la voie ordinaire, la marge de l'art. 24a pour
    les pièces de collection, et le parc clients qui suit le nouveau
    propriétaire."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        # Décor fleet en sudo : marques et modèles sont réservés à
        # Fleet/Administrateur (même leçon que l'atelier).
        brand = cls.env['fleet.vehicle.model.brand'].sudo().create({
            'name': "Volvo"})
        model = cls.env['fleet.vehicle.model'].sudo().create({
            'name': "V70", 'brand_id': brand.id})
        cls.seller = cls.partner_a
        cls.buyer = cls.partner_b
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': model.id,
            'license_plate': "FR 380 216",
            'megga_owner_id': cls.seller.id,
        })
        cls.Occasion = cls.env['megga.auto.occasion']

    def _occasion(self, **kw):
        vals = {
            'vehicle_id': self.vehicle.id,
            'seller_id': self.seller.id,
            'buy_date': '2026-09-01',
            'buy_price': 10000.0,
            'buyer_id': self.buyer.id,
            'sale_price': 12900.0,
        }
        vals.update(kw)
        return self.Occasion.create(vals)

    def test_sequence_et_flux(self):
        occasion = self._occasion()
        self.assertTrue(occasion.name.startswith('OCC/'))
        self.assertEqual(occasion.state, 'draft')
        with self.assertRaises(UserError):
            occasion.action_sell()   # pas encore au stock
        occasion.action_buy()
        self.assertEqual(occasion.state, 'stock')
        occasion.action_sell()
        self.assertEqual(occasion.state, 'sold')
        self.assertTrue(occasion.sale_date, "la date de vente est posée")
        self.assertEqual(self.vehicle.megga_owner_id, self.buyer,
                         "le nouveau propriétaire entre au parc clients")

    def test_fictif_montants(self):
        occasion = self._occasion()
        self.assertAlmostEqual(occasion.fictive_tax_amount, 749.31)
        self.assertAlmostEqual(occasion.sale_vat_amount, 966.60)
        self.assertAlmostEqual(occasion.net_vat_amount, 217.29,
                               msg="la charge nette est la TVA de la "
                                   "marge, par construction")
        self.assertEqual(occasion.margin_vat_amount, 0.0)

    def test_marge_montants(self):
        occasion = self._occasion(
            regime='marge', buy_price=30000.0, sale_price=36000.0)
        self.assertAlmostEqual(occasion.margin_amount, 6000.0)
        self.assertAlmostEqual(occasion.margin_vat_amount, 449.58)
        self.assertEqual(occasion.fictive_tax_amount, 0.0)
        self.assertEqual(occasion.net_vat_amount, 0.0)

    def test_marge_negative_sans_credit(self):
        occasion = self._occasion(
            regime='marge', buy_price=30000.0, sale_price=25000.0)
        self.assertAlmostEqual(occasion.margin_amount, -5000.0)
        self.assertEqual(occasion.margin_vat_amount, 0.0)

    def test_facture_de_reprise_fictive(self):
        occasion = self._occasion()
        occasion.action_buy()
        occasion.action_create_purchase_bill()
        bill = occasion.purchase_bill_id
        self.assertEqual(bill.move_type, 'in_invoice')
        self.assertEqual(bill.partner_id, self.seller)
        self.assertAlmostEqual(bill.amount_total, 10000.0,
                               msg="le vendeur touche le prix convenu")
        self.assertAlmostEqual(bill.amount_tax, 749.31,
                               msg="l'impôt fictif est EXTRAIT du prix")
        self.assertAlmostEqual(bill.amount_untaxed, 9250.69)
        tax = bill.invoice_line_ids.tax_ids
        self.assertEqual(len(tax), 1)
        vat_purchase = self.env['account.chart.template'].with_company(
            self.env.company).ref('vat_purchase_81')
        self.assertEqual(
            sorted(tax.invoice_repartition_line_ids.mapped('tag_ids.name')),
            sorted(vat_purchase.invoice_repartition_line_ids
                   .mapped('tag_ids.name')),
            "la copie garde les grilles d'impôt préalable du décompte")

    def test_facture_de_reprise_marge_sans_deduction(self):
        occasion = self._occasion(
            regime='marge', buy_price=30000.0, sale_price=36000.0)
        occasion.action_buy()
        occasion.action_create_purchase_bill()
        bill = occasion.purchase_bill_id
        self.assertEqual(bill.amount_tax, 0.0,
                         "art. 24a : pas de déduction fictive")
        self.assertAlmostEqual(bill.amount_total, 30000.0)
        self.assertFalse(bill.invoice_line_ids.tax_ids)

    def test_facture_de_vente_fictive(self):
        occasion = self._occasion()
        occasion.action_buy()
        occasion.action_sell()
        occasion.action_create_sale_invoice()
        invoice = occasion.sale_invoice_id
        self.assertEqual(invoice.move_type, 'out_invoice')
        self.assertAlmostEqual(invoice.amount_total, 12900.0,
                               msg="prix affiché = prix payé, TTC")
        self.assertAlmostEqual(invoice.amount_tax, 966.60)
        self.assertIn("FR 380 216", invoice.invoice_line_ids.name)

    def test_facture_de_vente_marge_sans_mention_de_tva(self):
        occasion = self._occasion(
            regime='marge', buy_price=30000.0, sale_price=36000.0)
        occasion.action_buy()
        occasion.action_sell()
        occasion.action_create_sale_invoice()
        invoice = occasion.sale_invoice_id
        self.assertEqual(invoice.amount_tax, 0.0,
                         "art. 24a : la facture ne mentionne pas la TVA")
        self.assertAlmostEqual(invoice.amount_total, 36000.0)
        self.assertFalse(invoice.invoice_line_ids.tax_ids)
        self.assertIn("24a", invoice.narration)

    def test_double_facturation_bloquee(self):
        occasion = self._occasion()
        occasion.action_buy()
        occasion.action_create_purchase_bill()
        with self.assertRaises(UserError):
            occasion.action_create_purchase_bill()
        with self.assertRaises(UserError):
            occasion.action_create_sale_invoice()   # pas encore vendue
        occasion.action_sell()
        occasion.action_create_sale_invoice()
        with self.assertRaises(UserError):
            occasion.action_create_sale_invoice()

    def test_taxes_idempotentes(self):
        company = self.env.company
        taxes_1 = company._megga_setup_occasion_taxes()
        avant = self.env['account.tax'].search_count(
            [('company_id', '=', company.id)])
        taxes_2 = company._megga_setup_occasion_taxes()
        self.assertEqual(taxes_1, taxes_2)
        self.assertEqual(
            self.env['account.tax'].search_count(
                [('company_id', '=', company.id)]),
            avant, "pas de doublon de taxes")
