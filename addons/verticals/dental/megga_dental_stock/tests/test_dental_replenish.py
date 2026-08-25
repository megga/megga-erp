from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase
from odoo.tools.safe_eval import safe_eval


class TestDentalReplenish(TransactionCase):
    """Le magasin qui se remplit tout seul : minimum et maximum par
    consommable, le planificateur du cœur propose le bon de commande,
    la réception remet des lots datés en rayon. Le gros du comportement
    est au cœur — on teste la COUTURE : le filtre cabinet, le cycle
    bout en bout, l'absence de doublon, et ce qui se passe quand le
    produit n'a pas de fournisseur."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.categ = cls.env.ref(
            'megga_dental_stock.product_category_dental_supplies')
        cls.stock = cls.env.ref('stock.stock_location_stock')
        cls.warehouse = cls.env.ref('stock.warehouse0')
        cls.fournisseur = cls.env['res.partner'].create({
            'name': "Dentaire Diffusion SA"})

        cls.compresse = cls._consommable("Compresses stériles 10x10")
        cls.gant = cls._consommable("Gants nitrile L")

        cls.patient = cls.env['megga.dental.patient'].create({
            'name': "Rémy Réassort"})
        cls.position = cls.env['megga.dental.position'].create({
            'code': "4.9100", 'name': "Soin à consommables", 'points': 30.0,
            'supply_ids': [Command.create({
                'product_id': cls.compresse.id, 'quantity': 4.0})],
        })

    @classmethod
    def _consommable(cls, nom, fournisseur=True, prix=10.0):
        produit = cls.env['product.product'].create({
            'name': nom,
            'type': 'consu',
            'is_storable': True,
            'tracking': 'lot',
            'use_expiration_date': True,
            'expiration_time': 400,
            'categ_id': cls.categ.id,
            'standard_price': prix,
        })
        if fournisseur:
            cls.env['product.supplierinfo'].create({
                'partner_id': cls.fournisseur.id,
                'product_tmpl_id': produit.product_tmpl_id.id,
                'price': prix,
                'delay': 3,
            })
        return produit

    def _regle(self, produit, mini, maxi):
        return self.env['stock.warehouse.orderpoint'].create({
            'product_id': produit.id,
            'location_id': self.stock.id,
            'warehouse_id': self.warehouse.id,
            'product_min_qty': mini,
            'product_max_qty': maxi,
            'trigger': 'auto',
        })

    def _en_stock(self, produit, quantite, lot=None):
        self.env['stock.quant']._update_available_quantity(
            produit, self.stock, quantite, lot_id=lot)

    def _lot(self, produit, nom, jours):
        return self.env['stock.lot'].create({
            'name': nom, 'product_id': produit.id,
            'expiration_date': fields.Datetime.now() + timedelta(days=jours),
        })

    def _planificateur(self):
        """Le planificateur DU CŒUR — jamais un cron maison.

        En Odoo 19 il vit sur `stock.rule` (le modèle
        `procurement.group` a disparu) : c'est exactement ce que le cron
        `stock.ir_cron_scheduler_action` appelle.
        """
        self.env['stock.rule'].run_scheduler()

    def _commandes(self, produit=None):
        domaine = [('partner_id', '=', self.fournisseur.id)]
        if produit is not None:
            domaine.append(('order_line.product_id', '=', produit.id))
        return self.env['purchase.order'].search(domaine)

    # ------------------------------------------------------------------
    # La règle et le bon de commande
    # ------------------------------------------------------------------
    def test_sous_le_mini_le_bon_de_commande_arrive(self):
        """Rayon sous le minimum : le planificateur propose la commande,
        chez le fournisseur du produit, à la quantité qui remonte au
        maximum."""
        self._en_stock(self.compresse, 2,
                       self._lot(self.compresse, "RE-1", 300))
        self._regle(self.compresse, 10.0, 40.0)

        self._planificateur()

        commandes = self._commandes(self.compresse)
        self.assertEqual(len(commandes), 1)
        self.assertEqual(commandes.state, 'draft',
                         "Le cabinet confirme lui-même : rien ne part "
                         "chez le fournisseur sans un geste humain.")
        ligne = commandes.order_line.filtered(
            lambda l: l.product_id == self.compresse)
        self.assertEqual(ligne.product_qty, 38.0)

    def test_au_dessus_du_mini_rien_ne_bouge(self):
        """Un rayon plein ne commande pas."""
        self._en_stock(self.compresse, 30,
                       self._lot(self.compresse, "RE-2", 300))
        self._regle(self.compresse, 10.0, 40.0)

        self._planificateur()

        self.assertFalse(self._commandes(self.compresse))

    def test_pas_de_doublon_au_second_passage(self):
        """Le planificateur tourne tous les jours : il ne recommande pas
        ce qui est déjà en commande."""
        self._en_stock(self.compresse, 2,
                       self._lot(self.compresse, "RE-3", 300))
        self._regle(self.compresse, 10.0, 40.0)
        self._planificateur()
        premieres = self._commandes(self.compresse)

        self._planificateur()

        self.assertEqual(self._commandes(self.compresse), premieres)
        self.assertEqual(
            sum(premieres.order_line.filtered(
                lambda l: l.product_id == self.compresse).mapped(
                    'product_qty')), 38.0)

    def test_sans_fournisseur_pas_de_commande_mais_pas_de_plantage(self):
        """Un consommable sans fournisseur ne fait pas tomber le
        planificateur : le cœur pose une activité d'avertissement sur le
        produit et poursuit avec les autres règles. Le magasin signale,
        il ne s'arrête pas."""
        orphelin = self._consommable("Fraise diamantée", fournisseur=False)
        self._en_stock(orphelin, 1)
        self._regle(orphelin, 5.0, 20.0)
        self._en_stock(self.compresse, 2,
                       self._lot(self.compresse, "RE-4", 300))
        self._regle(self.compresse, 10.0, 40.0)

        self._planificateur()

        self.assertTrue(self._commandes(self.compresse),
                        "La règle saine est servie malgré la voisine "
                        "en défaut.")
        self.assertTrue(
            orphelin.product_tmpl_id.activity_ids,
            "Le cœur prévient sur la fiche du produit sans fournisseur.")

    # ------------------------------------------------------------------
    # Le cycle complet : consommation -> commande -> réception
    # ------------------------------------------------------------------
    def test_cycle_complet_de_la_seance_au_rayon(self):
        """La séance consomme, le rayon passe sous le mini, la commande
        part, la réception remet un lot daté en rayon."""
        vieux = self._lot(self.compresse, "RE-VIEUX", 60)
        self._en_stock(self.compresse, 12, vieux)
        self._regle(self.compresse, 10.0, 30.0)

        seance = self.env['megga.dental.treatment'].create({
            'patient_id': self.patient.id,
            'line_ids': [Command.create({
                'position_id': self.position.id, 'quantity': 1.0})],
        })
        seance.action_confirm()
        seance.action_done()
        self.assertEqual(self._disponible(self.compresse), 8.0)

        self._planificateur()
        commande = self._commandes(self.compresse)
        self.assertEqual(len(commande), 1)
        commande.button_confirm()

        reception = commande.picking_ids
        self.assertTrue(reception)
        ligne = reception.move_ids.move_line_ids
        ligne.lot_name = "RE-NEUF"
        ligne.quantity = 22.0
        reception.move_ids.picked = True
        reception.button_validate()

        self.assertEqual(reception.state, 'done')
        self.assertEqual(self._disponible(self.compresse), 30.0)
        neuf = self.env['stock.lot'].search(
            [('name', '=', "RE-NEUF"),
             ('product_id', '=', self.compresse.id)])
        self.assertTrue(neuf.expiration_date,
                        "La réception date le lot depuis le délai du "
                        "produit.")
        self.assertGreater(neuf.expiration_date, vieux.expiration_date)

        # Et le cycle boucle : la séance suivante repart du lot le plus
        # ancien, pas de celui qui vient d'arriver. C'est tout l'intérêt
        # de dater les réceptions.
        suivante = self.env['megga.dental.treatment'].create({
            'patient_id': self.patient.id,
            'line_ids': [Command.create({
                'position_id': self.position.id, 'quantity': 1.0})],
        })
        suivante.action_confirm()
        suivante.action_done()

        servis = suivante.supply_picking_id.move_ids.move_line_ids
        self.assertEqual(servis.lot_id, vieux,
                         "FEFO : le lot fraîchement reçu attend son "
                         "tour derrière celui qui expire avant lui.")

    def test_deux_lots_en_rayon_le_plus_proche_part(self):
        """Rappel du socle, vu depuis le réassort : entre un lot ancien
        et un lot neuf, la séance sert l'ancien."""
        vieux = self._lot(self.compresse, "RE-A", 30)
        self._en_stock(self.compresse, 5, vieux)
        neuf = self._lot(self.compresse, "RE-B", 400)
        self._en_stock(self.compresse, 20, neuf)

        seance = self.env['megga.dental.treatment'].create({
            'patient_id': self.patient.id,
            'line_ids': [Command.create({
                'position_id': self.position.id, 'quantity': 1.0})],
        })
        seance.action_confirm()
        seance.action_done()

        lignes = seance.supply_picking_id.move_ids.move_line_ids
        self.assertEqual(lignes.lot_id, vieux)

    def test_cloture_avec_reassort_impossible_ne_bloque_pas(self):
        """Le croisement des deux chantiers, et le principe cardinal.

        Clore une séance valide un transfert ; `action_confirm` du cœur
        déclenche alors le réassort des règles automatiques touchées
        (`stock.move._trigger_scheduler`), EN SYNCHRONE, dans la même
        transaction que la clôture clinique. Si ce réassort explosait,
        la séance ne se clôturerait plus — le magasin bloquerait la
        clinique, ce que le produit refuse.

        Le cœur passe `raise_user_error=False` : les échecs de
        procurement deviennent des activités, pas des exceptions. Ce
        test tient cette promesse pour le pire cas du cabinet : un
        consommable sous son minimum, avec une règle automatique, et
        SANS fournisseur chez qui commander."""
        orphelin = self._consommable("Ciment provisoire", fournisseur=False)
        self._en_stock(orphelin, 6)
        self._regle(orphelin, 20.0, 50.0)
        position = self.env['megga.dental.position'].create({
            'code': "4.9200", 'name': "Scellement provisoire",
            'points': 18.0,
            'supply_ids': [Command.create({
                'product_id': orphelin.id, 'quantity': 2.0})],
        })
        seance = self.env['megga.dental.treatment'].create({
            'patient_id': self.patient.id,
            'line_ids': [Command.create({
                'position_id': position.id, 'quantity': 1.0})],
        })
        seance.action_confirm()

        seance.action_done()

        self.assertEqual(seance.state, 'done',
                         "La séance se clôt : le soin est fait.")
        self.assertEqual(seance.supply_picking_id.state, 'done')
        self.assertEqual(self._disponible(orphelin), 4.0)
        self.assertFalse(self._commandes(orphelin),
                         "Sans fournisseur, rien n'est commandé…")
        self.assertTrue(
            orphelin.product_tmpl_id.activity_ids,
            "…mais le cœur pose une activité sur la fiche produit.")

    # ------------------------------------------------------------------
    # Le raccourci du cabinet
    # ------------------------------------------------------------------
    def test_action_bornee_au_cabinet(self):
        """« À commander » ne montre que les consommables du cabinet :
        le réassort du restaurant d'à côté n'est pas son affaire."""
        action = self.env.ref(
            'megga_dental_stock.action_dental_replenishment')
        regle_cabinet = self._regle(self.compresse, 10.0, 40.0)
        autre = self.env['product.product'].create({
            'name': "Beurre", 'type': 'consu', 'is_storable': True})
        regle_autre = self._regle(autre, 1.0, 5.0)

        visibles = self.env['stock.warehouse.orderpoint'].search(
            safe_eval(action.domain))

        self.assertIn(regle_cabinet, visibles)
        self.assertNotIn(regle_autre, visibles)

    def test_l_ecran_suit_les_droits_du_coeur(self):
        """Le menu ne doit pas s'afficher pour refuser de s'ouvrir.

        L'écran des règles est ÉDITABLE, et l'ACL du cœur ne donne
        l'écriture qu'au responsable (`stock.group_stock_manager`) — le
        cœur garde d'ailleurs son propre menu « Replenishment » par ce
        groupe. Le module suit : le responsable voit le menu et ouvre
        l'écran ; le magasinier simple ne le voit pas, et garde les
        autres écrans du magasin, qui se lisent.

        Une action serveur, elle, aurait été refusée à l'exécution même
        au responsable : menu visible, écran fermé. Ce test tient la
        porte ouverte."""
        responsable = self.env['res.users'].create({
            'name': "Responsable réassort", 'login': "reassort_manager",
            'email': "reassort@exemple.ch",
            'group_ids': [(4, self.env.ref('stock.group_stock_manager').id),
                          (4, self.env.ref(
                              'megga_dental.group_dental_reception').id)],
        })
        magasinier = self.env['res.users'].create({
            'name': "Magasinier réassort", 'login': "reassort_user",
            'email': "magasin.reassort@exemple.ch",
            'group_ids': [(4, self.env.ref('stock.group_stock_user').id),
                          (4, self.env.ref(
                              'megga_dental.group_dental_reception').id)],
        })
        regle = self._regle(self.compresse, 10.0, 40.0)
        action = self.env.ref(
            'megga_dental_stock.action_dental_replenishment')

        # L'action est une action FENÊTRE : elle s'ouvre par une simple
        # lecture, sans droit d'exécution particulier.
        self.assertEqual(action._name, 'ir.actions.act_window')
        # Et sa vue ne porte PAS le js_class du cœur : ce panneau
        # « Horizon » appelle action_open_orderpoints, qui sème des
        # règles manuelles pour toute la société — restaurant compris.
        # On lit l'arch COMBINÉE (héritage résolu) : l'arch stockée ne
        # contient que le xpath, le test ne mordrait pas.
        vue = self.env.ref('megga_dental_stock.view_dental_orderpoint_list')
        combinee = vue.get_combined_arch()
        self.assertNotIn('stock_orderpoint_list', combinee)
        self.assertIn(
            'stock_orderpoint_list',
            self.env.ref(
                'stock.view_warehouse_orderpoint_tree_editable'
            ).get_combined_arch(),
            "Le cœur porte bien ce js_class : sans quoi le test "
            "ci-dessus ne prouverait rien.")
        lues = self.env['stock.warehouse.orderpoint'].with_user(
            responsable).search(safe_eval(action.domain))
        self.assertIn(regle, lues)
        # Et il peut vraiment écrire : l'écran est éditable.
        regle.with_user(responsable).write({'product_min_qty': 12.0})

        menu = self.env.ref(
            'megga_dental_stock.menu_dental_stock_replenish')
        Menu = self.env['ir.ui.menu']
        self.assertIn(menu.id,
                      Menu.with_user(responsable)._visible_menu_ids())
        self.assertNotIn(
            menu.id, Menu.with_user(magasinier)._visible_menu_ids(),
            "Le magasinier ne voit pas un écran qu'il ne peut pas "
            "remplir…")
        self.assertIn(
            self.env.ref('megga_dental_stock.menu_dental_stock_lots').id,
            Menu.with_user(magasinier)._visible_menu_ids(),
            "…mais il garde les écrans du magasin qui se lisent.")

    def test_commander_a_la_demande_depuis_l_ecran(self):
        """L'écran du cabinet n'est pas qu'un tableau : le bouton
        « Commander » du cœur y fonctionne.

        La vue réutilisée porte un `js_class` qui ajoute ce bouton —
        il appelle `action_replenish` sur les règles sélectionnées.
        C'est le geste du magasinier qui ne veut pas attendre le
        planificateur de la nuit ; il doit marcher depuis notre menu
        comme depuis l'app Inventaire."""
        self._en_stock(self.compresse, 3,
                       self._lot(self.compresse, "RE-DEMANDE", 300))
        regle = self._regle(self.compresse, 10.0, 25.0)

        regle.action_replenish()

        commande = self._commandes(self.compresse)
        self.assertEqual(len(commande), 1)
        ligne = commande.order_line.filtered(
            lambda l: l.product_id == self.compresse)
        self.assertEqual(ligne.product_qty, 22.0)

    def test_le_menu_a_commander_ouvre_bien_l_ecran_du_cabinet(self):
        """Comme tout le magasin : un raccourci, pas une porte
        dérobée — et le MÊME groupe que le menu équivalent du cœur.

        Le test suit le fil ENTIER, du menu jusqu'au périmètre :
        vérifier les groupes d'un côté et le domaine de l'action de
        l'autre laisserait le câblage du milieu sans témoin. On
        pourrait alors repointer ce menu sur l'écran de réappro complet
        du cœur — celui qui sème des règles pour toute la société — sans
        qu'un seul test ne morde."""
        menu = self.env.ref(
            'megga_dental_stock.menu_dental_stock_replenish')
        self.assertEqual(menu.group_ids,
                         self.env.ref('stock.group_stock_manager'))
        self.assertEqual(
            menu.action,
            self.env.ref('megga_dental_stock.action_dental_replenishment'),
            "Le menu du cabinet ouvre l'action du cabinet, pas celle "
            "du cœur.")
        self.assertEqual(
            menu.action.view_id,
            self.env.ref('megga_dental_stock.view_dental_orderpoint_list'),
            "…et il l'ouvre sur la vue SANS le js_class semeur.")
        self.assertEqual(
            menu.action.search_view_id,
            self.env.ref('stock.stock_reorder_report_search'))
        regle_cabinet = self._regle(self.compresse, 10.0, 40.0)
        depuis_le_menu = self.env['stock.warehouse.orderpoint'].search(
            safe_eval(menu.action.domain))
        self.assertIn(regle_cabinet, depuis_le_menu)
        self.assertEqual(
            menu.group_ids,
            self.env.ref('stock.menu_reordering_rules_replenish').group_ids,
            "Le cabinet ne diverge pas du cœur sur les droits.")
        self.assertEqual(
            menu.parent_id,
            self.env.ref('megga_dental_stock.menu_dental_stock_root'))

    def test_aucun_cron_maison(self):
        """Le planificateur du cœur suffit : un second ordonnanceur
        ferait des bons de commande en double."""
        maison = self.env['ir.model.data'].search([
            ('module', '=', 'megga_dental_stock'),
            ('model', '=', 'ir.cron'),
        ])
        self.assertFalse(maison, "Le module ne pose aucun cron.")
        self.assertTrue(
            self.env.ref('stock.ir_cron_scheduler_action').active,
            "Le planificateur du cœur, lui, est bien là et actif.")

    def _disponible(self, produit):
        return self.env['stock.quant']._get_available_quantity(
            produit, self.stock, allow_negative=True)
