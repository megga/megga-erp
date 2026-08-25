from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase


class TestAutoPortal(TransactionCase):
    """L'étanchéité du portail garage : le client connecté lit SES
    véhicules et SES réparations engagées — jamais celles du voisin,
    jamais un devis en rédaction, et il n'écrit rien nulle part.

    fleet.vehicle est un modèle du cœur, où vit aussi le parc de la
    société : la règle d'enregistrement est la seule séparation, donc
    elle se teste pour de bon."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context,
                                       no_reset_password=True))
        Users = cls.env['res.users']
        portal_group = cls.env.ref('base.group_portal')
        brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': "Peugeot"})
        cls.modele = cls.env['fleet.vehicle.model'].create({
            'name': "308", 'brand_id': brand.id})
        cls.piece = cls.env['product.product'].create({
            'name': "Plaquettes avant", 'type': 'consu',
            'list_price': 260.0})

        def monte(nom, login, plaque):
            partner = cls.env['res.partner'].create({'name': nom})
            user = Users.create({
                'name': nom, 'login': login,
                'email': '%s@exemple.ch' % login,
                'password': 'Portail-123!',
                'partner_id': partner.id,
                'group_ids': [(6, 0, [portal_group.id])],
            })
            vehicle = cls.env['fleet.vehicle'].create({
                'model_id': cls.modele.id,
                'license_plate': plaque,
                'megga_owner_id': partner.id,
            })
            engage = cls.env['megga.auto.workorder'].create({
                'vehicle_id': vehicle.id,
                'partner_id': partner.id,
                'line_ids': [Command.create({
                    'product_id': cls.piece.id,
                    'description': "Freins avant",
                    'price_unit': 260.0})],
            })
            engage.action_confirm()
            devis = cls.env['megga.auto.workorder'].create({
                'vehicle_id': vehicle.id,
                'partner_id': partner.id,
                'line_ids': [Command.create({
                    'product_id': cls.piece.id,
                    'description': "Devis interne, non remis",
                    'price_unit': 999.0})],
            })
            return user, partner, vehicle, engage, devis

        (cls.user, cls.partner, cls.vehicle, cls.engage,
         cls.devis) = monte("Morand Frédéric", "auto_client", "VD 100 001")
        (cls.user_voisin, cls.partner_voisin, cls.vehicle_voisin,
         cls.engage_voisin, _) = monte(
            "Bochud Anne", "auto_voisin", "VD 200 002")
        # Le vehicule de service du garage : personne au portail ne doit
        # le voir (il n'a pas de proprietaire client).
        cls.vehicle_garage = cls.env['fleet.vehicle'].create({
            'model_id': cls.modele.id,
            'license_plate': "VD 999 999",
        })

    def _en_client(self, model):
        return self.env[model].with_user(self.user)

    def test_voit_ses_vehicules(self):
        vehicules = self._en_client('fleet.vehicle').search([])
        self.assertEqual(vehicules, self.vehicle)

    def test_ne_voit_pas_le_vehicule_du_voisin(self):
        with self.assertRaises(AccessError):
            self.vehicle_voisin.with_user(self.user).read(['license_plate'])

    def test_ne_voit_pas_le_vehicule_de_service_du_garage(self):
        """Le parc de la société vit dans le même modèle : sans la
        règle, le client verrait les voitures du garage."""
        with self.assertRaises(AccessError):
            self.vehicle_garage.with_user(self.user).read(['license_plate'])

    def test_compteur_lisible_mais_pas_celui_du_voisin(self):
        """La page affiche le compteur, qui est un calcul sur le journal
        du cœur : il faut le droit de lire ce journal — sans quoi la
        page tombe en 403 — mais relevé par relevé."""
        Releve = self.env['fleet.vehicle.odometer']
        mien = Releve.create({
            'vehicle_id': self.vehicle.id, 'value': 84000.0})
        sien = Releve.create({
            'vehicle_id': self.vehicle_voisin.id, 'value': 12000.0})
        vus = Releve.with_user(self.user).search([])
        self.assertIn(mien, vus)
        self.assertNotIn(sien, vus)
        self.assertAlmostEqual(
            self.vehicle.with_user(self.user).odometer, 84000.0)

    def test_voit_ses_reparations_engagees(self):
        ordres = self._en_client('megga.auto.workorder').search([])
        self.assertEqual(ordres, self.engage)
        self.assertAlmostEqual(ordres.amount_total, 260.0)

    def test_le_devis_en_redaction_ne_sort_pas(self):
        with self.assertRaises(AccessError):
            self.devis.with_user(self.user).read(['name'])

    def test_ne_voit_pas_la_reparation_du_voisin(self):
        with self.assertRaises(AccessError):
            self.engage_voisin.with_user(self.user).read(['name'])

    def test_voit_le_detail_des_travaux(self):
        lignes = self._en_client('megga.auto.workorder.line').search([])
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes.description, "Freins avant")

    def test_les_lignes_du_devis_ne_sortent_pas(self):
        lignes = self._en_client('megga.auto.workorder.line').search([])
        self.assertNotIn("Devis interne, non remis",
                         lignes.mapped('description'))

    def test_lecture_seule(self):
        with self.assertRaises(AccessError):
            self.engage.with_user(self.user).write({'diagnosis': "pirate"})
        with self.assertRaises(AccessError):
            self.vehicle.with_user(self.user).write(
                {'license_plate': "VD 000 000"})
        with self.assertRaises(AccessError):
            self.env['megga.auto.workorder'].with_user(self.user).create({
                'vehicle_id': self.vehicle.id,
                'partner_id': self.partner.id,
            })
        with self.assertRaises(AccessError):
            self.engage.with_user(self.user).unlink()

    def test_le_catalogue_du_garage_reste_ferme(self):
        """Le portail affiche les travaux sans jamais lire
        product.product : ouvrir le catalogue d'un garage pour un
        libellé serait disproportionné."""
        with self.assertRaises(AccessError):
            self.env['product.product'].with_user(self.user).search([])
        lignes = self._en_client('megga.auto.workorder.line').search([])
        self.assertTrue(all(lignes.mapped('description')),
                        "la désignation est posée à la source")

    def test_l_atelier_reste_ferme(self):
        """Ce que le client n'a AUCUNE raison de lire : le référentiel
        des forfaits, qui est la structure de coût du garage."""
        for modele in ('megga.auto.package', 'megga.auto.package.line'):
            with self.assertRaises(AccessError):
                self.env[modele].with_user(self.user).search([])

    def test_l_ordre_termine_reste_visible(self):
        self.engage.action_done()
        ordres = self._en_client('megga.auto.workorder').search([])
        self.assertEqual(ordres, self.engage)

    def test_l_ordre_annule_disparait(self):
        self.engage.action_cancel()
        ordres = self._en_client('megga.auto.workorder').search([])
        self.assertFalse(ordres)

    def test_vehicule_revendu_sort_du_portail(self):
        """Le patron de l'occasion : le véhicule change de propriétaire,
        l'ancien client ne le voit plus."""
        self.vehicle.megga_owner_id = self.partner_voisin
        self.assertFalse(self._en_client('fleet.vehicle').search([]))
        self.assertEqual(
            self.env['fleet.vehicle'].with_user(self.user_voisin).search(
                [('id', '=', self.vehicle.id)]),
            self.vehicle)
