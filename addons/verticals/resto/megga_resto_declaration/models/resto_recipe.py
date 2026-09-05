from odoo import api, fields, models

from ..declaration_logic import Ingredient, missing_declarations
# Alias : le champ du modèle porte le même nom que la fonction. Sans
# lui, un lecteur ne sait plus lequel des deux il lit.
from ..declaration_logic import declaration_state as etat_declaration


class MeggaRestoRecipe(models.Model):
    """La déclaration légale du plat, déduite de sa fiche technique.

    Rien ne se saisit ici : tout vient des ingrédients. Ajouter le
    gluten à une farine le fait apparaître sur chaque plat qui l'emploie,
    et changer le pays d'une entrecôte met la carte à jour d'un coup.
    """
    _inherit = 'megga.resto.recipe'

    # NON stocké, à dessein. Un many2many calculé ET stocké serait le
    # premier du dépôt, et la maison garde la cicatrice d'un compute
    # stocké à travers une relation (le sous-total des productions :
    # le recalcul plantait toute création de ligne). La question utile
    # — « quels plats contiennent du gluten ? » — se répond par une
    # méthode de recherche, qui traduit la question en requête sur les
    # lignes ; le reste se calcule à la lecture, sur une poignée
    # d'ingrédients.
    allergen_ids = fields.Many2many(
        'megga.resto.allergen', string="Allergènes du plat",
        compute='_compute_allergen_ids', search='_search_allergen_ids',
        help="La réunion des allergènes de tous les ingrédients.")
    declaration_state = fields.Selection([
        ('complete', "Déclarable"),
        ('incomplete', "À compléter"),
    ], string="Déclaration", compute='_compute_declaration', store=True)
    declaration_missing = fields.Text(
        "Ce qui manque", compute='_compute_declaration', store=True,
        help="Nommément : quel ingrédient, et quoi. Un manque anonyme "
             "ne se corrige pas.")

    @api.depends('line_ids.product_id.megga_allergen_ids')
    def _compute_allergen_ids(self):
        for recipe in self:
            recipe.allergen_ids = recipe.line_ids.mapped(
                'product_id.megga_allergen_ids')

    def _search_allergen_ids(self, operator, value):
        """« Quels plats contiennent du gluten ? » — la question se pose
        sur le plat, elle se répond sur les lignes.

        La NÉGATION s'inverse au bon niveau : les plats SANS gluten ne
        sont pas ceux dont une ligne n'en porte pas (n'importe quel plat
        au gluten a aussi des lignes sans gluten), ce sont ceux dont
        AUCUNE ligne n'en porte. On cherche donc toujours la forme
        positive, puis on exclut."""
        inverses = {'not in': 'in', '!=': '=', 'not ilike': 'ilike'}
        positif = inverses.get(operator)
        lignes = self.env['megga.resto.recipe.line'].search(
            [('product_id.megga_allergen_ids', positif or operator, value)])
        return [('id', 'not in' if positif else 'in',
                 lignes.recipe_id.ids)]

    # Les quatre dépendances de la règle de complétude. Trois d'entre
    # elles vivent sur product.template et se lisent à travers la
    # variante : l'héritage par délégation du cœur les propage, et le
    # recalcul suit (cocher « vérifié » sur un article met à jour tous
    # les plats qui l'emploient).
    @api.depends('line_ids.product_id.megga_allergen_ids',
                 'line_ids.product_id.megga_allergens_checked',
                 'line_ids.product_id.megga_origin_required',
                 'line_ids.product_id.megga_origin_country_id')
    def _compute_declaration(self):
        for recipe in self:
            ingredients = recipe._declaration_ingredients()
            recipe.declaration_missing = "\n".join(
                missing_declarations(ingredients))
            recipe.declaration_state = etat_declaration(ingredients)

    def _declaration_ingredients(self):
        """Les ingrédients de la fiche, tels que la logique pure les
        attend : sans ORM, sans société, sans rien qui ne serve à la
        règle de complétude."""
        self.ensure_one()
        return [Ingredient(
            name=line.product_id.display_name,
            allergens_checked=line.product_id.megga_allergens_checked,
            allergen_count=len(line.product_id.megga_allergen_ids),
            origin_required=line.product_id.megga_origin_required,
            origin_known=bool(line.product_id.megga_origin_country_id),
        ) for line in self.line_ids]

    def _declaration_origins(self):
        """Les provenances à afficher, dans l'ordre de la fiche, chaque
        ingrédient une seule fois : [{'product': …, 'country': …}].

        Un ingrédient à déclarer dont le pays manque paraît QUAND MÊME,
        avec un pays vide : le trou doit se voir sur le papier, pas
        disparaître de la liste. Des dictionnaires plutôt que des
        couples — c'est le gabarit d'impression qui les lit, et
        `origine['country']` s'y relit mieux que `origine[1]`."""
        self.ensure_one()
        origines = []
        vus = set()
        for line in self.line_ids:
            produit = line.product_id
            if not produit.megga_origin_required or produit.id in vus:
                continue
            vus.add(produit.id)
            origines.append({
                'product': produit,
                'country': produit.megga_origin_country_id,
            })
        return origines
