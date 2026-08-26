from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase
from odoo.tools.safe_eval import safe_eval


class TestDentalStock(TransactionCase):
    """Le socle du magasin dentaire : la catégorie sort en FEFO, le lot
    périmé ne part jamais en soins (mais part au rebut), la réception
    date les lots toute seule, et le menu du cabinet reste gardé par
    les groupes du cœur."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.categ = cls.env.ref(
            'megga_dental_stock.product_category_dental_supplies')
        cls.care = cls.env.ref(
            'megga_dental_stock.stock_location_dental_care')
        cls.stock = cls.env.ref('stock.stock_location_stock')
        cls.customers = cls.env.ref('stock.stock_location_customers')
        cls.suppliers = cls.env.ref('stock.stock_location_suppliers')
        cls.warehouse = cls.env.ref('stock.warehouse0')

        cls.compresse = cls.env['product.product'].create({
            'name': "Compresses stériles 5x5",
            'type': 'consu',
            'is_storable': True,
            'tracking': 'lot',
            'use_expiration_date': True,
            'expiration_time': 365,
            'categ_id': cls.categ.id,
        })

        cls.magasinier = cls.env['res.users'].create({
            'name': "Magasinier du cabinet",
            'login': "dental_stock_user",
            'email': "magasin@exemple.ch",
            'group_ids': [(4, cls.env.ref('stock.group_stock_user').id),
                          (4, cls.env.ref(
                              'megga_dental.group_dental_reception').id)],
        })

    # ------------------------------------------------------------------
    # Décor
    # ------------------------------------------------------------------
    @classmethod
    def _lot(cls, name, expiration, product=None):
        """Un lot daté, posé en stock avec sa quantité."""
        product = product or cls.compresse
        lot = cls.env['stock.lot'].create({
            'name': name,
            'product_id': product.id,
            'expiration_date': expiration,
        })
        return lot

    def _mettre_en_stock(self, lot, quantity, product=None):
        product = product or self.compresse
        self.env['stock.quant']._update_available_quantity(
            product, self.stock, quantity, lot_id=lot)
        return lot

    def _picking_vers(self, destination, quantity=1.0, product=None,
                      picking_type=None):
        """Un transfert interne du stock vers `destination`."""
        product = product or self.compresse
        picking_type = picking_type or self.warehouse.out_type_id
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.stock.id,
            'location_dest_id': destination.id,
            'move_ids': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': quantity,
                'product_uom': product.uom_id.id,
                'location_id': self.stock.id,
                'location_dest_id': destination.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        return picking

    # ------------------------------------------------------------------
    # La configuration qui rend le FEFO effectif
    # ------------------------------------------------------------------
    def test_categorie_porte_le_fefo(self):
        """C'est la catégorie qui rend la sortie FEFO effective."""
        self.assertEqual(
            self.categ.removal_strategy_id,
            self.env.ref('product_expiry.removal_fefo'))
        self.assertEqual(
            self.env['stock.quant']._get_removal_strategy(
                self.compresse, self.stock),
            'fefo')

    def test_emplacement_de_consommation(self):
        """« Consommé en soins » sort définitivement du stock, et il est
        partagé entre sociétés (patron des emplacements du cœur)."""
        self.assertEqual(self.care.usage, 'customer')
        self.assertFalse(self.care.company_id)

    # ------------------------------------------------------------------
    # FEFO en vrai : ce qui périme le plus tôt part le premier
    # ------------------------------------------------------------------
    def test_fefo_sert_le_lot_le_plus_proche(self):
        """Deux lots en stock : la réservation prend celui qui expire en
        premier — même s'il est entré au rayon en dernier."""
        tard = self._lot("LOT-TARD", fields.Datetime.now() + timedelta(days=200))
        self._mettre_en_stock(tard, 10)
        tot = self._lot("LOT-TOT", fields.Datetime.now() + timedelta(days=20))
        self._mettre_en_stock(tot, 10)

        picking = self._picking_vers(self.care, quantity=3.0)

        self.assertEqual(picking.move_ids.move_line_ids.lot_id, tot,
                         "FEFO : le lot le plus proche de sa date d'abord.")

    def test_fefo_deborde_sur_le_lot_suivant(self):
        """Quand le premier lot ne suffit pas, le suivant complète —
        toujours dans l'ordre des péremptions."""
        tot = self._lot("LOT-A", fields.Datetime.now() + timedelta(days=10))
        self._mettre_en_stock(tot, 2)
        tard = self._lot("LOT-B", fields.Datetime.now() + timedelta(days=90))
        self._mettre_en_stock(tard, 10)

        picking = self._picking_vers(self.care, quantity=5.0)

        lignes = picking.move_ids.move_line_ids
        self.assertEqual(len(lignes), 2)
        par_lot = {ligne.lot_id: ligne.quantity for ligne in lignes}
        self.assertEqual(par_lot[tot], 2)
        self.assertEqual(par_lot[tard], 3)

    def test_fefo_ne_reserve_pas_un_lot_perime(self):
        """Le cœur écarte de lui-même le lot dont la date de retrait est
        passée : la réservation ne le propose jamais."""
        perime = self._lot("LOT-PERIME",
                           fields.Datetime.now() - timedelta(days=1))
        self._mettre_en_stock(perime, 10)
        bon = self._lot("LOT-BON", fields.Datetime.now() + timedelta(days=60))
        self._mettre_en_stock(bon, 10)

        picking = self._picking_vers(self.care, quantity=4.0)

        self.assertEqual(picking.move_ids.move_line_ids.lot_id, bon)

    # ------------------------------------------------------------------
    # La garde : le périmé ne part plus vers les soins
    # ------------------------------------------------------------------
    def _forcer_lot(self, picking, lot, quantity=1.0):
        """Le magasinier choisit son lot à la main — c'est le geste que
        la garde doit rattraper : l'écran ne protège rien."""
        move = picking.move_ids
        move.move_line_ids.unlink()
        self.env['stock.move.line'].create({
            'move_id': move.id,
            'picking_id': picking.id,
            'product_id': move.product_id.id,
            'product_uom_id': move.product_uom.id,
            'location_id': self.stock.id,
            'location_dest_id': picking.location_dest_id.id,
            'lot_id': lot.id,
            'quantity': quantity,
        })
        move.picked = True
        return picking

    def _valider(self, picking):
        """Valide comme le fait l'écran.

        Le cœur (product_expiry) AVERTIT d'un lot périmé par un wizard
        de confirmation — un avertissement qui se contourne d'un clic.
        On clique donc « Confirmer » : c'est précisément là que la garde
        du cabinet doit tenir. Avertir n'est pas refuser."""
        action = picking.button_validate()
        if isinstance(action, dict) \
                and action.get('res_model') == 'expiry.picking.confirmation':
            wizard = self.env[action['res_model']].with_context(
                action['context']).create({})
            return wizard.process()
        return action

    def test_perime_refuse_vers_les_soins(self):
        """Le refus nomme le lot et sa date : un message qui ne dit pas
        QUEL lot ne sert à rien au fauteuil."""
        perime = self._lot("LOT-X",
                           fields.Datetime.now() - timedelta(days=3))
        self._mettre_en_stock(perime, 5)
        picking = self._picking_vers(self.care, quantity=1.0)
        self._forcer_lot(picking, perime)

        with self.assertRaises(UserError) as refus:
            self._valider(picking)
        message = str(refus.exception)
        self.assertIn("LOT-X", message)
        self.assertIn("périmé", message)
        # Le refus vient bien de la garde du cabinet, pas de
        # l'avertissement du cœur : il nomme le geste de sortie.
        self.assertIn("rebut", message)

    def test_perime_part_au_rebut(self):
        """Le rebut reste permis : un lot périmé doit pouvoir être
        détruit proprement, sinon il s'immobilise en rayon pour
        toujours."""
        perime = self._lot("LOT-REBUT",
                           fields.Datetime.now() - timedelta(days=3))
        self._mettre_en_stock(perime, 5)

        scrap = self.env['stock.scrap'].create({
            'product_id': self.compresse.id,
            'product_uom_id': self.compresse.uom_id.id,
            'scrap_qty': 2.0,
            'lot_id': perime.id,
            'location_id': self.stock.id,
        })
        scrap.action_validate()

        self.assertEqual(scrap.state, 'done')
        self.assertEqual(
            self.env['stock.quant']._get_available_quantity(
                self.compresse, self.stock, lot_id=perime,
                allow_negative=True), 3.0)

    def test_perime_part_chez_un_client_ordinaire(self):
        """La garde ne vise QUE les soins : une sortie vers un autre
        emplacement client (rétrocession, retour) n'est pas son
        affaire."""
        perime = self._lot("LOT-CLIENT",
                           fields.Datetime.now() - timedelta(days=3))
        self._mettre_en_stock(perime, 5)
        picking = self._picking_vers(self.customers, quantity=1.0)
        self._forcer_lot(picking, perime)

        self._valider(picking)

        self.assertEqual(picking.state, 'done')

    def test_perime_refuse_dans_un_sous_emplacement_de_soins(self):
        """Un cabinet qui subdivise « Consommé en soins » (par cabinet,
        par praticien) ne sort pas de la garde : la descendance est
        couverte."""
        salle = self.env['stock.location'].create({
            'name': "Salle 2",
            'usage': 'customer',
            'location_id': self.care.id,
        })
        perime = self._lot("LOT-SALLE",
                           fields.Datetime.now() - timedelta(days=2))
        self._mettre_en_stock(perime, 5)
        picking = self._picking_vers(salle, quantity=1.0)
        self._forcer_lot(picking, perime)

        with self.assertRaises(UserError):
            self._valider(picking)

    def test_lot_valide_part_en_soins(self):
        """La garde ne gêne pas le flux normal."""
        bon = self._lot("LOT-OK", fields.Datetime.now() + timedelta(days=30))
        self._mettre_en_stock(bon, 5)
        picking = self._picking_vers(self.care, quantity=2.0)

        picking.move_ids.picked = True
        self._valider(picking)

        self.assertEqual(picking.state, 'done')
        self.assertEqual(
            self.env['stock.quant']._get_available_quantity(
                self.compresse, self.stock, lot_id=bon), 3.0)

    def test_lot_sans_peremption_part_en_soins(self):
        """Un consommable non périssable (instruments, articles secs)
        traverse la garde sans encombre."""
        vis = self.env['product.product'].create({
            'name': "Vis de cicatrisation",
            'type': 'consu',
            'is_storable': True,
            'tracking': 'lot',
            'categ_id': self.categ.id,
        })
        lot = self.env['stock.lot'].create({
            'name': "LOT-VIS", 'product_id': vis.id})
        self.env['stock.quant']._update_available_quantity(
            vis, self.stock, 5, lot_id=lot)
        picking = self._picking_vers(self.care, quantity=1.0, product=vis)

        picking.move_ids.picked = True
        self._valider(picking)

        self.assertEqual(picking.state, 'done')

    # ------------------------------------------------------------------
    # Péremption : dates calculées, réception qui date les lots
    # ------------------------------------------------------------------
    def test_reception_date_le_lot(self):
        """Une réception fournisseur crée le lot avec sa date de
        péremption, déduite du délai du produit."""
        self.compresse.write({'expiration_time': 30, 'alert_time': 7})
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.warehouse.in_type_id.id,
            'location_id': self.suppliers.id,
            'location_dest_id': self.stock.id,
            'move_ids': [(0, 0, {
                'product_id': self.compresse.id,
                'product_uom_qty': 10.0,
                'product_uom': self.compresse.uom_id.id,
                'location_id': self.suppliers.id,
                'location_dest_id': self.stock.id,
            })],
        })
        picking.action_confirm()
        ligne = picking.move_ids.move_line_ids
        ligne.lot_name = "LOT-RECEPTION"
        ligne.quantity = 10.0
        picking.move_ids.picked = True
        self._valider(picking)

        lot = self.env['stock.lot'].search([('name', '=', "LOT-RECEPTION")])
        self.assertTrue(lot.expiration_date)
        attendu = fields.Datetime.now() + timedelta(days=30)
        self.assertLess(abs((lot.expiration_date - attendu).total_seconds()),
                        3600, "La date de péremption suit le délai du produit.")

    def test_alert_date_calculee(self):
        """L'alerte se pose en amont de la péremption : le cabinet doit
        avoir le temps de commander."""
        self.compresse.write({'alert_time': 10})
        lot = self._lot("LOT-ALERTE",
                        fields.Datetime.now() + timedelta(days=40))

        self.assertTrue(lot.alert_date)
        self.assertEqual(
            (lot.expiration_date - lot.alert_date).days, 10)
        self.assertFalse(lot.product_expiry_alert)

    def test_lot_perime_signale(self):
        """Le drapeau du cœur porte le décor de la liste : périmé se
        lit d'un coup d'œil."""
        lot = self._lot("LOT-VIEUX",
                        fields.Datetime.now() - timedelta(days=1))
        self.assertTrue(lot.product_expiry_alert)

    # ------------------------------------------------------------------
    # Menu et ACL : des raccourcis gardés, pas un contournement
    # ------------------------------------------------------------------
    def test_menu_garde_par_les_groupes_du_coeur(self):
        """Le menu du cabinet n'ouvre rien de plus que les groupes stock
        du cœur : pas de nouveau groupe, pas de porte dérobée."""
        menu = self.env.ref('megga_dental_stock.menu_dental_stock_root')
        self.assertEqual(menu.group_ids,
                         self.env.ref('stock.group_stock_user'))
        self.assertEqual(
            menu.parent_id,
            self.env.ref('megga_dental.menu_dental_intendance'),
            "Le magasin vit sous « Intendance », aux côtés du registre "
            "et de la stérilisation.")
        self.assertEqual(
            menu.parent_id.parent_id,
            self.env.ref('megga_dental.menu_dental_root'))

    def test_menu_invisible_sans_droits_stock(self):
        """La réception sans droits stock ne voit pas le magasin : le
        menu est un raccourci, pas un contournement d'ACL."""
        receptionniste = self.env['res.users'].create({
            'name': "Réception sans stock",
            'login': "dental_stock_reception",
            'email': "reception.stock@exemple.ch",
            'group_ids': [(4, self.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        menu = self.env.ref('megga_dental_stock.menu_dental_stock_root')
        # _visible_menu_ids : l'API que le client web appelle pour
        # construire la barre de menus — search() sur ir.ui.menu ne
        # filtre PAS par groupes, elle donnerait un faux vert.
        Menu = self.env['ir.ui.menu']
        self.assertNotIn(
            menu.id, Menu.with_user(receptionniste)._visible_menu_ids())
        self.assertIn(
            menu.id, Menu.with_user(self.magasinier)._visible_menu_ids())

    def test_contexte_du_menu_pose_le_bon_produit(self):
        """Le menu « Consommables » crée d'emblée un produit stockable,
        tracé par lot et à péremption : trois réglages que personne
        n'aura à retrouver dans l'onglet Inventaire."""
        action = self.env.ref('megga_dental_stock.action_dental_stock_product')
        contexte = safe_eval(action.context)
        produit = self.env['product.template'].with_context(
            **contexte).create({'name': "Anesthésique articaïne"})

        self.assertEqual(produit.categ_id, self.categ)
        self.assertTrue(produit.is_storable)
        self.assertEqual(produit.tracking, 'lot')
        self.assertTrue(produit.use_expiration_date)

    def test_magasinier_lit_le_magasin(self):
        """L'utilisateur stock voit les vues du cabinet."""
        lot = self._lot("LOT-LU", fields.Datetime.now() + timedelta(days=50))
        self._mettre_en_stock(lot, 3)
        lots = self.env['stock.lot'].with_user(self.magasinier).search(
            [('product_id.categ_id', 'child_of', self.categ.id)])
        self.assertIn(lot, lots)

    def test_portail_ne_voit_rien_du_magasin(self):
        """Un patient connecté n'a rien à faire dans le magasin."""
        portail = self.env['res.users'].create({
            'name': "Patient Portail Stock",
            'login': "dental_stock_portal",
            'email': "portail.stock@exemple.ch",
            'group_ids': [(4, self.env.ref('base.group_portal').id)],
        })
        with self.assertRaises(AccessError):
            self.env['stock.quant'].with_user(portail).search_count([])
