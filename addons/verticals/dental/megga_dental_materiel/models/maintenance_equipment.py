from odoo import api, fields, models


class MaintenanceEquipment(models.Model):
    """Le matériel du cabinet, rattaché à son fauteuil.

    Tout le reste existe déjà dans `maintenance` : numéro de série,
    fournisseur et sa référence, modèle, date de mise en service, fin
    de garantie, coût, technicien responsable, équipe, historique des
    pannes, MTBF et MTTR. On n'en réécrit rien — le module a été écrit
    APRÈS avoir inventorié ces champs, et il n'ajoute que ce qui
    manquait vraiment.

    Ce qui manquait : le fauteuil. Un cabinet ne cherche pas
    « l'autoclave 3 », il cherche ce qu'il y a autour du fauteuil 2 —
    pour savoir ce qui s'arrête quand un appareil part en réparation.
    """
    _inherit = 'maintenance.equipment'

    # ondelete='restrict' : un fauteuil qui porte du matériel ne se
    # supprime plus. C'est la doctrine du dépôt pour tout référentiel
    # porteur d'histoire (les dossiers patients, les positions
    # tarifaires) : on n'efface pas, on archive.
    chair_id = fields.Many2one(
        'megga.dental.chair', string="Fauteuil",
        ondelete='restrict', index='btree_not_null',
        help="Le fauteuil ou la salle où cet appareil est installé. "
             "Facultatif : un compresseur de cave ne sert aucun "
             "fauteuil en particulier.")


class MeggaDentalChair(models.Model):
    """La fiche fauteuil montre son matériel."""
    _inherit = 'megga.dental.chair'

    equipment_ids = fields.One2many(
        'maintenance.equipment', 'chair_id', string="Matériel")
    equipment_count = fields.Integer(
        "Appareils", compute='_compute_equipment_count')

    @api.depends('equipment_ids')
    def _compute_equipment_count(self):
        # Compte en une requête, pas une par fauteuil. En `sudo` : le
        # NOMBRE d'appareils autour d'un fauteuil est de la logistique,
        # pas une donnée gardée — la lecture des équipements eux-mêmes
        # reste, elle, celle du cœur.
        groupes = self.env['maintenance.equipment'].sudo()._read_group(
            [('chair_id', 'in', self.ids)], ['chair_id'], ['__count'])
        par_fauteuil = {chair.id: nombre for chair, nombre in groupes}
        for chair in self:
            chair.equipment_count = par_fauteuil.get(chair.id, 0)

    def action_megga_open_equipment(self):
        """Le matériel de ce fauteuil, depuis sa fiche."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Matériel de %s", self.display_name),
            'res_model': 'maintenance.equipment',
            'view_mode': 'list,form',
            'domain': [('chair_id', '=', self.id)],
            'context': {'default_chair_id': self.id},
        }
