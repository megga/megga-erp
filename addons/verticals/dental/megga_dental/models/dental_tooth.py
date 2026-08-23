from odoo import api, fields, models


class MeggaDentalTooth(models.Model):
    """Référentiel des 52 dents en notation FDI / ISO 3950, chargé par
    data/megga.dental.tooth.csv (généré depuis dental_logic, source unique)."""
    _name = 'megga.dental.tooth'
    _description = "Dent (notation FDI / ISO 3950)"
    _order = 'number'

    number = fields.Integer("Numéro FDI", required=True)
    name = fields.Char("Désignation", required=True)
    deciduous = fields.Boolean("Dent de lait")

    _number_uniq = models.Constraint(
        'unique(number)', "Ce numéro FDI existe déjà.")

    @api.depends('number', 'name')
    def _compute_display_name(self):
        for tooth in self:
            tooth.display_name = "%s — %s" % (tooth.number, tooth.name)
