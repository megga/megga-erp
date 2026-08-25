from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MeggaDentalPositionSupply(models.Model):
    """Le kit de consommables d'une position tarifaire.

    C'est l'ACTE qui sait ce qu'il consomme, pas le praticien qui
    ressaisit au fauteuil : une obturation composite emporte sa
    seringue, ses compresses et sa paire de gants, une fois pour
    toutes. Le cabinet règle ses kits une fois ; les séances les
    décomptent toutes seules.

    C'est de la CONFIGURATION de cabinet, pas du clinique : les droits
    s'alignent sur ceux du tarif par points, dont ce modèle prolonge la
    fiche.
    """
    _name = 'megga.dental.position.supply'
    _description = "Consommable d'une position tarifaire"
    _order = 'position_id, sequence, id'

    position_id = fields.Many2one(
        'megga.dental.position', string="Position", required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product', string="Consommable", required=True,
        ondelete='restrict', index=True,
        help="Produit du magasin du cabinet, suivi en stock.")
    quantity = fields.Float(
        "Quantité par acte", default=1.0, required=True,
        help="Ce qu'un acte consomme. Deux actes de la même séance "
             "additionnent leurs besoins.")
    uom_id = fields.Many2one(
        'uom.uom', string="Unité",
        compute='_compute_uom_id', store=True, readonly=False,
        precompute=True)

    @api.depends('product_id')
    def _compute_uom_id(self):
        # L'unité de SAISIE : par défaut celle du produit, mais le
        # cabinet compte parfois autrement que l'économat (5 ml d'un
        # flacon au litre). Éditable, gardée par la contrainte.
        for supply in self:
            if supply.product_id:
                supply.uom_id = supply.product_id.uom_id

    @api.constrains('quantity')
    def _check_quantity(self):
        for supply in self:
            if supply.quantity <= 0:
                raise ValidationError(_(
                    "La quantité consommée par un acte doit être "
                    "strictement positive — un kit à zéro ne consomme "
                    "rien, autant retirer la ligne."))

    @api.constrains('product_id', 'uom_id')
    def _check_uom(self):
        """Une unité d'une autre grandeur ne se convertit pas : on ne
        décompte pas des grammes d'un article vendu à la pièce."""
        # _has_common_reference : l'API du cœur 19, où les unités
        # forment des arbres (parent_path) sans catégories —
        # convertible veut dire ancêtre commun.
        for supply in self:
            if not supply.uom_id or not supply.product_id:
                continue
            if not supply.uom_id._has_common_reference(
                    supply.product_id.uom_id):
                raise ValidationError(_(
                    "L'unité %(unite)s ne se convertit pas dans "
                    "l'unité de %(produit)s (%(reference)s).") % {
                        'unite': supply.uom_id.display_name,
                        'produit': supply.product_id.display_name,
                        'reference': supply.product_id.uom_id.display_name})

    def _megga_needed_quantity(self, acts):
        """Quantité consommée par `acts` actes, dans l'unité DU PRODUIT.

        Conversion sans arrondi (`round=False`) : arrondir ligne par
        ligne fausse les sommes — c'est la leçon des fiches techniques
        du restaurant, payée une fois. Le total, lui, sera arrondi par
        le mouvement de stock.
        """
        self.ensure_one()
        quantity = self.quantity * acts
        if self.uom_id and self.uom_id != self.product_id.uom_id:
            return self.uom_id._compute_quantity(
                quantity, self.product_id.uom_id, round=False)
        return quantity


class MeggaDentalPosition(models.Model):
    _inherit = 'megga.dental.position'

    supply_ids = fields.One2many(
        'megga.dental.position.supply', 'position_id',
        string="Consommables", copy=True)
