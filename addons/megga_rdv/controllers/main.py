from odoo import _, fields, http
from odoo.exceptions import UserError
from odoo.http import request

from ..rdv_logic import format_jour_fr


class MeggaRdvController(http.Controller):
    """Pages publiques de réservation. Tout passe par sudo() côté
    serveur : le visiteur ne lit jamais l'agenda des intervenants, il ne
    voit que des créneaux libres recalculés à chaque affichage — et la
    réservation re-vérifie le créneau au moment du POST."""

    def _type_ou_404(self, type_id):
        rdv_type = request.env['megga.rdv.type'].sudo().browse(
            int(type_id)).exists()
        if not rdv_type or not rdv_type.active:
            return None
        return rdv_type

    @http.route('/rdv', type='http', auth='public', sitemap=False)
    def rdv_types(self, **kw):
        types = request.env['megga.rdv.type'].sudo().search([])
        return request.render('megga_rdv.page_types', {'types': types})

    @http.route('/rdv/<int:type_id>', type='http', auth='public',
                sitemap=False)
    def rdv_slots(self, type_id, **kw):
        rdv_type = self._type_ou_404(type_id)
        if rdv_type is None:
            return request.not_found()
        jours, courant = [], None
        for slot in rdv_type._available_slots():
            if courant is None or courant['day'] != slot['day']:
                courant = {'day': slot['day'],
                           'label': format_jour_fr(slot['day']),
                           'slots': []}
                jours.append(courant)
            courant['slots'].append({
                'label': slot['label'],
                'value': fields.Datetime.to_string(slot['start']),
            })
        return request.render('megga_rdv.page_slots', {
            'rdv_type': rdv_type, 'jours': jours})

    @http.route('/rdv/<int:type_id>/formulaire', type='http',
                auth='public', methods=['GET'], sitemap=False)
    def rdv_form(self, type_id, creneau=None, **kw):
        rdv_type = self._type_ou_404(type_id)
        if rdv_type is None:
            return request.not_found()
        try:
            start = fields.Datetime.to_datetime(creneau)
        except (ValueError, TypeError):
            start = None
        if not start:
            return request.render('megga_rdv.page_invalid', {
                'rdv_type': rdv_type,
                'message': _("Créneau invalide — choisissez-en un autre.")})
        apercu = request.env['megga.rdv.booking'].sudo().new({
            'type_id': rdv_type.id, 'start': start,
            'guest_name': '-', 'email': '-'})
        return request.render('megga_rdv.page_form', {
            'rdv_type': rdv_type,
            'creneau': creneau,
            'creneau_label': apercu._local_label(),
        })

    @http.route('/rdv/<int:type_id>/reserver', type='http', auth='public',
                methods=['POST'], sitemap=False)
    def rdv_reserver(self, type_id, creneau=None, nom=None, email=None,
                     telephone=None, **kw):
        rdv_type = self._type_ou_404(type_id)
        if rdv_type is None:
            return request.not_found()
        try:
            start = fields.Datetime.to_datetime(creneau)
        except (ValueError, TypeError):
            start = None
        if not (start and (nom or '').strip() and (email or '').strip()):
            return request.render('megga_rdv.page_invalid', {
                'rdv_type': rdv_type,
                'message': _("Nom, e-mail et créneau sont obligatoires.")})
        try:
            booking = request.env['megga.rdv.booking'].sudo()._reserver(
                rdv_type, start, nom.strip(), email.strip(),
                (telephone or '').strip() or False)
        except UserError as exc:
            return request.render('megga_rdv.page_invalid', {
                'rdv_type': rdv_type, 'message': str(exc)})
        return request.render('megga_rdv.page_done', {
            'booking': booking,
            'creneau_label': booking._local_label(),
        })

    @http.route('/rdv/annuler/<string:token>', type='http', auth='public',
                sitemap=False)
    def rdv_annuler(self, token, **kw):
        booking = request.env['megga.rdv.booking'].sudo().search(
            [('access_token', '=', token)], limit=1)
        if not booking:
            return request.not_found()
        booking.action_cancel()
        return request.render('megga_rdv.page_cancelled', {
            'booking': booking,
            'creneau_label': booking._local_label(),
        })
