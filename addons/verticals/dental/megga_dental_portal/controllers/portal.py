from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class DentalPortal(CustomerPortal):
    """Les pages « Mon dossier dentaire ». Lecture seule ; l'étanchéité
    est portée par les règles d'enregistrement (le sien seulement,
    jamais un brouillon) — les contrôleurs ne font que lister ce que
    l'ORM veut bien rendre, et vérifient l'accès AVANT tout PDF :
    _show_report rend en sudo, sans contrôle à lui."""

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'dental_treatment_count' in counters:
            Treatment = request.env['megga.dental.treatment']
            values['dental_treatment_count'] = (
                Treatment.search_count([])
                if Treatment.has_access('read') else 0)
        return values

    @http.route(['/my/traitements'], type='http', auth='user', website=True)
    def portal_my_dental_treatments(self, **kw):
        treatments = request.env['megga.dental.treatment'].search(
            [], order='date desc, id desc')
        return request.render(
            'megga_dental_portal.portal_my_dental_treatments', {
                'treatments': treatments,
                'page_name': 'dental_treatments',
            })

    @http.route(['/my/ordonnances'], type='http', auth='user', website=True)
    def portal_my_prescriptions(self, **kw):
        prescriptions = request.env['megga.dental.prescription'].search(
            [], order='date desc, id desc')
        return request.render(
            'megga_dental_portal.portal_my_prescriptions', {
                'prescriptions': prescriptions,
                'page_name': 'dental_prescriptions',
            })

    @http.route(['/my/questionnaires'], type='http', auth='user',
                website=True)
    def portal_my_questionnaires(self, **kw):
        answers = request.env['megga.dental.questionnaire.answer'].search(
            [], order='date desc, id desc')
        return request.render(
            'megga_dental_portal.portal_my_questionnaires', {
                'answers': answers,
                'page_name': 'dental_questionnaires',
            })

    @http.route(['/my/ordonnances/<int:prescription_id>/pdf'],
                type='http', auth='user', website=True)
    def portal_prescription_pdf(self, prescription_id, **kw):
        # Le controle d'acces D'ABORD : regles d'enregistrement du
        # portail appliquees (le sien, emise) — sinon 403, jamais de
        # rendu.
        prescription = self._document_check_access(
            'megga.dental.prescription', prescription_id)
        return self._show_report(
            model=prescription, report_type='pdf',
            report_ref='megga_dental.action_report_prescription',
            download=True)

    @http.route(['/my/questionnaires/<int:answer_id>/pdf'],
                type='http', auth='user', website=True)
    def portal_questionnaire_pdf(self, answer_id, **kw):
        answer = self._document_check_access(
            'megga.dental.questionnaire.answer', answer_id)
        return self._show_report(
            model=answer, report_type='pdf',
            report_ref='megga_dental.action_report_questionnaire',
            download=True)
