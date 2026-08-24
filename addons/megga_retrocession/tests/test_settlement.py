from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSettlement(AccountTestInvoicingCommon):
    """Les deux faces de la rétrocession, sur le plan comptable suisse
    comme les tests du socle : la conciergerie ENCAISSE de la pharmacie
    (son volume de factures fournisseurs), le cabinet VERSE à
    l'apporteuse (le volume des factures clients qu'elle a amenées)."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        cls.pharmacie = Partner.create({'name': "Pharmacie du Bourg"})
        cls.labo = Partner.create({'name': "Laboratoire Central"})
        cls.apporteuse = Partner.create({'name': "Luxury Cares Services"})
        cls.patient = Partner.create({
            'name': "Karim Al-Test",
            'referrer_id': cls.apporteuse.id,
        })
        Agreement = cls.env['megga.retrocession.agreement']
        cls.accord_pharma = Agreement.create({
            'name': "Pharmacie du Bourg — 10 %",
            'partner_id': cls.pharmacie.id,
            'direction': 'receivable',
            'rate': 10.0,
        })
        cls.accord_apport = Agreement.create({
            'name': "Apport Luxury Cares — 8 %",
            'partner_id': cls.apporteuse.id,
            'direction': 'payable',
            'rate': 8.0,
        })

    def _move(self, move_type, partner, amount, invoice_date, post=True,
              **kw):
        vals = {
            'move_type': move_type,
            'partner_id': partner.id,
            'invoice_date': invoice_date,
            'invoice_line_ids': [Command.create({
                'name': "Prestation",
                'quantity': 1.0,
                'price_unit': amount,
            })],
        }
        vals.update(kw)
        move = self.env['account.move'].create(vals)
        if post:
            move.action_post()
        return move

    def _settlement(self, agreement, date_from, date_to):
        return self.env['megga.retrocession.settlement'].create({
            'agreement_id': agreement.id,
            'date_from': date_from,
            'date_to': date_to,
        })

    def test_encaisser_le_volume_de_la_pharmacie(self):
        """Le flux de la conciergerie : ses factures fournisseurs chez la
        pharmacie font le volume ; hors période, brouillons et autres
        partenaires ne comptent pas ; l'avoir se déduit."""
        self._move('in_invoice', self.pharmacie, 30000.0, '2026-01-15')
        self._move('in_invoice', self.pharmacie, 22000.0, '2026-03-10')
        self._move('in_refund', self.pharmacie, 2000.0, '2026-02-01')
        self._move('in_invoice', self.pharmacie, 5000.0, '2025-12-31')
        self._move('in_invoice', self.pharmacie, 9999.0, '2026-02-15',
                   post=False)
        self._move('in_invoice', self.labo, 7777.0, '2026-02-15')
        decompte = self._settlement(
            self.accord_pharma, '2026-01-01', '2026-06-30')
        self.assertTrue(decompte.name.startswith('RET/'))
        decompte.action_refresh()
        self.assertEqual(decompte.move_count, 3)
        self.assertAlmostEqual(decompte.volume, 50000.0)
        self.assertAlmostEqual(decompte.amount, 5000.0)
        decompte.action_confirm()
        self.assertEqual(decompte.state, 'confirmed')
        action = decompte.action_create_invoice()
        piece = decompte.invoice_id
        self.assertTrue(piece)
        self.assertEqual(action['res_id'], piece.id)
        self.assertEqual(piece.move_type, 'out_invoice',
                         "à encaisser : on facture le partenaire")
        self.assertEqual(piece.partner_id, self.pharmacie)
        self.assertAlmostEqual(piece.amount_untaxed, 5000.0)
        self.assertEqual(piece.invoice_origin, decompte.name)
        self.assertIn("10.00 %", piece.invoice_line_ids.name)
        self.assertEqual(decompte.state, 'invoiced')
        with self.assertRaises(UserError):
            decompte.action_create_invoice()

    def test_verser_la_commission_d_apport(self):
        """Le flux du cabinet : les factures clients marquées de
        l'apporteuse font le volume ; la pièce générée est une facture
        fournisseur provisionnée à son nom."""
        facture = self._move('out_invoice', self.patient, 8000.0,
                             '2026-01-20')
        self.assertEqual(facture.referrer_id, self.apporteuse,
                         "l'apporteuse du contact se propose d'elle-même")
        self._move('out_invoice', self.patient, 2000.0, '2026-02-20')
        self._move('out_refund', self.patient, 1000.0, '2026-03-01')
        self._move('out_invoice', self.pharmacie, 99999.0, '2026-02-05')
        decompte = self._settlement(
            self.accord_apport, '2026-01-01', '2026-03-31')
        decompte.action_confirm()
        self.assertEqual(decompte.move_count, 3)
        self.assertAlmostEqual(decompte.volume, 9000.0)
        self.assertAlmostEqual(decompte.amount, 720.0)
        decompte.action_create_invoice()
        piece = decompte.invoice_id
        self.assertEqual(piece.move_type, 'in_invoice',
                         "à verser : provision de la facture de l'apporteuse")
        self.assertEqual(piece.partner_id, self.apporteuse)
        self.assertEqual(piece.state, 'draft',
                         "la pièce reste à valider par la comptabilité")
        self.assertAlmostEqual(piece.amount_untaxed, 720.0)

    def test_apporteur_manuel_prime(self):
        """La proposition depuis le contact ne piétine jamais une saisie
        explicite, et un contact sans apporteur n'en reçoit aucun."""
        explicite = self._move(
            'out_invoice', self.patient, 100.0, '2026-04-01', post=False,
            referrer_id=self.labo.id)
        self.assertEqual(explicite.referrer_id, self.labo)
        sans = self._move(
            'out_invoice', self.pharmacie, 100.0, '2026-04-01', post=False)
        self.assertFalse(sans.referrer_id)

    def test_chevauchement_interdit(self):
        self._settlement(self.accord_pharma, '2026-01-01', '2026-03-31')
        with self.assertRaises(ValidationError):
            self._settlement(self.accord_pharma, '2026-03-31', '2026-06-30')
        # Le lendemain, lui, passe — et un autre accord n'est pas gêné.
        self._settlement(self.accord_pharma, '2026-04-01', '2026-06-30')
        self._settlement(self.accord_apport, '2026-01-01', '2026-06-30')
        with self.assertRaises(ValidationError):
            self._settlement(self.accord_pharma, '2026-08-01', '2026-07-01')

    def test_taux_fige(self):
        """La renégociation de l'accord ne réécrit pas l'historique : le
        décompte garde le taux en vigueur à sa création."""
        ancien = self._settlement(
            self.accord_pharma, '2026-01-01', '2026-03-31')
        self.assertAlmostEqual(ancien.rate, 10.0)
        self.accord_pharma.rate = 12.0
        self.assertAlmostEqual(ancien.rate, 10.0)
        nouveau = self._settlement(
            self.accord_pharma, '2026-04-01', '2026-06-30')
        self.assertAlmostEqual(nouveau.rate, 12.0)

    def test_jamais_compte_deux_fois(self):
        """La ceinture au-delà des périodes disjointes : une facture dont
        la date a été corrigée après coup reste attachée à son premier
        décompte et n'entre jamais dans un second."""
        piece = self._move('in_invoice', self.pharmacie, 1000.0,
                           '2026-01-31')
        janvier = self._settlement(
            self.accord_pharma, '2026-01-01', '2026-01-31')
        janvier.action_refresh()
        self.assertEqual(janvier.move_ids, piece)
        # La date est corrigée après coup : la pièce glisse en février.
        # Le numéro repart de zéro ('/') sinon la garde date/séquence
        # d'account refuse un numéro de janvier sur une date de février.
        piece.button_draft()
        piece.name = '/'
        piece.invoice_date = '2026-02-15'
        piece.action_post()
        fevrier = self._settlement(
            self.accord_pharma, '2026-02-01', '2026-02-28')
        fevrier.action_refresh()
        self.assertFalse(fevrier.move_ids,
                         "déjà comptée en janvier : jamais deux fois")

    def test_pas_son_propre_apporteur(self):
        with self.assertRaises(ValidationError):
            self.patient.referrer_id = self.patient
