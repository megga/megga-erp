from odoo import _, fields, models


class StockLot(models.Model):
    """Le sachet stérilisé porte son cycle.

    C'est tout le lien, et il suffit : le lot existe déjà pour la
    traçabilité, la péremption et le FEFO. On lui accroche le numéro de
    charge — l'étiquette du sachet, faite modèle.
    """
    _inherit = 'stock.lot'

    sterilisation_cycle_id = fields.Many2one(
        'megga.dental.sterilisation.cycle', string="Cycle de stérilisation",
        readonly=True, ondelete='restrict', index='btree_not_null',
        help="La charge d'autoclave d'où ce sachet est sorti.")
    sterilisation_line_id = fields.Many2one(
        'megga.dental.sterilisation.line', string="Ligne de charge",
        readonly=True, ondelete='set null', index='btree_not_null',
        help="La ligne de charge d'où ce sachet est sorti. C'est ce "
             "lien — et non le NOM du lot — qui relie la ligne à sa "
             "date de stérilité : déduire le lot de son nom rendait "
             "l'affichage faux dès qu'une charge changeait de "
             "composition.")
    sterilisation_state = fields.Selection(
        related='sterilisation_cycle_id.state', readonly=True,
        string="État du cycle")

    def _megga_sterilisation_refused(self):
        """Le motif qui interdit ce lot en soins, ou une chaîne vide.

        En `sudo` : l'état d'un cycle est une donnée de conformité, pas
        un dossier de patient. La garde doit tenir même pour un
        magasinier qui n'a aucun droit sur le registre de stérilisation
        — sans quoi elle ne garderait que ceux qui la connaissent.
        """
        self.ensure_one()
        cycle = self.sudo().sterilisation_cycle_id
        if not cycle:
            return ''
        if cycle.state == 'done':
            return ''
        if cycle.state == 'failed':
            return _(
                "le cycle %(cycle)s a été marqué NON CONFORME",
                cycle=cycle.name)
        return _(
            "le cycle %(cycle)s n'est pas validé", cycle=cycle.name)
