from odoo import api, fields, models


class MeggaRestoAllergen(models.Model):
    """Un allergène à déclaration obligatoire.

    La liste est FIXÉE PAR LA LOI — le restaurant n'a pas à l'inventer
    ni à la maintenir : elle est livrée avec le module et se met à jour
    avec lui, comme le référentiel des dents du cabinet. Ce qu'un
    restaurant peut faire : archiver ce qu'il ne sert jamais (pas de
    mollusques dans une pizzeria), et compléter la note d'aide de sa
    maison — « nos pâtes contiennent aussi de l'œuf ».

    Volontairement pauvre : ni société, ni état, ni chatter. Un
    référentiel légal n'a pas de cycle de vie.
    """
    _name = 'megga.resto.allergen'
    _description = "Allergène à déclaration obligatoire"
    _order = 'sequence, id'

    code = fields.Char("Code", required=True, index=True)
    name = fields.Char("Libellé", required=True)
    sequence = fields.Integer(default=10)
    note = fields.Text(
        "Ce que cela recouvre",
        help="Les denrées visées, pour que la salle sache répondre sans "
             "aller chercher la loi.")
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        'unique(code)', "Ce code d'allergène existe déjà.")

    @api.depends('code', 'name')
    def _compute_display_name(self):
        """« Lait » à l'écran, pas « megga.resto.allergen(3,) » — et
        le code reste cherchable."""
        for allergen in self:
            allergen.display_name = allergen.name or allergen.code
