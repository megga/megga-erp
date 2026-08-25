from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestChair(TransactionCase):
    """Fauteuils et créneaux : sans créneau rien ne change (compat) ;
    avec, les conflits sont refusés par fauteuil ET par praticien
    (confirmés seulement, bords adjacents permis) et la planification
    attribue toute seule le premier fauteuil libre."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        cls.reception = Users.create({
            'name': "Réception Fauteuil", 'login': "chair_reception",
            'email': "chair.reception@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        cls.dentiste_a = Users.create({
            'name': "Dr A", 'login': "chair_dr_a",
            'email': "dr.a@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_praticien').id)],
        })
        cls.dentiste_b = Users.create({
            'name': "Dr B", 'login': "chair_dr_b",
            'email': "dr.b@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_praticien').id)],
        })
        cls.patient = cls.env['megga.dental.patient'].create({
            'name': "Fabrice Fauteuil"})
        cls.acte = cls.env['product.product'].create({
            'name': "Contrôle", 'type': 'service', 'list_price': 90.0})
        Chair = cls.env['megga.dental.chair']
        cls.f1 = Chair.create({'name': "Fauteuil 1", 'sequence': 10})
        cls.f2 = Chair.create({'name': "Fauteuil 2", 'sequence': 20})

    def _treatment(self, start=False, dentist=None, chair=False, hours=1.0):
        return self.env['megga.dental.treatment'].create({
            'patient_id': self.patient.id,
            'dentist_id': (dentist or self.dentiste_a).id,
            'start_at': start,
            'duration': hours,
            'chair_id': chair and chair.id,
            'line_ids': [Command.create({
                'product_id': self.acte.id, 'price_unit': 90.0})],
        })

    def test_sans_creneau_rien_ne_change(self):
        treatment = self._treatment()
        treatment.action_confirm()
        self.assertEqual(treatment.state, 'confirmed')
        self.assertFalse(treatment.chair_id)
        self.assertFalse(treatment.stop_at)

    def test_fin_calculee(self):
        treatment = self._treatment(start='2026-09-01 08:00:00', hours=1.5)
        self.assertEqual(str(treatment.stop_at), '2026-09-01 09:30:00')

    def test_conflit_de_fauteuil_refuse(self):
        premier = self._treatment(start='2026-09-01 08:00:00', chair=self.f1)
        premier.action_confirm()
        second = self._treatment(
            start='2026-09-01 08:30:00', dentist=self.dentiste_b,
            chair=self.f1)
        with self.assertRaises(ValidationError) as capture:
            second.action_confirm()
        self.assertIn("Fauteuil 1", str(capture.exception))

    def test_bords_adjacents_permis(self):
        premier = self._treatment(start='2026-09-01 08:00:00', chair=self.f1)
        premier.action_confirm()
        suivant = self._treatment(
            start='2026-09-01 09:00:00', dentist=self.dentiste_b,
            chair=self.f1)
        suivant.action_confirm()
        self.assertEqual(suivant.state, 'confirmed')

    def test_attribution_automatique(self):
        premier = self._treatment(start='2026-09-01 08:00:00')
        premier.action_confirm()
        self.assertEqual(premier.chair_id, self.f1)
        second = self._treatment(
            start='2026-09-01 08:30:00', dentist=self.dentiste_b)
        second.action_confirm()
        self.assertEqual(second.chair_id, self.f2)

    def test_aucun_fauteuil_libre(self):
        self._treatment(start='2026-09-01 08:00:00').action_confirm()
        self._treatment(start='2026-09-01 08:15:00',
                        dentist=self.dentiste_b).action_confirm()
        troisieme = self._treatment(
            start='2026-09-01 08:30:00', dentist=self.reception)
        with self.assertRaises(UserError) as capture:
            troisieme.action_confirm()
        self.assertIn("Aucun fauteuil libre", str(capture.exception))
        self.assertFalse(troisieme.chair_id)

    def test_conflit_de_praticien_refuse(self):
        premier = self._treatment(start='2026-09-01 08:00:00', chair=self.f1)
        premier.action_confirm()
        meme_praticien = self._treatment(
            start='2026-09-01 08:30:00', chair=self.f2)
        with self.assertRaises(ValidationError) as capture:
            meme_praticien.action_confirm()
        self.assertIn("Dr A", str(capture.exception))

    def test_devis_et_termines_ne_bloquent_pas(self):
        occupant = self._treatment(start='2026-09-01 08:00:00', chair=self.f1)
        occupant.action_confirm()
        occupant.action_done()
        # La séance est terminée : le fauteuil est rendu.
        libre = self._treatment(
            start='2026-09-01 08:15:00', dentist=self.dentiste_b,
            chair=self.f1)
        libre.action_confirm()
        self.assertEqual(libre.state, 'confirmed')
        # Un simple devis sur le même créneau ne bloque personne.
        devis = self._treatment(start='2026-09-01 08:20:00', chair=self.f1)
        self.assertEqual(devis.state, 'draft')

    def test_deplacement_reverifie(self):
        premier = self._treatment(start='2026-09-01 08:00:00', chair=self.f1)
        premier.action_confirm()
        second = self._treatment(
            start='2026-09-01 10:00:00', dentist=self.dentiste_b,
            chair=self.f1)
        second.action_confirm()
        with self.assertRaises(ValidationError):
            second.start_at = '2026-09-01 08:30:00'

    def test_la_reception_planifie(self):
        treatment = self._treatment(
            start='2026-09-01 14:00:00', dentist=self.dentiste_b)
        as_reception = treatment.with_user(self.reception)
        as_reception.action_confirm()
        self.assertEqual(as_reception.chair_id, self.f1)
        self.assertEqual(as_reception.chair_id.name, "Fauteuil 1")
