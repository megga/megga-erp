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
        cycle = self._cycle(indicator='pending')
        cycle.action_validate()
        seance = self._seance_qui_consomme(cycle)

        cycle.indicator = 'fail'
        cycle.action_fail()

        servies = cycle._megga_served_treatments()
        self.assertIn(seance, servies)
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
        cycle = self._cycle()
        cycle.action_validate()

        seance = self._seance_qui_consomme(cycle)

        self.assertEqual(seance.sterilisation_cycle_ids, cycle)

    def test_une_seance_sans_consommation_ne_porte_aucun_cycle(self):
        """Le compute ne doit pas inventer de preuve."""
        patient = self.env['megga.dental.patient'].create(
            {'name': "Patient Sans Kit"})
        seance = self.env['megga.dental.treatment'].create(
            {'patient_id': patient.id})

        self.assertFalse(seance.sterilisation_cycle_ids)

    def test_le_fefo_sort_le_set_dont_la_sterilite_expire_en_premier(self):
        """La raison d'être de la catégorie dédiée : sans FEFO, le
        sachet du fond périme pendant qu'on ouvre celui du dessus, et
        une charge entière part au rebut."""
        ancien = self._cycle()
        ancien.action_validate()
        ancien.lot_ids.sudo().expiration_date = (
            fields.Datetime.now() + timedelta(days=10))
        recent = self._cycle()
        recent.action_validate()
        recent.lot_ids.sudo().expiration_date = (
            fields.Datetime.now() + timedelta(days=200))

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
                         ancien.lot_ids,
                         "Le sachet dont la stérilité expire en premier "
                         "part en premier.")

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

    def test_la_reception_tient_le_registre_sans_droit_stock(self):
        """Le geste réel : la personne qui décharge l'autoclave est de
        l'équipe du cabinet. L'entrée en rayon est un effet SYSTÈME du
        flux — elle ne lui donne aucun droit sur le magasin."""
        assistante = self.env['res.users'].create({
            'name': "Assistante", 'login': "steri_assistante",
            'email': "assistante@exemple.ch",
            'group_ids': [(4, self.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        cycle = self._cycle().with_user(assistante)

        cycle.action_validate()

        self.assertEqual(cycle.state, 'done')
        self.assertTrue(cycle.sudo().lot_ids)
        # Et sa fiche s'ouvre : la date de stérilité vit sur la LIGNE
        # de charge, pas seulement sur le lot — sans quoi l'écran de
        # celle qui vient de valider la charge lui serait refusé.
        vue = cycle.with_user(assistante)
        vue.read(['name', 'state', 'line_ids'])
        self.assertEqual(vue.line_ids.sterility_deadline,
                         cycle.date_start + timedelta(days=180))
        # Le coeur ouvre la LECTURE des quantites a tout employe
        # (access_stock_quant_all) : ce que la reception ne peut pas,
        # c'est tenir le magasin. Creer un lot lui est refuse — et
        # c'est pourtant ce que la validation vient de faire pour elle.
        with self.assertRaises(AccessError):
            self.env['stock.lot'].with_user(assistante).create({
                'name': "A LA MAIN",
                'product_id': self.set_examen.id,
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
            self.env.ref('megga_dental.menu_dental_root'))
        # Le modèle est celui du cabinet : pas de domaine à poser, tout
        # cycle de stérilisation EST du cabinet.
        self.assertFalse(safe_eval(action.domain or '[]'))

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
