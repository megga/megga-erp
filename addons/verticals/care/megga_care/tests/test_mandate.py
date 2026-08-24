from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestMandate(AccountTestInvoicingCommon):
    """Cycle complet offre -> en cours -> facturation au fil de l'eau ->
    clôture sous garde-fou, sur le plan comptable suisse comme les tests
    du socle : la facture émise ici est celle qui repart en QR-facture via
    megga_qr_export (débiteur aux Émirats compris) et revient par camt."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids = [(4, cls.env.ref(
            'megga_care.group_care_coordination').id)]
        cls.patient = cls.env['megga.care.patient'].create({
            'name': "Karim Al-Test",
            'country_id': cls.env.ref('base.ae').id,
        })
        cls.labo = cls.env['res.partner'].create({
            'name': "Laboratoire Central"})
        cls.type_consultation = cls.env.ref(
            'megga_care.service_type_consultation')
        cls.type_labo = cls.env.ref('megga_care.service_type_laboratoire')
        cls.type_radio = cls.env.ref('megga_care.service_type_radiologie')

    def _mandate(self, **kw):
        """Le check-up du transcript : labo 500 facturés / 450 de coût,
        radiologie 1000, cardiologue 500 — honoraires au forfait 1500."""
        vals = {
            'patient_id': self.patient.id,
            'date_start': '2026-08-24',
            'fee_mode': 'forfait',
            'fee_flat': 1500.0,
            'event_ids': [
                Command.create({
                    'name': "Petit laboratoire",
                    'service_type_id': self.type_labo.id,
                    'provider_id': self.labo.id,
                    'date': '2026-08-24 07:00:00',
                    'price_client': 500.0,
                    'cost_price': 450.0,
                }),
                Command.create({
                    'name': "Trois examens de base",
                    'service_type_id': self.type_radio.id,
                    'date': '2026-08-24 08:00:00',
                    'price_client': 1000.0,
                    'cost_price': 1000.0,
                }),
                Command.create({
                    'name': "Consultation de cardiologie",
                    'service_type_id': self.type_consultation.id,
                    'date': '2026-08-24 09:00:00',
                    'price_client': 500.0,
                    'cost_price': 500.0,
                }),
            ],
        }
        vals.update(kw)
        return self.env['megga.care.mandate'].create(vals)

    def _bill(self, partner, amount):
        """Une pièce fournisseur minimale, comme celle qui arrive par
        e-mail : un montant, un créancier."""
        return self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'invoice_date': '2026-08-24',
            'invoice_line_ids': [Command.create({
                'name': "Analyses",
                'quantity': 1.0,
                'price_unit': amount,
            })],
        })

    def test_montants(self):
        mandat = self._mandate()
        self.assertTrue(mandat.name.startswith('MAN/'))
        self.assertAlmostEqual(mandat.fee_total, 1500.0)
        self.assertAlmostEqual(mandat.amount_client, 3500.0)
        self.assertAlmostEqual(mandat.amount_cost, 1950.0)
        self.assertAlmostEqual(mandat.amount_margin, 1550.0)
        labo = mandat.event_ids.filtered(lambda e: e.provider_id == self.labo)
        self.assertAlmostEqual(labo.margin, 50.0,
                               "la rétrocession du laboratoire : 500 − 450")
        self.assertTrue(labo.retrocession)

    def test_cloture_sous_garde_fou(self):
        mandat = self._mandate()
        mandat.action_confirm()
        self.assertEqual(mandat.unbilled_event_count, 3)
        # Rien n'est facturé au client : la clôture refuse.
        with self.assertRaises(UserError):
            mandat.action_close()

    def test_facturation(self):
        mandat = self._mandate()
        mandat.action_confirm()
        action = mandat.action_create_invoice()
        facture = mandat.invoice_ids
        self.assertEqual(len(facture), 1)
        self.assertEqual(action['res_id'], facture.id)
        self.assertEqual(facture.move_type, 'out_invoice')
        self.assertEqual(facture.partner_id, self.patient.partner_id,
                         "la facture vise le contact délégué du client")
        self.assertEqual(facture.invoice_origin, mandat.name)
        # 3 événements + la ligne d'honoraires.
        self.assertEqual(len(facture.invoice_line_ids), 4)
        self.assertAlmostEqual(facture.amount_untaxed, 3500.0)
        self.assertEqual(
            set(mandat.event_ids.mapped('billing_state')), {'invoiced'})
        self.assertEqual(mandat.unbilled_event_count, 0)
        self.assertEqual(mandat.fee_invoice_line_id.move_id, facture)
        ligne_labo = mandat.event_ids.filtered(
            lambda e: e.provider_id == self.labo).client_invoice_line_id
        self.assertIn("[LABO]", ligne_labo.name)
        self.assertIn("Laboratoire Central", ligne_labo.name)

    def test_facturation_progressive(self):
        """Les longs mandats se facturent au fil de l'eau : une deuxième
        facture n'emporte que le nouveau, et les honoraires ne partent
        qu'une fois."""
        mandat = self._mandate()
        mandat.action_confirm()
        mandat.action_create_invoice()
        self.env['megga.care.event'].create({
            'mandate_id': mandat.id,
            'name': "Consultation de suivi",
            'service_type_id': self.type_consultation.id,
            'date': '2026-09-02 09:00:00',
            'price_client': 400.0,
        })
        self.assertEqual(mandat.unbilled_event_count, 1)
        mandat.action_create_invoice()
        self.assertEqual(len(mandat.invoice_ids), 2)
        seconde = mandat.invoice_ids.sorted('id')[-1]
        self.assertEqual(len(seconde.invoice_line_ids), 1,
                         "pas de seconde ligne d'honoraires")
        self.assertAlmostEqual(seconde.amount_untaxed, 400.0)
        # Plus rien à facturer : l'appel suivant le dit clairement.
        with self.assertRaises(UserError):
            mandat.action_create_invoice()

    def test_cloture_verte(self):
        """Tout facturé au client, tous les coûts couverts par une pièce
        rattachée à l'événement : la clôture passe."""
        mandat = self._mandate()
        mandat.action_confirm()
        mandat.action_create_invoice()
        self.assertEqual(mandat.uncovered_cost_count, 3)
        with self.assertRaises(UserError):
            mandat.action_close()
        piece = self._bill(self.labo, 1950.0)
        mandat.event_ids.write({'supplier_invoice_id': piece.id})
        self.assertEqual(mandat.uncovered_cost_count, 0)
        mandat.action_close()
        self.assertEqual(mandat.state, 'done')
        self.assertTrue(mandat.date_end, "la clôture date la fin du mandat")

    def test_annulation_bloquee_par_facture_vivante(self):
        mandat = self._mandate()
        mandat.action_confirm()
        mandat.action_create_invoice()
        with self.assertRaises(UserError):
            mandat.action_cancel()
