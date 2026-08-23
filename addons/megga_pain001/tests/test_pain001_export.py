import base64
import xml.etree.ElementTree as ET

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged

NS = {'p': 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.09'}
QRR = '210000000003139471430009017'   # checksum mod10r valide


@tagged('post_install', '-at_install')
class TestPain001Export(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.company_data['default_journal_bank']
        cls.journal.bank_account_id = cls.env['res.partner.bank'].create({
            'acc_number': 'CH9300762011623852957',
            'partner_id': cls.env.company.partner_id.id,
        })
        cls.supplier = cls.env['res.partner'].create({
            'name': 'Menuiserie Golay Sarl',
            'street': 'Grand-Rue 12',
            'zip': '1347',
            'city': 'Le Sentier',
            'country_id': cls.env.ref('base.ch').id,
        })
        cls.supplier_qr_account = cls.env['res.partner.bank'].create({
            'acc_number': 'CH4431999123000889012',   # QR-IBAN
            'partner_id': cls.supplier.id,
            'allow_out_payment': True,
        })

    def _payment(self, memo, amount=400.0, bank=None):
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.supplier.id,
            'partner_bank_id': (bank or self.supplier_qr_account).id,
            'journal_id': self.journal.id,
            'amount': amount,
            'currency_id': self.env.ref('base.CHF').id,
            'memo': memo,
        })
        payment.action_post()
        return payment

    def _export(self, payments, **extra):
        wizard = self.env['megga.pain001.export.wizard'].create({
            'journal_id': self.journal.id,
            'payment_ids': [(6, 0, payments.ids)],
            **extra,
        })
        action = wizard.action_export()
        attachment_id = int(action['url'].split('/web/content/')[1].split('?')[0])
        attachment = self.env['ir.attachment'].browse(attachment_id)
        return ET.fromstring(base64.b64decode(attachment.datas))

    def test_export_qrr(self):
        payment = self._payment(QRR)
        root = self._export(payment)
        self.assertEqual(root.findtext('.//p:GrpHdr/p:NbOfTxs', namespaces=NS), '1')
        self.assertEqual(root.findtext('.//p:CdtrRefInf/p:Tp/p:CdOrPrtry/p:Prtry',
                                       namespaces=NS), 'QRR')
        self.assertEqual(root.findtext('.//p:CdtrRefInf/p:Ref', namespaces=NS), QRR)
        self.assertEqual(root.findtext('.//p:DbtrAcct/p:Id/p:IBAN', namespaces=NS),
                         'CH9300762011623852957')
        self.assertTrue(payment.megga_pain_msg_id)

    def test_reexport_blocked_then_forced(self):
        payment = self._payment(QRR)
        self._export(payment)
        with self.assertRaises(UserError):
            self._export(payment)
        root = self._export(payment, force_reexport=True)
        self.assertEqual(root.findtext('.//p:GrpHdr/p:NbOfTxs', namespaces=NS), '1')

    def test_qr_iban_without_qrr_is_refused(self):
        payment = self._payment('Facture 2026-0788')   # mémo libre, QR-IBAN
        with self.assertRaises(UserError):
            self._export(payment)

    def test_unstructured_message_on_normal_iban(self):
        normal_account = self.env['res.partner.bank'].create({
            'acc_number': 'CH5604835012345678009',
            'partner_id': self.supplier.id,
            'allow_out_payment': True,
        })
        payment = self._payment('Facture 2026-0788', bank=normal_account)
        root = self._export(payment)
        self.assertEqual(root.findtext('.//p:RmtInf/p:Ustrd', namespaces=NS),
                         'Facture 2026-0788')

    def test_missing_partner_bank_is_refused(self):
        payment = self._payment(QRR)
        payment_no_bank = payment.copy({'partner_bank_id': False, 'memo': QRR})
        payment_no_bank.action_post()
        with self.assertRaises(UserError):
            self._export(payment | payment_no_bank)
