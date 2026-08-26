from odoo import fields, models


class StockMove(models.Model):
    """Le mouvement se souvient de la ligne de charge qui l'a créé.

    Sans ce lien, il n'y en avait aucun : `_megga_enter_stock` appariait
    les mouvements aux lignes PAR POSITION, après `action_confirm`. Or le
    cœur FUSIONNE les mouvements confirmés qui partagent produit,
    emplacements et unité (`_merge_moves`) — deux lignes du même set dans
    une charge donnaient donc un seul mouvement, le `zip` en perdait une,
    et des sachets n'entraient jamais en rayon. En silence.

    Le champ sert deux fois : il porte le lien, et il empêche la fusion
    (il est ajouté aux champs distinctifs du cœur), ce qui garde une
    ligne de charge = un mouvement = un lot.
    """
    _inherit = 'stock.move'

    sterilisation_line_id = fields.Many2one(
        'megga.dental.sterilisation.line', string="Ligne de charge",
        readonly=True, ondelete='set null', index='btree_not_null',
        help="La ligne de charge de stérilisation d'où vient ce "
             "mouvement d'entrée.")

    def _prepare_merge_moves_distinct_fields(self):
        """Deux lignes de charge ne se fondent pas en un mouvement.

        Point d'extension prévu par le cœur pour exactement ce cas.
        """
        return super()._prepare_merge_moves_distinct_fields() + [
            'sterilisation_line_id']
