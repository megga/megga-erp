from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase
from odoo.tools import mute_logger


class TestClinicalNote(TransactionCase):
    """Le journal clinique s'écrit au stylo : horodatage et auteur
    forcés par le serveur, aucune modification, aucune suppression —
    la correction passe par une rectification chaînée, et le dossier
    porteur ne se supprime plus (il s'archive)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        cls.reception = Users.create({
            'name': "Réception Note", 'login': "note_reception",
            'email': "note.reception@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        cls.soins = Users.create({
            'name': "Soins Note", 'login': "note_soins",
            'email': "note.soins@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_praticien').id)],
        })
        cls.patient = cls.env['megga.dental.patient'].create({
            'name': "Nina Journal",
        })

    def _note(self, body="Constat du jour.", **kw):
        return self.env['megga.dental.clinical.note'].create({
            'patient_id': self.patient.id, 'body': body, **kw})

    def test_horodatage_et_auteur_forces(self):
        note = self.env['megga.dental.clinical.note'].with_user(
            self.soins).create({
                'patient_id': self.patient.id,
                'body': "Note antidatée ?",
                'date_time': '2020-01-01 08:00:00',
                'author_id': self.reception.id,
            })
        # Toute valeur fournie est ecrasee par le serveur.
        self.assertEqual(str(note.date_time)[:7], "2026-08")
        self.assertEqual(note.author_id, self.soins)

    def test_aucune_modification(self):
        note = self._note()
        with self.assertRaises(UserError):
            note.body = "Version remaniée"
        with self.assertRaises(UserError):
            note.sudo().write({'kind': 'exam'})

    def test_aucune_suppression(self):
        note = self._note()
        with self.assertRaises(UserError):
            note.unlink()
        with self.assertRaises(UserError):
            note.sudo().unlink()
        self.assertTrue(note.exists())

    def test_le_dossier_porteur_ne_se_supprime_plus(self):
        patient = self.env['megga.dental.patient'].create({
            'name': "Dossier Verrouillé"})
        self.env['megga.dental.clinical.note'].create({
            'patient_id': patient.id, 'body': "Première note."})
        with self.assertRaises(Exception), \
                self.env.cr.savepoint(), \
                mute_logger('odoo.sql_db'):
            patient.unlink()
        self.assertTrue(patient.exists())
        # L'archivage, lui, reste la voie de sortie.
        patient.active = False
        self.assertFalse(patient.active)

    def test_rectification_chainee(self):
        note = self._note(body="Dent 26 obturée.")
        action = note.action_rectify()
        self.assertEqual(
            action['context']['default_rectifies_id'], note.id)
        rectif = self.env['megga.dental.clinical.note'].create({
            'patient_id': self.patient.id,
            'rectifies_id': note.id,
            'kind': 'session',   # force a rectification par le serveur
            'body': "Lire : dent 27, non 26.",
        })
        self.assertEqual(rectif.kind, 'rectification')
        self.assertTrue(note.rectified)
        self.assertEqual(note.rectification_ids, rectif)
        self.assertFalse(rectif.rectified)

    def test_rectification_meme_dossier(self):
        note = self._note()
        autre = self.env['megga.dental.patient'].create({
            'name': "Autre Dossier"})
        with self.assertRaises(ValidationError):
            self.env['megga.dental.clinical.note'].create({
                'patient_id': autre.id,
                'rectifies_id': note.id,
                'body': "Rectification égarée.",
            })

    def test_chronologie_du_journal(self):
        premiere = self._note(body="Première.")
        seconde = self._note(body="Seconde.")
        journal = self.env['megga.dental.clinical.note'].search(
            [('patient_id', '=', self.patient.id)])
        self.assertEqual(journal[0], seconde)
        self.assertEqual(journal[-1], premiere)
        self.assertEqual(self.patient.clinical_note_count, 2)

    def test_lpd_reception_aveugle(self):
        note = self._note()
        Note = self.env['megga.dental.clinical.note'].with_user(
            self.reception)
        with self.assertRaises(AccessError):
            Note.search([])
        with self.assertRaises(AccessError):
            Note.create({
                'patient_id': self.patient.id, 'body': "Interdit."})
        with self.assertRaises(AccessError):
            note.with_user(self.reception).read(['body'])
        with self.assertRaises(AccessError):
            self.patient.with_user(self.reception).read(
                ['clinical_note_count'])

    def test_soins_ecrivent_et_lisent(self):
        note = self.env['megga.dental.clinical.note'].with_user(
            self.soins).create({
                'patient_id': self.patient.id,
                'kind': 'incident',
                'body': "Malaise vagal en fin de séance, résolu.",
            })
        self.assertEqual(note.author_id, self.soins)
        self.assertIn("Soins Note", note.display_name)

    def test_pas_de_droit_de_suppression_du_tout(self):
        # L'ACL elle-meme ne donne unlink a personne (0 partout) : la
        # garde python n'est que la seconde bretelle.
        acl = self.env['ir.model.access'].sudo().search([
            ('model_id.model', '=', 'megga.dental.clinical.note')])
        self.assertTrue(acl)
        self.assertFalse(any(acl.mapped('perm_unlink')))
