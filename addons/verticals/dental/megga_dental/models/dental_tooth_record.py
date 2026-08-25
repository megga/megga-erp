from odoo import api, fields, models

from ..dental_logic import SURFACES

# Sélection partagée avec la position tarifaire (« constat au terme de
# l'acte ») : une seule liste, deux usages.
CONDITION_SELECTION = [
    ('carie', "Carie"),
    ('a_surveiller', "À surveiller"),
    ('obturation', "Obturation"),
    ('devitalisee', "Dévitalisée"),
    ('couronne', "Couronne"),
    ('implant', "Implant"),
    ('absente', "Absente / extraite"),
    ('saine', "Saine (contrôle)"),
]

SURFACE_SELECTION = [
    (code, label[0].upper() + label[1:]) for code, label in SURFACES.items()
]


class MeggaDentalToothRecord(models.Model):
    """Constat dentaire : l'état d'une dent — ou d'une de ses surfaces —
    à une date donnée. L'odontogramme n'est que la LECTURE du dernier
    constat par dent et par surface : on n'efface jamais l'histoire, on
    pose un constat par-dessus (l'obturation par-dessus la carie), ce
    qui rejoint l'exigence de traçabilité de la nLPD.

    Données de santé (art. 5 nLPD) : le modèle entier est réservé au
    groupe Soins — la réception n'a AUCUN droit dessus (aucune ligne
    ir.model.access), contrairement aux traitements dont elle voit les
    montants pour facturer."""
    _name = 'megga.dental.tooth.record'
    _description = "Constat dentaire"
    _order = 'date desc, id desc'

    patient_id = fields.Many2one(
        'megga.dental.patient', string="Patient", required=True,
        ondelete='cascade', index=True)
    tooth_id = fields.Many2one(
        'megga.dental.tooth', string="Dent", required=True,
        ondelete='restrict', index=True)
    surface = fields.Selection(
        SURFACE_SELECTION, string="Surface",
        help="Laisser vide pour un constat sur la dent entière "
             "(extraction, couronne, implant…).")
    condition = fields.Selection(
        CONDITION_SELECTION, string="Constat", required=True)
    date = fields.Date(
        "Date", required=True, default=fields.Date.context_today)
    dentist_id = fields.Many2one(
        'res.users', string="Praticien",
        default=lambda self: self.env.user)
    note = fields.Char("Note")
    line_id = fields.Many2one(
        'megga.dental.treatment.line', string="Acte d'origine",
        readonly=True, ondelete='set null',
        help="Renseigné quand le constat a été inscrit automatiquement "
             "au terme d'un traitement.")

    @api.depends('tooth_id.number', 'condition', 'surface')
    def _compute_display_name(self):
        conditions = dict(CONDITION_SELECTION)
        surfaces = dict(SURFACE_SELECTION)
        for record in self:
            name = "%s — %s" % (
                record.tooth_id.number, conditions.get(record.condition, ''))
            if record.surface:
                name += " (%s)" % surfaces[record.surface]
            record.display_name = name
