from odoo import models


class StockWarehouse(models.Model):
    """Le type d'opération « Consommation en soins ».

    Un type DÉDIÉ, pas la livraison client de l'entrepôt : deux raisons,
    et la seconde est structurante.

    D'abord la lisibilité — le magasinier distingue au tableau de bord
    ce qui part au fauteuil de ce qui part chez un client, et la
    séquence porte son propre préfixe.

    Ensuite la traçabilité dégradée, qui est un CHOIX du produit : les
    deux cases de lots sont décochées (`use_create_lots` et
    `use_existing_lots`). C'est la seule configuration où le cœur laisse
    valider un mouvement de produit tracé SANS lot — vérifié dans
    `stock.move.line._action_done` : « If the user disabled both
    checkboxes […] he's allowed to enter tracked products without a
    lot_id ». Sans elle, une séance close alors qu'il ne reste aucun lot
    servable planterait sur « You need to supply a Lot/Serial Number » :
    le magasin bloquerait la clinique, exactement ce que le produit
    refuse. La réservation FEFO, elle, continue de poser les lots — elle
    les tient des quants, pas du type d'opération.

    Le reliquat est désactivé (`create_backorder='never'`) : une
    consommation constate ce qui a été utilisé, elle ne laisse pas une
    commande à servir plus tard.
    """
    _inherit = 'stock.warehouse'

    MEGGA_CARE_SEQUENCE_CODE = 'SOINS'

    def _megga_dental_care_picking_type(self):
        """Le type d'opération de cet entrepôt, créé au premier besoin."""
        self.ensure_one()
        PickingType = self.env['stock.picking.type'].sudo()
        existing = PickingType.search([
            ('warehouse_id', '=', self.id),
            ('sequence_code', '=', self.MEGGA_CARE_SEQUENCE_CODE),
        ], limit=1)
        if existing:
            return existing
        care = self.env.ref(
            'megga_dental_stock.stock_location_dental_care')
        # La séquence est créée par le cœur au `create` du type
        # (stock.picking.type.create la pose quand elle manque) : pas de
        # séquence de data à maintenir ici.
        return PickingType.create({
            'name': "Consommation en soins",
            'code': 'internal',
            'sequence_code': self.MEGGA_CARE_SEQUENCE_CODE,
            'warehouse_id': self.id,
            'company_id': self.company_id.id,
            'default_location_src_id': self.lot_stock_id.id,
            'default_location_dest_id': care.id,
            'use_create_lots': False,
            'use_existing_lots': False,
            'create_backorder': 'never',
        })
