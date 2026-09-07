from datetime import datetime, time

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.megga_resto.resto_logic import merge_needs

from ..ecart_logic import consommation_reelle, ecart, ecart_pct, perte, valorisation

# Les commandes REELLEMENT encaissees. Un brouillon n'a rien consomme,
# une annulation non plus.
ETATS_VENDUS = ('paid', 'done')


class MeggaRestoEcart(models.Model):
    """Le relevé d'écart matière d'une période.

    Il ne tient aucun stock : le restaurant compte au début et à la fin,
    saisit ses entrées, et le module confronte le résultat à ce que les
    fiches techniques disaient de la vente. C'est l'arithmétique que
    tout restaurateur trace déjà à la main — faite sur les vrais
    chiffres de la caisse.
    """
    _name = 'megga.resto.ecart'
    _description = "Relevé d'écart matière"
    _inherit = ['mail.thread']
    _order = 'date_stop desc, id desc'

    name = fields.Char(
        "Référence", readonly=True, copy=False, default='/')
    label = fields.Char(
        "Période", required=True,
        help="Septembre 2026, semaine 38, service du samedi…")
    date_start = fields.Date("Du", required=True)
    date_stop = fields.Date("Au", required=True)
    state = fields.Selection([
        ('draft', "Brouillon"),
        ('confirmed', "Arrêté"),
        ('cancelled', "Annulé"),
    ], string="État", default='draft', required=True, copy=False,
        tracking=True)
    line_ids = fields.One2many(
        'megga.resto.ecart.line', 'ecart_id', string="Ingrédients",
        copy=True)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    ecart_value_total = fields.Monetary(
        "Écart net", compute='_compute_totaux', store=True,
        currency_field='currency_id',
        help="La somme signée : les sous-consommations y compensent les "
             "pertes. À lire avec le total des pertes, jamais seul.")
    perte_total = fields.Monetary(
        "Pertes", compute='_compute_totaux', store=True,
        currency_field='currency_id',
        help="La somme des seuls écarts positifs — ce que la période a "
             "réellement coûté en matière non vendue.")
    note = fields.Text("Notes")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'megga.resto.ecart') or '/'
        return super().create(vals_list)

    @api.depends('label', 'date_start', 'date_stop')
    def _compute_display_name(self):
        for releve in self:
            releve.display_name = "%s — %s" % (
                releve.name, releve.label or "")

    @api.depends('line_ids.ecart_value')
    def _compute_totaux(self):
        for releve in self:
            valeurs = releve.line_ids.mapped('ecart_value')
            releve.ecart_value_total = sum(valeurs)
            releve.perte_total = sum(perte(v) for v in valeurs)

    @api.constrains('date_start', 'date_stop')
    def _check_periode(self):
        for releve in self:
            if releve.date_stop < releve.date_start:
                raise ValidationError(_(
                    "La période se termine avant de commencer : "
                    "du %(debut)s au %(fin)s.",
                    debut=releve.date_start, fin=releve.date_stop))

    def _pos_lines(self):
        """Les lignes de caisse de la période.

        Les bornes se calculent DANS LE FUSEAU DU RESTAURANT puis se
        convertissent en UTC. Minuit local n'est pas minuit UTC : une
        commande encaissée à 00h30 le samedi l'a été à 23h30 UTC le
        vendredi, et serait perdue par une comparaison de dates brutes.
        """
        self.ensure_one()
        tz = pytz.timezone(self.env.user.tz or 'Europe/Zurich')
        debut = tz.localize(
            datetime.combine(self.date_start, time.min)
        ).astimezone(pytz.utc).replace(tzinfo=None)
        fin = tz.localize(
            datetime.combine(self.date_stop, time.max)
        ).astimezone(pytz.utc).replace(tzinfo=None)
        return self.env['pos.order.line'].search([
            ('order_id.state', 'in', ETATS_VENDUS),
            ('order_id.date_order', '>=', debut),
            ('order_id.date_order', '<=', fin),
            ('order_id.company_id', '=', self.company_id.id),
        ])

    def _besoins_theoriques(self):
        """Ce que les plats vendus auraient dû consommer : chaque ligne
        de caisse, sa fiche technique, ses ingrédients convertis dans
        l'unité de l'article — round=False, la leçon des fiches :
        l'arrondi du cœur transformerait 1 g en 0.01 kg — puis agrégés.

        Un plat vendu sans fiche technique ne peut rien dire : il est
        ignoré ici, et compté à part pour être signalé.
        """
        self.ensure_one()
        Recipe = self.env['megga.resto.recipe']
        besoins = []
        produits = {}
        sans_fiche = self.env['product.product']
        for ligne in self._pos_lines():
            recette = Recipe.search(
                [('product_id', '=', ligne.product_id.id)], limit=1)
            if not recette:
                sans_fiche |= ligne.product_id
                continue
            for ing in recette.line_ids:
                qty_base = ing.uom_id._compute_quantity(
                    ing.quantity, ing.product_id.uom_id, round=False)
                produits[ing.product_id.id] = ing.product_id
                besoins.append((ing.product_id.id, qty_base * ligne.qty))
        return merge_needs(besoins), produits, sans_fiche

    def action_calculer(self):
        """(Re)calcule la consommation théorique depuis la caisse.

        NE TOUCHE JAMAIS aux comptages saisis à la main : seule la
        colonne théorique est réécrite. Un chef qui a passé sa soirée à
        compter ses stocks ne doit pas les perdre parce qu'il relance le
        calcul.
        """
        Line = self.env['megga.resto.ecart.line']
        for releve in self:
            if releve.state != 'draft':
                raise UserError(_(
                    "Le relevé %s est arrêté — ses chiffres ne bougent "
                    "plus.") % releve.name)
            totaux, produits, sans_fiche = releve._besoins_theoriques()
            attendus = dict(totaux)
            existantes = {l.product_id.id: l for l in releve.line_ids}
            for pid, qty in totaux:
                if pid in existantes:
                    existantes[pid].write({
                        'theorique': qty,
                        'cost_unit': produits[pid].standard_price,
                    })
                else:
                    Line.create({
                        'ecart_id': releve.id,
                        'product_id': pid,
                        'theorique': qty,
                        'cost_unit': produits[pid].standard_price,
                    })
            # Un ingredient releve a la main mais qu'aucune vente
            # n'appelle : sa theorique retombe a zero, elle ne reste pas
            # sur la valeur d'un calcul precedent.
            for pid, ligne in existantes.items():
                if pid not in attendus:
                    ligne.theorique = 0.0
            if sans_fiche:
                releve.message_post(body=_(
                    "Plats vendus sans fiche technique, donc absents de "
                    "la consommation théorique : %s.") % ", ".join(
                        sans_fiche.mapped('display_name')))
        return True

    def action_confirm(self):
        for releve in self:
            if releve.state != 'draft':
                raise UserError(_("Seul un brouillon peut être arrêté."))
            if not releve.line_ids:
                raise UserError(_(
                    "Rien à arrêter : lancez le calcul, ou saisissez au "
                    "moins un ingrédient."))
            releve.state = 'confirmed'

    def action_cancel(self):
        for releve in self:
            if releve.state == 'cancelled':
                raise UserError(_("Ce relevé est déjà annulé."))
            releve.state = 'cancelled'

    def action_draft(self):
        for releve in self:
            if releve.state != 'cancelled':
                raise UserError(_(
                    "Seul un relevé annulé revient en brouillon."))
            releve.state = 'draft'


