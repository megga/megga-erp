from datetime import datetime

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEventBill(AccountTestInvoicingCommon):
    """La liaison facture fournisseur <-> événement du mandat — la
    fonctionnalité qu'Office Maker n'a pas — et la parité agenda : le
    mandat EST le calendrier."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids = [(4, cls.env.ref(
            'megga_care.group_care_coordination').id)]
        cls.patient = cls.env['megga.care.patient'].create({
            'name': "Nour El-Test"})
        cls.labo = cls.env['res.partner'].create({
            'name': "Laboratoire Central"})
        cls.mandat = cls.env['megga.care.mandate'].create({
            'patient_id': cls.patient.id,
            'date_start': '2026-08-24',
        })
        cls.event = cls.env['megga.care.event'].create({
            'mandate_id': cls.mandat.id,
            'name': "Petit laboratoire",
            'service_type_id': cls.env.ref(
                'megga_care.service_type_laboratoire').id,
            'provider_id': cls.labo.id,
            'date': '2026-08-24 07:00:00',
            'duration': 1.0,
            'price_client': 500.0,
        })

    def _bill(self, amount):
        return self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.labo.id,
            'invoice_date': '2026-08-24',
            'invoice_line_ids': [Command.create({
                'name': "Analyses",
                'quantity': 1.0,
                'price_unit': amount,
            })],
        })

    def test_liaison_refuse_une_facture_client(self):
        facture_client = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.patient.partner_id.id,
        })
        with self.assertRaises(ValidationError):
            self.event.supplier_invoice_id = facture_client

    def test_cout_propose_depuis_la_piece(self):
        """Au rattachement, le coût réel se propose depuis le montant HT
        de la pièce — et ne piétine jamais une saisie manuelle (une même
        pièce peut couvrir plusieurs événements)."""
        piece = self._bill(450.0)
        self.assertEqual(self.event.cost_state, 'none')
        self.event.supplier_invoice_id = piece
        self.assertAlmostEqual(self.event.cost_price, 450.0)
        self.assertEqual(self.event.cost_state, 'covered')
        self.assertAlmostEqual(self.event.margin, 50.0)
        deja_saisi = self.env['megga.care.event'].create({
            'mandate_id': self.mandat.id,
            'name': "Second prélèvement",
            'service_type_id': self.env.ref(
                'megga_care.service_type_laboratoire').id,
            'date': '2026-08-25 07:00:00',
            'cost_price': 120.0,
        })
        deja_saisi.supplier_invoice_id = piece
        self.assertAlmostEqual(deja_saisi.cost_price, 120.0,
                               "la saisie manuelle prime sur la pièce")

    def test_pont_depuis_la_piece(self):
        piece = self._bill(450.0)
        self.event.supplier_invoice_id = piece
        self.assertEqual(piece.care_event_ids, self.event)
        self.assertEqual(piece.care_event_count, 1)
        action = piece.action_view_care_events()
        self.assertEqual(
            action['domain'], [('supplier_invoice_id', '=', piece.id)])

    def test_evenement_facture_indestructible(self):
        self.mandat.action_confirm()
        self.mandat.action_create_invoice()
        self.assertEqual(self.event.billing_state, 'invoiced')
        with self.assertRaises(UserError):
            self.event.unlink()

    def test_agenda_synchronise(self):
        """Parité Office Maker : l'événement du mandat pilote l'agenda —
        création au premier appel, propagation des déplacements,
        disparition avec l'événement."""
        action = self.event.action_open_calendar_event()
        rdv = self.event.calendar_event_id
        self.assertTrue(rdv)
        self.assertEqual(action['res_id'], rdv.id)
        self.assertEqual(rdv.start, datetime(2026, 8, 24, 7, 0, 0))
        self.assertEqual(rdv.stop, datetime(2026, 8, 24, 8, 0, 0))
        self.assertIn("Nour El-Test", rdv.name)
        # Second appel : pas de doublon.
        self.event.action_open_calendar_event()
        self.assertEqual(self.event.calendar_event_id, rdv)
        # Le labo est repoussé de deux heures : l'agenda suit.
        self.event.write({'date': '2026-08-24 09:00:00', 'duration': 1.5})
        self.assertEqual(rdv.start, datetime(2026, 8, 24, 9, 0, 0))
        self.assertEqual(rdv.stop, datetime(2026, 8, 24, 10, 30, 0))
        # L'événement part, le rendez-vous aussi.
        self.event.unlink()
        self.assertFalse(rdv.exists())
