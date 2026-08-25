import re

from odoo import fields
from odoo.tests import HttpCase, tagged

JETON = re.compile(r'name="csrf_token"\s+value="([^"]+)"')


@tagged('post_install', '-at_install')
class TestRestoPortalHttp(HttpCase):
    """Les routes, en vrai — et surtout l'annulation en ligne : la
    sienne, à venir, encore annulable. Tout le reste est refusé, et
    aucune de ces gardes ne dépend du bouton affiché."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context,
                                       no_reset_password=True))
        Users = cls.env['res.users']
        portal_group = cls.env.ref('base.group_portal')
        cls.demain = fields.Datetime.add(fields.Datetime.now(), days=1)
        cls.hier = fields.Datetime.subtract(fields.Datetime.now(), days=1)

        def monte(nom, login):
            partner = cls.env['res.partner'].create({'name': nom})
            Users.create({
                'name': nom, 'login': login,
                'email': '%s@exemple.ch' % login,
                'password': 'Portail-123!',
                'partner_id': partner.id,
                'group_ids': [(6, 0, [portal_group.id])],
            })
            return partner

        cls.partner_a = monte("Web Salle A", "web.restoa")
        cls.partner_b = monte("Web Salle B", "web.restob")
        Resa = cls.env['megga.resto.reservation']
        cls.resa_a = Resa.create({
            'guest_name': "Web Salle A", 'partner_id': cls.partner_a.id,
            'start': cls.demain, 'party_size': 2})
        cls.resa_a.action_confirm()
        cls.resa_b = Resa.create({
            'guest_name': "Web Salle B", 'partner_id': cls.partner_b.id,
            'start': cls.demain, 'party_size': 3})
        cls.resa_b.action_confirm()
        cls.resa_passee = Resa.create({
            'guest_name': "Web Salle A", 'partner_id': cls.partner_a.id,
            'start': cls.hier, 'party_size': 2})
        cls.resa_passee.action_confirm()

    def _jeton(self):
        page = self.url_open('/my/reservations')
        self.assertEqual(page.status_code, 200)
        trouve = JETON.search(page.text)
        self.assertTrue(trouve, "le formulaire d'annulation porte un jeton")
        return trouve.group(1)

    def _annuler(self, reservation, jeton):
        return self.url_open(
            '/my/reservations/%d/annuler' % reservation.id,
            data={'csrf_token': jeton})

    def test_la_page_liste_les_siennes(self):
        self.authenticate("web.restoa", "Portail-123!")
        page = self.url_open('/my/reservations')
        self.assertEqual(page.status_code, 200)
        self.assertIn(self.resa_a.name, page.text)
        self.assertNotIn(self.resa_b.name, page.text)

    def test_la_carte_d_accueil(self):
        self.authenticate("web.restoa", "Portail-123!")
        page = self.url_open('/my')
        self.assertEqual(page.status_code, 200)
        self.assertIn("Mes réservations", page.text)

    def test_annule_la_sienne(self):
        self.authenticate("web.restoa", "Portail-123!")
        jeton = self._jeton()
        reponse = self._annuler(self.resa_a, jeton)
        self.assertEqual(reponse.status_code, 200)
        self.resa_a.invalidate_recordset()
        self.assertEqual(self.resa_a.state, 'cancelled')
        self.assertTrue(any(
            "portail" in (m.body or "")
            for m in self.resa_a.message_ids),
            "l'annulation du client est tracée au chatter")

    def test_n_annule_pas_celle_du_voisin(self):
        self.authenticate("web.restoa", "Portail-123!")
        jeton = self._jeton()
        self._annuler(self.resa_b, jeton)
        self.resa_b.invalidate_recordset()
        self.assertEqual(self.resa_b.state, 'confirmed',
                         "la réservation du voisin ne bouge pas")

    def test_n_annule_pas_un_service_passe(self):
        self.authenticate("web.restoa", "Portail-123!")
        jeton = self._jeton()
        self._annuler(self.resa_passee, jeton)
        self.resa_passee.invalidate_recordset()
        self.assertEqual(self.resa_passee.state, 'confirmed',
                         "le couvert était mis : ça se règle au téléphone")

    def test_n_annule_pas_une_table_installee(self):
        """Course reelle : le client a la page ouverte, la salle installe
        la table, il clique Annuler. Le bouton a disparu pour les
        suivants, mais le POST doit etre refuse quand meme — la garde
        vit dans le controleur, pas dans le gabarit."""
        self.authenticate("web.restoa", "Portail-123!")
        jeton = self._jeton()
        self.resa_a.action_seat()
        self._annuler(self.resa_a, jeton)
        self.resa_a.invalidate_recordset()
        self.assertEqual(self.resa_a.state, 'seated')