class MeggaRestoEcartLine(models.Model):
    """Un ingrédient du relevé : ce que l'inventaire dit, ce que les
    fiches disaient, et la différence."""
    _name = 'megga.resto.ecart.line'
    _description = "Ingrédient d'un relevé d'écart"
    # Les plus grosses pertes en tete : c'est l'ordre dans lequel on lit
    # un releve d'ecart, jamais l'ordre alphabetique.
    _order = 'ecart_value desc, id'

    ecart_id = fields.Many2one(
        'megga.resto.ecart', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string="Ingrédient", required=True)
    uom_id = fields.Many2one(related='product_id.uom_id', string="Unité")
    currency_id = fields.Many2one(related='ecart_id.currency_id')

    stock_initial = fields.Float("Stock de départ", digits=(12, 3))
    achats = fields.Float(
        "Entrées", digits=(12, 3),
        help="Ce qui est entré pendant la période : livraisons, "
             "transferts, retours.")
    stock_final = fields.Float("Stock de fin", digits=(12, 3))

    # NON calculee : c'est une MESURE, prise a un instant donne. La
    # recalculer silencieusement parce qu'une fiche a change ensuite
    # falsifierait un releve deja arrete.
    theorique = fields.Float(
        "Consommation théorique", digits=(12, 3), readonly=True,
        help="Ce que les plats vendus auraient dû consommer, d'après "
             "les fiches techniques au moment du calcul.")
    cost_unit = fields.Float(
        "Prix de revient", digits='Product Price', readonly=True,
        help="Le prix de revient de l'ingrédient au moment du calcul.")

    reelle = fields.Float(
        "Consommation réelle", compute='_compute_ecart', store=True,
        digits=(12, 3))
    ecart_qty = fields.Float(
        "Écart", compute='_compute_ecart', store=True, digits=(12, 3),
        help="Positif : consommé en plus que la théorie — une perte.")
    ecart_pct = fields.Float(
        "Écart (%)", compute='_compute_ecart', store=True)
    ecart_value = fields.Monetary(
        "Écart valorisé", compute='_compute_ecart', store=True,
        currency_field='currency_id')

    @api.depends('stock_initial', 'achats', 'stock_final', 'theorique',
                 'cost_unit')
    def _compute_ecart(self):
        for ligne in self:
            reelle = consommation_reelle(
                ligne.stock_initial, ligne.achats, ligne.stock_final)
            ligne.reelle = reelle
            ligne.ecart_qty = ecart(reelle, ligne.theorique)
            ligne.ecart_pct = ecart_pct(reelle, ligne.theorique) or 0.0
            ligne.ecart_value = valorisation(
                ligne.ecart_qty, ligne.cost_unit)

    _produit_uniq = models.Constraint(
        'unique(ecart_id, product_id)',
        "Cet ingrédient figure déjà sur le relevé.")
