from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDecompteTva(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.tax_sale_81 = cls.env['account.tax'].search([
            ('company_id', '=', company.id),
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', 8.1),
        ], limit=1)
        cls.tax_purchase_81 = cls.env['account.tax'].search([
            ('company_id', '=', company.id),
            ('type_tax_use', '=', 'purchase'),
            ('amount', '=', 8.1),
        ], limit=1)
        assert cls.tax_sale_81 and cls.tax_purchase_81, \
            "taxes 8.1% absentes du plan comptable suisse"

    def _move(self, move_type, partner, amount, tax, invoice_date):
        move = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': partner.id,
            'invoice_date': invoice_date,
            'date': invoice_date,
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 1,
                'price_unit': amount,
                'tax_ids': [Command.set(tax.ids)],
            })],
        })
        move.action_post()
        return move

    def _values(self, date_from='2026-01-01', date_to='2026-03-31'):
        wizard = self.env['megga.tva.decompte.wizard'].create({
            'date_from': date_from,
            'date_to': date_to,
        })
        _rows, values = wizard._compute_rubriques()
        return values

    def test_decompte_facture_et_fournisseur(self):
        self._move('out_invoice', self.partner_a, 1000.0,
                   self.tax_sale_81, '2026-02-10')
        self._move('in_invoice', self.partner_a, 500.0,
                   self.tax_purchase_81, '2026-02-15')
        values = self._values()
        self.assertAlmostEqual(values['tax_ch_303a'], 1000.0)     # base 8.1%
        self.assertAlmostEqual(values['tax_ch_303b'], 81.0)       # TVA due
        self.assertAlmostEqual(values['tax_ch_200'], 1000.0)      # CA total
        self.assertAlmostEqual(values['tax_ch_399'], 81.0)        # total dû
        self.assertAlmostEqual(values['tax_ch_479'], 40.5)        # imp. préalable
        # 500 = max(0, 399-479) ; 510 = max(0, 479-399)
        self.assertAlmostEqual(values['tax_ch_399'] - values['tax_ch_479'], 40.5)

    def test_rubriques_500_510(self):
        self._move('out_invoice', self.partner_a, 1000.0,
                   self.tax_sale_81, '2026-02-10')
        rows, values = self.env['megga.tva.decompte.wizard'].create({
            'date_from': '2026-01-01', 'date_to': '2026-03-31',
        })._compute_rubriques()
        par_nom = {r['name']: r['value'] for r in rows}
        ligne_500 = next(v for n, v in par_nom.items() if n.startswith('500'))
        ligne_510 = next(v for n, v in par_nom.items() if n.startswith('510'))
        self.assertAlmostEqual(ligne_500, 81.0)
        self.assertAlmostEqual(ligne_510, 0.0)

    def test_periode_filtre(self):
        self._move('out_invoice', self.partner_a, 1000.0,
                   self.tax_sale_81, '2026-02-10')
        values = self._values('2026-04-01', '2026-06-30')
        self.assertAlmostEqual(values['tax_ch_303a'], 0.0)
        self.assertAlmostEqual(values['tax_ch_399'], 0.0)

    def test_avoir_diminue_le_decompte(self):
        self._move('out_invoice', self.partner_a, 1000.0,
                   self.tax_sale_81, '2026-02-10')
        self._move('out_refund', self.partner_a, 200.0,
                   self.tax_sale_81, '2026-02-20')
        values = self._values()
        self.assertAlmostEqual(values['tax_ch_303a'], 800.0)
        self.assertAlmostEqual(values['tax_ch_303b'], 64.8)
