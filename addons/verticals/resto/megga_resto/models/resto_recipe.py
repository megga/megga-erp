from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..resto_logic import food_cost_pct, margin, margin_pct


class MeggaRestoRecipe(models.Model):
    """Fiche technique d'un plat : les ingrédients d'une portion, leur
    coût (prix de revient des articles), et ce que cela donne face au
    prix de carte — coût matière (food cost) et marge brute. Le nerf de
    la guerre d'un restaurant, absent du cœur Community."""
    _name = 'megga.resto.recipe'
    _description = "Fiche technique (coût matière)"
    _rec_name = 'product_id'
    _order = 'product_id'

    product_id = fields.Many2one(
        'product.product', string="Plat (article vendu)", required=True,
        index=True)
    line_ids = fields.One2many(
        'megga.resto.recipe.line', 'recipe_id',
        string="Ingrédients (par portion)", copy=True)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    cost_total = fields.Monetary(
        "Coût matière / portion", compute='_compute_cost_total', store=True,
        currency_field='currency_id')
    sale_price = fields.Float(
        related='product_id.list_price', string="Prix de carte")
    margin = fields.Monetary(
        "Marge brute", compute='_compute_ratios',
        currency_field='currency_id')
    margin_pct = fields.Float("Marge (%)", compute='_compute_ratios')
    food_cost = fields.Float(
        "Coût matière (%)", compute='_compute_ratios')
    notes = fields.Text("Progression, dressage, allergènes…")

    _product_uniq = models.Constraint(
        'unique(product_id)', "Ce plat a déjà une fiche technique.")

    @api.depends('line_ids.cost')
    def _compute_cost_total(self):
        for recipe in self:
            recipe.cost_total = sum(recipe.line_ids.mapped('cost'))

    @api.depends('cost_total', 'product_id.list_price')
    def _compute_ratios(self):
        for recipe in self:
            price = recipe.product_id.list_price
            recipe.margin = margin(recipe.cost_total, price)
            recipe.margin_pct = margin_pct(recipe.cost_total, price) or 0.0
            recipe.food_cost = food_cost_pct(recipe.cost_total, price) or 0.0

    def action_apply_cost(self):
        """Reporte le coût matière calculé comme prix de revient de
        l'article vendu — les marges du POS et de la comptabilité
        analytique repartent alors du même chiffre que la fiche."""
        for recipe in self:
            recipe.product_id.standard_price = recipe.cost_total
        return True


class MeggaRestoRecipeLine(models.Model):
    _name = 'megga.resto.recipe.line'
    _description = "Ingrédient de fiche technique"
    _order = 'recipe_id, sequence, id'

    recipe_id = fields.Many2one(
        'megga.resto.recipe', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product', string="Ingrédient", required=True)
    quantity = fields.Float(
        "Quantité", required=True, default=1.0,
        help="Dans l'unité de la ligne : 200 g d'un article tenu en kg "
             "se saisit 200 + g, le coût est converti.")
    # L'unité de SAISIE : par défaut celle de l'ingrédient, mais la
    # cuisine pèse en grammes ce que l'économat achète en kilos. Seules
    # les unités convertibles sont offertes — en 19, les unités forment
    # des arbres (relative_uom_id) sans catégories : convertible veut
    # dire même racine.
    uom_id = fields.Many2one(
        'uom.uom', string="Unité", required=True,
        compute='_compute_uom_id', store=True, readonly=False,
        precompute=True, ondelete='restrict',
        domain="[('id', 'in', allowed_uom_ids)]")
    allowed_uom_ids = fields.Many2many(
        'uom.uom', compute='_compute_allowed_uom_ids')
    currency_id = fields.Many2one(related='recipe_id.currency_id')
    cost = fields.Monetary(
        "Coût", compute='_compute_cost', store=True,
        currency_field='currency_id')

    @api.model
    def _uom_root(self, uom):
        """Racine de l'arbre d'unités (kg et g partagent la leur, pas
        le litre) : c'est le critère de convertibilité du cœur 19."""
        while uom.relative_uom_id:
            uom = uom.relative_uom_id
        return uom

    @api.constrains('product_id', 'uom_id')
    def _check_uom_convertible(self):
        for line in self:
            product_uom = line.product_id.uom_id
            if line.uom_id and product_uom and \
                    self._uom_root(line.uom_id) != self._uom_root(product_uom):
                raise ValidationError(_(
                    "« %(uom)s » n'est pas convertible en « %(puom)s », "
                    "l'unité de l'ingrédient %(product)s.",
                    uom=line.uom_id.name, puom=product_uom.name,
                    product=line.product_id.display_name))

    @api.depends('product_id')
    def _compute_uom_id(self):
        for line in self:
            if line.product_id:
                line.uom_id = line.product_id.uom_id

    @api.depends('product_id.uom_id')
    def _compute_allowed_uom_ids(self):
        Uom = self.env['uom.uom']
        for line in self:
            if line.product_id:
                root = self._uom_root(line.product_id.uom_id)
                line.allowed_uom_ids = Uom.search(
                    [('id', 'child_of', root.id)])
            else:
                line.allowed_uom_ids = Uom.search([])

    @api.depends('quantity', 'uom_id', 'product_id.uom_id',
                 'product_id.standard_price')
    def _compute_cost(self):
        for line in self:
            # round=False : l'arrondi par défaut du cœur (à l'arrondi de
            # l'unité CIBLE, vers le haut) transformerait 1 g en 0.01 kg
            # — un coût multiplié par dix.
            qty = line.uom_id._compute_quantity(
                line.quantity, line.product_id.uom_id, round=False)
            line.cost = qty * line.product_id.standard_price
