from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase


class TestDentalSupply(TransactionCase):
    """Le pont acte → consommation : ce que le cabinet consomme se
    déduit de ce qu'il soigne. Zéro ressaisie au fauteuil, jamais deux
    fois, jamais bloquant — et le magasin ne raconte pas les soins."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.categ = cls.env.ref(
            'megga_dental_stock.product_category_dental_supplies')
        cls.care = cls.env.ref(
            'megga_dental_stock.stock_location_dental_care')
        cls.stock = cls.env.ref('stock.stock_location_stock')
        cls.warehouse = cls.env.ref('stock.warehouse0')

        cls.compresse = cls._consommable("Compresses stériles")
        cls.gant = cls._consommable("Gants nitrile")

        Position = cls.env['megga.dental.position']
        cls.obturation = Position.create({
            'code': "4.0100", 'name': "Obturation composite",
            'points': 40.0,
            'supply_ids': [Command.create({
                'product_id': cls.compresse.id, 'quantity': 2.0,
            }), Command.create({
                'product_id': cls.gant.id, 'quantity': 1.0,
            })],
        })
        cls.detartrage = Position.create({
            'code': "4.0200", 'name': "Détartrage",
            'points': 25.0,
            'supply_ids': [Command.create({
                'product_id': cls.compresse.id, 'quantity': 3.0,
            })],
        })
        cls.controle = Position.create({
            'code': "4.0000", 'name': "Contrôle annuel", 'points': 20.0})

        cls.patient = cls.env['megga.dental.patient'].create({
            'name': "Sophie Consommable"})
        cls.dentiste = cls.env['res.users'].create({
            'name': "Dr Kit", 'login': "supply_dentist",
            'email': "dr.kit@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_praticien').id)],
        })

    @classmethod
    def _consommable(cls, nom, tracking='lot', expiration=True):
        return cls.env['product.product'].create({
            'name': nom,
            'type': 'consu',
            'is_storable': True,
            'tracking': tracking,
            'use_expiration_date': expiration,
            'expiration_time': 365 if expiration else 0,
            'categ_id': cls.categ.id,
        })

    @classmethod
    def _lot(cls, product, name, jours):
        return cls.env['stock.lot'].create({
            'name': name, 'product_id': product.id,
            'expiration_date': fields.Datetime.now() + timedelta(days=jours),
        })

    def _en_stock(self, product, quantity, lot=None):
        self.env['stock.quant']._update_available_quantity(
            product, self.stock, quantity, lot_id=lot)

    def _seance(self, positions, quantities=None):
        """Une séance planifiée, prête à être close."""
        quantities = quantities or [1.0] * len(positions)
        treatment = self.env['megga.dental.treatment'].create({
            'patient_id': self.patient.id,
            'dentist_id': self.dentiste.id,
            'line_ids': [Command.create({
                'position_id': position.id, 'quantity': quantity,
            }) for position, quantity in zip(positions, quantities)],
        })
        treatment.action_confirm()
        return treatment

    def _dispo(self, product, lot=None):
        return self.env['stock.quant']._get_available_quantity(
            product, self.stock, lot_id=lot, strict=bool(lot),
            allow_negative=True)

    # ------------------------------------------------------------------
    # Le décompte lui-même
    # ------------------------------------------------------------------
    def test_cloture_consomme(self):
        """Clore la séance sort du magasin ce que l'acte a mangé."""
        lot = self._lot(self.compresse, "CMP-1", 90)
        self._en_stock(self.compresse, 10, lot)
        self._en_stock(self.gant, 10, self._lot(self.gant, "GNT-1", 200))
        treatment = self._seance([self.obturation])

        treatment.action_done()

        picking = treatment.supply_picking_id
        self.assertTrue(picking)
        self.assertEqual(picking.state, 'done')
        self.assertEqual(self._dispo(self.compresse), 8.0)
        self.assertEqual(self._dispo(self.gant), 9.0)

    def test_deux_actes_un_seul_mouvement_par_produit(self):
        """Obturation (2 compresses) + détartrage (3) = UNE ligne de 5 :
        le magasin compte des compresses, pas des actes."""
        self._en_stock(self.compresse, 20,
                       self._lot(self.compresse, "CMP-2", 90))
        self._en_stock(self.gant, 5, self._lot(self.gant, "GNT-2", 200))
        treatment = self._seance([self.obturation, self.detartrage])

        treatment.action_done()

        moves = treatment.supply_picking_id.move_ids
        compresses = moves.filtered(
            lambda m: m.product_id == self.compresse)
        self.assertEqual(len(compresses), 1)
        self.assertEqual(compresses.product_uom_qty, 5.0)
        self.assertEqual(self._dispo(self.compresse), 15.0)

    def test_quantite_de_l_acte_multiplie(self):
        """Deux obturations consomment deux fois le kit."""
        self._en_stock(self.compresse, 20,
                       self._lot(self.compresse, "CMP-3", 90))
        self._en_stock(self.gant, 20, self._lot(self.gant, "GNT-3", 200))
        treatment = self._seance([self.obturation], quantities=[2.0])

        treatment.action_done()

        self.assertEqual(self._dispo(self.compresse), 16.0)
        self.assertEqual(self._dispo(self.gant), 18.0)

    def test_position_sans_kit_ne_cree_rien(self):
        """Pas de coquille vide : une séance sans consommable réglé ne
        crée aucun transfert."""
        treatment = self._seance([self.controle])

        treatment.action_done()

        self.assertFalse(treatment.supply_picking_id)
        self.assertEqual(treatment.state, 'done')

    def test_conversion_d_unite(self):
        """Le kit se saisit dans SON unité : 500 g d'un article au kilo
        décomptent 0.5 kg — sans arrondi en route."""
        kilo = self.env.ref('uom.product_uom_kgm')
        gramme = self.env.ref('uom.product_uom_gram')
        alginate = self.env['product.product'].create({
            'name': "Alginate", 'type': 'consu', 'is_storable': True,
            'uom_id': kilo.id, 'categ_id': self.categ.id})
        position = self.env['megga.dental.position'].create({
            'code': "4.0300", 'name': "Empreinte", 'points': 15.0,
            'supply_ids': [Command.create({
                'product_id': alginate.id,
                'quantity': 500.0, 'uom_id': gramme.id})],
        })
        self._en_stock(alginate, 5.0)
        treatment = self._seance([position])

        treatment.action_done()

        self.assertAlmostEqual(self._dispo(alginate), 4.5, places=6)

    # ------------------------------------------------------------------
    # FEFO et péremption
    # ------------------------------------------------------------------
    def test_fefo_a_la_cloture(self):
        """Deux lots en rayon : part celui qui expire en premier."""
        tard = self._lot(self.compresse, "CMP-TARD", 300)
        self._en_stock(self.compresse, 10, tard)
        tot = self._lot(self.compresse, "CMP-TOT", 20)
        self._en_stock(self.compresse, 10, tot)
        self._en_stock(self.gant, 10, self._lot(self.gant, "GNT-4", 200))
        treatment = self._seance([self.obturation])

        treatment.action_done()

        lignes = treatment.supply_picking_id.move_ids.filtered(
            lambda m: m.product_id == self.compresse).move_line_ids
        self.assertEqual(lignes.lot_id, tot)
        self.assertEqual(self._dispo(self.compresse, tot), 8.0)
        self.assertEqual(self._dispo(self.compresse, tard), 10.0)

    def test_lot_perime_jamais_choisi(self):
        """Le périmé reste en rayon — il ne part pas au fauteuil."""
        perime = self._lot(self.compresse, "CMP-PERIME", -2)
        self._en_stock(self.compresse, 10, perime)
        bon = self._lot(self.compresse, "CMP-BON", 60)
        self._en_stock(self.compresse, 10, bon)
        self._en_stock(self.gant, 10, self._lot(self.gant, "GNT-5", 200))
        treatment = self._seance([self.obturation])

        treatment.action_done()

        lignes = treatment.supply_picking_id.move_ids.filtered(
            lambda m: m.product_id == self.compresse).move_line_ids
        self.assertEqual(lignes.lot_id, bon)
        self.assertEqual(self._dispo(self.compresse, perime), 10.0)

    def test_plus_que_du_perime_sort_sans_lot(self):
        """Traçabilité dégradée, jamais blocage : la séance se clôt, le
        mouvement part sans lot, une activité le dit au magasin."""
        perime = self._lot(self.compresse, "CMP-SEUL", -5)
        self._en_stock(self.compresse, 10, perime)
        self._en_stock(self.gant, 10, self._lot(self.gant, "GNT-6", 200))
        treatment = self._seance([self.obturation])

        treatment.action_done()

        picking = treatment.supply_picking_id
        self.assertEqual(picking.state, 'done')
        lignes = picking.move_ids.filtered(
            lambda m: m.product_id == self.compresse).move_line_ids
        self.assertFalse(lignes.lot_id)
        self.assertEqual(self._dispo(self.compresse, perime), 10.0,
                         "Le lot périmé reste en rayon, à détruire.")
        activite = picking.activity_ids
        self.assertTrue(activite)
        # La note est du HTML : les motifs y tiennent en lignes, et le
        # nom du produit y figure — le magasin doit savoir QUOI vérifier.
        self.assertIn("Compresses", activite.note)
        self.assertIn("<br", activite.note)

    # ------------------------------------------------------------------
    # Le stock ne bloque jamais la clinique
    # ------------------------------------------------------------------
    def test_stock_a_zero_la_cloture_passe(self):
        """Rien en rayon : la séance se clôt, le quant passe en négatif,
        l'activité signale l'écart. La clinique d'abord."""
        treatment = self._seance([self.obturation])

        treatment.action_done()

        self.assertEqual(treatment.state, 'done')
        picking = treatment.supply_picking_id
        self.assertEqual(picking.state, 'done')
        self.assertEqual(self._dispo(self.compresse), -2.0)
        self.assertEqual(self._dispo(self.gant), -1.0)
        self.assertTrue(picking.activity_ids)

    def test_stock_partiel_complete_sans_lot(self):
        """Une compresse en rayon, deux nécessaires : la première part
        de son lot, la seconde part quand même."""
        lot = self._lot(self.compresse, "CMP-PARTIEL", 90)
        self._en_stock(self.compresse, 1, lot)
        self._en_stock(self.gant, 10, self._lot(self.gant, "GNT-7", 200))
        treatment = self._seance([self.obturation])

        treatment.action_done()

        self.assertEqual(self._dispo(self.compresse, lot), 0.0)
        self.assertEqual(self._dispo(self.compresse), -1.0)
        self.assertTrue(treatment.supply_picking_id.activity_ids)

    # ------------------------------------------------------------------
    # Jamais deux fois
    # ------------------------------------------------------------------
    def test_cloture_rejouee_ne_double_rien(self):
        """Garde d'état : une séance terminée refuse d'être re-close."""
        self._en_stock(self.compresse, 10,
                       self._lot(self.compresse, "CMP-IDEM", 90))
        self._en_stock(self.gant, 10, self._lot(self.gant, "GNT-8", 200))
        treatment = self._seance([self.obturation])
        treatment.action_done()
        picking = treatment.supply_picking_id

        with self.assertRaises(UserError):
            treatment.action_done()

        self.assertEqual(treatment.supply_picking_id, picking)
        self.assertEqual(self._dispo(self.compresse), 8.0)

    def test_consume_rappele_a_la_main_ne_double_rien(self):
        """Ceinture d'idempotence : le lien vers le transfert suffit,
        marquage par IDENTITÉ et non par valeur."""
        self._en_stock(self.compresse, 10,
                       self._lot(self.compresse, "CMP-CEINTURE", 90))
        self._en_stock(self.gant, 10, self._lot(self.gant, "GNT-9", 200))
        treatment = self._seance([self.obturation])
        treatment.action_done()
        picking = treatment.supply_picking_id

        treatment._consume_supplies()
        treatment._consume_supplies()

        self.assertEqual(treatment.supply_picking_id, picking)
        self.assertEqual(self._dispo(self.compresse), 8.0)

    def test_annulation_ne_reintegre_rien(self):
        """Une compresse sortie ne se remet pas en boîte : le geste
        inverse est un ajustement d'inventaire, tracé."""
        self._en_stock(self.compresse, 10,
                       self._lot(self.compresse, "CMP-ANNUL", 90))
        self._en_stock(self.gant, 10, self._lot(self.gant, "GNT-10", 200))
        treatment = self._seance([self.obturation])
        treatment.action_done()

        treatment.action_cancel()

        self.assertEqual(treatment.state, 'cancelled')
        self.assertEqual(treatment.supply_picking_id.state, 'done')
        self.assertEqual(self._dispo(self.compresse), 8.0)

    # ------------------------------------------------------------------
    # nLPD : le magasin ne raconte pas les soins
    # ------------------------------------------------------------------
    def test_lpd_le_mouvement_ne_dit_que_la_reference(self):
        """Le magasinier lit un transfert, pas un dossier médical."""
        self._en_stock(self.compresse, 10,
                       self._lot(self.compresse, "CMP-LPD", 90))
        self._en_stock(self.gant, 10, self._lot(self.gant, "GNT-11", 200))
        treatment = self._seance([self.obturation, self.detartrage])
        treatment.patient_id.write({'name': "Sophie Consommable"})

        treatment.action_done()

        picking = treatment.supply_picking_id
        self.assertEqual(picking.origin, treatment.name)
        self.assertFalse(picking.partner_id,
                         "Nommer le patient serait le raconter.")
        empreinte = " ".join([
            picking.origin or '', picking.name or '', picking.note or '',
            " ".join(picking.move_ids.mapped('description_picking') or []),
        ])
        # L'empreinte porte bien quelque chose : sans cette assertion,
        # un picking muet ferait passer le test pour rien.
        self.assertIn(treatment.name, empreinte)
        for interdit in ("Sophie", "Obturation", "Détartrage", "4.0100"):
            self.assertNotIn(interdit, empreinte)

    def test_reception_clot_sans_droits_stock(self):
        """L'effet système passe pour qui n'a aucun droit sur le
        magasin — et ne lui en donne aucun pour autant."""
        receptionniste = self.env['res.users'].create({
            'name': "Réception Kit", 'login': "supply_reception",
            'email': "reception.kit@exemple.ch",
            'group_ids': [(4, self.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        self._en_stock(self.compresse, 10,
                       self._lot(self.compresse, "CMP-SUDO", 90))
        self._en_stock(self.gant, 10, self._lot(self.gant, "GNT-12", 200))
        treatment = self._seance([self.obturation])

        treatment.with_user(receptionniste).action_done()

        self.assertEqual(treatment.state, 'done')
        self.assertEqual(self._dispo(self.compresse), 8.0)
        with self.assertRaises(AccessError):
            self.env['stock.picking'].with_user(
                receptionniste).search_count([])

    # ------------------------------------------------------------------
    # Le type d'opération dédié
    # ------------------------------------------------------------------
    def test_type_operation_dedie_et_reutilise(self):
        """Un type « Consommation en soins » par entrepôt, créé une
        fois : lots libres (traçabilité dégradée possible), pas de
        reliquat."""
        premier = self.warehouse._megga_dental_care_picking_type()
        second = self.warehouse._megga_dental_care_picking_type()

        self.assertEqual(premier, second)
        self.assertFalse(premier.use_create_lots)
        self.assertFalse(premier.use_existing_lots)
        self.assertEqual(premier.create_backorder, 'never')
        self.assertEqual(premier.default_location_dest_id, self.care)
        self.assertTrue(premier.sequence_id)

    def test_lot_date_sur_produit_sans_peremption(self):
        """Le trou que le cœur ne bouche pas.

        Le cœur n'écarte les lots périmés de la réservation QUE si le
        produit coche « utiliser la date de péremption ». Décochez-la
        après coup — un cabinet le fait — et un lot daté et périmé
        redevient réservable : la garde du magasin refuserait alors la
        sortie et la clôture de séance planterait. La ceinture du pont
        le retire avant, et la séance passe."""
        gaze = self._consommable("Gaze héritée", expiration=False)
        perime = self.env['stock.lot'].create({
            'name': "GAZ-VIEILLE", 'product_id': gaze.id,
            'expiration_date': fields.Datetime.now() - timedelta(days=10),
        })
        self._en_stock(gaze, 10, perime)
        position = self.env['megga.dental.position'].create({
            'code': "4.0500", 'name': "Pansement", 'points': 12.0,
            'supply_ids': [Command.create({
                'product_id': gaze.id, 'quantity': 2.0})],
        })
        treatment = self._seance([position])

        treatment.action_done()

        self.assertEqual(treatment.state, 'done')
        picking = treatment.supply_picking_id
        self.assertEqual(picking.state, 'done')
        self.assertFalse(picking.move_ids.move_line_ids.lot_id,
                         "Le lot périmé est écarté, la sortie part "
                         "sans lot plutôt que de bloquer la séance.")
        self.assertEqual(self._dispo(gaze, perime), 10.0)
        self.assertTrue(picking.activity_ids)

    def test_kit_a_produit_non_stockable_ignore(self):
        """Un kit peut porter un service (forfait de stérilisation) :
        rien à décompter, et surtout pas de mouvement vide."""
        service = self.env['product.product'].create({
            'name': "Forfait stérilisation", 'type': 'service'})
        position = self.env['megga.dental.position'].create({
            'code': "4.0400", 'name': "Acte à service", 'points': 10.0,
            'supply_ids': [Command.create({
                'product_id': service.id, 'quantity': 1.0})],
        })
        treatment = self._seance([position])

        treatment.action_done()

        self.assertFalse(treatment.supply_picking_id)

    def test_kit_fractionnaire(self):
        """Un demi-flacon par acte : la fraction traverse le décompte
        sans se faire arrondir en route, rayon vide compris."""
        position = self.env['megga.dental.position'].create({
            'code': "4.0600", 'name': "Polissage", 'points': 8.0,
            'supply_ids': [Command.create({
                'product_id': self.compresse.id, 'quantity': 0.4})],
        })
        treatment = self._seance([position], quantities=[3.0])

        treatment.action_done()

        self.assertEqual(treatment.state, 'done')
        self.assertEqual(treatment.supply_picking_id.state, 'done')
        self.assertAlmostEqual(self._dispo(self.compresse), -1.2, places=6)

    def test_acte_a_quantite_nulle_ne_bloque_pas(self):
        """Un acte saisi à zéro ne fait pas de mouvement — et surtout
        n'empêche pas de clore : le cœur refuse de valider un transfert
        à quantité nulle."""
        self._en_stock(self.compresse, 10,
                       self._lot(self.compresse, "CMP-ZERO", 90))
        treatment = self._seance([self.obturation], quantities=[0.0])

        treatment.action_done()

        self.assertEqual(treatment.state, 'done')
        self.assertFalse(treatment.supply_picking_id)
        self.assertEqual(self._dispo(self.compresse), 10.0)

    def test_acte_nul_et_acte_reel_dans_la_meme_seance(self):
        """L'acte à zéro s'efface, l'autre est servi normalement."""
        self._en_stock(self.compresse, 10,
                       self._lot(self.compresse, "CMP-MIXTE", 90))
        self._en_stock(self.gant, 10, self._lot(self.gant, "GNT-13", 200))
        treatment = self._seance([self.obturation, self.detartrage],
                                 quantities=[0.0, 1.0])

        treatment.action_done()

        picking = treatment.supply_picking_id
        self.assertTrue(picking)
        self.assertEqual(picking.move_ids.product_id, self.compresse)
        self.assertEqual(self._dispo(self.compresse), 7.0)
        self.assertEqual(self._dispo(self.gant), 10.0)

    def test_seance_annulee_ne_consomme_rien(self):
        """Annuler une séance planifiée ne sort rien du magasin : seule
        la clôture décompte."""
        self._en_stock(self.compresse, 10,
                       self._lot(self.compresse, "CMP-CANCEL", 90))
        treatment = self._seance([self.obturation])

        treatment.action_cancel()

        self.assertFalse(treatment.supply_picking_id)
        self.assertEqual(self._dispo(self.compresse), 10.0)

    def test_kit_refuse_une_quantite_nulle(self):
        """Un kit à zéro ne consomme rien : autant retirer la ligne."""
        with self.assertRaises(ValidationError):
            self.env['megga.dental.position.supply'].create({
                'position_id': self.controle.id,
                'product_id': self.compresse.id,
                'quantity': 0.0,
            })

    def test_kit_refuse_une_unite_incompatible(self):
        """On ne décompte pas des grammes d'un article à la pièce."""
        with self.assertRaises(ValidationError):
            self.env['megga.dental.position.supply'].create({
                'position_id': self.controle.id,
                'product_id': self.compresse.id,
                'quantity': 1.0,
                'uom_id': self.env.ref('uom.product_uom_kgm').id,
            })
