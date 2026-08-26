from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class MeggaDentalSterilisationCycle(models.Model):
    """Une charge d'autoclave, et ce qu'elle a produit.

    Le cycle est un document de PREUVE : il dit quel appareil, quel
    jour, quel programme, avec quels contrôles — et quels sets en sont
    sortis. Il ne s'efface pas et, une fois validé, il ne se modifie
    plus : même doctrine que l'ordonnance émise et le journal clinique.

    Ce qu'il ne réinvente pas : l'appareil est un équipement du registre
    (`megga_dental_materiel`), les sets sont des lots datés du magasin
    (`megga_dental_stock`), et la péremption de stérilité est la
    péremption tout court — donc le FEFO du cœur et la garde du cabinet
    s'appliquent sans une ligne de plus.
    """
    _name = 'megga.dental.sterilisation.cycle'
    _description = "Cycle de stérilisation"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(
        "Numéro de cycle", required=True, copy=False, readonly=True,
        default=lambda self: _("Nouveau"),
        help="Le numéro qui part sur l'étiquette des sachets. C'est lui "
             "qui relie un instrument à sa charge.")
    equipment_id = fields.Many2one(
        'maintenance.equipment', string="Autoclave", required=True,
        ondelete='restrict', index='btree_not_null', tracking=True,
        help="L'appareil du registre du matériel. Son historique "
             "d'entretien et ses validations périodiques sont la "
             "moitié de la preuve.")
    chair_id = fields.Many2one(
        'megga.dental.chair', string="Fauteuil desservi",
        related='equipment_id.chair_id', readonly=True)
    date_start = fields.Datetime(
        "Début du cycle", required=True, tracking=True, copy=False,
        default=fields.Datetime.now)
    user_id = fields.Many2one(
        'res.users', string="Opérateur", tracking=True,
        default=lambda self: self.env.user,
        help="Qui a chargé et lancé l'autoclave.")
    program = fields.Selection(
        [('b', "Cycle B — charge creuse, poreuse ou emballée"),
         ('s', "Cycle S — charge définie par le fabricant"),
         ('n', "Cycle N — instruments massifs nus")],
        string="Programme", default='b', required=True, tracking=True)
    temperature = fields.Float(
        "Palier (°C)", default=134.0, copy=False,
        help="Température du palier de stérilisation relevée au rapport "
             "de cycle.")
    plateau_minutes = fields.Float(
        "Durée du palier (min)", default=18.0, copy=False)
    helix_ok = fields.Boolean(
        "Test Helix conforme", tracking=True, copy=False,
        help="Contrôle de pénétration de vapeur, exigé pour une charge "
             "creuse ou emballée (cycle B).")
    indicator = fields.Selection(
        [('none', "Sans objet"),
         ('pending', "En attente"),
         ('pass', "Conforme"),
         ('fail', "Non conforme")],
        string="Indicateur biologique", default='none', required=True,
        tracking=True, copy=False,
        help="Le résultat arrive souvent le LENDEMAIN, une fois les "
             "sachets déjà distribués : c'est précisément pour ce "
             "cas-là que le rappel existe.")
    state = fields.Selection(
        [('draft', "Brouillon"),
         ('done', "Validé"),
         ('failed', "Non conforme")],
        string="État", default='draft', required=True, tracking=True,
        copy=False)
    # Dupliquer un cycle sert a REJOUER la meme composition : les
    # lignes se copient, les RELEVES non. Un indicateur biologique
    # recopie ferait etat d'un controle que la nouvelle charge n'a
    # jamais subi — dans un registre dont c'est tout l'objet — et un
    # « non conforme » herite condamnerait la copie a ne jamais pouvoir
    # etre validee ni supprimee.
    line_ids = fields.One2many(
        'megga.dental.sterilisation.line', 'cycle_id', string="Charge",
        copy=True)
    lot_ids = fields.One2many(
        'stock.lot', 'sterilisation_cycle_id', string="Sets produits",
        readonly=True)
    picking_id = fields.Many2one(
        'stock.picking', string="Entrée en stock", readonly=True,
        copy=False,
        help="Le mouvement engendré par la validation. Sa présence "
             "interdit une seconde entrée.")
    note = fields.Text("Observations", copy=False)
    company_id = fields.Many2one(
        'res.company', string="Société", required=True,
        default=lambda self: self.env.company,
        help="La société dont l'entrepôt recevra les sets.")

    _name_uniq = models.Constraint(
        'unique(name)', "Ce numéro de cycle existe déjà.")

    @api.constrains('temperature', 'plateau_minutes')
    def _check_releves(self):
        for cycle in self:
            if cycle.temperature < 0 or cycle.plateau_minutes < 0:
                raise ValidationError(_(
                    "Un relevé de cycle ne peut pas être négatif."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Nouveau"):
                # Séquence sans société : `next_by_code` ne la
                # retrouverait pas depuis une autre société. Leçon des
                # séquences du module dentaire.
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'megga.dental.sterilisation.cycle') or _("Nouveau")
        return super().create(vals_list)

    def write(self, vals):
        """Un cycle clos est figé : c'est une preuve, pas un brouillon.

        Trois champs restent ouverts, et un seul compte vraiment :
        l'indicateur biologique, dont le résultat arrive le lendemain.
        L'état et les observations suivent — marquer non conforme est
        justement le geste qu'on attend après coup.
        """
        OUVERTS = {'indicator', 'note', 'picking_id',
                   'message_ids', 'message_follower_ids',
                   'activity_ids', 'message_main_attachment_id'}
        figes = set(vals) - OUVERTS
        # `state` ne s'écrit que par les actions : le laisser ouvert
        # aurait rendu le gel décoratif — un write({'state': 'draft'})
        # et tout redevenait modifiable. Ce refus-là passe AVANT celui
        # du gel : sur une charge close, le message du gel serait sorti
        # le premier et aurait conseillé le mauvais geste.
        if self.env.context.get('megga_sterilisation_state'):
            figes.discard('state')
        elif 'state' in vals:
            raise UserError(_(
                "L'état d'un cycle se change par ses boutons : valider "
                "la charge, ou la marquer non conforme. Chacun fait ce "
                "qu'il annonce — l'un fait entrer les sets en rayon, "
                "l'autre les bloque et nomme les séances servies."))
        if figes:
            clos = self.filtered(lambda c: c.state != 'draft')
            if clos:
                raise UserError(_(
                    "Le cycle %(cycle)s est clos : son relevé ne se "
                    "modifie plus.\n\n"
                    "Un registre de stérilisation est un document de "
                    "preuve. Si le résultat d'un contrôle change, "
                    "marquez le cycle NON CONFORME — ses sets seront "
                    "bloqués et les séances servies seront nommées.",
                    cycle=clos[0].name))
        res = super().write(vals)
        # L'indicateur biologique qui revient NON CONFORME est le geste
        # du lendemain : il doit bloquer les sets, pas seulement noircir
        # une case. Sans cela, la garde du magasin — qui ne lit que
        # l'etat — laissait passer une charge declaree non conforme.
        if vals.get('indicator') == 'fail':
            a_bloquer = self.filtered(lambda c: c.state == 'done')
            if a_bloquer:
                a_bloquer.action_fail()
        return res

    def _megga_set_state(self, valeur):
        """Le seul chemin vers `state` — les actions passent par ici."""
        return self.with_context(megga_sterilisation_state=True).write(
            {'state': valeur})

    def unlink(self):
        """Aucun cycle ne s'efface, jamais — pas même en brouillon.

        Un cycle en brouillon dit qu'une charge est passée à
        l'autoclave. L'effacer effacerait la question « qu'est devenue
        cette charge ? ». Doctrine du dépôt pour tout ce qui porte une
        histoire.
        """
        raise UserError(_(
            "Un cycle de stérilisation ne se supprime pas : c'est un "
            "document de preuve.\n\n"
            "Une charge qui n'a pas abouti se marque NON CONFORME."))

    # ------------------------------------------------------------------
    # Le cycle
    # ------------------------------------------------------------------
    def action_validate(self):
        """Le cycle est conforme : ses sets entrent en rayon.

        En `sudo` pour la partie MAGASIN, exactement comme la clôture
        de séance décompte les consommables : celui qui décharge
        l'autoclave est de l'équipe du cabinet, il n'a pas à détenir
        les droits d'inventaire pour que le système constate une
        entrée. Et il n'en gagne aucun : la lecture du magasin reste
        gardée par les groupes stock du cœur.
        """
        for cycle in self:
            if cycle.state != 'draft':
                raise UserError(_(
                    "Le cycle %s est déjà clos.", cycle.name))
            if not cycle.line_ids:
                raise UserError(_(
                    "Le cycle %s ne contient aucun set : il n'y a rien "
                    "à faire entrer en rayon.", cycle.name))
            if cycle.indicator == 'fail':
                raise UserError(_(
                    "L'indicateur biologique du cycle %s est non "
                    "conforme : cette charge ne peut pas être "
                    "validée.", cycle.name))
            if cycle.program == 'b' and not cycle.helix_ok:
                raise UserError(_(
                    "Le cycle %s est un cycle B : sans test Helix "
                    "conforme, la pénétration de vapeur n'est pas "
                    "prouvée.\n\n"
                    "Si le test a échoué, marquez la charge non "
                    "conforme.", cycle.name))
            cycle._megga_enter_stock()
            cycle._megga_set_state('done')
        return True

    def action_fail(self):
        """La charge est non conforme — y compris après coup.

        C'est le geste du lendemain, quand l'indicateur biologique
        revient : les sets encore en rayon sont bloqués par la garde du
        magasin, et les séances déjà servies sont nommées.
        """
        for cycle in self:
            if cycle.state == 'failed':
                continue
            cycle._megga_set_state('failed')
            servies = cycle._megga_served_treatments()
            if servies:
                cycle.message_post(body=_(
                    "Charge marquée NON CONFORME. %(nombre)s séance(s) "
                    "ont déjà consommé des sets de ce cycle : "
                    "%(seances)s\n\n"
                    "Ce relevé suit les sorties passées par la clôture "
                    "de séance. Un set sorti à la main, hors séance, "
                    "n'y figure pas : vérifiez aussi ce qui manque en "
                    "rayon.",
                    nombre=len(servies),
                    seances=", ".join(servies.mapped('name'))))
            else:
                cycle.message_post(body=_(
                    "Charge marquée NON CONFORME. Aucune séance n'a "
                    "encore consommé de set de ce cycle ; ceux qui "
                    "restent en rayon sont bloqués.\n\n"
                    "Ce relevé suit les sorties passées par la clôture "
                    "de séance. Un set sorti à la main n'y figure pas."))
        return True

    def action_back_to_draft(self):
        """Une charge non conforme jamais validée revient au brouillon.

        Une charge VALIDÉE, elle, ne revient pas : ses sets sont partis
        en rayon et peut-être au fauteuil. On refait un cycle, on ne
        réécrit pas l'histoire.
        """
        for cycle in self:
            if cycle.picking_id:
                raise UserError(_(
                    "Le cycle %s a déjà fait entrer ses sets en rayon : "
                    "il ne revient pas au brouillon.\n\n"
                    "Repassez la charge à l'autoclave et enregistrez un "
                    "NOUVEAU cycle.", cycle.name))
            cycle._megga_set_state('draft')
        return True

    def _megga_enter_stock(self):
        """Crée les lots des sets et les fait entrer en rayon.

        Le patron est celui de la consommation de séance, à l'envers :
        un transfert depuis l'emplacement virtuel « Stérilisation »
        (usage `production` — les sachets stériles n'existaient pas
        avant le cycle) vers le stock de l'entrepôt.

        Ceinture d'idempotence par IDENTITÉ, pas par valeur : le lien
        `picking_id` interdit une seconde entrée, doctrine du dépôt.
        """
        self.ensure_one()
        if self.picking_id:
            return self.picking_id
        Warehouse = self.env['stock.warehouse'].sudo()
        warehouse = Warehouse.search(
            [('company_id', '=', self.company_id.id)], limit=1)
        if not warehouse:
            raise UserError(_(
                "Aucun entrepôt n'est configuré pour cette société : "
                "les sets ne peuvent pas entrer en rayon."))
        picking_type = warehouse._megga_dental_sterilisation_picking_type()
        source = picking_type.default_location_src_id
        destination = picking_type.default_location_dest_id
        Picking = self.env['stock.picking'].sudo()
        picking = Picking.create({
            'picking_type_id': picking_type.id,
            'location_id': source.id,
            'location_dest_id': destination.id,
            'company_id': self.company_id.id,
            # Le numéro de cycle, et rien d'autre : le magasin n'a pas
            # à savoir ce qui a été soigné (nLPD, doctrine du chantier
            # 2). Pas de partner_id.
            'origin': self.name,
            'move_ids': [(0, 0, {
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'location_id': source.id,
                'location_dest_id': destination.id,
                # Le lien qui tient tout : il retrouve le mouvement de
                # CETTE ligne après confirmation, et il empêche le cœur
                # de fusionner deux lignes du même set.
                'sterilisation_line_id': line.id,
            }) for line in self.line_ids],
        })
        picking.action_confirm()
        for line in self.line_ids:
            move = picking.move_ids.filtered(
                lambda m: m.sterilisation_line_id == line)
            if not move:
                raise UserError(_(
                    "Le mouvement d'entrée de %s est introuvable : "
                    "l'entrée en rayon est annulée.",
                    line.product_id.display_name))
            lot = self.env['stock.lot'].sudo().create({
                'name': line._megga_lot_name(),
                'product_id': line.product_id.id,
                'company_id': self.company_id.id,
                'sterilisation_cycle_id': self.id,
                'sterilisation_line_id': line.id,
                # La stérilité expire à partir du CYCLE, pas de la
                # saisie : `expiration_date` du cœur est un compute
                # stocké `readonly=False`, il se pose donc à la main.
                'expiration_date': line._megga_sterility_deadline(),
            })
            move.move_line_ids.unlink()
            self.env['stock.move.line'].sudo().create({
                'move_id': move.id,
                'picking_id': picking.id,
                'product_id': move.product_id.id,
                'product_uom_id': move.product_uom.id,
                'lot_id': lot.id,
                'location_id': move.location_id.id,
                'location_dest_id': move.location_dest_id.id,
                'quantity': line.quantity,
            })
            move.picked = True
        # `skip_expired` : le cœur interpose un assistant de confirmation
        # dès qu'une ligne porte un lot dont la date de RETRAIT est
        # atteinte (`_check_expired_lots` regarde `removal_date`, pas
        # seulement la péremption). Un set qui SORT de l'autoclave n'est
        # pas périmé — mais avec un délai de retrait égal au délai de
        # péremption, ou une charge saisie après coup, il l'est aux yeux
        # du cœur dès sa création. Sans ce contexte, l'assistant
        # remplace la validation, le contrôle ci-dessous voit un
        # transfert non validé, et la charge devient IMPOSSIBLE à
        # valider — définitivement. La garde qui compte est celle de la
        # SORTIE vers les soins, et elle, reste entière.
        picking.with_context(
            skip_backorder=True, skip_expired=True).button_validate()
        if picking.state != 'done':
            raise UserError(_(
                "L'entrée en rayon du cycle %(cycle)s n'a pas abouti "
                "(%(etat)s) : la charge n'est pas validée.",
                cycle=self.name, etat=picking.state))
        self.picking_id = picking.id
        # Toujours le TRANSFERT, jamais le retour de `button_validate` :
        # celui-ci vaut True ou une action client, et un appelant qui
        # ferait `.origin` dessus casserait un jour sur deux.
        return picking

    # ------------------------------------------------------------------
    # Les deux sens de la traçabilité
    # ------------------------------------------------------------------
    def _megga_served_treatments(self):
        """Les séances qui ont consommé un set de ce cycle.

        En `sudo` sur le MAGASIN : remonter des lots aux mouvements est
        de la logistique, et le geste est destiné à l'équipe du
        cabinet, qui n'a aucun droit sur `stock.lot`.

        LIMITE CONNUE, dite au rappel lui-même : le lien passe par le
        TRANSFERT de consommation, donc par la clôture de séance. Un
        set sorti à la main — soin d'urgence, sortie manuelle — n'a pas
        de séance à nommer et n'y figure pas.
        """
        self.ensure_one()
        # Le sudo commence ICI, sur les lots : `lot_ids` est un One2many
        # vers stock.lot, ferme a qui n'a pas le magasin — c'est-a-dire
        # a toute l'equipe du cabinet. Le poser une ligne plus bas
        # rendait le rappel inaccessible a ceux a qui il est destine.
        lots = self.sudo().lot_ids
        if not lots:
            return self.env['megga.dental.treatment']
        lignes = self.env['stock.move.line'].sudo().search([
            ('lot_id', 'in', lots.ids),
            ('state', '=', 'done'),
        ])
        pickings = lignes.picking_id
        if not pickings:
            return self.env['megga.dental.treatment']
        # En `sudo` jusqu'au bout : le registre est tenu par le
        # gestionnaire d'équipements, qui n'a aucun droit sur le
        # dentaire. Chercher les séances avec SES droits aurait fait
        # échouer le rappel — le geste central du module — pour la
        # persona même à qui le menu est donné. Ce qui sort d'ici est
        # une liste de RÉFÉRENCES de séances, jamais un dossier : même
        # arbitrage que le mouvement de stock (D7).
        return self.env['megga.dental.treatment'].sudo().search(
            [('supply_picking_id', 'in', pickings.ids)])

    def action_megga_served_treatments(self):
        """Le rappel : les séances servies par cette charge."""
        self.ensure_one()
        servies = self._megga_served_treatments()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Séances servies par %s", self.name),
            'res_model': 'megga.dental.treatment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', servies.ids)],
        }


