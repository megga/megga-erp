from odoo import _, api, fields, models

# Types de clichés usuels d'un cabinet dentaire. Le DICOM brut n'est
# pas du ressort de cette v1 : on archive l'EXPORT image (PNG/JPEG)
# que produit n'importe quel capteur ; le fichier natif reste dans le
# logiciel d'imagerie du fabricant.
KIND_SELECTION = [
    ('retro', "Rétro-alvéolaire"),
    ('bitewing', "Interproximal (bitewing)"),
    ('pano', "Panoramique (OPT)"),
    ('cbct', "CBCT (coupe exportée)"),
    ('ceph', "Téléradiographie"),
    ('photo', "Photo clinique"),
    ('autre', "Autre document"),
]


class MeggaDentalImaging(models.Model):
    """Cliché d'imagerie rattaché au dossier : radio, photo clinique,
    coupe exportée. L'image vit en PIÈCE JOINTE (ir.attachment,
    filestore) : elle suit les sauvegardes du stack comme le reste.

    Données de santé (art. 5 nLPD) : modèle entièrement fermé à la
    réception — aucune ligne ir.model.access, le patron des constats,
    ordonnances et questionnaires."""
    _name = 'megga.dental.imaging'
    _description = "Imagerie dentaire"
    _order = 'date desc, id desc'

    patient_id = fields.Many2one(
        'megga.dental.patient', string="Patient", required=True,
        ondelete='cascade', index=True)
    kind = fields.Selection(
        KIND_SELECTION, string="Type", required=True, default='retro')
    name = fields.Char(
        "Libellé", required=True,
        compute='_compute_name', store=True, readonly=False,
        precompute=True)
    date = fields.Date(
        "Date", required=True, default=fields.Date.context_today)
    tooth_ids = fields.Many2many(
        'megga.dental.tooth', string="Dents",
        help="Vide pour un cliché d'ensemble (panoramique, téléradio).")
    treatment_id = fields.Many2one(
        'megga.dental.treatment', string="Traitement", ondelete='set null')
    dentist_id = fields.Many2one(
        'res.users', string="Praticien",
        default=lambda self: self.env.user)
    image = fields.Image("Cliché", required=True, attachment=True)
    note = fields.Char("Note")

    @api.depends('kind', 'tooth_ids')
    def _compute_name(self):
        labels = dict(KIND_SELECTION)
        for imaging in self:
            name = labels.get(imaging.kind, "?")
            teeth = imaging.tooth_ids.sorted('number')
            if teeth:
                prefixe = _("dent") if len(teeth) == 1 else _("dents")
                name = "%s — %s %s" % (
                    name, prefixe,
                    ", ".join(str(tooth.number) for tooth in teeth))
            imaging.name = name
