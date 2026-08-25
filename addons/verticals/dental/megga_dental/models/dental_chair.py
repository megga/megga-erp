from odoo import api, fields, models


class MeggaDentalChair(models.Model):
    """Fauteuil (ou salle) du cabinet : la ressource MATÉRIELLE que les
    séances se partagent. Le planning par fauteuil vit sur le
    traitement (créneau + garde de conflits) ; ici, le référentiel —
    de la logistique, pas des données de santé : la réception le lit
    pour planifier."""
    _name = 'megga.dental.chair'
    _description = "Fauteuil"
    _order = 'sequence, id'

    name = fields.Char("Nom", required=True)
    sequence = fields.Integer(
        default=10,
        help="Ordre d'attribution automatique : à créneau libre égal, "
             "le premier de la liste gagne.")
    note = fields.Char("Note", help="Équipement particulier, étage…")
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint(
        'unique(name)', "Ce fauteuil existe déjà.")
