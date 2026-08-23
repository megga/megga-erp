from datetime import date

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestTreatment(AccountTestInvoicingCommon):
    """Cycle complet devis -> planifié -> terminé -> facture, sur le plan
    comptable suisse comme les tests du socle : la facture émise ici est
    celle qui repart en QR-facture via megga_qr_export."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        # L'utilisateur comptable du décor reçoit le groupe Soins : les
        # dossiers patients sont désormais fermés hors groupes dentaires.
        cls.env.user.group_ids = [(4, cls.env.ref(
            'megga_dental.group_dental_praticien').id)]
        cls.patient = cls.env['megga.dental.patient'].create({
            'name': "Alice Dupont",
            'birthdate': '1990-05-01',
        })
        cls.detartrage = cls.env['product.product'].create({
            'name': "Détartrage et hygiène",
            'type': 'service',
            'list_price': 140.0,
        })
        cls.composite = cls.env['product.product'].create({
            'name': "Obturation composite",
            'type': 'service',
            'list_price': 180.0,
        })
        cls.teeth_16_26 = cls.env['megga.dental.tooth'].search(
            [('number', 'in', (16, 26))])

    def _treatment(self, **kw):
        vals = {
            'patient_id': self.patient.id,
            'date': '2026-08-31',
            'line_ids': [
                Command.create({
                    'product_id': self.detartrage.id,
                    'description': "Détartrage et hygiène",
                    'quantity': 1.0,
                    'price_unit': 140.0,
                }),
                Command.create({
                    'product_id': self.composite.id,
                    'description': "Obturation composite",
                    'tooth_ids': [Command.set(self.teeth_16_26.ids)],
                    'quantity': 2.0,
                    'price_unit': 180.0,
                }),
            ],
        }
        vals.update(kw)
        return self.env['megga.dental.treatment'].create(vals)

    def test_montants(self):
        traitement = self._treatment()
        self.assertTrue(traitement.name.startswith('TRT/'))
        self.assertAlmostEqual(
            sum(traitement.line_ids.mapped('subtotal')), 500.0)
        self.assertAlmostEqual(traitement.amount_total, 500.0)

    def test_planifier_exige_des_actes(self):
        vide = self._treatment(line_ids=[])
        with self.assertRaises(UserError):
            vide.action_confirm()

    def test_terminer_arme_le_rappel(self):
        traitement = self._treatment()
        traitement.action_confirm()
        traitement.action_done()
        self.assertEqual(traitement.state, 'done')
        self.assertEqual(self.patient.last_visit_date, date(2026, 8, 31))
        # 31 août + 6 mois : l'écrêtage de fin de mois donne le 28 février.
        self.assertEqual(self.patient.recall_date, date(2027, 2, 28))

    def test_facturation(self):
        traitement = self._treatment()
        traitement.action_confirm()
        traitement.action_done()
        action = traitement.action_create_invoice()
        facture = traitement.invoice_id
        self.assertTrue(facture)
        self.assertEqual(action['res_id'], facture.id)
        self.assertEqual(facture.move_type, 'out_invoice')
        self.assertEqual(facture.partner_id, self.patient.partner_id,
                         "la facture doit viser le contact délégué du patient")
        self.assertAlmostEqual(facture.amount_untaxed, 500.0)
        self.assertEqual(facture.invoice_origin, traitement.name)
        ligne = facture.invoice_line_ids.filtered(
            lambda l: l.product_id == self.composite)
        self.assertIn("dents 16, 26", ligne.name)

    def test_double_facturation_bloquee(self):
        traitement = self._treatment()
        traitement.action_confirm()
        traitement.action_done()
        traitement.action_create_invoice()
        with self.assertRaises(UserError):
            traitement.action_create_invoice()

    def test_facturation_exige_termine(self):
        traitement = self._treatment()
        with self.assertRaises(UserError):
            traitement.action_create_invoice()
