from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged

from ..pilotage_logic import TRANCHES, tranche_age


@tagged('post_install', '-at_install')
class TestPilotage(AccountTestInvoicingCommon):
    """La vue d'analyse et le rapport : ce que la base répond, et ce que
    la fiduciaire lit."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client_a = cls.env['res.partner'].create({'name': "Aubert SA"})
        cls.client_b = cls.env['res.partner'].create({'name': "Berger Sàrl"})
        cls.produit = cls.env['product.product'].create({
            'name': "Prestation", 'type': 'service', 'list_price': 100.0})
        cls.Age = cls.env['megga.pilotage.age']

    def _facture(self, partner, jours, montant=100.0, poster=True):
        echeance = fields.Date.subtract(
            fields.Date.context_today(self.env.user), days=jours)
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': echeance,
            'invoice_date_due': echeance,
            'invoice_line_ids': [Command.create({
                'product_id': self.produit.id,
                'quantity': 1, 'price_unit': montant})],
        })
        if poster:
            move.action_post()
        return move

    def _lignes(self):
        return self.Age.search([
            ('company_id', '=', self.env.company.id)])

    def test_le_sql_classe_comme_la_logique_pure(self):
        """Deux chemins, une seule règle : la vue classe en SQL, le
        rapport en Python. S'ils divergeaient, l'écran et le papier
        diraient deux choses — et personne ne le verrait."""
        for jours in (-10, 0, 1, 15, 30, 31, 45, 60, 61, 75, 90, 91, 400):
            move = self._facture(self.client_a, jours)
            ligne = self.Age.search([('move_id', '=', move.id)])
            self.assertEqual(
                ligne.bucket, tranche_age(jours),
                "SQL et Python doivent classer %s jours pareil" % jours)

    def test_une_ligne_par_facture_ouverte(self):
        self._facture(self.client_a, 12)
        self._facture(self.client_b, 40)
        self.assertEqual(len(self._lignes()), 2)

    def test_la_facture_payee_disparait(self):
        facture = self._facture(self.client_a, 12)
        self.assertTrue(self._lignes())
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=facture.ids
        ).create({}).action_create_payments()
        self.assertFalse(self._lignes())

    def test_le_brouillon_n_y_est_pas(self):
        self._facture(self.client_a, 12, poster=False)
        self.assertFalse(self._lignes())

    def test_les_jours_de_retard_ne_sont_jamais_negatifs(self):
        """Une facture à échoir a zéro jour de retard, pas moins :
        sinon la colonne se lit à l'envers."""
        self._facture(self.client_a, -20)
        ligne = self._lignes()
        self.assertEqual(ligne.days_overdue, 0)
        self.assertEqual(ligne.bucket, 'not_due')

    def test_le_debiteur_est_l_entite_commerciale(self):
        service = self.env['res.partner'].create({
            'name': "Aubert SA — achats",
            'parent_id': self.client_a.id, 'type': 'invoice'})
        self._facture(self.client_a, 12)
        self._facture(service, 12)
        self.assertEqual(
            set(self._lignes().mapped('partner_id')), {self.client_a},
            "les services d'un même client comptent pour un débiteur")

    def test_le_montant_est_en_devise_de_la_societe(self):
        facture = self._facture(self.client_a, 12, montant=250.0)
        ligne = self._lignes()
        self.assertEqual(ligne.company_currency_id,
                         self.env.company.currency_id)
        self.assertAlmostEqual(ligne.amount_residual,
                               facture.amount_residual_signed)

    def test_la_balance_par_client_ventile_et_ordonne(self):
        self._facture(self.client_a, 100, montant=1000.0)
        self._facture(self.client_a, 15, montant=200.0)
        self._facture(self.client_b, 15, montant=50.0)
        balance = self.Age._balance_par_client(self.env.company)
        self.assertEqual(len(balance), 2)
        self.assertEqual(balance[0]['partner'], self.client_a,
                         "la plus grosse dette en tête")
        tranches = balance[0]['tranches']
        self.assertGreater(tranches['b90p'], 0.0)
        self.assertGreater(tranches['b30'], 0.0)
        self.assertEqual(list(tranches), list(TRANCHES))

    def test_le_rappel_deja_servi_est_visible(self):
        """La balance dit aussi où en est le recouvrement."""
        niveau = self.env['megga.relance.niveau'].create({
            'name': "1er rappel", 'delay_days': 10,
            'subject': "Rappel", 'body': "Facture ouverte."})
        facture = self._facture(self.client_a, 20)
        facture.megga_relance_niveau_id = niveau
        self.assertEqual(self._lignes().relance_niveau_id, niveau)

    def test_le_rapport_imprimable(self):
        self._facture(self.client_a, 100, montant=1000.0)
        self._facture(self.client_b, 5, montant=75.0)
        html = self.env['ir.actions.report']._render_qweb_html(
            'megga_pilotage.report_balance_agee',
            self.env.company.ids)[0].decode()
        self.assertIn("Balance âgée", html)
        self.assertIn("Aubert SA", html)
        self.assertIn("Berger Sàrl", html)
        self.assertIn("Plus de 90 jours", html)

    def test_le_rapport_sans_impaye(self):
        html = self.env['ir.actions.report']._render_qweb_html(
            'megga_pilotage.report_balance_agee',
            self.env.company.ids)[0].decode()
        self.assertIn("Aucune facture client ouverte", html)
