from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class MeggaDentalClinicalNote(models.Model):
    """Journal clinique du dossier : des notes qui s'écrivent AU STYLO.

    Immuables dès la création — le serveur force l'horodatage et
    l'auteur, aucune modification ensuite, aucune suppression jamais
    (l'ACL ne donne le droit à personne ET la garde python double
    l'interdit). L'erreur se corrige par une note de RECTIFICATION,
    chaînée à l'originale : l'histoire du dossier ne se réécrit pas
    (traçabilité, art. 8 nLPD). Le dossier qui porte des notes ne se
    supprime plus (restrict) — il s'archive.

    Données de santé pures : modèle fermé à la réception, comme tout
    le clinique. Pas de mail.thread : le journal EST le fil."""
    _name = 'megga.dental.clinical.note'
    _description = "Note clinique (immuable)"
    _order = 'date_time desc, id desc'

    patient_id = fields.Many2one(
        'megga.dental.patient', string="Patient", required=True,
        ondelete='restrict', index=True)
    date_time = fields.Datetime(
        "Horodatage", readonly=True,
        help="Posé par le serveur à l'écriture — il ne se choisit pas : "
             "une note sur une séance passée le dit dans son texte.")
    author_id = fields.Many2one(
        'res.users', string="Auteur", readonly=True,
        help="Posé par le serveur : on n'écrit pas au nom d'un autre.")
    kind = fields.Selection([
        ('session', "Note de séance"),
        ('exam', "Observation"),
        ('call', "Contact patient"),
        ('incident', "Incident"),
        ('rectification', "Rectification"),
    ], string="Type", required=True, default='session')
    body = fields.Text("Note", required=True)
    tooth_ids = fields.Many2many(
        'megga.dental.tooth', string="Dents")
    treatment_id = fields.Many2one(
        'megga.dental.treatment', string="Traitement", ondelete='set null')
    rectifies_id = fields.Many2one(
        'megga.dental.clinical.note', string="Rectifie", readonly=True,
        ondelete='restrict')
    rectification_ids = fields.One2many(
        'megga.dental.clinical.note', 'rectifies_id',
        string="Rectifiée par")
    rectified = fields.Boolean(
        "Rectifiée", compute='_compute_rectified')

    @api.depends('rectification_ids')
    def _compute_rectified(self):
        for note in self:
            note.rectified = bool(note.rectification_ids)

    @api.depends('date_time', 'author_id')
    def _compute_display_name(self):
        for note in self:
            quand = fields.Datetime.context_timestamp(
                note, note.date_time).strftime("%d.%m.%Y %H:%M") \
                if note.date_time else "?"
            note.display_name = "%s — %s" % (
                quand, note.author_id.name or "?")

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            # L'horodatage et l'auteur ne se choisissent pas : toute
            # valeur fournie est ecrasee.
            vals['date_time'] = now
            vals['author_id'] = self.env.uid
            if vals.get('rectifies_id'):
                vals['kind'] = 'rectification'
        notes = super().create(vals_list)
        for note in notes:
            if note.rectifies_id and \
                    note.rectifies_id.patient_id != note.patient_id:
                raise ValidationError(_(
                    "Une rectification appartient au même dossier que "
                    "la note qu'elle corrige."))
        return notes

    def write(self, vals):
        raise UserError(_(
            "Une note clinique ne se modifie pas — elle s'écrit au "
            "stylo. Corrigez par une note de rectification."))

    @api.ondelete(at_uninstall=False)
    def _unlink_never(self):
        raise UserError(_(
            "Une note clinique ne se supprime jamais — l'histoire du "
            "dossier reste. Archivez le dossier s'il doit sortir de "
            "la circulation."))

    def action_rectify(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Rectifier"),
            'res_model': 'megga.dental.clinical.note',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_rectifies_id': self.id,
                'default_kind': 'rectification',
                'default_treatment_id': self.treatment_id.id,
            },
        }
