from odoo import api, fields, models
from odoo.tools import SQL

from ..pilotage_logic import BORNES, LIBELLES, TRANCHES, tranche_age, ventiler


class MeggaPilotageAge(models.Model):
    """La balance âgée du poste clients : une ligne par facture ouverte,
    rangée par âge de la créance. Absente du dépôt Community — les
    rapports comptables (`account_reports`) sont Enterprise.

    Vue SQL (`_auto = False`) : le pivot, le graphe et le regroupement
    travaillent en base, sans rien stocker ni dupliquer. La règle de
    classement est celle de `pilotage_logic`, réécrite ici en SQL ; un
    test compare les deux verdicts sur toute la plage pour qu'ils ne
    divergent jamais.
    """
    _name = 'megga.pilotage.age'
    _description = "Balance âgée du poste clients"
    _auto = False
    _rec_name = 'move_id'
    _order = 'days_overdue desc, id'

    move_id = fields.Many2one('account.move', string="Facture", readonly=True)
    partner_id = fields.Many2one(
        'res.partner', string="Client", readonly=True,
        help="L'entité commerciale : les services d'un même client "
             "comptent pour un seul débiteur.")
    company_id = fields.Many2one('res.company', readonly=True)
    company_currency_id = fields.Many2one(
        'res.currency', string="Devise", readonly=True)
    invoice_date = fields.Date("Date de facture", readonly=True)
    invoice_date_due = fields.Date("Échéance", readonly=True)
    days_overdue = fields.Integer("Jours de retard", readonly=True)
    bucket = fields.Selection(
        [(cle, LIBELLES[cle]) for cle in TRANCHES],
        string="Tranche", readonly=True)
    # Montant en devise de la SOCIETE (`amount_residual_signed`) : un
    # tableau de bord additionne, et on n'additionne pas des francs avec
    # des euros. Le detail en devise d'origine reste sur la facture.
    amount_residual = fields.Monetary(
        "Reste dû", readonly=True,
        currency_field='company_currency_id')
    relance_niveau_id = fields.Many2one(
        'megga.relance.niveau', string="Dernier rappel", readonly=True,
        help="Où en est le recouvrement de cette facture.")

    @property
    def _table_query(self) -> SQL:
        # Les memes bornes que la logique pure, injectees dans le SQL :
        # une seule source de verite pour les seuils.
        b30, b60, b90 = BORNES
        return SQL(
            """
            SELECT am.id AS id,
                   am.id AS move_id,
                   am.commercial_partner_id AS partner_id,
                   am.company_id AS company_id,
                   rc.currency_id AS company_currency_id,
                   am.invoice_date AS invoice_date,
                   am.invoice_date_due AS invoice_date_due,
                   GREATEST(CURRENT_DATE - am.invoice_date_due, 0)
                       AS days_overdue,
                   CASE
                       WHEN CURRENT_DATE - am.invoice_date_due <= 0
                           THEN 'not_due'
                       WHEN CURRENT_DATE - am.invoice_date_due <= %(b30)s
                           THEN 'b30'
                       WHEN CURRENT_DATE - am.invoice_date_due <= %(b60)s
                           THEN 'b60'
                       WHEN CURRENT_DATE - am.invoice_date_due <= %(b90)s
                           THEN 'b90'
                       ELSE 'b90p'
                   END AS bucket,
                   am.amount_residual_signed AS amount_residual,
                   am.megga_relance_niveau_id AS relance_niveau_id
              FROM account_move am
              -- La devise de la societe vient de res_company : sur
              -- account_move, company_currency_id est un related NON
              -- stocke, donc pas une colonne (vecu).
              JOIN res_company rc ON rc.id = am.company_id
             WHERE am.move_type = 'out_invoice'
               AND am.state = 'posted'
               AND am.payment_state NOT IN
                   ('paid', 'reversed', 'invoicing_legacy')
               AND am.amount_residual > 0
               AND am.invoice_date_due IS NOT NULL
            """,
            b30=b30, b60=b60, b90=b90,
        )

    def _search(self, domain, offset=0, limit=None, order=None, **kw):
        """Vider account.move AVANT d'interroger la vue.

        La vue lit la TABLE, pas le cache de l'ORM : une écriture encore
        en vol — un paiement enregistré, un rappel qui vient de marquer
        sa facture — resterait invisible, et la balance mentirait d'un
        cran. Le cœur ne le fait pas dans ses propres vues d'analyse
        parce qu'une requête web arrive après le commit ; un appel
        programmatique, lui, n'a pas cette chance."""
        self.env['account.move'].flush_model()
        return super()._search(
            domain, offset=offset, limit=limit, order=order, **kw)

    @api.model
    def _balance_par_client(self, company):
        """La balance âgée telle qu'elle s'imprime : une ligne par
        client, ventilée par tranche, la plus grosse dette en tête.
        Classement en PYTHON ici (règle unique de `pilotage_logic`)."""
        lignes = self.search([('company_id', '=', company.id)])
        par_client = {}
        for ligne in lignes:
            jours = (fields.Date.context_today(self)
                     - ligne.invoice_date_due).days
            par_client.setdefault(ligne.partner_id, []).append(
                (tranche_age(jours), ligne.amount_residual))
        balance = [{
            'partner': partner,
            'tranches': ventiler(couples),
            'total': sum(montant for _tranche, montant in couples),
        } for partner, couples in par_client.items()]
        balance.sort(key=lambda d: d['total'], reverse=True)
        return balance


class ReportBalanceAgee(models.AbstractModel):
    """Le rendu du rapport imprimable. Modèle de rendu (et non simple
    gabarit) parce qu'il faut ventiler côté serveur — et parce que la
    mise en page DIN imprime SON titre avant le corps (leçon des
    ordonnances dentaires)."""
    _name = 'report.megga_pilotage.report_balance_agee'
    _description = "Rendu de la balance âgée"

    @api.model
    def _get_report_values(self, docids, data=None):
        company = self.env.company
        Age = self.env['megga.pilotage.age']
        balance = Age._balance_par_client(company)
        return {
            'doc_model': 'res.company',
            'docs': company,
            'balance': balance,
            'tranches': TRANCHES,
            'libelles': LIBELLES,
            'totaux': ventiler([
                (tranche, ligne['tranches'][tranche])
                for ligne in balance for tranche in TRANCHES]),
            'total_general': sum(ligne['total'] for ligne in balance),
            'devise': company.currency_id,
            'din5008_document_title': "Balance âgée",
        }
