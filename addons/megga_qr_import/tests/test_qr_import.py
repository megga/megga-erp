from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged

from ..qr_parser import parse_spc
from .test_qr_parser import QR_IBAN, QRR, payload


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestQrImport(AccountTestInvoicingCommon):
    """Le chemin complet de Nathalie : l'e-mail crée le brouillon (cadre
    du cœur), la QR le remplit — créancier par IBAN, compte bancaire,
    montant, référence — sans jamais écraser une saisie."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        cls.Move = cls.env['account.move']

    def _bill(self, **kw):
        vals = {'move_type': 'in_invoice'}
        vals.update(kw)
        return self.Move.create(vals)

    def _attach(self, move, contenu, mimetype='text/plain'):
        return self.env['ir.attachment'].create({
            'name': "facture-qr.txt",
            'raw': contenu.encode('utf-8'),
            'mimetype': mimetype,
            'res_model': 'account.move',
            'res_id': move.id,
        })

    def test_remplit_un_brouillon_vide(self):
        facture = self._bill()
        facture._megga_qr_apply(parse_spc(payload()))
        partenaire = facture.partner_id
        self.assertEqual(partenaire.name, "Max Muster & Söhne",
                         "créancier inconnu : créé depuis la charge")
        self.assertEqual(partenaire.city, "Seldwyla")
        self.assertEqual(partenaire.country_id.code, 'CH')
        self.assertEqual(facture.partner_bank_id.partner_id, partenaire)
        self.assertEqual(
            facture.partner_bank_id.sanitized_acc_number, QR_IBAN)
        self.assertEqual(len(facture.invoice_line_ids), 1)
        self.assertAlmostEqual(facture.invoice_line_ids.price_unit, 1949.75)
        self.assertEqual(facture.payment_reference, QRR,
                         "la référence QRR nourrit le mémo de paiement"
                         " — et donc l'ordre pain.001")

    def test_rapproche_par_iban(self):
        connu = self.env['res.partner'].create({'name': "Labo Connu"})
        self.env['res.partner.bank'].create({
            'acc_number': QR_IBAN, 'partner_id': connu.id})
        avant = self.env['res.partner'].search_count([])
        facture = self._bill()
        facture._megga_qr_apply(parse_spc(payload()))
        self.assertEqual(facture.partner_id, connu,
                         "l'IBAN identifie le créancier existant")
        self.assertEqual(self.env['res.partner'].search_count([]), avant,
                         "aucun doublon de contact")

    def test_n_ecrase_jamais(self):
        choisi = self.env['res.partner'].create({'name': "Fournisseur Choisi"})
        facture = self._bill(
            partner_id=choisi.id,
            payment_reference="SAISIE-MANUELLE",
            invoice_line_ids=[Command.create({
                'name': "Ligne saisie", 'quantity': 1.0,
                'price_unit': 99.0})],
        )
        facture._megga_qr_apply(parse_spc(payload()))
        self.assertEqual(facture.partner_id, choisi)
        self.assertEqual(facture.payment_reference, "SAISIE-MANUELLE")
        self.assertEqual(len(facture.invoice_line_ids), 1)
        self.assertAlmostEqual(facture.invoice_line_ids.price_unit, 99.0)
        # Seul ajout non destructif : le compte du créancier, pour payer.
        self.assertEqual(
            facture.partner_bank_id.sanitized_acc_number, QR_IBAN)

    def test_decodeur_de_bout_en_bout(self):
        """Par le cadre du cœur (_extend_with_attachments), comme quand
        la pièce arrive par l'alias e-mail du journal d'achat."""
        facture = self._bill()
        piece = self._attach(facture, payload())
        facture._extend_with_attachments(
            facture._to_files_data(piece), new=False)
        self.assertEqual(facture.partner_id.name, "Max Muster & Söhne")
        self.assertAlmostEqual(facture.amount_untaxed, 1949.75)
        self.assertEqual(facture.payment_reference, QRR)

    def test_ignore_les_factures_client(self):
        facture = self.Move.create({'move_type': 'out_invoice'})
        piece = self._attach(facture, payload())
        facture._extend_with_attachments(
            facture._to_files_data(piece), new=False)
        self.assertFalse(facture.partner_id,
                         "la QR ne concerne que les pièces d'achat")

    def test_charge_malformee_ignoree(self):
        facture = self._bill()
        piece = self._attach(facture, payload(**{'1': '0100'}))
        facture._extend_with_attachments(
            facture._to_files_data(piece), new=False)
        self.assertFalse(facture.partner_id)
        self.assertFalse(facture.invoice_line_ids,
                         "charge non conforme : rejetée, jamais devinée")
