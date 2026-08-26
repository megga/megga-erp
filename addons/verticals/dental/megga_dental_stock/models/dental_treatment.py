from odoo import _, api, fields, models
from odoo.tools.mail import plaintext2html

from ..dental_stock_logic import merge_needs


class MeggaDentalTreatment(models.Model):
    """La consommation part à la clôture de la séance.

    Le soin est fait : le magasin le CONSTATE. Il n'interdit rien, il ne
    ralentit rien, et il ne raconte pas ce qui s'est passé au fauteuil.
    """
    _inherit = 'megga.dental.treatment'

    supply_picking_id = fields.Many2one(
        'stock.picking', string="Consommation", readonly=True, copy=False,
        help="Le mouvement de stock engendré par la clôture de cette "
             "séance. Sa présence interdit un second décompte.")
    supply_done = fields.Boolean(
        "Consommables décomptés", compute='_compute_supply_done')

    @api.depends('supply_picking_id')
    def _compute_supply_done(self):
        for treatment in self:
            treatment.supply_done = bool(treatment.supply_picking_id)

    def action_done(self):
        """La clôture clinique reste souveraine : `super()` d'abord."""
        res = super().action_done()
        self._consume_supplies()
        return res

    def _consume_supplies(self):
        """Décompte du magasin ce que les actes de la séance ont mangé.

        En `sudo` : c'est un effet SYSTÈME du flux, exactement comme
        `_create_tooth_records` du module dentaire. La réception peut
        clore une séance sans détenir le moindre droit sur le magasin —
        et elle n'en gagne aucun pour autant : la LECTURE reste gardée
        par les groupes stock du cœur.

        Quatre règles portent cette méthode, et chacune a son test :

        1. JAMAIS DEUX FOIS. La garde d'état de `action_done` (qui
           refuse tout état autre que « planifié ») donne l'idempotence
           de premier rang ; le lien vers le picking est la ceinture,
           pour l'appel direct. Marquage par IDENTITÉ, pas par valeur.
        2. LE STOCK NE BLOQUE JAMAIS LA CLINIQUE. Rien en rayon ? La
           consommation part quand même — le quant passe en négatif — et
           une activité signale l'écart au magasin. Le soin est fait.
        3. LE PÉRIMÉ NE SORT PAS. Le cœur écarte de la réservation les
           lots dont la date de retrait est passée — mais SEULEMENT si
           le produit coche « utiliser la date de péremption »
           (contexte `with_expiration`). Décochez-la après coup, et un
           lot daté redevient réservable : la garde du magasin
           refuserait la sortie et la séance planterait. D'où la
           ceinture, qui retire le périmé avant la validation (un test
           dédié la prouve : il tombe dès qu'on l'enlève). Plus rien de
           servable ? La ligne part SANS lot (traçabilité dégradée,
           jamais bloquante) et la même activité le dit.
        4. LE MAGASIN NE RACONTE PAS LES SOINS (nLPD). Le mouvement
           porte la RÉFÉRENCE de la séance, jamais le diagnostic, jamais
           le détail des actes, jamais le patient. Un magasinier qui lit
           les mouvements ne lit pas le dossier médical.
        """
        Picking = self.env['stock.picking'].sudo()
        Warehouse = self.env['stock.warehouse'].sudo()
        for treatment in self:
            # 1. Ceinture d'idempotence.
            if treatment.supply_picking_id:
                continue
            needs = treatment.sudo()._megga_supply_needs()
            if not needs:
                # Pas de coquille vide : une séance sans kit ne crée
                # aucun mouvement.
                continue
            warehouse = Warehouse.search(
                [('company_id', '=', treatment.company_id.id)], limit=1)
            if not warehouse:
                continue
            picking_type = warehouse._megga_dental_care_picking_type()
            source = picking_type.default_location_src_id
            destination = picking_type.default_location_dest_id
            picking = Picking.create({
                'picking_type_id': picking_type.id,
                'location_id': source.id,
                'location_dest_id': destination.id,
                'company_id': treatment.company_id.id,
                # nLPD : la référence de la séance, et rien d'autre.
                # Pas de partner_id — ce serait nommer le patient.
                'origin': treatment.name,
                'move_ids': [(0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': quantity,
                    'product_uom': product.uom_id.id,
                    'location_id': source.id,
                    'location_dest_id': destination.id,
                }) for product, quantity in needs],
            })
            picking.action_confirm()
            picking.action_assign()
            picking._megga_serve_from_stock()
            picking.with_context(
                skip_backorder=True, skip_expired=True).button_validate()
            treatment.supply_picking_id = picking.id

    def _megga_supply_needs(self):
        """Les besoins de la séance : [(produit, quantité)], agrégés.

        Deux actes qui partagent un consommable font une seule ligne :
        c'est `merge_needs` (logique pure, testée sans ORM) qui le
        garantit, et l'ordre d'apparition des actes est préservé.
        """
        self.ensure_one()
        needs = []
        produits = {}
        for line in self.line_ids:
            for supply in line.position_id.supply_ids:
                product = supply.product_id
                if not product.is_storable:
                    # Un consommable non suivi en stock n'a rien à
                    # décompter : le kit peut porter un service.
                    continue
                produits[product.id] = product
                needs.append(
                    (product.id, supply._megga_needed_quantity(line.quantity)))
        # Un besoin NUL ne fait pas de mouvement : un acte saisi à zéro
        # (ça arrive) produirait sinon un transfert à quantité nulle,
        # que le cœur refuse de valider — et la séance ne se clôturerait
        # plus. Le magasin ne bloque jamais la clinique, y compris sur
        # une saisie bizarre.
        return [(produits[pid], qty) for pid, qty in merge_needs(needs)
                if produits[pid].uom_id.compare(qty, 0) > 0]


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _megga_serve_from_stock(self):
        """Sert ce qui peut l'être, constate le reste, ne bloque rien.

        Appelée sur un transfert de consommation déjà réservé. Elle
        écarte les lots périmés qui auraient échappé au cœur, complète
        le manque par une ligne sans lot, et marque le tout comme fait :
        la consommation est un fait accompli, pas un brouillon à
        oublier.
        """
        self.ensure_one()
        alerte = []
        for move in self.move_ids:
            for lignes, motif in self._megga_unservable_lines(move):
                lignes = lignes.exists()
                if not lignes:
                    continue
                alerte.append(motif)
                lignes.unlink()
            manque = move.product_uom_qty - move.quantity
            if move.product_uom.compare(manque, 0) > 0:
                # Rien de servable en rayon : on sort quand même. Le
                # quant passe en négatif, le magasin verra l'écart.
                self.env['stock.move.line'].sudo().create({
                    'move_id': move.id,
                    'picking_id': self.id,
                    'product_id': move.product_id.id,
                    'product_uom_id': move.product_uom.id,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                    'quantity': manque,
                })
                alerte.append(_(
                    "%(produit)s : %(manque)s %(unite)s sortie(s) sans "
                    "lot — stock insuffisant ou plus rien de servable.") % {
                        'produit': move.product_id.display_name,
                        'manque': move.product_uom.round(manque),
                        'unite': move.product_uom.name})
            move.picked = True
        if alerte:
            self._megga_flag_supply_gap(alerte)

    def _megga_unservable_lines(self, move):
        """Ce que le cabinet ne peut PAS servir sur ce mouvement, et pourquoi.

        Rend une liste de `(lignes, motif)`. Les lignes sont retirées
        de la réservation avant validation, et le manque repart sans
        lot : c'est la ceinture qui fait que LE STOCK NE BLOQUE JAMAIS
        LA CLINIQUE. Sans elle, une garde du magasin refuserait la
        sortie depuis `_action_done` et la séance ne se clôturerait
        plus — la garde tirerait sur le soin au lieu de tirer sur le
        magasin.

        POINT D'EXTENSION : chaque module du magasin y ajoute ses
        refus. Toute garde ajoutée sur `stock.move.line._action_done`
        DOIT avoir sa contrepartie ici, sans quoi elle bloque la
        clinique — c'est la leçon du chantier 5, qui l'avait oubliée.
        """
        perimes = move.move_line_ids.filtered(
            lambda ml: ml.lot_id.product_expiry_alert)
        if not perimes:
            return []
        return [(perimes, _(
            "%(produit)s : %(lots)s écarté(s), périmé(s).") % {
                'produit': move.product_id.display_name,
                'lots': ", ".join(perimes.mapped('lot_id.name'))})]

    def _megga_flag_supply_gap(self, motifs):
        """Signale l'écart au magasin — pas à la clinique.

        L'activité vit sur le TRANSFERT, pas sur la séance : c'est le
        responsable du magasin qui doit réagir (recompter, commander,
        détruire un périmé), et lui n'a aucun accès au dentaire. Le
        destinataire suit le patron du cœur (`product_expiry`) : le
        responsable du produit, à défaut le super-utilisateur.
        """
        self.ensure_one()
        responsable = self.move_ids.product_id.responsible_id[:1]
        # La note d'activité est du HTML : un texte brut y perdrait ses
        # retours à la ligne (et ses esperluettes). plaintext2html —
        # même leçon que les corps de chatter du socle.
        note = _("La séance %(origine)s a été close alors que le "
                 "magasin ne pouvait pas la servir complètement :\n"
                 "%(motifs)s\n\n"
                 "Le soin est fait, le stock le constate — vérifiez "
                 "les quantités en rayon.") % {
                     'origine': self.origin or self.name,
                     'motifs': "\n".join("- %s" % m for m in motifs)}
        self.sudo().activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=responsable.id or self.env.ref('base.user_root').id,
            summary=_("Écart de consommation au fauteuil"),
            note=plaintext2html(note))
