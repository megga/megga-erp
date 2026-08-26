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
        """Le compte, avec les droits du lecteur — jamais en `sudo`.

        Un compteur doit dire la même chose que l'écran qu'il ouvre.
        En `sudo`, il traverse les règles du cœur : celle qui borne un
        employé aux équipements qu'il suit, et surtout la règle
        MULTI-SOCIÉTÉ (`maintenance_equipment_comp_rule`). Le fauteuil,
        lui, n'a pas de société : un cabinet à deux sociétés aurait vu
        « 5 appareils » sur un onglet qui n'en montre que 3.

        Le bouton et l'onglet sont réservés au gestionnaire
        d'équipements ; pour lui, la règle du cœur ne filtre rien
        d'autre que la société — c'est-à-dire exactement ce qu'il doit
        voir.
        """
        # Un compte se fait sur des identifiants RÉELS : dans un
        # onchange, `self` porte des NewId dont l'origine est le vrai
        # fauteuil, et `_read_group` regroupe sur cette origine.
        origines = {chair: chair._origin.id for chair in self}
        groupes = self.env['maintenance.equipment']._read_group(
            [('chair_id', 'in', list(filter(None, origines.values())))],
            ['chair_id'], ['__count'])
        par_fauteuil = {chair.id: nombre for chair, nombre in groupes}
        for chair in self:
            chair.equipment_count = par_fauteuil.get(origines[chair], 0)

    def action_megga_open_equipment(self):
        """Le matériel de ce fauteuil, depuis sa fiche.

        Sur les vues du cabinet, pas sur celles du cœur : c'est le même
        écran que le menu « Appareils », resserré sur un fauteuil.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Matériel de %s", self.display_name),
            'res_model': 'maintenance.equipment',
            'view_mode': 'list,form',
            'search_view_id': [
                self.env.ref(
                    'megga_dental_materiel.view_dental_equipment_search').id,
                'search'],
            'views': [
                (self.env.ref(
                    'megga_dental_materiel.view_dental_equipment_list').id,
                 'list'),
                (False, 'form'),
            ],
            'domain': [('chair_id', '=', self.id)],
            'context': {'default_chair_id': self.id,
                        'default_maintenance_team_id': self.env.ref(
                            'megga_dental_materiel.'
                            'maintenance_team_dental').id},
        }
