import base64

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import file_open


@tagged('post_install', '-at_install')
class TestCamtImport(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.company_data['default_journal_bank']
        cls.journal.bank_account_id = cls.env['res.partner.bank'].create({
            'acc_number': 'CH4431999123000889012',
            'partner_id': cls.env.company.partner_id.id,
        })

    def _fixture(self, name, transform=None):
        with file_open('megga_camt/tests/fixtures/%s' % name, 'rb') as handle:
            data = handle.read()
        if transform:
            data = transform(data)
        return self.env['ir.attachment'].create({
            'name': name,
            'datas': base64.b64encode(data),
        })

    def _run(self, *attachments):
        wizard = self.env['megga.camt.import.wizard'].create({
            'journal_id': self.journal.id,
            'attachment_ids': [(6, 0, [a.id for a in attachments])],
        })
        return wizard.action_import()

    def test_import_camt053(self):
        self._run(self._fixture('camt053_releve.xml'))
        statement = self.env['account.bank.statement'].search(
            [('name', '=', 'MEGGA-053-0001')])
        self.assertEqual(len(statement), 1)
        self.assertEqual(statement.journal_id, self.journal)
        self.assertAlmostEqual(statement.balance_start, 1000.00)
        self.assertAlmostEqual(statement.balance_end_real, 1650.00)
        self.assertEqual(len(statement.line_ids), 3)
        self.assertEqual(sorted(statement.line_ids.mapped('amount')),
                         [-50.0, 300.0, 400.0])
        credit_400 = statement.line_ids.filtered(lambda l: l.amount == 400.0)
        self.assertEqual(credit_400.partner_name, 'Alice Favre')
        self.assertEqual(len(credit_400.ref), 27)   # référence QRR
        self.assertEqual(credit_400.megga_import_ref, 'SVCR-N1-01')

    def test_import_camt054_batch(self):
        self._run(self._fixture('camt054_avis_credit_qrr.xml'))
        statement = self.env['account.bank.statement'].search(
            [('name', '=', 'MEGGA-054-0001')])
        self.assertEqual(len(statement.line_ids), 3)
        self.assertTrue(all(l.amount == 300.0 for l in statement.line_ids))
        self.assertTrue(all(len(l.ref) == 27 for l in statement.line_ids))

    def test_reimport_is_idempotent(self):
        self._run(self._fixture('camt053_releve.xml'))
        with self.assertRaises(UserError):
            self._run(self._fixture('camt053_releve.xml'))
        self.assertEqual(self.env['account.bank.statement'].search_count(
            [('name', '=', 'MEGGA-053-0001')]), 1)

    def test_currency_guard(self):
        attachment = self._fixture(
            'camt053_releve.xml',
            transform=lambda d: d.replace(b'CHF', b'EUR'))
        with self.assertRaises(UserError):
            self._run(attachment)

    def test_iban_guard(self):
        attachment = self._fixture(
            'camt053_releve.xml',
            transform=lambda d: d.replace(
                b'CH4431999123000889012</IBAN></Id><Ccy>',
                b'CH9300762011623852957</IBAN></Id><Ccy>'))
        with self.assertRaises(UserError):
            self._run(attachment)
