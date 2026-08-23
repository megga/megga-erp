import logging

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged

_logger = logging.getLogger(__name__)


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestQrForeignDebtor(AccountTestInvoicingCommon):
    """Structure calquée sur l10n_ch/tests/test_l10n_ch_qr_print.py (amont),
    pour rester alignée sur les conventions de la localisation."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        # Le controle amont exige une adresse postale complete du CREANCIER
        # (partenaire de la societe) — une vraie societe en a une.
        cls.env.company.partner_id.write({
            'street': 'Rue du Stand 1',
            'zip': '1204',
            'city': 'Geneve',
            'country_id': cls.env.ref('base.ch').id,
        })
        cls.qr_bank_account = cls.env['res.partner.bank'].create({
            'acc_number': "CH4431999123000889012",
            'partner_id': cls.env.company.partner_id.id,
            'allow_out_payment': True,
        })
        cls.partner_ch = cls.env['res.partner'].create({
            'name': 'Client Suisse',
            'street': 'Bahnhofstrasse 1',
            'zip': '8001',
            'city': 'Zurich',
            'country_id': cls.env.ref('base.ch').id,
        })
        cls.partner_fr = cls.env['res.partner'].create({
            'name': 'Client Export',
            'street': '12 Rue de la Paix',
            'zip': '75002',
            'city': 'Paris',
            'country_id': cls.env.ref('base.fr').id,
        })

    def _invoice(self, partner):
        return self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'partner_bank_id': self.qr_bank_account.id,
            'currency_id': self.env.ref('base.CHF').id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [(0, 0, {'product_id': self.product_a.id})],
        })

    def _print_qr_bill(self, invoice):
        try:
            invoice.action_invoice_sent()
            return True
        except UserError as e:
            _logger.warning(str(e))
            return False

    def test_foreign_debtor_gets_qr(self):
        """Un débiteur étranger à l'adresse complète reçoit une QR-facture."""
        invoice = self._invoice(self.partner_fr)
        invoice.action_post()
        self.assertTrue(
            invoice.l10n_ch_is_qr_valid,
            "Adresse complète + pays FR : la QR-facture doit être valide (norme SIX)",
        )
        self.assertTrue(self._print_qr_bill(invoice))
        self.assertFalse(
            self.qr_bank_account._check_for_qr_code_errors(
                'ch_qr', invoice.amount_total, invoice.currency_id,
                self.partner_fr, "libre", invoice.payment_reference,
            ),
            "Aucune erreur ne doit bloquer l'impression pour un débiteur FR complet",
        )

    def test_swiss_debtor_still_qr(self):
        """Non-régression : le débiteur suisse reste QR-valide."""
        invoice = self._invoice(self.partner_ch)
        invoice.action_post()
        self.assertTrue(invoice.l10n_ch_is_qr_valid)

    def test_debtor_without_country_still_blocked(self):
        """Parité avec le test amont : partner_a (sans adresse ni pays)
        reste non-QR — le garde sur le pays manquant est conservé."""
        invoice = self._invoice(self.partner_a)
        invoice.action_post()
        self.assertFalse(invoice.l10n_ch_is_qr_valid)
