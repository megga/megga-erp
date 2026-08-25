from odoo import _, fields, http
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class RestoPortal(CustomerPortal):
    """Les pages « Mes réservations ». La lecture est portée par la règle
    d'enregistrement (les siennes seulement) ; l'annulation est le seul
    geste d'écriture de tous les portails Megga, et il passe par une
    action dédiée : contrôle d'accès d'abord, gardes métier ensuite,
    exécution en sudo (les ACL du portail restent en lecture seule) et
    trace au chatter — jamais un write générique."""

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'resto_reservation_count' in counters:
            Reservation = request.env['megga.resto.reservation']
            values['resto_reservation_count'] = (
                Reservation.search_count([])
                if Reservation.has_access('read') else 0)
        return values

    @http.route(['/my/reservations'], type='http', auth='user', website=True)
    def portal_my_reservations(self, **kw):
        reservations = request.env['megga.resto.reservation'].search(
            [], order='start desc, id desc')
        return request.render(
            'megga_resto_portal.portal_my_reservations', {
                'reservations': reservations,
                'page_name': 'resto_reservations',
                'maintenant': fields.Datetime.now(),
                'erreur': kw.get('erreur'),
            })

    @http.route(['/my/reservations/<int:reservation_id>/annuler'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_cancel_reservation(self, reservation_id, **kw):
        # Le controle d'acces D'ABORD : la regle du portail s'applique
        # (la reservation doit etre la sienne) — sinon refus.
        reservation = self._document_check_access(
            'megga.resto.reservation', reservation_id)
        # Puis les gardes metier : on n'annule pas une table deja
        # installee, ni un service passe (le restaurant a mis le couvert
        # — l'annulation tardive se regle au telephone, pas en ligne).
        if reservation.state not in ('draft', 'confirmed'):
            return request.redirect(
                '/my/reservations?erreur=etat')
        if reservation.stop and reservation.stop <= fields.Datetime.now():
            return request.redirect(
                '/my/reservations?erreur=passee')
        # sudo : le portail n'a aucun droit d'ecriture, et il ne doit
        # pas en avoir. L'action du modele garde ses propres regles.
        sudo_reservation = reservation.sudo()
        try:
            sudo_reservation.action_cancel()
        except UserError:
            return request.redirect('/my/reservations?erreur=etat')
        sudo_reservation.message_post(
            body=_("Annulée par le client depuis le portail."))
        return request.redirect('/my/reservations')
