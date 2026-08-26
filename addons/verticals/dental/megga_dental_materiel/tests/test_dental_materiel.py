from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import Form, TransactionCase
from psycopg2 import IntegrityError
from odoo.tools import mute_logger
from odoo.tools.safe_eval import safe_eval


class TestDentalMateriel(TransactionCase):
    """Le registre du matériel : ce qui se révise, se calibre et se
    prouve, rattaché au fauteuil qu'il sert. Le comportement est celui
    du cœur `maintenance` — on teste la COUTURE : le lien au fauteuil,
    le refus de supprimer un fauteuil équipé, le compteur de la fiche,
    et l'entretien périodique qui engendre le suivant."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Chair = cls.env['megga.dental.chair']
        cls.fauteuil_1 = Chair.create({'name': "Fauteuil 1", 'sequence': 10})
        cls.fauteuil_2 = Chair.create({'name': "Fauteuil 2", 'sequence': 20})
        cls.equipe = cls.env.ref(
            'megga_dental_materiel.maintenance_team_dental')
        cls.categorie_sterilisation = cls.env.ref(
            'megga_dental_materiel.equipment_category_sterilisation')

    def _gestionnaire(self, cle):
        """Le responsable technique : le seul à qui le cœur montre le
        registre entier."""
        return self.env['res.users'].create({
            'name': "Resp. %s" % cle, 'login': "materiel_%s" % cle,
            'email': "%s@exemple.ch" % cle,
            'group_ids': [
                (4, self.env.ref(
                    'megga_dental.group_dental_praticien').id),
                (4, self.env.ref(
                    'maintenance.group_equipment_manager').id)],
        })

    def _appareil(self, nom, fauteuil=None, categorie=None):
        return self.env['maintenance.equipment'].create({
            'name': nom,
            'chair_id': fauteuil.id if fauteuil else False,
            'category_id': (categorie or self.categorie_sterilisation).id,
            'maintenance_team_id': self.equipe.id,
        })

    # ------------------------------------------------------------------
    # Le lien au fauteuil
    # ------------------------------------------------------------------
    def test_appareil_rattache_a_son_fauteuil(self):
        """La question du cabinet : qu'y a-t-il autour du fauteuil 2 ?"""
        scialytique = self._appareil("Scialytique", self.fauteuil_2)
        aspiration = self._appareil("Aspiration chirurgicale",
                                    self.fauteuil_2)
        self._appareil("Autoclave B", self.fauteuil_1)

        self.assertEqual(self.fauteuil_2.equipment_ids,
                         scialytique | aspiration)
        self.assertEqual(self.fauteuil_2.equipment_count, 2)
        self.assertEqual(self.fauteuil_1.equipment_count, 1)

    def test_appareil_sans_fauteuil(self):
        """Le compresseur de la cave ne sert aucun fauteuil en
        particulier : le lien est facultatif, et ces appareils-là sont
        justement ceux dont la panne arrête tout le cabinet."""
        compresseur = self._appareil("Compresseur du local technique")

        self.assertFalse(compresseur.chair_id)
        self.assertEqual(self.fauteuil_1.equipment_count, 0)

    def test_compteur_suit_le_deplacement(self):
        """Un appareil qu'on déplace d'un fauteuil à l'autre : les deux
        compteurs suivent.

        Sans vider le cache à la main : c'est la DÉPENDANCE du compute
        qu'on tient ici. Un `invalidate_recordset()` ferait passer ce
        test même si `@api.depends` disparaissait — il ne prouverait
        alors plus rien."""
        camera = self._appareil("Caméra intra-orale", self.fauteuil_1)
        self.assertEqual(self.fauteuil_1.equipment_count, 1)
        self.assertEqual(self.fauteuil_2.equipment_count, 0)

        camera.chair_id = self.fauteuil_2

        self.assertEqual(self.fauteuil_1.equipment_count, 0)
        self.assertEqual(self.fauteuil_2.equipment_count, 1)

        camera.unlink()

        self.assertEqual(self.fauteuil_2.equipment_count, 0)

    @mute_logger('odoo.sql_db')
    def test_fauteuil_equipe_ne_se_supprime_pas(self):
        """Doctrine du dépôt : un référentiel porteur ne s'efface pas.

        Supprimer un fauteuil qui porte du matériel effacerait le
        rattachement de l'appareil sans que personne ne le décide."""
        self._appareil("Unit dentaire", self.fauteuil_1)

        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.fauteuil_1.unlink()

    def test_fauteuil_equipe_s_archive(self):
        """La voie de sortie : on archive, le matériel reste rattaché."""
        unit = self._appareil("Unit dentaire", self.fauteuil_1)

        self.fauteuil_1.active = False

        self.assertFalse(self.fauteuil_1.active)
        self.assertEqual(unit.chair_id, self.fauteuil_1)

    def test_fauteuil_sans_materiel_se_supprime(self):
        """La garde ne vise que les fauteuils équipés."""
        vide = self.env['megga.dental.chair'].create({'name': "Salle vide"})

        vide.unlink()

        self.assertFalse(vide.exists())

    def test_action_du_bouton_de_la_fiche(self):
        """Le bouton de la fiche fauteuil ouvre SON matériel.

        Et il l'ouvre sur les vues du CABINET : le bouton d'un écran du
        cabinet qui renverrait sur la liste générique du cœur poserait
        la même question deux fois, avec deux réponses différentes."""
        unit = self._appareil("Unit 1", self.fauteuil_1)
        self._appareil("Unit 2", self.fauteuil_2)
        gestionnaire = self._gestionnaire("bouton_fiche")

        action = self.fauteuil_1.with_user(
            gestionnaire).action_megga_open_equipment()

        vus = self.env['maintenance.equipment'].with_user(
            gestionnaire).search(action['domain'])
        self.assertEqual(vus, unit)
        self.assertEqual(action['context']['default_chair_id'],
                         self.fauteuil_1.id)
        self.assertEqual(
            action['context']['default_maintenance_team_id'],
            self.equipe.id,
            "Un appareil créé depuis ce bouton reste dans le "
            "périmètre du cabinet.")
        self.assertIn(
            (self.env.ref(
                'megga_dental_materiel.view_dental_equipment_list').id,
             'list'),
            action['views'])

    # ------------------------------------------------------------------
    # L'entretien préventif du cœur
    # ------------------------------------------------------------------
    def test_entretien_periodique_engendre_le_suivant(self):
        """« Autoclave : validation trimestrielle. »

        Le mécanisme est celui du cœur : une demande préventive
        récurrente engendre la suivante quand on la clôt — pas de cron
        maison, pas de périodicité maison."""
        autoclave = self._appareil("Autoclave B classe B", self.fauteuil_1)
        debut = fields.Datetime.now()
        demande = self.env['maintenance.request'].create({
            'name': "Validation trimestrielle de l'autoclave",
            'equipment_id': autoclave.id,
            'maintenance_team_id': self.equipe.id,
            'maintenance_type': 'preventive',
            'recurring_maintenance': True,
            'repeat_interval': 3,
            'repeat_unit': 'month',
            'repeat_type': 'forever',
            'schedule_date': debut,
        })
        terminee = self.env['maintenance.stage'].search(
            [('done', '=', True)], limit=1)

        demande.stage_id = terminee

        suivantes = self.env['maintenance.request'].search([
            ('equipment_id', '=', autoclave.id),
            ('id', '!=', demande.id),
        ])
        self.assertEqual(len(suivantes), 1,
                         "Clore la validation du trimestre engendre "
                         "celle du trimestre suivant.")
        attendue = debut + relativedelta(months=3)
        self.assertEqual(suivantes.schedule_date.date(), attendue.date())
        self.assertEqual(suivantes.maintenance_type, 'preventive')
        self.assertTrue(suivantes.recurring_maintenance)

    def test_entretien_correctif_ne_se_reproduit_pas(self):
        """Une panne n'est pas un rendez-vous : la réparer ne programme
        pas la suivante."""
        compresseur = self._appareil("Compresseur")
        demande = self.env['maintenance.request'].create({
            'name': "Compresseur en panne",
            'equipment_id': compresseur.id,
            'maintenance_team_id': self.equipe.id,
            'maintenance_type': 'corrective',
        })
        terminee = self.env['maintenance.stage'].search(
            [('done', '=', True)], limit=1)

        demande.stage_id = terminee

        self.assertEqual(
            self.env['maintenance.request'].search_count(
                [('equipment_id', '=', compresseur.id)]), 1)

    def test_equipe_et_familles_du_cabinet(self):
        """Le décor livré : une équipe partagée et les familles
        d'appareils qu'un cabinet possède toutes.

        `assertTrue(env.ref(...))` ne prouverait que l'existence — on
        tient ici ce qui compte vraiment : ni société, ni responsable
        hérité du cœur."""
        self.assertFalse(self.equipe.company_id,
                         "L'équipe est partagée : un cabinet à deux "
                         "sociétés ne veut pas deux équipes techniques.")
        attendues = {
            'equipment_category_sterilisation': "Stérilisation",
            'equipment_category_imagerie': "Imagerie",
            'equipment_category_fauteuil': "Unit et fauteuil",
            'equipment_category_technique': "Local technique",
        }
        for xmlid, libelle in attendues.items():
            famille = self.env.ref('megga_dental_materiel.%s' % xmlid)
            self.assertEqual(famille.name, libelle)
            self.assertFalse(
                famille.company_id,
                "Les familles suivent l'équipe : partagées.")
            self.assertFalse(
                famille.technician_user_id,
                "Le cœur met par défaut l'utilisateur qui INSTALLE, "
                "soit OdooBot — et il le recopie ensuite sur chaque "
                "appareil de la famille, puis sur ses demandes.")

    def test_le_robot_du_systeme_n_herite_de_rien(self):
        """Le défaut du cœur, pris à la racine.

        `_onchange_category_id` recopie le responsable de la famille sur
        l'appareil, et `_compute_user_id` recopie celui de l'appareil
        sur la demande. Une famille livrée au nom d'OdooBot aurait donc
        nommé le robot du système technicien de tout le cabinet."""
        formulaire = Form(self.env['maintenance.equipment'])
        formulaire.name = "Autoclave neuf"
        formulaire.category_id = self.categorie_sterilisation
        appareil = formulaire.save()

        self.assertFalse(appareil.technician_user_id)

        demande = self.env['maintenance.request'].create({
            'name': "Première validation",
            'equipment_id': appareil.id,
            'maintenance_team_id': self.equipe.id,
        })

        self.assertFalse(demande.user_id)

    # ------------------------------------------------------------------
    # Menus et droits : ceux du cœur, pas un de plus
    # ------------------------------------------------------------------
    def test_menus_suivent_les_droits_reels(self):
        """Le menu ne doit pas s'ouvrir sur un écran vide.

        Le cœur borne la lecture des équipements d'un employé ordinaire
        à ceux dont il est SUIVEUR (`equipment_rule_user`). Le registre
        complet est donc réservé au gestionnaire ; « Entretiens », lui,
        reste ouvert à tout employé, comme dans l'app Maintenance."""
        appareils = self.env.ref(
            'megga_dental_materiel.menu_dental_materiel_equipment')
        entretiens = self.env.ref(
            'megga_dental_materiel.menu_dental_materiel_requests')
        self.assertEqual(
            appareils.group_ids,
            self.env.ref('maintenance.group_equipment_manager'))
        self.assertEqual(
            entretiens.group_ids,
            self.env.ref('maintenance.menu_m_request_form').group_ids)
        racine = self.env.ref(
            'megga_dental_materiel.menu_dental_materiel_root')
        self.assertEqual(appareils.parent_id, racine)
        self.assertEqual(
            entretiens.parent_id, racine,
            "Les deux écrans vivent sous le menu du cabinet : sans "
            "témoin, « Entretiens » pouvait retourner sous l'app "
            "Maintenance sans qu'un test ne morde.")
        self.assertEqual(
            racine.parent_id,
            self.env.ref('megga_dental.menu_dental_root'),
            "C'est le PARENT dentaire qui garde vraiment le "
            "raccourci : les groupes du menu racine se réduisent à "
            "base.group_user.")

    def test_le_praticien_ne_voit_pas_un_registre_vide(self):
        """Le praticien ne voit pas « Appareils » — il y verrait le
        vide, la règle du cœur ne lui montrant que ce qu'il suit — mais
        il voit « Entretiens », où son geste a un sens."""
        praticien = self.env['res.users'].create({
            'name': "Dr Menus", 'login': "materiel_menus",
            'email': "dr.menus@exemple.ch",
            'group_ids': [(4, self.env.ref(
                'megga_dental.group_dental_praticien').id)],
        })
        Menu = self.env['ir.ui.menu']
        visibles = Menu.with_user(praticien)._visible_menu_ids()

        self.assertNotIn(
            self.env.ref(
                'megga_dental_materiel.menu_dental_materiel_equipment').id,
            visibles)
        self.assertIn(
            self.env.ref(
                'megga_dental_materiel.menu_dental_materiel_requests').id,
            visibles)

    def test_le_praticien_signale_une_panne_sans_tenir_le_registre(self):
        """Le geste réel : le praticien constate au fauteuil, il
        signale. Le cœur ouvre la CRÉATION des demandes à tout employé,
        mais borne la lecture des équipements à ceux qu'on suit."""
        praticien = self.env['res.users'].create({
            'name': "Dr Matériel", 'login': "materiel_dentiste",
            'email': "dr.materiel@exemple.ch",
            'group_ids': [(4, self.env.ref(
                'megga_dental.group_dental_praticien').id)],
        })
        autoclave = self._appareil("Autoclave", self.fauteuil_1)

        # Le cœur ne lui montre que ce qu'il SUIT : le registre du
        # cabinet ne lui est pas ouvert, et c'est pourquoi le menu
        # « Appareils » ne lui est pas proposé.
        lus = self.env['maintenance.equipment'].with_user(
            praticien).search([('chair_id', '=', self.fauteuil_1.id)])
        self.assertFalse(lus)

        panne = self.env['maintenance.request'].with_user(praticien).create({
            'name': "Cycle interrompu",
            'equipment_id': autoclave.id,
            'maintenance_team_id': self.equipe.id,
        })
        self.assertTrue(panne, "Signaler une panne reste ouvert à "
                               "tout employé : c'est le geste du "
                               "fauteuil.")

        # …et il ne modifie pas le registre lui-même : c'est le
        # gestionnaire d'équipements qui en répond.
        with self.assertRaises(AccessError):
            autoclave.with_user(praticien).write({'name': "Renommé"})

    def test_portail_ne_voit_pas_le_registre(self):
        """Un patient connecté n'a rien à faire dans le local
        technique."""
        portail = self.env['res.users'].create({
            'name': "Patient Portail Matériel",
            'login': "materiel_portal",
            'email': "portail.materiel@exemple.ch",
            'group_ids': [(4, self.env.ref('base.group_portal').id)],
        })
        with self.assertRaises(AccessError):
            self.env['maintenance.equipment'].with_user(
                portail).search_count([])

    def test_la_fiche_fauteuil_ne_montre_pas_un_compteur_menteur(self):
        """Le compteur et l'écran qu'il ouvre doivent dire la même chose.

        Le compteur se calcule en `sudo` — le NOMBRE d'appareils autour
        d'un fauteuil est de la logistique. Mais la LISTE, elle, passe
        par la règle du cœur, qui ne montre à un employé ordinaire que
        les équipements dont il est suiveur. Sans garde, le praticien
        lirait « 1 appareil » sur un onglet vide : le défaut du menu
        « Appareils », reporté sur la fiche.

        La garde est donc la même : bouton et onglet au gestionnaire
        d'équipements."""
        praticien = self.env['res.users'].create({
            'name': "Dr Fiche", 'login': "materiel_fiche",
            'email': "dr.fiche@exemple.ch",
            'group_ids': [(4, self.env.ref(
                'megga_dental.group_dental_praticien').id)],
        })
        self._appareil("Unit dentaire", self.fauteuil_1)

        # Le compteur et la liste disent LA MÊME CHOSE à chacun : au
        # praticien, rien (la règle du cœur ne lui montre que ce qu'il
        # suit) ; au gestionnaire, l'appareil. C'est le calcul sans
        # `sudo` qui l'assure — et la garde de vue ci-dessous évite de
        # lui afficher un zéro qui ne pourra jamais devenir autre chose.
        fauteuil_vu = self.fauteuil_1.with_user(praticien)
        self.assertEqual(fauteuil_vu.equipment_count, 0)
        self.assertFalse(fauteuil_vu.equipment_ids)

        vu_du_responsable = self.fauteuil_1.with_user(
            self._gestionnaire("fiche_resp"))
        self.assertEqual(vu_du_responsable.equipment_count, 1)
        self.assertEqual(len(vu_du_responsable.equipment_ids), 1)

        arch_praticien = self.env['megga.dental.chair'].with_user(
            praticien).get_view(view_type='form')['arch']
        self.assertNotIn('equipment_count', arch_praticien,
                         "Un compteur qu'on ne peut pas ouvrir n'a rien "
                         "à faire sur la fiche.")
        self.assertNotIn('equipment_ids', arch_praticien)

        gestionnaire = self._gestionnaire("fiche_arch")
        arch_gestionnaire = self.env['megga.dental.chair'].with_user(
            gestionnaire).get_view(view_type='form')['arch']
        self.assertIn('equipment_count', arch_gestionnaire)
        self.assertIn('equipment_ids', arch_gestionnaire)

    def test_le_compteur_ne_franchit_pas_la_societe(self):
        """Le compteur dit ce que l'écran montre, société comprise.

        Le fauteuil n'a pas de société — c'est du mobilier, pas de la
        comptabilité. L'appareil, lui, en a une, et le cœur borne sa
        lecture aux sociétés autorisées
        (`maintenance_equipment_comp_rule`). Un compteur calculé en
        `sudo` aurait annoncé « 2 appareils » sur un onglet qui n'en
        montre qu'un."""
        autre_societe = self.env['res.company'].create({'name': "Cabinet B"})
        gestionnaire = self._gestionnaire("societe")
        self._appareil("Unit de la société A", self.fauteuil_1)
        self.env['maintenance.equipment'].create({
            'name': "Unit de la société B",
            'chair_id': self.fauteuil_1.id,
            'company_id': autre_societe.id,
        })

        vu = self.fauteuil_1.with_user(gestionnaire)
        self.assertEqual(len(vu.equipment_ids), 1,
                         "La liste, elle, respecte la règle du cœur.")
        self.assertEqual(vu.equipment_count, 1,
                         "Et le compteur dit la même chose qu'elle.")

    def test_compteur_sur_un_fauteuil_qui_n_existe_pas_encore(self):
        """Ouvrir « Nouveau » ne doit pas planter : un fauteuil en cours
        de saisie n'a pas d'identifiant, et le compte se fait sur des
        identifiants."""
        neuf = self.env['megga.dental.chair'].new({'name': "Fauteuil 3"})

        self.assertEqual(neuf.equipment_count, 0)

    def test_le_menu_ouvre_bien_les_ecrans_du_cabinet(self):
        """Le câblage lui-même : le menu, l'action, sa vue et son
        périmètre.

        Vérifier les groupes d'un menu d'un côté et le domaine d'une
        action de l'autre laisse le fil du milieu sans témoin : on peut
        repointer le menu sur l'écran complet du cœur sans casser un
        seul test. On ferme donc la boucle menu → action → vue."""
        appareils = self.env.ref(
            'megga_dental_materiel.menu_dental_materiel_equipment')
        entretiens = self.env.ref(
            'megga_dental_materiel.menu_dental_materiel_requests')

        self.assertEqual(appareils.action, self.env.ref(
            'megga_dental_materiel.action_dental_equipment'))
        self.assertEqual(entretiens.action, self.env.ref(
            'megga_dental_materiel.action_dental_maintenance_request'))

        action = appareils.action
        self.assertEqual(action.view_id, self.env.ref(
            'megga_dental_materiel.view_dental_equipment_list'))
        self.assertEqual(action.search_view_id, self.env.ref(
            'megga_dental_materiel.view_dental_equipment_search'))
        # Le regroupement par fauteuil est LA question du cabinet : il
        # doit être posé d'entrée, et le filtre doit exister vraiment.
        contexte = safe_eval(action.context, {'uid': self.env.uid})
        self.assertEqual(contexte['search_default_group_chair'], 1)
        self.assertIn('name="group_chair"',
                      action.search_view_id.arch)

        requetes = entretiens.action
        self.assertEqual(requetes.res_model, 'maintenance.request')
        self.assertEqual(requetes.view_id, self.env.ref(
            'maintenance.hr_equipment_request_view_kanban'))
        # `search_default_active` n'a de sens que si le cœur porte
        # encore un filtre nommé `active` : un contexte sans filtre est
        # un contexte sans effet.
        recherche = self.env.ref(
            'maintenance.hr_equipment_request_view_search')
        self.assertIn('name="active"', recherche.arch)

    def test_les_ecrans_sont_bornes_au_cabinet(self):
        """« Raccourci filtré » n'est pas une figure de style.

        Sans domaine, le menu dentaire ouvrirait la base entière :
        l'imprimante de la réception, la camionnette du garage, le
        matériel d'une autre verticale. Le périmètre annoncé est le
        FAUTEUIL ou l'ÉQUIPE du cabinet — on le tient ici des deux
        côtés, appareils et entretiens."""
        autre_equipe = self.env['maintenance.team'].create(
            {'name': "Bureau"})
        au_fauteuil = self._appareil("Unit dentaire", self.fauteuil_1)
        au_cabinet = self._appareil("Compresseur du local technique")
        ailleurs = self.env['maintenance.equipment'].create({
            'name': "Imprimante de la réception",
            'maintenance_team_id': autre_equipe.id,
        })

        action = self.env.ref(
            'megga_dental_materiel.action_dental_equipment')
        vus = self.env['maintenance.equipment'].search(
            safe_eval(action.domain))

        self.assertIn(au_fauteuil, vus)
        self.assertIn(au_cabinet, vus,
                      "Le local technique n'a pas de fauteuil et reste "
                      "du cabinet : c'est même lui dont la panne "
                      "arrête tout.")
        self.assertNotIn(ailleurs, vus)

        # …et les entretiens suivent le même périmètre.
        def _demande(nom, appareil):
            return self.env['maintenance.request'].create({
                'name': nom, 'equipment_id': appareil.id})

        du_cabinet = _demande("Cycle interrompu", au_fauteuil)
        du_local = _demande("Fuite d'air", au_cabinet)
        du_bureau = _demande("Bourrage papier", ailleurs)

        entretiens = self.env.ref(
            'megga_dental_materiel.action_dental_maintenance_request')
        lues = self.env['maintenance.request'].search(
            safe_eval(entretiens.domain))

        self.assertIn(du_cabinet, lues)
        self.assertIn(du_local, lues)
        self.assertNotIn(du_bureau, lues)

    def test_ce_qui_est_cree_depuis_l_ecran_y_reste(self):
        """Le piège du domaine : saisir un appareil sans fauteuil dans
        l'écran du cabinet, et le voir disparaître à l'enregistrement.

        Le contexte des deux actions pose l'équipe du cabinet par
        défaut : ce qu'on crée là reste là."""
        action = self.env.ref(
            'megga_dental_materiel.action_dental_equipment')
        contexte = safe_eval(action.context, {'uid': self.env.uid})

        self.assertEqual(contexte['default_maintenance_team_id'],
                         self.equipe.id)

        cree = self.env['maintenance.equipment'].with_context(
            **contexte).create({'name': "Adoucisseur d'eau"})

        self.assertFalse(cree.chair_id)
        self.assertIn(cree, self.env['maintenance.equipment'].search(
            safe_eval(action.domain)),
            "Sans ce défaut, l'appareil disparaîtrait sous les yeux "
            "de celui qui vient de le saisir.")

    def test_la_fiche_fauteuil_s_ouvre_depuis_la_liste(self):
        """L'écran phare du chantier doit être atteignable.

        La liste des fauteuils est ÉDITABLE : cliquer une ligne l'édite
        sur place et n'ouvre JAMAIS la fiche. Sans `open_form_view`, le
        formulaire livré par ce module — son onglet « Matériel », son
        compteur — n'existait que pour les tests."""
        liste = self.env.ref('megga_dental.view_dental_chair_list')
        combinee = liste.get_combined_arch()

        self.assertIn('open_form_view', combinee)
        self.assertIn(
            'editable', combinee,
            "Si la liste cessait d'être éditable, cette garde "
            "deviendrait inutile — et ce test devrait tomber pour "
            "qu'on s'en aperçoive.")

    def test_l_appareil_archive_reste_trouvable(self):
        """On va justement chercher dans le registre ce qu'on a
        remplacé. Notre vue de recherche remplace celle du cœur : sans
        son filtre « Archivé », un appareil déclassé devenait
        introuvable depuis l'écran du cabinet."""
        remplace = self._appareil("Vieil autoclave", self.fauteuil_1)
        remplace.active = False

        recherche = self.env.ref(
            'megga_dental_materiel.view_dental_equipment_search')
        self.assertIn('name="inactive"', recherche.arch)

        action = self.env.ref(
            'megga_dental_materiel.action_dental_equipment')
        archives = self.env['maintenance.equipment'].search(
            safe_eval(action.domain) + [('active', '=', False)])
        self.assertIn(remplace, archives)

    def test_la_fiche_fauteuil_remplace_la_liste_seule(self):
        """Le fauteuil n'avait qu'une liste éditable ; montrer son
        matériel demande une fiche, et l'action du cabinet doit
        l'ouvrir."""
        action = self.env.ref('megga_dental.action_dental_chair')

        self.assertEqual(action.view_mode, 'list,form')
        arch = self.env['megga.dental.chair'].get_view(
            view_type='form')['arch']
        self.assertIn('equipment_ids', arch)
