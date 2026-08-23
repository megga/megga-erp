from odoo import api, fields, models


class MeggaDentalPosition(models.Model):
    """Position du tarif dentaire par points.

    En Suisse, les actes dentaires se facturent par POSITIONS : chaque
    position porte un nombre de points tarifaires (PT), et le montant
    vaut points × valeur du point. La valeur du point est celle du
    cabinet pour les patients privés, et celle de la convention pour les
    assurances sociales (AA/AI/AM).

    Le CATALOGUE officiel des positions (numéros, libellés, points) est
    une œuvre sous licence de la SSO : il n'est PAS embarqué ici. Chaque
    cabinet, au bénéfice de sa propre licence, importe ses positions
    (import CSV standard : code, name, points, chapter — un exemple de
    fichier est fourni dans docs/) ou les saisit à la main.
    """
    _name = 'megga.dental.position'
    _description = "Position tarifaire (points)"
    _order = 'code, id'

    code = fields.Char("Numéro", required=True, index=True)
    name = fields.Char("Libellé", required=True)
    points = fields.Float(
        "Points tarifaires (PT)", required=True, digits=(12, 2))
    chapter = fields.Char(
        "Chapitre",
        help="Regroupement du catalogue (diagnostic, prophylaxie, "
             "conservatrice…) — libre, pour le tri et la recherche.")
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        'unique(code)',
        "Ce numéro de position existe déjà au catalogue.")

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for position in self:
            position.display_name = "%s — %s" % (position.code, position.name)


class ResCompany(models.Model):
    _inherit = 'res.company'

    dental_point_value = fields.Float(
        "Valeur du point (privé)", digits=(12, 2), default=1.0,
        help="Valeur du point tarifaire appliquée aux patients privés — "
             "propre au cabinet. Les traitements aux assurances sociales "
             "(AA/AI/AM) utilisent la valeur de la convention.")
