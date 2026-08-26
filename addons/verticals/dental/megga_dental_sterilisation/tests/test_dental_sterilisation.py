from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase
from odoo.tools.safe_eval import safe_eval


class TestDentalSterilisation(TransactionCase):
    """La traçabilité de stérilisation : la charge, ses sets, et le lien
    dans les deux sens.

    Le module ne réinvente ni le lot, ni la péremption, ni le FEFO : on
    teste donc la COUTURE — le cycle qui fait entrer ses sets, la garde
    qui refuse un set non conforme en soins, le rappel qui nomme les
    séances servies, et la preuve qui remonte depuis la séance.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.categorie = cls.env.ref(
            'megga_dental_sterilisation.product_category_dental_sets')
        cls.autoclave = cls.env['maintenance.equipment'].create({
            'name': "Autoclave classe B",
            'category_id': cls.env.ref(
                'megga_dental_materiel.equipment_category_sterilisation').id,
            'maintenance_team_id': cls.env.ref(
                'megga_dental_materiel.maintenance_team_dental').id,
        })
        cls.set_examen = cls.env['product.product'].create({
            'name': "Set d'examen stérilisé",
            'type': 'consu',
            'is_storable': True,
            'tracking': 'lot',
            'use_expiration_date': True,
            # 180 jours : la stérilité d'un sachet pelable, pas la
            # péremption d'un consommable.
            'expiration_time': 180,
            'categ_id': cls.categorie.id,
        })
        cls.set_chirurgie = cls.env['product.product'].create({
            'name': "Set de chirurgie stérilisé",
            'type': 'consu',
            'is_storable': True,
            'tracking': 'lot',
            'use_expiration_date': True,
            'expiration_time': 90,
            'categ_id': cls.categorie.id,
        })
        cls.entrepot = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1)
        cls.soins = cls.env.ref(
            'megga_dental_stock.stock_location_dental_care')

    # ------------------------------------------------------------------
    # Aides
    # ------------------------------------------------------------------
    def _cycle(self, lignes=None, **valeurs):
        base = {
            'equipment_id': self.autoclave.id,
            'helix_ok': True,
            'line_ids': [(0, 0, {
                'product_id': produit.id, 'quantity': quantite,
            }) for produit, quantite in (
                [(self.set_examen, 4.0)] if lignes is None
                else lignes)],
        }
        base.update(valeurs)
        return self.env['megga.dental.sterilisation.cycle'].create(base)

    def _consomme(self, lot, quantite=1.0, destination=None):
        """Envoie un set vers les soins — le geste que la garde vise."""
        destination = destination or self.soins
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.entrepot.out_type_id.id,
            'location_id': self.entrepot.lot_stock_id.id,
            'location_dest_id': destination.id,
            'move_ids': [(0, 0, {
                'product_id': lot.product_id.id,
                'product_uom_qty': quantite,
                'product_uom': lot.product_id.uom_id.id,
                'location_id': self.entrepot.lot_stock_id.id,
                'location_dest_id': destination.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        move = picking.move_ids
        move.move_line_ids.unlink()
        self.env['stock.move.line'].create({
            'move_id': move.id,
            'picking_id': picking.id,
            'product_id': move.product_id.id,
            'product_uom_id': move.product_uom.id,
            'lot_id': lot.id,
            'location_id': move.location_id.id,
            'location_dest_id': move.location_dest_id.id,
            'quantity': quantite,
        })
        move.picked = True
        return picking.with_context(
            skip_backorder=True, skip_expired=True).button_validate()

    # ------------------------------------------------------------------
    # Le cycle
    # ------------------------------------------------------------------
    def test_le_cycle_prend_son_numero(self):
        """Le numéro de cycle est ce qui part sur l'étiquette."""
        cycle = self._cycle()

        self.assertTrue(cycle.name.startswith('STE/'))
        self.assertEqual(cycle.state, 'draft')

    def test_valider_fait_entrer_les_sets_en_rayon(self):
        """Le geste central : la charge validée devient du stock tracé.

        Un lot par ligne, le numéro de cycle en nom, et la stérilité qui
        expire au délai du produit — compté depuis le CYCLE, pas depuis
        la saisie."""
        cycle = self._cycle(lignes=[(self.set_examen, 4.0),
                                    (self.set_chirurgie, 2.0)])

        cycle.action_validate()

        self.assertEqual(cycle.state, 'done')
        self.assertEqual(len(cycle.lot_ids), 2)
        examen = cycle.lot_ids.filtered(
            lambda l: l.product_id == self.set_examen)
        self.assertEqual(examen.sterilisation_cycle_id, cycle)
        attendue = cycle.date_start + timedelta(days=180)
        self.assertEqual(examen.expiration_date, attendue,
                         "La stérilité court depuis la charge.")
        chirurgie = cycle.lot_ids.filtered(
            lambda l: l.product_id == self.set_chirurgie)
        self.assertEqual(chirurgie.expiration_date,
                         cycle.date_start + timedelta(days=90))
        # …et les sachets sont vraiment en rayon.
        self.assertEqual(
            self.env['stock.quant']._get_available_quantity(
                self.set_examen, self.entrepot.lot_stock_id,
                lot_id=examen, strict=True), 4.0)

    def test_les_lots_d_une_charge_se_distinguent(self):
        """Deux types de sets dans une charge : les lots portent tous le
        numéro de cycle, et se distinguent quand même."""
        cycle = self._cycle(lignes=[(self.set_examen, 3.0),
                                    (self.set_chirurgie, 1.0)])

        cycle.action_validate()

        noms = sorted(cycle.lot_ids.mapped('name'))
        self.assertEqual(noms, ["%s-1" % cycle.name, "%s-2" % cycle.name])

    def test_une_charge_d_un_seul_set_garde_le_numero_nu(self):
        """Le cas courant : le lot EST le numéro de cycle."""
        cycle = self._cycle()

        cycle.action_validate()

        self.assertEqual(cycle.lot_ids.name, cycle.name)

    def test_valider_deux_fois_ne_double_pas_le_stock(self):
        """Ceinture d'idempotence par IDENTITÉ : le lien vers le
        transfert interdit une seconde entrée."""
        cycle = self._cycle()
        cycle.action_validate()
        transfert = cycle.picking_id

        with self.assertRaises(UserError):
            cycle.action_validate()

        self.assertEqual(cycle.picking_id, transfert)
        self.assertEqual(len(cycle.lot_ids), 1)

    def test_une_charge_vide_ne_se_valide_pas(self):
        """Pas de coquille vide : une charge sans set n'a rien à faire
        entrer en rayon."""
        cycle = self._cycle(lignes=[])

        with self.assertRaises(UserError):
            cycle.action_validate()

    def test_un_cycle_b_sans_helix_ne_se_valide_pas(self):
        """Le contrôle qui prouve la pénétration de vapeur : sans lui,
        une charge emballée n'est pas prouvée stérile."""
        cycle = self._cycle(helix_ok=False)

        with self.assertRaises(UserError):
            cycle.action_validate()

    def test_un_cycle_n_se_valide_sans_helix(self):
        """Le test Helix vise la charge creuse ou emballée : l'exiger
        d'un cycle N bloquerait le cabinet pour rien."""
        cycle = self._cycle(program='n', helix_ok=False)

        cycle.action_validate()

        self.assertEqual(cycle.state, 'done')

    def test_un_indicateur_non_conforme_bloque_la_validation(self):
        """Si le résultat est déjà connu, la charge ne part pas en
        rayon."""
        cycle = self._cycle(indicator='fail')

        with self.assertRaises(UserError):
            cycle.action_validate()

    # ------------------------------------------------------------------
    # Le registre est un document de preuve
    # ------------------------------------------------------------------
    def test_un_cycle_clos_est_fige(self):
        """Comme l'ordonnance émise : le relevé ne se réécrit pas."""
        cycle = self._cycle()
        cycle.action_validate()

        with self.assertRaises(UserError):
            cycle.temperature = 121.0

    def test_l_indicateur_reste_ouvert_apres_validation(self):
        """Le seul champ qui doit rester ouvert : son résultat arrive le
        lendemain, une fois les sachets distribués."""
        cycle = self._cycle(indicator='pending')
        cycle.action_validate()

        cycle.indicator = 'pass'

        self.assertEqual(cycle.indicator, 'pass')

    def test_un_cycle_ne_se_supprime_pas(self):
        """Un registre de stérilisation ne s'efface pas — pas même un
        brouillon : il dit qu'une charge est passée."""
        cycle = self._cycle()

        with self.assertRaises(UserError):
            cycle.unlink()

    def test_une_charge_validee_ne_revient_pas_en_brouillon(self):
        """Ses sets sont partis en rayon, peut-être au fauteuil : on
        refait un cycle, on ne réécrit pas l'histoire."""
        cycle = self._cycle()
        cycle.action_validate()
        cycle.action_fail()

        with self.assertRaises(UserError):
            cycle.action_back_to_draft()

    def test_une_charge_ratee_avant_validation_revient_en_brouillon(self):
        """Rien n'est sorti : la charge se reprend."""
        cycle = self._cycle()
        cycle.action_fail()

        cycle.action_back_to_draft()

        self.assertEqual(cycle.state, 'draft')

    # ------------------------------------------------------------------
    # La garde : un set non conforme ne part pas en soins
    # ------------------------------------------------------------------
    def test_un_set_conforme_part_en_soins(self):
        """La garde ne gêne pas le cas normal."""
        cycle = self._cycle()
        cycle.action_validate()

        self._consomme(cycle.lot_ids)

        self.assertEqual(
            self.env['stock.quant']._get_available_quantity(
                self.set_examen, self.entrepot.lot_stock_id,
                lot_id=cycle.lot_ids, strict=True), 3.0)

    def test_un_set_non_conforme_ne_part_jamais_en_soins(self):
        """LE geste du lendemain : l'indicateur revient non conforme, et
        les sachets encore en rayon sont bloqués — même préparés sur le
        plateau."""
        cycle = self._cycle(indicator='pending')
        cycle.action_validate()
        cycle.indicator = 'fail'
        cycle.action_fail()

        with self.assertRaises(UserError) as refus:
            self._consomme(cycle.lot_ids)

        self.assertIn(cycle.name, str(refus.exception))

    def test_le_rebut_d_un_set_non_conforme_reste_permis(self):
        """Sans quoi un sachet non conforme resterait immobilisé en
        rayon pour toujours."""
        cycle = self._cycle()
        cycle.action_validate()
        cycle.action_fail()
        # Odoo 19 : le rebut n'est plus un booleen sur
        # l'emplacement, c'est usage='inventory' (le champ
        # `scrap_location` a disparu — verifie dans le coeur).
        rebut = self.env['stock.location'].search(
            [('usage', '=', 'inventory'),
             ('company_id', 'in', [False, self.env.company.id])], limit=1)

        self._consomme(cycle.lot_ids, destination=rebut)

        self.assertEqual(
            self.env['stock.quant']._get_available_quantity(
                self.set_examen, self.entrepot.lot_stock_id,
                lot_id=cycle.lot_ids, strict=True), 3.0)

    def test_la_garde_ne_vise_que_les_sets_du_registre(self):
        """Un lot ordinaire du magasin n'a pas de cycle : la garde de la
        stérilisation le laisse passer (celle du chantier 1, elle,
        continue de veiller sur sa péremption)."""
        compresse = self.env['product.product'].create({
            'name': "Compresses", 'type': 'consu', 'is_storable': True,
            'tracking': 'lot',
            'categ_id': self.env.ref(
                'megga_dental_stock.product_category_dental_supplies').id,
        })
        lot = self.env['stock.lot'].create({
            'name': "CMP-001", 'product_id': compresse.id})
        self.env['stock.quant']._update_available_quantity(
            compresse, self.entrepot.lot_stock_id, 5.0, lot_id=lot)

        self._consomme(lot)

        self.assertFalse(lot.sterilisation_cycle_id)

    def test_les_deux_gardes_coexistent(self):
        """Un set d'un cycle conforme mais PÉRIMÉ reste refusé : la
        garde du chantier 1 ne saute pas parce que la nôtre passe."""
        cycle = self._cycle()
        cycle.action_validate()
        cycle.lot_ids.sudo().expiration_date = (
            fields.Datetime.now() - timedelta(days=1))

        with self.assertRaises(UserError) as refus:
            self._consomme(cycle.lot_ids)

        self.assertIn("périmé", str(refus.exception))

    # ------------------------------------------------------------------
    # Les deux sens de la traçabilité
    # ------------------------------------------------------------------
    def _seance_qui_consomme(self, cycle, quantite=1.0):
        """Une séance close qui a consommé un set de la charge."""
        patient = self.env['megga.dental.patient'].create(
            {'name': "Patiente Stérile"})
        position = self.env['megga.dental.position'].create({
            'code': "9.9%s" % len(cycle.lot_ids), 'name': "Examen",
            'points': 10.0,
            'supply_ids': [(0, 0, {
                'product_id': self.set_examen.id,
                'quantity': quantite})],
        })
        seance = self.env['megga.dental.treatment'].create({
            'patient_id': patient.id,
            'line_ids': [(0, 0, {
                'position_id': position.id, 'quantity': 1.0})],
        })
        seance.action_confirm()
        seance.action_done()
        return seance

    def test_le_rappel_nomme_les_seances_servies(self):
        """La question à laquelle le cabinet doit répondre en une
        minute : l'indicateur revient non conforme — qui a été soigné
        avec cette charge ?"""
        temoin = self._cycle(lignes=[(self.set_chirurgie, 2.0)])
        temoin.action_validate()
        cycle = self._cycle(indicator='pending')
        cycle.action_validate()
        seance = self._seance_qui_consomme(cycle)

        cycle.action_fail()

        servies = cycle._megga_served_treatments()
        self.assertEqual(servies, seance,
                         "Exactement la séance servie — une méthode qui "
                         "renverrait tout passerait le test sinon.")
        self.assertFalse(temoin._megga_served_treatments())
        action = cycle.action_megga_served_treatments()
        self.assertIn(
            seance,
            self.env['megga.dental.treatment'].search(action['domain']))

    def test_le_rappel_d_une_charge_jamais_servie_ne_nomme_personne(self):
        """Le cas le plus fréquent, et le plus rassurant."""
        cycle = self._cycle()
        cycle.action_validate()

        cycle.action_fail()

        self.assertFalse(cycle._megga_served_treatments())

    def test_la_seance_porte_les_cycles_qui_l_ont_servie(self):
        """La preuve, dans l'autre sens : « avec quoi m'a-t-on
        soigné ? »."""
        temoin = self._cycle(lignes=[(self.set_chirurgie, 2.0)])
        temoin.action_validate()
        cycle = self._cycle()
        cycle.action_validate()

        seance = self._seance_qui_consomme(cycle)

        self.assertEqual(seance.sterilisation_cycle_ids, cycle,
                         "Le cycle qui l'a servie, et lui seul : la "
                         "charge témoin existe et n'y figure pas.")

    def test_une_seance_sans_consommation_ne_porte_aucun_cycle(self):
        """Le compute ne doit pas inventer de preuve."""
        patient = self.env['megga.dental.patient'].create(
            {'name': "Patient Sans Kit"})
        seance = self.env['megga.dental.treatment'].create(
            {'patient_id': patient.id})

        self.assertFalse(seance.sterilisation_cycle_ids)

    def test_le_fefo_sort_le_set_dont_la_sterilite_expire_en_premier(self):
        """La raison d'être de la stratégie posée sur la catégorie : le
        sachet dont la stérilité expire en premier part en premier,
        sinon il périme au fond du tiroir pendant qu'on ouvre celui du
        dessus, et une charge entière part au rebut.

        Les deux charges se distinguent par leur DATE, pas par une
        retouche de la date du lot : `removal_date` — ce sur quoi le
        FEFO trie vraiment — ne suit un changement de péremption que
        par le delta avec `_origin`, lequel vaut zéro sur un
        enregistrement déjà sauvé. Le module, lui, pose la date à la
        CRÉATION du lot, où le cœur la calcule bien.

        La charge validée EN PREMIER est la plus récente : FIFO et FEFO
        ne disent donc pas la même chose, et le test ne peut plus
        passer par hasard."""
        recente = self._cycle()
        recente.action_validate()
        vieille = self._cycle(
            date_start=fields.Datetime.now() - timedelta(days=100))
        vieille.action_validate()

        self.assertGreater(recente.lot_ids.removal_date,
                           vieille.lot_ids.removal_date,
                           "La charge la plus vieille expire en premier.")

        picking = self.env['stock.picking'].create({
            'picking_type_id': self.entrepot.out_type_id.id,
            'location_id': self.entrepot.lot_stock_id.id,
            'location_dest_id': self.soins.id,
            'move_ids': [(0, 0, {
                'product_id': self.set_examen.id,
                'product_uom_qty': 2.0,
                'product_uom': self.set_examen.uom_id.id,
                'location_id': self.entrepot.lot_stock_id.id,
                'location_dest_id': self.soins.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()

        self.assertEqual(picking.move_ids.move_line_ids.lot_id,
                         vieille.lot_ids,
                         "Le sachet dont la stérilité expire en premier "
                         "part en premier — et non le premier entré.")

    # ------------------------------------------------------------------
    # nLPD, droits et câblage
    # ------------------------------------------------------------------
    def test_l_entree_en_stock_ne_nomme_personne(self):
        """Le magasin ne raconte pas les soins : le transfert porte le
        numéro de cycle, jamais un patient."""
        cycle = self._cycle()
        cycle.action_validate()

        self.assertEqual(cycle.picking_id.origin, cycle.name)
        self.assertFalse(cycle.picking_id.partner_id)

    def _responsable(self, cle="steri_resp"):
        """Le responsable technique : celui qui tient le registre."""
        return self.env['res.users'].create({
            'name': "Resp. technique", 'login': cle,
            'email': "%s@exemple.ch" % cle,
            'group_ids': [
                (4, self.env.ref(
                    'megga_dental.group_dental_reception').id),
                (4, self.env.ref(
                    'maintenance.group_equipment_manager').id)],
        })

    def test_le_responsable_tient_le_registre_sans_droit_stock(self):
        """L'entrée en rayon est un effet SYSTÈME du flux.

        Celui qui décharge l'autoclave n'a aucun droit sur le magasin —
        il ne peut pas créer un lot à la main — et la validation en crée
        pour lui sans lui en donner le droit."""
        responsable = self._responsable()
        cycle = self._cycle().with_user(responsable)

        cycle.action_validate()

        self.assertEqual(cycle.state, 'done')
        self.assertTrue(cycle.sudo().lot_ids)
        # Sa fiche s'ouvre : la date de stérilité vit sur la LIGNE de
        # charge, pas seulement sur le lot — sans quoi l'écran de celui
        # qui vient de valider la charge lui serait refusé.
        cycle.read(['name', 'state', 'line_ids'])
        self.assertEqual(cycle.line_ids.sterility_deadline,
                         cycle.sudo().lot_ids.expiration_date)
        with self.assertRaises(AccessError):
            self.env['stock.lot'].with_user(responsable).create({
                'name': "A LA MAIN",
                'product_id': self.set_examen.id,
            })

    def test_le_responsable_voit_vraiment_son_autoclave(self):
        """LA raison du groupe choisi, et la leçon du chantier 4.

        Le cycle exige un autoclave. Le cœur ouvre la lecture des
        équipements à tout employé, mais une règle d'enregistrement la
        borne à ceux dont on est SUIVEUR : la réception seule aurait
        cherché son autoclave dans une liste VIDE, sur un champ
        obligatoire. Menu visible, écran inutilisable."""
        responsable = self._responsable("steri_resp_voit")
        praticien = self.env['res.users'].create({
            'name': "Dr Steri", 'login': "steri_praticien",
            'email': "dr.steri@exemple.ch",
            'group_ids': [(4, self.env.ref(
                'megga_dental.group_dental_praticien').id)],
        })

        vus = self.env['maintenance.equipment'].with_user(
            responsable).name_search()
        self.assertIn(self.autoclave.id, [ident for ident, _nom in vus])

        rien = self.env['maintenance.equipment'].with_user(
            praticien).name_search()
        self.assertNotIn(
            self.autoclave.id, [ident for ident, _nom in rien],
            "C'est la règle du cœur, et c'est pourquoi le menu est "
            "gardé par le gestionnaire d'équipements.")

    def test_la_reception_lit_le_registre_mais_ne_le_tient_pas(self):
        """Elle doit lire les cycles — la preuve d'une séance en dépend —
        sans pouvoir enregistrer une charge."""
        assistante = self.env['res.users'].create({
            'name': "Assistante", 'login': "steri_assistante",
            'email': "assistante@exemple.ch",
            'group_ids': [(4, self.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        cycle = self._cycle()
        cycle.action_validate()

        cycle.with_user(assistante).read(['name', 'state'])

        with self.assertRaises(AccessError):
            self.env['megga.dental.sterilisation.cycle'].with_user(
                assistante).create({
                    'equipment_id': self.autoclave.id,
                    'helix_ok': True,
                })

    def test_le_portail_ne_voit_pas_le_registre(self):
        """Un patient connecté n'a rien à faire dans la salle de
        stérilisation."""
        portail = self.env['res.users'].create({
            'name': "Patient Portail", 'login': "steri_portail",
            'email': "portail.steri@exemple.ch",
            'group_ids': [(4, self.env.ref('base.group_portal').id)],
        })
        with self.assertRaises(AccessError):
            self.env['megga.dental.sterilisation.cycle'].with_user(
                portail).search_count([])

    def test_le_menu_ouvre_bien_l_ecran_du_cabinet(self):
        """Le câblage entier : menu → action → vue. Leçon du chantier 4,
        où trois tests touchaient chacun un bout sans jamais se
        rejoindre."""
        menu = self.env.ref(
            'megga_dental_sterilisation.menu_dental_sterilisation_cycles')
        action = self.env.ref(
            'megga_dental_sterilisation.action_dental_sterilisation_cycle')

        self.assertEqual(menu.action, action)
        self.assertEqual(action.res_model,
                         'megga.dental.sterilisation.cycle')
        self.assertEqual(action.view_id, self.env.ref(
            'megga_dental_sterilisation.'
            'view_dental_sterilisation_cycle_list'))
        self.assertEqual(action.search_view_id, self.env.ref(
            'megga_dental_sterilisation.'
            'view_dental_sterilisation_cycle_search'))
        self.assertEqual(
            menu.parent_id,
            self.env.ref('megga_dental_sterilisation.'
                         'menu_dental_sterilisation_root'))
        self.assertEqual(
            menu.parent_id.parent_id,
            self.env.ref('megga_dental.menu_dental_intendance'))
        self.assertEqual(
            menu.parent_id.parent_id.parent_id,
            self.env.ref('megga_dental.menu_dental_root'))
        # Le modèle est celui du cabinet : pas de domaine à poser, tout
        # cycle de stérilisation EST du cabinet.
        self.assertFalse(safe_eval(action.domain or '[]'))

    # ------------------------------------------------------------------
    # « Intendance » : le conteneur des trois familles
    #
    # Ce module est le seul où les trois sont installés à la fois — le
    # seul endroit, donc, où l'on peut tester le regroupement.
    # ------------------------------------------------------------------
    def test_les_trois_familles_vivent_sous_intendance_dans_l_ordre(self):
        """Le magasin compte, la stérilisation prouve, le registre
        entretient : c'est la formule du produit, et c'est l'ordre du
        menu."""
        intendance = self.env.ref('megga_dental.menu_dental_intendance')
        magasin = self.env.ref('megga_dental_stock.menu_dental_stock_root')
        registre = self.env.ref(
            'megga_dental_materiel.menu_dental_materiel_root')
        sterilisation = self.env.ref(
            'megga_dental_sterilisation.menu_dental_sterilisation_root')

        self.assertEqual(
            intendance.parent_id, self.env.ref('megga_dental.menu_dental_root'))
        # Nom et séquence sont verrouillés ici parce que le conteneur
        # est RE-DÉCLARÉ dans les trois modules (pour que chacun soit
        # installable seul sur une base en service) : sans ce témoin,
        # une copie pourrait le renommer ou le déplacer en silence, et
        # la dernière chargée gagnerait.
        self.assertEqual(intendance.name, "Intendance")
        self.assertEqual(
            intendance.sequence, 40,
            "« Intendance » reprend la place du magasin : entre "
            "« Constats » (30) et « Configuration » (90).")
        self.assertLess(
            self.env.ref('megga_dental.menu_dental_tooth_records').sequence,
            intendance.sequence)
        self.assertLess(
            intendance.sequence,
            self.env.ref('megga_dental.menu_dental_config').sequence)
        for racine in (magasin, sterilisation, registre):
            self.assertEqual(racine.parent_id, intendance)
        self.assertEqual(
            [magasin.sequence, sterilisation.sequence, registre.sequence],
            [10, 20, 30],
            "L'ordre porte la formule : compter, prouver, entretenir.")

    def test_intendance_ne_porte_aucun_groupe(self):
        """Le conteneur ne garde rien, et c'est ce qui le rend sûr.

        `_visible_menu_ids` remonte l'ascendance depuis les menus
        porteurs d'une action accessible et s'arrête dès qu'un ancêtre
        a été écarté par ses propres groupes — mais c'est `load_menus`
        qui achève le travail : un sous-arbre dont l'ancêtre a disparu
        n'a plus d'app_id et sort de la barre. Un groupe posé ici
        décapiterait les deux autres familles."""
        intendance = self.env.ref('megga_dental.menu_dental_intendance')
        self.assertFalse(
            intendance.group_ids,
            "Poser un groupe sur « Intendance » masquerait les familles "
            "qui ne le portent pas, quels que soient leurs propres "
            "droits.")
        self.assertFalse(
            intendance.action,
            "« Intendance » est un conteneur : sans action et sans "
            "enfant visible, le cœur ne l'affiche pas du tout.")

    def test_intendance_ne_decapite_aucune_famille(self):
        """LE témoin du regroupement : chaque rôle voit sa famille, et
        voit « Intendance » avec elle.

        Ce qui ferme la stérilisation au magasinier, ce n'est PAS
        l'ACL — elle lui en donne la lecture par `stock.group_stock_user`
        (security/ir.model.access.csv) — c'est le `groups=` posé sur
        « Cycles d'autoclave », le menu racine de la stérilisation
        portant lui-même `base.group_user`. Le responsable technique,
        lui, n'a aucun groupe stock. Si le conteneur portait le groupe
        de l'un, l'autre perdrait tout son sous-arbre sans qu'un seul
        droit n'ait changé."""
        Menu = self.env['ir.ui.menu']
        intendance = self.env.ref('megga_dental.menu_dental_intendance')
        magasin = self.env.ref('megga_dental_stock.menu_dental_stock_root')
        sterilisation = self.env.ref(
            'megga_dental_sterilisation.menu_dental_sterilisation_root')

        magasinier = self.env['res.users'].create({
            'name': "Magasinier intendance",
            'login': "intendance_magasinier",
            'email': "magasinier.intendance@exemple.ch",
            'group_ids': [
                (4, self.env.ref('megga_dental.group_dental_reception').id),
                (4, self.env.ref('stock.group_stock_user').id),
            ],
        })
        technicien = self.env['res.users'].create({
            'name': "Responsable technique intendance",
            'login': "intendance_technicien",
            'email': "technicien.intendance@exemple.ch",
            'group_ids': [
                (4, self.env.ref('megga_dental.group_dental_reception').id),
                (4, self.env.ref(
                    'maintenance.group_equipment_manager').id),
            ],
        })

        # `load_menus`, PAS `_visible_menu_ids` : c'est ce que le
        # client web appelle, et c'est la seule couche qui coupe
        # vraiment. `_visible_menu_ids` marque le descendant AVANT de
        # remonter — un groupe posé sur « Intendance » y laisserait
        # donc « Stérilisation » présent, et le témoin serait vert sous
        # la mutation qu'il prétend attraper.
        vus_magasinier = Menu.with_user(magasinier).load_menus(False)
        vus_technicien = Menu.with_user(technicien).load_menus(False)

        # La CHAÎNE entière, pas la seule présence du conteneur :
        # « Intendance » est de toute façon ouvert à tout employé par
        # « Entretiens », donc l'y trouver seul ne prouverait rien.
        racine = self.env.ref('megga_dental.menu_dental_root')
        self.assertLessEqual(
            {magasin.id, intendance.id, racine.id}, set(vus_magasinier),
            "Le magasin, son conteneur et l'app : la chaîne entière.")
        self.assertLessEqual(
            {sterilisation.id, intendance.id, racine.id},
            set(vus_technicien),
            "Un groupe stock posé sur « Intendance » aurait coupé la "
            "stérilisation au responsable technique.")
        # Et chacun voit LA SIENNE, pas celle de l'autre.
        self.assertNotIn(sterilisation.id, vus_magasinier)
        self.assertNotIn(magasin.id, vus_technicien)

    def test_la_seance_se_clot_meme_avec_un_set_non_conforme(self):
        """LA règle cardinale du dépôt : le stock ne bloque jamais la
        clinique.

        Une garde qui refuse une sortie depuis `_action_done` tire sur
        le SOIN si rien ne retire la ligne fautive avant. Le chantier 2
        avait écrit cette ceinture pour le périmé ; la garde de
        stérilisation avait été livrée sans la sienne — la séance ne se
        clôturait plus."""
        cycle = self._cycle(indicator='pending')
        cycle.action_validate()
        cycle.indicator = 'fail'
        self.assertEqual(cycle.state, 'failed')

        seance = self._seance_qui_consomme(cycle)

        self.assertEqual(seance.state, 'done',
                         "Le soin est fait : la séance se clôt.")
        self.assertTrue(seance.supply_picking_id)
        # Le set non conforme n'est PAS parti : la ligne est sortie
        # sans lot, et le magasin a été prévenu.
        lignes = seance.supply_picking_id.sudo().move_ids.move_line_ids
        self.assertFalse(lignes.lot_id & cycle.sudo().lot_ids)
        self.assertTrue(seance.supply_picking_id.sudo().activity_ids)

    def test_l_indicateur_non_conforme_bloque_a_lui_seul(self):
        """Le geste réel du lendemain, c'est de changer l'indicateur —
        pas de cliquer un bouton. La garde ne lisait que l'état : une
        charge déclarée non conforme continuait de servir."""
        cycle = self._cycle(indicator='pending')
        cycle.action_validate()

        cycle.indicator = 'fail'

        self.assertEqual(cycle.state, 'failed')
        with self.assertRaises(UserError):
            self._consomme(cycle.lot_ids)

    def test_deux_lignes_du_meme_set_font_deux_lots(self):
        """Le cœur FUSIONNE les mouvements confirmés qui partagent
        produit et emplacements. L'appariement par position perdait
        alors une ligne : des sachets n'entraient jamais en rayon, en
        silence."""
        cycle = self._cycle(lignes=[(self.set_examen, 4.0),
                                    (self.set_examen, 6.0)])

        cycle.action_validate()

        self.assertEqual(len(cycle.lot_ids), 2)
        self.assertEqual(
            self.env['stock.quant']._get_available_quantity(
                self.set_examen, self.entrepot.lot_stock_id), 10.0,
            "Les dix sachets sont en rayon, pas quatre.")

    def test_l_etat_ne_se_force_pas_par_un_write(self):
        """Le gel serait décoratif si un write le levait."""
        cycle = self._cycle()
        cycle.action_validate()

        with self.assertRaises(UserError):
            cycle.write({'state': 'draft'})

    def test_la_charge_d_un_cycle_clos_ne_se_retouche_pas(self):
        """Le gel du cycle ne suffisait pas : ses LIGNES restaient
        modifiables et supprimables — le registre pouvait dire autre
        chose que ce qui est sorti de l'autoclave."""
        cycle = self._cycle()
        cycle.action_validate()

        with self.assertRaises(UserError):
            cycle.line_ids.quantity = 99.0
        with self.assertRaises(UserError):
            cycle.line_ids.unlink()

    def test_dupliquer_un_cycle_repart_en_brouillon(self):
        """Sans `copy=False`, la copie naissait « Validée » sans le
        moindre set — et un cycle validé ne se corrige ni ne s'efface."""
        cycle = self._cycle()
        cycle.action_validate()

        copie = cycle.copy()

        self.assertEqual(copie.state, 'draft')
        self.assertFalse(copie.picking_id)
        self.assertNotEqual(copie.name, cycle.name)

    def test_les_sets_sont_des_consommables_du_cabinet(self):
        """La catégorie sœur les rendait invisibles PARTOUT : dans les
        écrans du magasin, et surtout dans le sélecteur de kit — un set
        ne pouvait donc pas être rattaché à un acte, alors que « clore
        une séance décompte les sets » est la promesse du module."""
        cycle = self._cycle()
        cycle.action_validate()
        consommables = self.env.ref(
            'megga_dental_stock.product_category_dental_supplies')

        self.assertEqual(self.categorie.parent_id, consommables)
        self.assertEqual(
            self.categorie.removal_strategy_id,
            self.env.ref('product_expiry.removal_fefo'),
            "Le cœur ne remonte pas la chaîne des parents pour la "
            "stratégie : elle reste posée explicitement.")

        lots = self.env.ref('megga_dental_stock.action_dental_stock_lot')
        self.assertIn(cycle.lot_ids,
                      self.env['stock.lot'].search(safe_eval(lots.domain)))

        # Et le sélecteur de kit du chantier 2 les propose.
        vue = self.env.ref('megga_dental_stock.view_dental_position_form')
        self.assertIn('child_of', vue.arch)
        proposables = self.env['product.product'].search(
            [('categ_id', 'child_of', consommables.id)])
        self.assertIn(self.set_examen, proposables)

    def test_le_menu_suit_les_droits_reels(self):
        """La leçon du chantier 4, rouverte par celui-ci et refermée :
        le menu porte le groupe qui peut vraiment s'en servir."""
        menu = self.env.ref(
            'megga_dental_sterilisation.menu_dental_sterilisation_cycles')

        self.assertEqual(
            menu.group_ids,
            self.env.ref('maintenance.group_equipment_manager'))
        self.assertEqual(
            menu.group_ids,
            self.env.ref(
                'megga_dental_materiel.menu_dental_materiel_equipment'
            ).group_ids,
            "Le même groupe que le registre du matériel : les deux "
            "écrans exigent de voir les équipements du cabinet.")

    def test_le_registre_d_un_cabinet_ne_se_lit_pas_depuis_l_autre(self):
        """Le cycle porte une société : sans règle multi-sociétés, un
        cabinet verrait — et pourrait marquer non conforme — les
        charges de l'autre."""
        autre = self.env['res.company'].create({'name': "Cabinet B"})
        cycle = self._cycle()
        responsable = self._responsable("steri_multi")
        responsable.write({
            'company_ids': [(4, autre.id)],
            'company_id': autre.id,
        })

        vus = self.env['megga.dental.sterilisation.cycle'].with_user(
            responsable).with_context(
                allowed_company_ids=[autre.id]).search([])

        self.assertNotIn(cycle, vus)

    def test_une_charge_deja_perimee_a_l_entree_se_valide_quand_meme(self):
        """Un set qui SORT de l'autoclave n'est pas périmé.

        Le cœur interpose un assistant dès qu'une ligne porte un lot
        dont la date de RETRAIT est atteinte — pas seulement la
        péremption. Sans `skip_expired`, l'assistant remplaçait la
        validation, le contrôle de l'entrée voyait un transfert non
        validé, et la charge devenait DÉFINITIVEMENT impossible à
        valider. La garde qui compte est celle de la sortie vers les
        soins, et elle reste entière."""
        self.set_examen.product_tmpl_id.removal_time = 200

        cycle = self._cycle()
        cycle.action_validate()

        self.assertEqual(cycle.state, 'done')
        self.assertEqual(cycle.picking_id.state, 'done')
        self.assertEqual(
            self.env['stock.quant']._get_available_quantity(
                self.set_examen, self.entrepot.lot_stock_id,
                lot_id=cycle.lot_ids, strict=True), 4.0)

    def test_une_ligne_ne_s_ajoute_pas_a_une_charge_close(self):
        """Le gel ne voyait que le chemin `line_ids` : une ligne créée
        en direct passait, et le registre annonçait des sachets qui ne
        sont jamais entrés en rayon."""
        cycle = self._cycle()
        cycle.action_validate()

        with self.assertRaises(UserError):
            self.env['megga.dental.sterilisation.line'].create({
                'cycle_id': cycle.id,
                'product_id': self.set_chirurgie.id,
                'quantity': 5.0,
            })

    def test_le_rappel_marche_sans_droit_dentaire(self):
        """Le registre est tenu par le gestionnaire d'équipements, qui
        n'a aucun droit sur le dentaire. Chercher les séances avec SES
        droits faisait échouer le rappel — le geste central du module —
        pour la persona même à qui le menu est donné."""
        technique = self.env['res.users'].create({
            'name': "Technicien externe", 'login': "steri_technique",
            'email': "technique@exemple.ch",
            'group_ids': [(4, self.env.ref(
                'maintenance.group_equipment_manager').id)],
        })
        cycle = self._cycle(indicator='pending')
        cycle.action_validate()
        seance = self._seance_qui_consomme(cycle)

        # Il ne lit pas les séances — et il doit pourtant pouvoir
        # marquer la charge non conforme et savoir qu'elle a servi.
        with self.assertRaises(AccessError):
            self.env['megga.dental.treatment'].with_user(
                technique).search_count([])

        cycle.with_user(technique).action_fail()

        self.assertEqual(cycle.state, 'failed')
        self.assertIn(seance.name, cycle.message_ids[0].body)

    def test_dupliquer_ne_recopie_aucun_releve(self):
        """Un indicateur recopié ferait état d'un contrôle que la
        nouvelle charge n'a jamais subi — et un « non conforme » hérité
        condamnerait la copie à ne jamais pouvoir être validée ni
        supprimée."""
        cycle = self._cycle(indicator='pending', helix_ok=True,
                            temperature=121.0)
        cycle.action_validate()
        cycle.indicator = 'fail'

        copie = cycle.copy()

        self.assertEqual(copie.state, 'draft')
        self.assertEqual(copie.indicator, 'none')
        self.assertFalse(copie.helix_ok)
        self.assertEqual(copie.temperature, 134.0)
        self.assertEqual(len(copie.line_ids), 1,
                         "La composition, elle, se rejoue.")

    def test_la_date_de_sterilite_suit_le_lot_et_non_son_nom(self):
        """Le lot se retrouve par son LIEN. Déduire le lot de son nom
        cessait de correspondre dès qu'une charge changeait de
        composition, et l'écran retombait en silence sur un recalcul —
        deux dates divergentes, ce que le code dit éviter."""
        cycle = self._cycle(lignes=[(self.set_examen, 4.0),
                                    (self.set_chirurgie, 2.0)])
        cycle.action_validate()

        for ligne in cycle.line_ids:
            self.assertEqual(ligne.lot_ids.sterilisation_line_id, ligne)
            self.assertEqual(ligne.sterility_deadline,
                             ligne.lot_ids.expiration_date)

        # Le délai du produit change APRÈS coup : le lot fait foi.
        self.set_examen.product_tmpl_id.expiration_time = 3
        examen = cycle.line_ids.filtered(
            lambda l: l.product_id == self.set_examen)
        self.assertEqual(examen.sterility_deadline,
                         examen.lot_ids.expiration_date)

    def test_les_boutons_suivent_les_droits(self):
        """Trois boutons visibles qui lèvent une AccessError au clic :
        la fiche est atteignable depuis la séance et depuis le lot."""
        arch = self.env['megga.dental.sterilisation.cycle'].with_user(
            self._responsable("steri_boutons")).get_view(
                view_type='form')['arch']
        self.assertIn('action_validate', arch)

        assistante = self.env['res.users'].create({
            'name': "Assistante boutons", 'login': "steri_boutons_lect",
            'email': "boutons@exemple.ch",
            'group_ids': [(4, self.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        arch_lecture = self.env[
            'megga.dental.sterilisation.cycle'].with_user(
                assistante).get_view(view_type='form')['arch']
        self.assertNotIn('action_validate', arch_lecture)
        self.assertNotIn('action_fail', arch_lecture)

    def test_la_composition_d_un_cabinet_ne_se_lit_pas_depuis_l_autre(self):
        """L'en-tête était cachée par sa règle, son contenu non — et
        une ligne de charge dit quels sets et combien de sachets."""
        autre = self.env['res.company'].create({'name': "Cabinet C"})
        cycle = self._cycle()
        responsable = self._responsable("steri_multi_ligne")
        responsable.write({
            'company_ids': [(4, autre.id)],
            'company_id': autre.id,
        })

        vues = self.env['megga.dental.sterilisation.line'].with_user(
            responsable).with_context(
                allowed_company_ids=[autre.id]).search([])

        self.assertFalse(vues & cycle.line_ids)

    def test_l_etat_force_dit_le_bon_geste(self):
        """Sur une charge close, le message du gel sortait le premier
        et conseillait le mauvais geste."""
        cycle = self._cycle()
        cycle.action_validate()

        with self.assertRaises(UserError) as refus:
            cycle.write({'state': 'draft'})

        self.assertIn("boutons", str(refus.exception))

    def test_un_set_perime_et_non_conforme_n_est_compte_qu_une_fois(self):
        """Deux motifs sur le même sachet : l'activité du magasin ne
        doit pas l'annoncer écarté deux fois, ni pour le mauvais
        motif."""
        cycle = self._cycle()
        cycle.action_validate()
        cycle.lot_ids.sudo().expiration_date = (
            fields.Datetime.now() - timedelta(days=1))
        cycle.action_fail()

        seance = self._seance_qui_consomme(cycle)

        self.assertEqual(seance.state, 'done')
        activites = seance.supply_picking_id.sudo().activity_ids
        self.assertEqual(len(activites), 1)
        self.assertEqual(activites.note.count(cycle.lot_ids.name), 1,
                         "Le sachet est nommé une fois, pour le motif "
                         "qui l'a réellement emporté.")

    def test_aucun_cron_maison(self):
        """Rien ne tourne tout seul ici : un cycle se saisit, un
        indicateur se relève. Inventer un cron ferait croire à une
        surveillance qui n'existe pas."""
        maison = self.env['ir.model.data'].search([
            ('module', '=', 'megga_dental_sterilisation'),
            ('model', '=', 'ir.cron'),
        ])

        self.assertFalse(maison)

    def test_une_ligne_de_charge_sans_sachet_est_refusee(self):
        """Une ligne à zéro produirait un mouvement à quantité nulle,
        que le cœur refuse de valider."""
        with self.assertRaises(ValidationError):
            self._cycle(lignes=[(self.set_examen, 0.0)])

    def test_un_set_non_trace_est_refuse(self):
        """Sans lot, aucun numéro de cycle ne peut être porté par le
        sachet : la traçabilité n'existerait pas."""
        vrac = self.env['product.product'].create({
            'name': "Sachets en vrac", 'type': 'consu',
            'is_storable': True, 'tracking': 'none',
            'categ_id': self.categorie.id,
        })

        with self.assertRaises(ValidationError):
            self._cycle(lignes=[(vrac, 2.0)])
