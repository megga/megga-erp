from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..resto_logic import merge_needs


class MeggaRestoProduction(models.Model):
    """Une production de cuisine : un banquet, un service, une journée —
    des plats à fiche technique multipliés par des portions. La liste de
    courses en découle : ingrédients agrégés multi-plats, convertis dans
    l'unité de l'économat (celle de l'article), coût prévisionnel. C'est
    l'outil que le chef emporte au marché."""
    _name = 'megga.resto.production'
    _description = "Production de cuisine"
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(
        "Référence", readonly=True, copy=False, default='/')
    label = fields.Char(
        "Occasion", required=True,
        help="Banquet Dupont, service du samedi soir, semaine 38…")
    date = fields.Date(
        "Date de production", required=True,
        default=fields.Date.context_today)
    state = fields.Selection([
        ('draft', "Brouillon"),
        ('confirmed', "Confirmée"),
        ('done', "Produite"),
        ('cancelled', "Annulée"),
    ], string="État", default='draft', required=True, copy=False,
        tracking=True)
    line_ids = fields.One2many(
        'megga.resto.production.line', 'production_id',
        string="Plats", copy=True)
    shopping_ids = fields.One2many(
        'megga.resto.shopping.line', 'production_id',
        string="Liste de courses", readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    cost_total = fields.Monetary(
        "Coût matière prévu", compute='_compute_cost_total', store=True,
        currency_field='currency_id')
    note = fields.Text("Notes")

    @api.depends('shopping_ids.cost')
    def _compute_cost_total(self):
        for production in self:
            production.cost_total = sum(
                production.shopping_ids.mapped('cost'))

    @api.depends('label', 'date')
    def _compute_display_name(self):
        for production in self:
            production.display_name = "%s — %s" % (
                production.name, production.label or "")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'megga.resto.production') or '/'
        return super().create(vals_list)

    def _build_shopping(self):
        """(Re)construit la liste de courses : chaque ingrédient de
        chaque fiche, converti dans l'unité de l'article (celle de
        l'économat — round=False, leçon des fiches : l'arrondi du cœur
        transformerait 1 g en 0.01 kg), multiplié par les portions,
        agrégé par ingrédient. Le coût s'évalue sur la quantité agrégée
        au prix de revient du jour."""
        Shopping = self.env['megga.resto.shopping.line']
        for production in self:
            if not production.line_ids:
                raise UserError(_(
                    "Ajoutez au moins un plat avant de calculer la "
                    "liste de courses."))
            sans_fiche = production.line_ids.filtered(
                lambda l: not l.recipe_id)
            if sans_fiche:
                raise UserError(_(
                    "Aucune fiche technique pour %s — créez-la d'abord "
                    "(Restaurant ▸ Fiches techniques).") % ", ".join(
                        sans_fiche.mapped('product_id.display_name')))
            production.shopping_ids.unlink()
            produits = {}
            besoins = []
            for line in production.line_ids:
                for ing in line.recipe_id.line_ids:
                    qty_base = ing.uom_id._compute_quantity(
                        ing.quantity, ing.product_id.uom_id, round=False)
                    produits[ing.product_id.id] = ing.product_id
                    besoins.append(
                        (ing.product_id.id, qty_base * line.portions))
            Shopping.create([{
                'production_id': production.id,
                'product_id': pid,
                'quantity': qty,
                'cost': qty * produits[pid].standard_price,
            } for pid, qty in merge_needs(besoins)])

    def action_refresh_shopping(self):
        for production in self:
            if production.state == 'done':
                raise UserError(_(
                    "Le marché est fait — la liste d'une production "
                    "produite ne bouge plus."))
            if production.state == 'cancelled':
                raise UserError(_(
                    "Cette production est annulée."))
        self._build_shopping()
        return True

    def action_confirm(self):
        for production in self:
            if production.state != 'draft':
                raise UserError(_(
                    "Seul un brouillon peut être confirmé."))
            production._build_shopping()
            production.state = 'confirmed'

    def action_done(self):
        for production in self:
            if production.state != 'confirmed':
                raise UserError(_(
                    "Seule une production confirmée peut être soldée."))
            production.state = 'done'

    def action_cancel(self):
        for production in self:
            if production.state == 'done':
                raise UserError(_(
                    "Une production produite ne s'annule plus."))
            production.state = 'cancelled'

    def action_draft(self):
        for production in self:
            if production.state != 'cancelled':
                raise UserError(_(
                    "Seule une production annulée revient en brouillon."))
            production.state = 'draft'

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft_or_cancelled(self):
        for production in self:
            if production.state in ('confirmed', 'done'):
                raise UserError(_(
                    "La production %s est engagée — annulez-la au lieu "
                    "de la supprimer.") % production.name)


class MeggaRestoProductionLine(models.Model):
    _name = 'megga.resto.production.line'
    _description = "Plat d'une production"
    _order = 'production_id, sequence, id'

    production_id = fields.Many2one(
        'megga.resto.production', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product', string="Plat", required=True)
    recipe_id = fields.Many2one(
        'megga.resto.recipe', string="Fiche technique",
        compute='_compute_recipe_id',
        help="La fiche du plat — sans elle, pas de liste de courses.")
    portions = fields.Float("Portions", required=True, default=10.0)
    currency_id = fields.Many2one(related='production_id.currency_id')
    cost_portion = fields.Monetary(
        related='recipe_id.cost_total', string="Coût / portion",
        currency_field='currency_id')
    # NON stocké, à dessein : un sous-total stocké dépendant de
    # recipe_id.cost_total exigerait d'inverser la dépendance en SQL —
    # impossible à travers recipe_id, compute non stocké (vécu : le
    # recalcul du coût d'une fiche plantait alors TOUTE création de
    # ligne de fiche). Le chiffre engagé vit dans la liste de courses,
    # elle stockée.
    subtotal = fields.Monetary(
        "Coût prévu", compute='_compute_subtotal',
        currency_field='currency_id')

    @api.constrains('portions')
    def _check_portions(self):
        for line in self:
            if line.portions <= 0:
                raise ValidationError(_(
                    "Le nombre de portions doit être strictement "
                    "positif."))

    @api.depends('product_id')
    def _compute_recipe_id(self):
        Recipe = self.env['megga.resto.recipe']
        for line in self:
            line.recipe_id = Recipe.search(
                [('product_id', '=', line.product_id.id)], limit=1) \
                if line.product_id else False

    @api.depends('portions', 'recipe_id.cost_total')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.portions * line.recipe_id.cost_total


class MeggaRestoShoppingLine(models.Model):
    """Une ligne de la liste de courses : l'ingrédient agrégé sur toute
    la production, dans l'unité de l'article (celle de l'économat)."""
    _name = 'megga.resto.shopping.line'
    _description = "Ligne de liste de courses"
    _order = 'production_id, id'

    production_id = fields.Many2one(
        'megga.resto.production', required=True, ondelete='cascade',
        index=True)
    product_id = fields.Many2one(
        'product.product', string="Ingrédient", required=True)
    quantity = fields.Float("Quantité", digits=(12, 3))
    uom_id = fields.Many2one(related='product_id.uom_id', string="Unité")
    currency_id = fields.Many2one(related='production_id.currency_id')
    cost = fields.Monetary("Coût prévu", currency_field='currency_id')
