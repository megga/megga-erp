from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date, formatLang
from odoo.tools.mail import plaintext2html

from ..relance_logic import jours_de_retard, niveau_applicable


class MeggaRelanceNiveau(models.Model):
    """Un cran de rappel : combien de jours après l'échéance, quel ton,
    quels frais annoncés. Le cabinet règle ses propres crans — la loi
    n'impose pas de nombre de rappels (art. 102 CO : la demeure naît de
    l'interpellation ; une échéance convenue suffit même sans rappel)."""
    _name = 'megga.relance.niveau'
    _description = "Niveau de rappel"
    _order = 'delay_days, id'

    name = fields.Char("Niveau", required=True)
    delay_days = fields.Integer(
        "Jours après l'échéance", required=True, default=10,
        help="À partir de combien de jours de retard ce niveau "
             "s'applique.")
    active = fields.Boolean(default=True)
    subject = fields.Char(
        "Objet du courriel", required=True,
        default="Rappel de facture")
    body = fields.Text(
        "Texte du rappel", required=True,
        help="Le corps du message envoyé au client.")
    fees = fields.Monetary(
        "Frais de rappel annoncés", currency_field='currency_id',
        help="Montant ANNONCÉ dans le texte du rappel. Megga ne le "
             "facture pas tout seul : des frais de rappel se "
             "contestent, ils s'ajoutent en conscience sur une note "
             "de débit.")
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')

    _delay_uniq = models.Constraint(
        'unique(company_id, delay_days)',
        "Deux niveaux de rappel ne peuvent pas partager le même délai.")


