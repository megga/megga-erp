from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestEcart(TransactionCase):
    """L'écart matière : ce que la caisse a vendu, confronté à ce que
    l'inventaire a compté."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Fuseau fixe : les bornes de periode se calculent dedans, les
        # tests seraient sinon a la merci du reglage de la machine.
        cls.env.user.tz = 'Europe/Zurich'
        cls.kg = cls.env.ref('uom.product_uom_kgm')
        cls.g = cls.env.ref('uom.product_uom_gram')

        Product = cls.env['product.product']
        cls.boeuf = Product.create({
            'name': "Entrecôte", 'type': 'consu',
            'uom_id': cls.kg.id, 'standard_price': 38.0})
        cls.beurre = Product.create({
            'name': "Beurre", 'type': 'consu',
            'uom_id': cls.kg.id, 'standard_price': 12.0})
        cls.plat_viande = Product.create({
            'name': "Entrecôte café de Paris", 'type': 'consu',
            'list_price': 46.0, 'available_in_pos': True})
        cls.plat_puree = Product.create({
            'name': "Purée maison", 'type': 'consu',
            'list_price': 9.0, 'available_in_pos': True})
        cls.plat_sans_fiche = Product.create({
            'name': "Café", 'type': 'consu',
            'list_price': 4.5, 'available_in_pos': True})

        Recipe = cls.env['megga.resto.recipe']
        # 200 g de boeuf + 30 g de beurre par portion.
        Recipe.create({
            'product_id': cls.plat_viande.id,
            'line_ids': [
                (0, 0, {'product_id': cls.boeuf.id,
                        'quantity': 200.0, 'uom_id': cls.g.id}),
                (0, 0, {'product_id': cls.beurre.id,
                        'quantity': 30.0, 'uom_id': cls.g.id}),
            ]})
        # 50 g de beurre par portion : le beurre est partage.
        Recipe.create({
            'product_id': cls.plat_puree.id,
            'line_ids': [
                (0, 0, {'product_id': cls.beurre.id,
                        'quantity': 50.0, 'uom_id': cls.g.id}),
            ]})

        config = cls.env['pos.config'].create({'name': "Caisse de test"})
        cls.session = cls.env['pos.session'].create({
            'config_id': config.id, 'user_id': cls.env.uid})
        cls.session.action_pos_session_open()

    @classmethod
    def _vente(cls, produit, qty, quand, etat='paid'):
        """Une commande encaissée, à l'heure UTC donnée."""
        commande = cls.env['pos.order'].create({
            'company_id': cls.env.company.id,
            'session_id': cls.session.id,
            'amount_tax': 0.0, 'amount_total': 0.0,
            'amount_paid': 0.0, 'amount_return': 0.0,
            'date_order': quand,
            'lines': [(0, 0, {
                'name': "L", 'product_id': produit.id, 'qty': qty,
                'price_subtotal': 0.0, 'price_subtotal_incl': 0.0})],
        })
        commande.state = etat
        return commande

    def _releve(self, debut='2026-09-01', fin='2026-09-01'):
        return self.env['megga.resto.ecart'].create({
            'label': "Essai", 'date_start': debut, 'date_stop': fin})

    def _ligne(self, releve, produit):
        return releve.line_ids.filtered(lambda l: l.product_id == produit)

    # ------------------------------------------------ la part theorique

    def test_theorique_depuis_la_caisse(self):
        """Dix entrecôtes vendues, 200 g de bœuf la portion : deux kilos
        auraient dû partir — et la conversion se fait dans l'unité de
        l'économat."""
        self._vente(self.plat_viande, 10.0, '2026-09-01 18:30:00')
        releve = self._releve()
        releve.action_calculer()
        self.assertAlmostEqual(
            self._ligne(releve, self.boeuf).theorique, 2.0)
        self.assertAlmostEqual(
            self._ligne(releve, self.beurre).theorique, 0.3)

    def test_un_ingredient_partage_fait_une_seule_ligne(self):
        """Le beurre de l'entrecôte et celui de la purée s'additionnent
        sur une ligne, pas deux."""
        self._vente(self.plat_viande, 10.0, '2026-09-01 18:30:00')
        self._vente(self.plat_puree, 10.0, '2026-09-01 19:00:00')
        releve = self._releve()
        releve.action_calculer()
        lignes = self._ligne(releve, self.beurre)
        self.assertEqual(len(lignes), 1)
        self.assertAlmostEqual(lignes.theorique, 0.8)   # 0.3 + 0.5

    def test_le_prix_de_revient_est_fige_au_calcul(self):
        """La théorique est une MESURE : le prix qui la valorise est
        celui du jour du calcul, pas celui d'aujourd'hui."""
        self._vente(self.plat_viande, 10.0, '2026-09-01 18:30:00')
        releve = self._releve()
        releve.action_calculer()
        ligne = self._ligne(releve, self.boeuf)
        self.assertAlmostEqual(ligne.cost_unit, 38.0)
        self.boeuf.standard_price = 50.0
        self.assertAlmostEqual(ligne.cost_unit, 38.0)

    # ------------------------------------------------------ les bornes

    def test_une_vente_hors_periode_ne_compte_pas(self):
        self._vente(self.plat_viande, 10.0, '2026-09-05 18:30:00')
        releve = self._releve()
        releve.action_calculer()
        self.assertFalse(releve.line_ids)

    def test_les_bornes_se_lisent_dans_le_fuseau_du_restaurant(self):
        """Une commande encaissée à 00h30 le 2 septembre l'a été à 22h30
        UTC le 1er : elle appartient au 2, pas au 1er. Sans conversion,
        le service de fin de soirée tomberait dans le mauvais jour."""
        self._vente(self.plat_viande, 4.0, '2026-09-01 22:30:00')
        premier = self._releve('2026-09-01', '2026-09-01')
        premier.action_calculer()
        self.assertFalse(premier.line_ids)
        second = self._releve('2026-09-02', '2026-09-02')
        second.action_calculer()
        self.assertAlmostEqual(
            self._ligne(second, self.boeuf).theorique, 0.8)

    def test_un_brouillon_ou_une_annulation_n_a_rien_consomme(self):
        self._vente(self.plat_viande, 10.0, '2026-09-01 18:30:00',
                    etat='draft')
        self._vente(self.plat_viande, 10.0, '2026-09-01 19:00:00',
                    etat='cancel')
        releve = self._releve()
        releve.action_calculer()
        self.assertFalse(releve.line_ids)

    def test_un_plat_sans_fiche_est_signale(self):
        """On ne peut rien dire de ce qu'on n'a pas décrit — mais on le
        dit, au lieu de l'oublier en silence."""
        self._vente(self.plat_sans_fiche, 20.0, '2026-09-01 18:30:00')
        releve = self._releve()
        releve.action_calculer()
        self.assertFalse(releve.line_ids)
        corps = "".join(releve.message_ids.mapped('body'))
        self.assertIn("sans fiche technique", corps)
        self.assertIn("Café", corps)

    # ------------------------------------------------------- l'ecart

    def test_ecart_et_valorisation(self):
        """Deux kilos théoriques, 2.2 réellement partis : 200 g de perte
        à 38.00 le kilo, soit CHF 7.60."""
        self._vente(self.plat_viande, 10.0, '2026-09-01 18:30:00')
        releve = self._releve()
        releve.action_calculer()
        ligne = self._ligne(releve, self.boeuf)
        ligne.write({'stock_initial': 5.0, 'achats': 0.0,
                     'stock_final': 2.8})
        self.assertAlmostEqual(ligne.reelle, 2.2)
        self.assertAlmostEqual(ligne.ecart_qty, 0.2)
        self.assertAlmostEqual(ligne.ecart_pct, 10.0)
        self.assertAlmostEqual(ligne.ecart_value, 7.6)

    def test_les_pertes_ne_se_compensent_pas(self):
        """Le total des pertes ne somme que les écarts positifs : une
        sous-consommation ne rachète pas un gaspillage."""
        self._vente(self.plat_viande, 10.0, '2026-09-01 18:30:00')
        releve = self._releve()
        releve.action_calculer()
        # Boeuf : 0.2 kg de trop a 38 = +7.60
        self._ligne(releve, self.boeuf).write({
            'stock_initial': 5.0, 'stock_final': 2.8})
        # Beurre : 0.1 kg de moins a 12 = -1.20
        self._ligne(releve, self.beurre).write({
            'stock_initial': 1.0, 'stock_final': 0.8})
        self.assertAlmostEqual(releve.ecart_value_total, 6.4)
        self.assertAlmostEqual(releve.perte_total, 7.6)

    # -------------------------------------------------- le recalcul

    def test_les_comptages_survivent_au_recalcul(self):
        """Un chef qui a passé sa soirée à compter ne perd pas ses
        chiffres parce qu'il relance le calcul."""
        self._vente(self.plat_viande, 10.0, '2026-09-01 18:30:00')
        releve = self._releve()
        releve.action_calculer()
        ligne = self._ligne(releve, self.boeuf)
        ligne.write({'stock_initial': 5.0, 'achats': 1.0,
                     'stock_final': 2.8})
        self._vente(self.plat_viande, 5.0, '2026-09-01 20:00:00')
        releve.action_calculer()
        self.assertAlmostEqual(ligne.stock_initial, 5.0)
        self.assertAlmostEqual(ligne.achats, 1.0)
        self.assertAlmostEqual(ligne.stock_final, 2.8)
        self.assertAlmostEqual(ligne.theorique, 3.0)   # 15 portions

    def test_la_theorique_retombe_a_zero_sans_vente(self):
        """Un ingrédient relevé à la main que plus aucune vente
        n'appelle : sa théorique ne reste pas sur un ancien calcul."""
        self._vente(self.plat_viande, 10.0, '2026-09-01 18:30:00')
        releve = self._releve()
        releve.action_calculer()
        ligne = self._ligne(releve, self.boeuf)
        self.assertAlmostEqual(ligne.theorique, 2.0)
        vide = self._releve('2026-09-03', '2026-09-03')
        vide.write({'line_ids': [(0, 0, {'product_id': self.boeuf.id})]})
        vide.action_calculer()
        self.assertAlmostEqual(vide.line_ids.theorique, 0.0)

    # --------------------------------------------------- les gardes

    def test_une_periode_a_l_envers_est_refusee(self):
        with self.assertRaises(ValidationError):
            self._releve('2026-09-10', '2026-09-01')

    def test_un_releve_arrete_ne_se_recalcule_plus(self):
        self._vente(self.plat_viande, 10.0, '2026-09-01 18:30:00')
        releve = self._releve()
        releve.action_calculer()
        releve.action_confirm()
        with self.assertRaises(UserError):
            releve.action_calculer()

    def test_on_n_arrete_pas_un_releve_vide(self):
        with self.assertRaises(UserError):
            self._releve().action_confirm()

    def test_un_ingredient_ne_figure_qu_une_fois(self):
        releve = self._releve()
        releve.write({'line_ids': [(0, 0, {'product_id': self.boeuf.id})]})
        with self.assertRaises(Exception):
            releve.write({
                'line_ids': [(0, 0, {'product_id': self.boeuf.id})]})
            releve.flush_recordset()

    # ---------------------------------------------------- le papier

    def test_le_rapport_porte_les_ecarts(self):
        self._vente(self.plat_viande, 10.0, '2026-09-01 18:30:00')
        releve = self._releve()
        releve.action_calculer()
        self._ligne(releve, self.boeuf).write({
            'stock_initial': 5.0, 'stock_final': 2.8})
        html = self.env['ir.actions.report']._render_qweb_html(
            'megga_resto_ecart.report_ecart', releve.ids)[0].decode()
        self.assertIn("Relevé d'écart matière", html)
        self.assertIn("Entrecôte", html)
        self.assertIn(releve.name, html)
