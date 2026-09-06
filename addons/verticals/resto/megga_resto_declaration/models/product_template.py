from odoo import fields, models


class ProductTemplate(models.Model):
    """Ce qu'un article apporte à la déclaration du plat.

    Les champs vivent sur product.template — donc une seule saisie pour
    toutes les variantes, et la fiche technique les lit à travers la
    variante sans rien faire de plus.

    Préfixe `megga_` : product.template est un modèle DU CŒUR, partagé
    par toutes les verticales (le garage vend ses pièces sur le même
    modèle). Le préfixe évite la collision et dit d'où vient le champ —
    même convention que `megga_owner_id` sur les véhicules du garage.
    """
    _inherit = 'product.template'

    megga_allergen_ids = fields.Many2many(
        'megga.resto.allergen', string="Allergènes",
        help="Ce que cet ingrédient apporte d'allergène au plat. Tout "
             "plat qui l'emploie en hérite.")
    megga_allergens_checked = fields.Boolean(
        "Allergènes vérifiés",
        help="À cocher quand quelqu'un a REGARDÉ l'étiquette — y compris "
             "pour constater qu'il n'y a aucun allergène. Sans cette "
             "case, une liste vide veut dire « pas encore renseigné », "
             "et la déclaration du plat reste incomplète. Cocher un "
             "allergène vaut vérification : on a bien regardé.")
    megga_origin_required = fields.Boolean(
        "Provenance à déclarer",
        help="Viande et poisson : le pays de production doit figurer sur "
             "la carte.")
    megga_origin_country_id = fields.Many2one(
        'res.country', string="Pays de production",
        help="Le pays où la denrée a été produite — celui qui paraîtra "
             "sur la carte, pas celui du fournisseur.")
