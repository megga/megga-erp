from odoo import fields, models


class MeggaCareServiceType(models.Model):
    """Référentiel des types de prestation : l'axe d'analyse « par type »
    des statistiques, et le porteur des deux drapeaux fiscaux du métier —
    rétrocession (laboratoires, pharmacies : marge sur volume) et
    exclusion du champ TVA (art. 21 al. 2 ch. 3 LTVA : les traitements
    médicaux refacturés sont exclus ; la pharmacie, elle, est imposable)."""
    _name = 'megga.care.service.type'
    _description = "Type de prestation de conciergerie"
    _order = 'sequence, id'

    name = fields.Char("Type de prestation", required=True)
    code = fields.Char("Code", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    retrocession = fields.Boolean(
        "Ouvre droit à rétrocession",
        help="Le prestataire reverse une marge sur le volume apporté"
             " (laboratoires, pharmacies) : le coût réel est inférieur au"
             " prix facturé au client.")
    vat_exempt = fields.Boolean(
        "Exclu du champ TVA (art. 21 LTVA)",
        help="Prestation médicale exclue du champ de l'impôt : elle"
             " n'entre pas dans le chiffre d'affaires déterminant pour"
             " l'assujettissement.")

    _code_uniq = models.Constraint(
        'unique(code)', "Ce code de prestation existe déjà.")
