from odoo import _, fields, models


class MeggaDentalTreatment(models.Model):
    """La preuve, dans l'autre sens : quels cycles ont servi la séance.

    C'est la question du patient, et celle de l'expert : « avec quoi
    m'a-t-on soigné ? ». Elle se répond depuis la séance, sans passer
    par le magasin.
    """
    _inherit = 'megga.dental.treatment'

    sterilisation_cycle_ids = fields.Many2many(
        'megga.dental.sterilisation.cycle', string="Cycles de stérilisation",
        compute='_compute_sterilisation_cycle_ids',
        help="Les charges d'autoclave dont sont sortis les sets "
             "consommés par cette séance.")

    def _compute_sterilisation_cycle_ids(self):
        """Remonte des lots consommés jusqu'aux cycles.

        Compute NON stocké : il n'est donc ni filtrable ni triable dans
        un domaine (leçon ORM du dépôt) — il s'affiche, on ne cherche
        pas dessus. Le sens inverse, lui, part du cycle et passe par
        une recherche vraie.

        En `sudo` sur le magasin : lire ses propres mouvements de
        consommation est de la logistique. Le praticien n'a aucun droit
        stock et doit pourtant pouvoir montrer la preuve.
        """
        Ligne = self.env['stock.move.line'].sudo()
        avec_transfert = self.filtered('supply_picking_id')
        (self - avec_transfert).sterilisation_cycle_ids = False
        if not avec_transfert:
            return
        lignes = Ligne.search([
            ('picking_id', 'in', avec_transfert.supply_picking_id.ids),
            ('state', '=', 'done'),
            ('lot_id.sterilisation_cycle_id', '!=', False),
        ])
        par_transfert = {}
        for ligne in lignes:
            par_transfert.setdefault(ligne.picking_id.id, set()).add(
                ligne.lot_id.sterilisation_cycle_id.id)
        for treatment in avec_transfert:
            treatment.sterilisation_cycle_ids = [(6, 0, list(
                par_transfert.get(treatment.supply_picking_id.id, [])))]


class StockWarehouse(models.Model):
    """Le type d'opération « Sortie de stérilisation ».

    Un type DÉDIÉ, comme la consommation en soins, et pour les mêmes
    raisons : le magasinier distingue au tableau de bord ce qui sort de
    l'autoclave de ce qui arrive du fournisseur, et la séquence porte
    son propre préfixe.

    Les deux cases de lots sont COCHÉES ici — c'est l'inverse exact de
    la consommation : une entrée de stérilisation crée des lots (le
    numéro de cycle) et les pose. Sans elles, le cœur refuserait la
    ligne de lot que la validation du cycle vient d'écrire.
    """
    _inherit = 'stock.warehouse'

    MEGGA_STERI_SEQUENCE_CODE = 'STERI'

    def _megga_dental_sterilisation_picking_type(self):
        """Le type d'opération de cet entrepôt, créé au premier besoin."""
        self.ensure_one()
        PickingType = self.env['stock.picking.type'].sudo()
        existing = PickingType.search([
            ('warehouse_id', '=', self.id),
            ('sequence_code', '=', self.MEGGA_STERI_SEQUENCE_CODE),
        ], limit=1)
        if existing:
            return existing
        source = self.env.ref(
            'megga_dental_sterilisation.stock_location_dental_sterilisation')
        # La séquence est créée par le cœur au `create` du type : pas de
        # séquence de data à maintenir ici.
        return PickingType.create({
            'name': _("Sortie de stérilisation"),
            'code': 'internal',
            'sequence_code': self.MEGGA_STERI_SEQUENCE_CODE,
            'warehouse_id': self.id,
            'company_id': self.company_id.id,
            'default_location_src_id': source.id,
            'default_location_dest_id': self.lot_stock_id.id,
            'use_create_lots': True,
            'use_existing_lots': True,
            'create_backorder': 'never',
        })
