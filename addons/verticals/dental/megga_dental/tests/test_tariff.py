from psycopg2 import IntegrityError

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestTariff(AccountTestInvoicingCommon):
    """Le tarif par points : montant = points × valeur du point. Le
    catalogue officiel étant sous licence SSO, les positions de ce décor
    sont FICTIVES — la mécanique, elle, est bien celle du tarif suisse
    (valeur du cabinet en privé, valeur de la convention aux assurances
    sociales, valeur figée sur le traitement)."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids = [(4, cls.env.ref(
            'megga_dental.group_dental_praticien').id)]
        cls.env.company.sudo().dental_point_value = 1.15
        cls.patient = cls.env['megga.dental.patient'].create({
            'name': "Bruno Tarif"})
        Position = cls.env['megga.dental.position']
        cls.pos_consult = Position.create({
            'code': "9001", 'name': "Consultation (fictive)",
            'points': 45.0, 'chapter': "Exemple"})
        cls.pos_hygiene = Position.create({
            'code': "9002", 'name': "Hygiène (fictive)",
            'points': 62.5, 'chapter': "Exemple"})
        cls.fourniture = cls.env['product.product'].create({
            'name': "Gouttière (produit)", 'type': 'service',
            'list_price': 90.0})
        cls.tooth_16 = cls.env['megga.dental.tooth'].search(
            [('number', '=', 16)], limit=1)

    def _treatment(self, lines, **kw):
        vals = {
            'patient_id': self.patient.id,
            'date': '2026-09-07',
            'line_ids': lines,
        }
        vals.update(kw)
        return self.env['megga.dental.treatment'].create(vals)

    def test_affichage_et_code_unique(self):
        self.assertEqual(self.pos_consult.display_name,
                         "9001 — Consultation (fictive)")
        with self.assertRaises(IntegrityError), \
                mute_logger('odoo.sql_db'), self.cr.savepoint():
            self.env['megga.dental.position'].create({
                'code': "9001", 'name': "Doublon", 'points': 1.0})

    def test_prix_depuis_les_points(self):
        traitement = self._treatment([
            Command.create({'position_id': self.pos_consult.id}),
            Command.create({'position_id': self.pos_hygiene.id,
                            'quantity': 2.0}),
        ])
        self.assertEqual(traitement.tariff_kind, 'prive')
        self.assertAlmostEqual(traitement.point_value, 1.15)
        consult, hygiene = traitement.line_ids
        self.assertAlmostEqual(consult.points, 45.0)
        self.assertAlmostEqual(consult.price_unit, 51.75)   # 45 × 1.15
        self.assertAlmostEqual(hygiene.price_unit, 71.88)   # 62.5 × 1.15
        self.assertAlmostEqual(hygiene.subtotal, 143.76)
        self.assertAlmostEqual(traitement.amount_total, 195.51)

    def test_tarif_social(self):
        traitement = self._treatment(
            [Command.create({'position_id': self.pos_consult.id})],
            tariff_kind='social')
        self.assertAlmostEqual(traitement.point_value, 1.0,
                               msg="convention AA/AI/AM : le point vaut 1")
        self.assertAlmostEqual(traitement.line_ids.price_unit, 45.0)

    def test_changement_de_tarif_recalcule(self):
        traitement = self._treatment(
            [Command.create({'position_id': self.pos_consult.id})])
        self.assertAlmostEqual(traitement.line_ids.price_unit, 51.75)
        traitement.tariff_kind = 'social'
        self.assertAlmostEqual(traitement.point_value, 1.0)
        self.assertAlmostEqual(traitement.line_ids.price_unit, 45.0,
                               msg="le changement de tarif recalcule "
                                   "toutes les lignes")

    def test_valeur_figee_sur_le_traitement(self):
        avant = self._treatment(
            [Command.create({'position_id': self.pos_consult.id})])
        self.env.company.sudo().dental_point_value = 1.60
        self.assertAlmostEqual(avant.point_value, 1.15,
                               msg="un devis émis ne bouge pas quand le "
                                   "cabinet change sa valeur du point")
        self.assertAlmostEqual(avant.line_ids.price_unit, 51.75)
        apres = self._treatment(
            [Command.create({'position_id': self.pos_consult.id})])
        self.assertAlmostEqual(apres.point_value, 1.60)
        self.assertAlmostEqual(apres.line_ids.price_unit, 72.0)

    def test_points_modifiables_sur_la_ligne(self):
        traitement = self._treatment(
            [Command.create({'position_id': self.pos_consult.id})])
        ligne = traitement.line_ids
        ligne.points = 20.0
        self.assertAlmostEqual(ligne.price_unit, 23.0,
                               msg="20 PT × 1.15 — la correction manuelle "
                                   "des points recalcule le prix")

    def test_ligne_sans_source_refusee(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._treatment([Command.create({
                'description': "Ni position ni produit",
                'price_unit': 10.0})])

    def test_melange_position_et_produit(self):
        traitement = self._treatment([
            Command.create({'position_id': self.pos_consult.id}),
            Command.create({'product_id': self.fourniture.id,
                            'price_unit': 90.0}),
        ])
        self.assertAlmostEqual(traitement.amount_total, 141.75)

    def test_facture_avec_positions(self):
        traitement = self._treatment([
            Command.create({'position_id': self.pos_consult.id,
                            'tooth_ids': [Command.set(self.tooth_16.ids)]}),
            Command.create({'product_id': self.fourniture.id,
                            'price_unit': 90.0}),
        ])
        traitement.action_confirm()
        traitement.action_done()
        traitement.action_create_invoice()
        facture = traitement.invoice_id
        self.assertAlmostEqual(facture.amount_untaxed, 141.75)
        ligne_position = facture.invoice_line_ids.filtered(
            lambda l: not l.product_id)
        self.assertEqual(
            ligne_position.name,
            "[9001] Consultation (fictive) — dent 16",
            "le numero de position figure sur la facture")
        self.assertAlmostEqual(ligne_position.price_unit, 51.75)

    def test_reception_lit_le_tarif_sans_le_gerer(self):
        reception = self.env['res.users'].sudo().create({
            'name': "Réception Tarif", 'login': "tarif_reception",
            'email': "tarif.reception@exemple.ch",
            'group_ids': [(4, self.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        self.assertEqual(
            self.pos_consult.with_user(reception).points, 45.0)
        with self.assertRaises(AccessError):
            self.env['megga.dental.position'].with_user(reception).create({
                'code': "9099", 'name': "Interdit", 'points': 1.0})
