import base64
import io

from PIL import Image

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase


def _png():
    buf = io.BytesIO()
    Image.new('RGB', (4, 4), (40, 40, 40)).save(buf, 'PNG')
    return base64.b64encode(buf.getvalue())


class TestImaging(TransactionCase):
    """Imagerie au dossier : libellé auto-composé (type + dents),
    image en pièce jointe (filestore, donc sauvegardes), rattachements
    dents/traitement, et modèle entièrement fermé à la réception."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        cls.reception = Users.create({
            'name': "Réception Radio", 'login': "radio_reception",
            'email': "radio.reception@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        cls.soins = Users.create({
            'name': "Soins Radio", 'login': "radio_soins",
            'email': "radio.soins@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_praticien').id)],
        })
        cls.patient = cls.env['megga.dental.patient'].create({
            'name': "Rachel Rayon",
        })
        Tooth = cls.env['megga.dental.tooth']
        cls.t16 = Tooth.search([('number', '=', 16)])
        cls.t17 = Tooth.search([('number', '=', 17)])
        cls.png = _png()

    def _imaging(self, **kw):
        vals = {
            'patient_id': self.patient.id,
            'image': self.png,
        }
        vals.update(kw)
        return self.env['megga.dental.imaging'].create(vals)

    def test_libelle_par_type_et_dent(self):
        cliche = self._imaging(kind='retro', tooth_ids=[(6, 0, self.t16.ids)])
        self.assertEqual(cliche.name, "Rétro-alvéolaire — dent 16")
        pano = self._imaging(kind='pano')
        self.assertEqual(pano.name, "Panoramique (OPT)")

    def test_libelle_multi_dents(self):
        cliche = self._imaging(
            kind='bitewing', tooth_ids=[(6, 0, (self.t16 + self.t17).ids)])
        self.assertEqual(cliche.name, "Interproximal (bitewing) — dents 16, 17")

    def test_libelle_suit_le_type(self):
        cliche = self._imaging(kind='retro')
        self.assertEqual(cliche.name, "Rétro-alvéolaire")
        cliche.kind = 'photo'
        self.assertEqual(cliche.name, "Photo clinique")
        # Et il reste modifiable a la main.
        cliche.name = "Sourire avant blanchiment"
        self.assertEqual(cliche.name, "Sourire avant blanchiment")

    def test_image_en_piece_jointe(self):
        cliche = self._imaging(kind='retro')
        attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'megga.dental.imaging'),
            ('res_id', '=', cliche.id),
            ('res_field', '=', 'image'),
        ])
        self.assertEqual(len(attachment), 1)

    def test_rattachements(self):
        treatment = self.env['megga.dental.treatment'].create({
            'patient_id': self.patient.id})
        cliche = self._imaging(
            kind='retro', treatment_id=treatment.id,
            tooth_ids=[(6, 0, self.t16.ids)])
        self.assertEqual(cliche.treatment_id, treatment)
        self.assertEqual(self.patient.imaging_count, 1)

    def test_cascade_avec_le_dossier(self):
        patient = self.env['megga.dental.patient'].create({
            'name': "Dossier Éphémère"})
        cliche = self._imaging(patient_id=patient.id)
        patient.unlink()
        self.assertFalse(cliche.exists())

    def test_lpd_reception_aveugle(self):
        cliche = self._imaging(kind='retro')
        Imaging = self.env['megga.dental.imaging'].with_user(self.reception)
        with self.assertRaises(AccessError):
            Imaging.search([])
        with self.assertRaises(AccessError):
            Imaging.create({
                'patient_id': self.patient.id, 'image': self.png})
        with self.assertRaises(AccessError):
            cliche.with_user(self.reception).read(['image'])
        with self.assertRaises(AccessError):
            self.patient.with_user(self.reception).read(['imaging_count'])

    def test_soins_au_travail(self):
        cliche = self.env['megga.dental.imaging'].with_user(
            self.soins).create({
                'patient_id': self.patient.id,
                'kind': 'photo',
                'image': self.png,
            })
        self.assertEqual(cliche.name, "Photo clinique")
        self.assertTrue(cliche.image)

    def test_pano_sans_dents_reste_un_ensemble(self):
        pano = self._imaging(kind='pano')
        self.assertFalse(pano.tooth_ids)
        pano.tooth_ids = [(6, 0, self.t16.ids)]
        self.assertEqual(pano.name, "Panoramique (OPT) — dent 16")
