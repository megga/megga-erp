from odoo import _, models
from odoo.exceptions import UserError


class StockMoveLine(models.Model):
    """Un set d'un cycle non conforme ne part jamais en soins.

    Seconde garde du magasin dentaire, au MÊME point d'accrochage que
    la première (`_action_done`) et pour la même raison : un cycle peut
    devenir non conforme entre la préparation du plateau et la clôture
    de la séance — l'indicateur biologique revient le lendemain.

    Elle vise, comme l'autre, la seule destination soins : un set non
    conforme doit pouvoir être détruit proprement (rebut), sans quoi il
    resterait immobilisé en rayon pour toujours.
    """
    _inherit = 'stock.move.line'

    def _action_done(self):
        self._megga_dental_refuse_unsterile()
        return super()._action_done()

    def _megga_dental_refuse_unsterile(self):
        """Refuse toute ligne qui enverrait un set non stérile en soins."""
        # Sortie immédiate : cette surcharge est sur le chemin de TOUS
        # les mouvements du système, toutes verticales confondues.
        if not self.lot_id:
            return
        cycles = self.lot_id.sudo().sterilisation_cycle_id
        if not cycles:
            return
        care = self.env.ref(
            'megga_dental_stock.stock_location_dental_care',
            raise_if_not_found=False)
        if not care:
            return
        # parent_path porte la descendance : le test vaut un `child_of`
        # sans requête. Jamais de préfixe vide — il ferait correspondre
        # TOUTES les destinations. Leçon de la garde du chantier 1.
        prefix = care.sudo().parent_path or ''
        if not prefix:
            prefix = '%s/' % care.id
        for line in self:
            lot = line.lot_id
            if not lot or not lot.sudo().sterilisation_cycle_id:
                continue
            if line.product_uom_id.compare(line.quantity, 0) <= 0:
                continue
            destination = line.location_dest_id.sudo()
            if not destination or not (
                    destination.parent_path or '').startswith(prefix):
                continue
            motif = lot._megga_sterilisation_refused()
            if not motif:
                continue
            raise UserError(_(
                "Le set %(lot)s de %(produit)s ne peut pas partir en "
                "soins : %(motif)s.\n\n"
                "Sortez-le du rayon et repassez-le à l'autoclave — le "
                "rebut, lui, reste permis.",
                lot=lot.name,
                produit=line.product_id.display_name,
                motif=motif,
            ))
