from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase


class TestRestoPortal(TransactionCase):
    """L'étanchéité du portail salle : le client lit LES SIENNES et rien
    d'autre, n'écrit rien par l'ORM, et ne lit pas les notes de service.
    L'annulation en ligne est testée par les routes (test_portal_http),
    parce qu'elle vit dans le contrôleur — c'est là qu'est la garde."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context,
                                       no_reset_password=True))
        Users = cls.env['res.users']
        portal_group = cls.env.ref('base.group_portal')
        cls.demain = fields.Datetime.add(fields.Datetime.now(), days=1)

        def monte(nom, login):
            partner = cls.env['res.partner'].create({'name': nom})
            user = Users.create({
                'name': nom, 'login': login,
                'email': '%s@exemple.ch' % login,
                'password': 'Portail-123!',
                'partner_id': partner.id,
                'group_ids': [(6, 0, [portal_group.id])],
            })
            reservation = cls.env['megga.resto.reservation'].create({
                'guest_name': nom, 'partner_id': partner.id,
                'start': cls.demain, 'party_size': 2,
                'notes': "Remarque de service, pas pour le client",
            })
            reservation.action_confirm()
            return user, partner, reservation

        cls.user, cls.partner, cls.resa = monte(
            "Rochat Famille", "resto_client")
        cls.user_voisin, cls.partner_voisin, cls.resa_voisin = monte(
            "Dupont Jean", "resto_voisin")
        # Une table prise au telephone, sans contact : elle n'appartient
        # a personne au portail.
        cls.resa_anonyme = cls.env['megga.resto.reservation'].create({
            'guest_name': "Client au téléphone",
            'start': cls.demain, 'party_size': 4,
        })

    def _en_client(self):
        return self.env['megga.resto.reservation'].with_user(self.user)

    def test_voit_les_siennes(self):
        self.assertEqual(self._en_client().search([]), self.resa)

    def test_ne_voit_pas_celle_du_voisin(self):
        with self.assertRaises(AccessError):
            self.resa_voisin.with_user(self.user).read(['name'])

    def test_ne_voit_pas_la_reservation_sans_contact(self):
        with self.assertRaises(AccessError):
            self.resa_anonyme.with_user(self.user).read(['name'])

    def test_les_notes_de_service_ne_redescendent_pas(self):
        """L'ORM les refuse au portail — pas seulement le gabarit qui
        ne les affiche pas."""
        with self.assertRaises(AccessError):
            self.resa.with_user(self.user).read(['notes'])
        self.assertNotIn(
            'notes',
            self._en_client().fields_get().keys())

    def test_lecture_seule_par_l_orm(self):
        with self.assertRaises(AccessError):
            self.resa.with_user(self.user).write({'party_size': 99})
        with self.assertRaises(AccessError):
            self.resa.with_user(self.user).unlink()
        with self.assertRaises(AccessError):
            self._en_client().create({
                'guest_name': "Pirate", 'partner_id': self.partner.id,
                'start': self.demain, 'party_size': 2})

    def test_la_salle_reste_fermee(self):
        """Le plan de salle et les fiches techniques n'ont rien à faire
        chez le client."""
        for modele in ('restaurant.table', 'megga.resto.recipe',
                       'megga.resto.production'):
            with self.assertRaises(AccessError):
                self.env[modele].with_user(self.user).search([])

    def test_l_annulation_reste_visible(self):
        """Une réservation annulée ne disparaît pas du portail : le
        client doit voir ce qu'il a annulé."""
        self.resa.action_cancel()
        self.assertEqual(self._en_client().search([]), self.resa)
        self.assertEqual(self.resa.with_user(self.user).state, 'cancelled')