class MeggaRelance(models.Model):
    """Un rappel adressé à UN client, portant TOUTES ses factures échues
    au niveau du jour. Regrouper est le comportement attendu : un client
    qui doit trois factures reçoit un courrier, pas trois.

    Le cron PROPOSE (brouillon) ; l'envoi reste un geste — une relance
    part sous la signature du cabinet, pas toute seule pendant la nuit.
    """
    _name = 'megga.relance'
    _description = "Rappel de facture"
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(
        "Référence", readonly=True, copy=False, default='/')
    partner_id = fields.Many2one(
        'res.partner', string="Client", required=True,
        ondelete='restrict', index=True)
    niveau_id = fields.Many2one(
        'megga.relance.niveau', string="Niveau", required=True,
        ondelete='restrict')
    date = fields.Date(
        "Date", required=True, default=fields.Date.context_today)
    move_ids = fields.Many2many(
        'account.move', string="Factures rappelées")
    amount_due = fields.Monetary(
        "Montant dû", compute='_compute_amount_due', store=True,
        currency_field='currency_id')
    state = fields.Selection([
        ('draft', "À envoyer"),
        ('sent', "Envoyé"),
        ('cancelled', "Abandonné"),
    ], string="État", default='draft', required=True, copy=False,
        tracking=True)
    sent_on = fields.Datetime("Envoyé le", readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    # La devise du RAPPEL, pas celle de la societe : un client facture
    # en euros se relance en euros, et on n'additionne jamais deux
    # devises sous un meme total.
    currency_id = fields.Many2one(
        'res.currency', string="Devise", required=True,
        default=lambda self: self.env.company.currency_id)

    @api.depends('move_ids.amount_residual')
    def _compute_amount_due(self):
        for relance in self:
            relance.amount_due = sum(
                relance.move_ids.mapped('amount_residual'))

    @api.depends('partner_id', 'niveau_id')
    def _compute_display_name(self):
        for relance in self:
            relance.display_name = "%s — %s (%s)" % (
                relance.name, relance.partner_id.display_name,
                relance.niveau_id.name or "")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'megga.relance') or '/'
        return super().create(vals_list)

    def action_send(self):
        """Envoie le rappel et MARQUE les factures. Le monde a pu bouger
        depuis la proposition de la nuit : on revérifie avant d'écrire
        au client — rien n'est plus gênant qu'un rappel pour une facture
        payée la veille."""
        for relance in self:
            if relance.state != 'draft':
                raise UserError(_(
                    "Ce rappel a déjà été envoyé ou abandonné."))
            relance._rafraichir_factures()
            destinataire = relance.partner_id.email
            if not destinataire:
                raise UserError(_(
                    "%s n'a pas d'adresse de courriel — envoyez le "
                    "rappel par la poste et marquez-le remis.")
                    % relance.partner_id.display_name)
            relance._post_mail()
            relance._marquer()
            relance.write({
                'state': 'sent',
                'sent_on': fields.Datetime.now(),
            })

    def _rafraichir_factures(self):
        """Retire du courrier ce qui n'est plus dû (payé, annulé, sorti
        du circuit) et refuse d'écrire s'il ne reste rien."""
        self.ensure_one()
        encore_dues = self._factures_echues(self.company_id)
        self.move_ids = [(6, 0, (self.move_ids & encore_dues).ids)]
        if not self.move_ids:
            raise UserError(_(
                "Plus rien à rappeler : ces factures ont été réglées, "
                "annulées ou sorties du circuit depuis la proposition. "
                "Abandonnez ce rappel."))

    def _marquer(self):
        """Chaque facture reçoit LE CRAN QUI LUI EST APPLICABLE, et le
        marquage ne redescend jamais : envoyer un vieux brouillon après
        un rappel plus sévère ne doit pas rouvrir un cran déjà servi."""
        self.ensure_one()
        niveaux = self.env['megga.relance.niveau'].search(
            [('company_id', '=', self.company_id.id)])
        delais = niveaux.mapped('delay_days')
        aujourdhui = fields.Date.context_today(self)
        for move in self.move_ids:
            position = niveau_applicable(
                jours_de_retard(move.invoice_date_due, aujourdhui),
                delais)
            propre = niveaux[position] if position is not None \
                else self.niveau_id
            deja = move.megga_relance_niveau_id
            if deja and deja.delay_days >= propre.delay_days:
                continue
            move.write({
                'megga_relance_niveau_id': propre.id,
                'megga_relance_date': self.date,
            })

    def _post_mail(self):
        """Le courriel part par le chatter : la trace et l'envoi ne font
        qu'un — un rappel sans trace est un rappel qu'on ne peut pas
        prouver.

        Deux exigences que le code doit tenir : le corps est construit
        en TEXTE puis converti par `plaintext2html` — `message_post`
        échappe toute chaîne qui n'est pas du Markup, donc un
        « <br/> » écrit à la main partirait en toutes lettres, et le
        texte d'un niveau contenant « & » ou « < » casserait le
        message ; et tout est composé dans la LANGUE DU CLIENT, pas
        dans celle de qui clique."""
        self.ensure_one()
        env = self.env(context=dict(
            self.env.context, lang=self.partner_id.lang or self.env.lang))
        lignes = "\n".join(
            "- %s : %s (échue le %s)" % (
                move.name,
                formatLang(env, move.amount_residual,
                           currency_obj=move.currency_id),
                format_date(env, move.invoice_date_due))
            for move in self.move_ids)
        corps = "%s\n\n%s\n\n%s" % (
            self.niveau_id.body, lignes,
            _("Total dû : %s") % formatLang(
                env, self.amount_due, currency_obj=self.currency_id))
        if self.niveau_id.fees:
            corps += "\n\n" + _("Frais de rappel annoncés : %s.") % \
                formatLang(env, self.niveau_id.fees,
                           currency_obj=self.currency_id)
        self.message_post(
            body=plaintext2html(corps),
            subject=self.niveau_id.subject,
            partner_ids=self.partner_id.ids,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

    def action_mark_sent(self):
        """Rappel remis autrement (poste, guichet) : on marque, on trace,
        on n'envoie pas de courriel — mais on revérifie tout autant."""
        for relance in self:
            if relance.state != 'draft':
                raise UserError(_("Ce rappel n'est plus à envoyer."))
            relance._rafraichir_factures()
            relance._marquer()
            relance.write({
                'state': 'sent',
                'sent_on': fields.Datetime.now(),
            })
            relance.message_post(
                body=_("Rappel remis hors courriel (poste ou guichet)."))

    def action_cancel(self):
        self.filtered(lambda r: r.state == 'draft').write(
            {'state': 'cancelled'})

    @api.model
    def _factures_echues(self, company):
        """Les factures client ouvertes et échues de `company`. On ne
        relance ni un brouillon, ni une facture payée, ni une facture
        que le comptable a explicitement sortie du circuit
        (`megga_relance_exclue`).

        Pourquoi notre propre drapeau et pas `no_followup` du coeur : ce
        champ-la est un CROCHET INERTE en Community — calcule et non
        stocke sur la facture comme sur la ligne, il ne se filtre pas en
        SQL et ne memorise rien (c'est le module Enterprise qui le rend
        persistant). S'y fier donnerait une case a cocher qui oublie."""
        return self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            # 'blocked' : le litige, vrai crochet STOCKE du coeur 19 —
            # une facture en litige ne se relance pas.
            ('payment_state', 'not in',
             ('paid', 'in_payment', 'reversed', 'blocked',
              'invoicing_legacy')),
            ('amount_residual', '>', 0),
            ('invoice_date_due', '!=', False),
            ('company_id', '=', company.id),
            ('megga_relance_exclue', '=', False),
        ])

    @api.model
    def _cron_megga_relances(self):
        """Chaque jour : prépare UN rappel en BROUILLON par client (et
        par devise) dont le retard atteint un cran non encore servi.
        N'envoie rien — c'est la maison qui décide.

        Trois choix que le code doit tenir, et que des tests gardent :
        - un client, un courrier : le cran retenu est le PLUS ÉLEVÉ que
          ses factures appellent, et la lettre les porte toutes ;
        - une devise, un courrier : on n'additionne pas des francs et
          des euros sous un seul total ;
        - le débiteur est l'entité commerciale (`commercial_partner_id`),
          pas le contact de facturation — sinon deux services du même
          client reçoivent deux lettres.
        """
        aujourdhui = fields.Date.context_today(self)
        Niveau = self.env['megga.relance.niveau']
        # Ce que la nuit a produit : rappels crees OU mis a jour.
        touches = self.env['megga.relance']
        for company in self.env['res.company'].search([]):
            niveaux = Niveau.search([('company_id', '=', company.id)])
            if not niveaux:
                continue
            delais = niveaux.mapped('delay_days')
            groupes = defaultdict(lambda: self.env['account.move'])
            for move in self._factures_echues(company):
                retard = jours_de_retard(
                    move.invoice_date_due, aujourdhui)
                position = niveau_applicable(retard, delais)
                if position is None:
                    continue
                niveau = niveaux[position]
                deja = move.megga_relance_niveau_id
                if deja and deja.delay_days >= niveau.delay_days:
                    continue
                groupes[
                    (move.commercial_partner_id, move.currency_id)
                ] |= move
            for (partner, devise), moves in groupes.items():
                if self._avoirs_couvrent(partner, devise, company, moves):
                    continue
                niveau = self._niveau_du_courrier(
                    moves, niveaux, delais, aujourdhui)
                # Un brouillon attend deja pour ce client dans cette
                # devise : on le MET A JOUR (le monde a pu bouger depuis
                # la nuit derniere), on ne l'empile pas et on ne le jette
                # pas — il porte peut-etre deja des notes du comptable.
                attente = self.search([
                    ('partner_id', '=', partner.id),
                    ('currency_id', '=', devise.id),
                    ('company_id', '=', company.id),
                    ('state', '=', 'draft'),
                ], limit=1)
                if attente:
                    inchange = (attente.niveau_id == niveau
                                and attente.move_ids == moves)
                    if not inchange:
                        attente.write({
                            'niveau_id': niveau.id,
                            'date': aujourdhui,
                            'move_ids': [(6, 0, moves.ids)],
                        })
                        touches |= attente
                    continue
                touches |= self.create({
                    'partner_id': partner.id,
                    'niveau_id': niveau.id,
                    'company_id': company.id,
                    'currency_id': devise.id,
                    'move_ids': [(6, 0, moves.ids)],
                })
        return touches

    @api.model
    def _niveau_du_courrier(self, moves, niveaux, delais, aujourdhui):
        """Le cran de la lettre : le plus élevé qu'appelle l'une des
        factures. Chaque facture reste ensuite marquée à SON propre
        cran (voir `_marquer`) — la lettre monte le ton, elle ne fait
        pas sauter des crans à une facture jeune."""
        retenus = niveaux.browse()
        for move in moves:
            position = niveau_applicable(
                jours_de_retard(move.invoice_date_due, aujourdhui),
                delais)
            if position is not None:
                retenus |= niveaux[position]
        return max(retenus, key=lambda n: n.delay_days)

    @api.model
    def _avoirs_couvrent(self, partner, devise, company, moves):
        """Un client dont les avoirs ouverts couvrent la dette échue ne
        doit rien : on ne lui écrit pas. Le lettrage reste au
        comptable — nous, nous nous taisons."""
        avoirs = self.env['account.move'].search([
            ('move_type', '=', 'out_refund'),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ('paid', 'reversed')),
            ('commercial_partner_id', '=', partner.id),
            ('currency_id', '=', devise.id),
            ('company_id', '=', company.id),
        ])
        if not avoirs:
            return False
        du = sum(moves.mapped('amount_residual'))
        credit = sum(abs(a.amount_residual) for a in avoirs)
        return credit >= du


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Le cran deja servi est porte par la FACTURE (pas par le client) :
    # deux factures du meme client peuvent etre a des stades differents.
    # On stocke l'IDENTITE du niveau, pas son delai : un delai se
    # reregle (« finalement, le 2e rappel a 25 jours »), et comparer des
    # nombres mutables ferait repartir des crans deja servis.
    megga_relance_niveau_id = fields.Many2one(
        'megga.relance.niveau', string="Dernier rappel envoyé",
        readonly=True, copy=False, ondelete='restrict',
        help="Niveau du dernier rappel envoyé pour cette facture. "
             "Garantit qu'un même cran ne repart pas deux fois.")
    megga_relance_date = fields.Date(
        "Dernier rappel le", readonly=True, copy=False)
    megga_relance_exclue = fields.Boolean(
        "Hors rappels", copy=False,
        help="Cette facture ne part plus en rappel : litige, "
             "arrangement de paiement, recouvrement confié. Le suivi "
             "reprend en décochant.")
