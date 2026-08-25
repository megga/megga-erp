from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class AutoPortal(CustomerPortal):
    """Les pages « Mon garage ». Lecture seule ; l'étanchéité est portée
    par les règles d'enregistrement (le sien seulement, jamais un devis
    en rédaction) — les contrôleurs ne font que lister ce que l'ORM veut
    bien rendre, et vérifient l'accès AVANT tout PDF : _show_report rend
    en sudo, sans contrôle à lui."""

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'auto_vehicle_count' in counters:
            Vehicle = request.env['fleet.vehicle']
            values['auto_vehicle_count'] = (
                Vehicle.search_count([])
                if Vehicle.has_access('read') else 0)
        return values

    @http.route(['/my/vehicules'], type='http', auth='user', website=True)
    def portal_my_vehicles(self, **kw):
        vehicles = request.env['fleet.vehicle'].search([], order='id')
        return request.render(
            'megga_auto_portal.portal_my_vehicles', {
                'vehicles': vehicles,
                'page_name': 'auto_vehicles',
            })

    @http.route(['/my/reparations'], type='http', auth='user', website=True)
    def portal_my_workorders(self, **kw):
        orders = request.env['megga.auto.workorder'].search(
            [], order='date desc, id desc')
        return request.render(
            'megga_auto_portal.portal_my_workorders', {
                'orders': orders,
                'page_name': 'auto_workorders',
            })

    @http.route(['/my/vehicules/<int:vehicle_id>/carnet'],
                type='http', auth='user', website=True)
    def portal_vehicle_carnet(self, vehicle_id, **kw):
        # Le controle d'acces D'ABORD : la regle du portail s'applique
        # (le vehicule doit etre le sien) — sinon refus, jamais de
        # rendu. Le carnet lui-meme est ensuite rendu en sudo, donc
        # complet : c'est voulu, un carnet d'entretien se transmet avec
        # le vehicule (il ne porte aucun prix).
        vehicle = self._document_check_access('fleet.vehicle', vehicle_id)
        return self._show_report(
            model=vehicle, report_type='pdf',
            report_ref='megga_auto.action_report_carnet',
            download=True)
