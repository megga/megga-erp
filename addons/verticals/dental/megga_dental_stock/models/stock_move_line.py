from odoo import _, fields, models
from odoo.exceptions import UserError


class StockMoveLine(models.Model):
    """Le périmé ne part plus vers les soins.

    LA garde métier du magasin dentaire. Elle vit dans le MODÈLE, pas
    dans la vue : un bouton masqué n'est pas une garde, et l'état
    change entre la lecture de l'écran et la validation du mouvement
    (un lot périme à minuit, la séance se clôt à 8h05).

    Point d'accrochage : `_action_done` de `stock.move.line`, appelé
    par `stock.move._action_done` sur les seules lignes réellement
    validées (les non-« picked » sont retirées avant). Une
    `@api.constrains` sur les champs d'état serait le piège : elle
    tirerait sur des brouillons en cours d'édition et manquerait les
    validations qui n'écrivent pas le champ surveillé.

    Le refus ne vise QUE la destination soins. Le rebut (usage
    `inventory`), le retour fournisseur et l'ajustement d'inventaire
    restent permis : un lot périmé doit pouvoir être détruit
    proprement, et l'interdire l'immobiliserait en rayon pour
    toujours.
    """
    _inherit = 'stock.move.line'

    def _action_done(self):
        self._megga_dental_refuse_expired()
        return super()._action_done()

    def _megga_dental_refuse_expired(self):
        """Refuse toute ligne qui enverrait un lot périmé en soins."""
        # Sortie immédiate du cas courant : cette surcharge est sur le
        # chemin de TOUS les mouvements de stock du système, y compris
        # ceux des autres verticales. Sans lot, rien à garder — un seul
        # accès groupé suffit à le savoir.
        if not self.lot_id:
            return
        # sudo : l'emplacement de consommation est de la CONFIGURATION,
        # pas une donnée métier. Le lire ne renseigne personne sur un
        # patient, et la garde doit tenir même pour un profil qui n'a
        # pas le référentiel des emplacements en lecture.
        care = self.env.ref(
            'megga_dental_stock.stock_location_dental_care',
            raise_if_not_found=False)
        if not care:
            return
        # parent_path (« 1/7/12/ ») porte la descendance : le test vaut
        # un `child_of` sans requête, et couvre un cabinet qui aurait
        # subdivisé l'emplacement de consommation. Jamais de préfixe
        # vide — il ferait correspondre TOUTES les destinations.
        prefix = care.sudo().parent_path or ''
        if not prefix:
            prefix = '%s/' % care.id
        for line in self:
            lot = line.lot_id
            if not lot or not lot.expiration_date:
                continue
            if line.product_uom_id.compare(line.quantity, 0) <= 0:
                continue
            destination = line.location_dest_id.sudo()
            if not destination or not (destination.parent_path or '').startswith(prefix):
                continue
            # product_expiry_alert : la date de péremption est atteinte,
            # comparée à l'heure du serveur par le cœur.
            if not lot.product_expiry_alert:
                continue
            raise UserError(_(
                "Le lot %(lot)s de %(produit)s est périmé depuis le "
                "%(date)s : il ne peut pas partir en soins.\n\n"
                "Sortez-le du rayon et détruisez-le proprement (rebut) — "
                "le rebut, lui, reste permis.",
                lot=lot.name,
                produit=line.product_id.display_name,
                date=fields.Datetime.context_timestamp(
                    lot, lot.expiration_date).strftime('%d.%m.%Y'),
            ))
