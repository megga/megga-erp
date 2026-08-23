from odoo import _, api, fields, models

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
        help="Dans l'unité de mesure de l'ingrédient (pas de conversion "
             "d'unités dans cette version : 0.3 pour 300 g d'un article "
             "tenu en kg).")
    uom_id = fields.Many2one(
        related='product_id.uom_id', string="Unité")
    currency_id = fields.Many2one(related='recipe_id.currency_id')
    cost = fields.Monetary(
        "Coût", compute='_compute_cost', store=True,
        currency_field='currency_id')

    @api.depends('quantity', 'product_id.standard_price')
    def _compute_cost(self):
        for line in self:
            line.cost = line.quantity * line.product_id.standard_price