class MeggaDentalSterilisationLine(models.Model):
    """Un type de set dans la charge, et combien de sachets."""
    _name = 'megga.dental.sterilisation.line'
    _description = "Ligne de charge de stérilisation"
    _order = 'cycle_id, id'

    cycle_id = fields.Many2one(
        'megga.dental.sterilisation.cycle', string="Cycle",
        required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string="Set", required=True,
        ondelete='restrict', index='btree_not_null',
        domain="[('is_storable', '=', True), ('tracking', '=', 'lot')]",
        help="Le sachet stérilisé, tenu en stock et tracé par lot — "
             "c'est ce qui rend la péremption de stérilité et le FEFO "
             "possibles sans une ligne de code de plus.")
    quantity = fields.Float(
        "Sachets", default=1.0, required=True,
        digits='Product Unit of Measure')
    uom_name = fields.Char(related='product_id.uom_id.name', readonly=True)
    lot_ids = fields.One2many(
        'stock.lot', 'sterilisation_line_id', string="Lots produits",
        readonly=True)
    sterility_deadline = fields.Datetime(
        "Stérilité jusqu'au", compute='_compute_sterility_deadline',
        help="Calculée depuis le début du cycle et le délai réglé sur "
             "le produit. C'est la date que porte l'étiquette du "
             "sachet.")

    @api.depends('product_id', 'cycle_id.date_start',
                 'lot_ids.expiration_date')
    def _compute_sterility_deadline(self):
        """La même date que celle posée sur le lot, une seule source.

        Elle vit ICI, sur la ligne de charge, et non seulement sur le
        lot : la personne qui décharge l'autoclave est de l'équipe du
        cabinet et n'a AUCUN droit sur `stock.lot`. Lui montrer la date
        depuis le lot lui aurait fermé sa propre fiche — et lui ouvrir
        `stock.lot` pour cela aurait ouvert tous les lots de la
        société, restaurant compris. La date se recalcule, elle ne se
        déduit pas d'un droit.
        """
        for line in self:
            # Une fois la charge validée, c'est le LOT qui fait foi :
            # sa date est celle qui a été posée à la validation, et
            # elle ne bouge plus. Recalculer aurait fait mentir l'écran
            # dès qu'on change le délai réglé sur le produit — « une
            # seule source » n'aurait pas été vrai.
            #
            # Le lot se retrouve par son LIEN, jamais par son nom :
            # `_megga_lot_name` dépend du rang de la ligne dans la
            # charge, si bien qu'ajouter une ligne faisait cesser la
            # correspondance et retomber en silence sur un recalcul.
            lot = line.sudo().lot_ids[:1]
            line.sterility_deadline = (
                lot.expiration_date if lot
                else line._megga_sterility_deadline())

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.product_id.uom_id.compare(line.quantity, 0) <= 0:
                raise ValidationError(_(
                    "Une ligne de charge sans sachet ne veut rien dire : "
                    "mettez une quantité, ou retirez la ligne."))

    @api.constrains('product_id')
    def _check_tracking(self):
        for line in self:
            if line.product_id.tracking != 'lot':
                raise ValidationError(_(
                    "%s n'est pas tracé par lot : sans lot, aucun "
                    "numéro de cycle ne peut être porté par le sachet, "
                    "et la traçabilité n'existe pas.",
                    line.product_id.display_name))

    def _megga_check_cycle_draft(self, geste):
        """Une charge close ne se retouche pas, ligne par ligne non plus.

        Le gel du cycle ne suffisait pas : ses LIGNES restaient
        modifiables et supprimables, si bien qu'on pouvait réécrire la
        composition d'une charge déjà validée — le registre disait
        alors autre chose que ce qui est sorti de l'autoclave.
        """
        clos = self.filtered(lambda l: l.cycle_id.state != 'draft')
        if clos:
            raise UserError(_(
                "La charge du cycle %(cycle)s est close : sa "
                "composition ne se %(geste)s plus.\n\n"
                "Le registre doit dire ce qui est sorti de "
                "l'autoclave, pas ce qu'on aurait voulu y mettre.",
                cycle=clos[0].cycle_id.name, geste=geste))

    @api.model_create_multi
    def create(self, vals_list):
        lignes = super().create(vals_list)
        # Le gel du cycle ne voyait que le chemin `line_ids` : une
        # ligne creee EN DIRECT sur une charge close passait, et le
        # registre annoncait des sachets qui ne sont jamais entres en
        # rayon.
        lignes._megga_check_cycle_draft(_("complete"))
        return lignes

    def write(self, vals):
        self._megga_check_cycle_draft(_("modifie"))
        return super().write(vals)

    def unlink(self):
        self._megga_check_cycle_draft(_("supprime"))
        return super().unlink()

    def _megga_lot_name(self):
        """Le lot porte le numéro de cycle — c'est l'étiquette.

        Une charge peut contenir plusieurs types de sets : le nom du
        lot les distingue, sans jamais perdre le numéro de cycle qui
        est la clé de la traçabilité.
        """
        self.ensure_one()
        freres = self.cycle_id.line_ids
        if len(freres) == 1:
            return self.cycle_id.name
        rang = list(freres).index(self) + 1
        return "%s-%s" % (self.cycle_id.name, rang)

    def _megga_sterility_deadline(self):
        """La stérilité expire un délai après le CYCLE.

        Le délai est celui du produit (`expiration_time` du cœur, en
        jours) : un sachet pelable ne se garde pas aussi longtemps
        qu'un conteneur. Sans délai réglé, pas de date — le cœur
        traitera le set comme un consommable sans péremption, et la
        garde du magasin ne mordra pas. C'est un réglage du cabinet,
        documenté au README.
        """
        self.ensure_one()
        jours = self.product_id.product_tmpl_id.expiration_time
        if not jours or not self.product_id.use_expiration_date:
            return False
        return self.cycle_id.date_start + timedelta(days=jours)
