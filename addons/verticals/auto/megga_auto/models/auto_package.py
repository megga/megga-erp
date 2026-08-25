from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    megga_labor_rate = fields.Float(
        "Taux horaire atelier", digits=(12, 2),
        help="Prix de l'heure de main-d'œuvre facturée. Figé sur chaque "
             "ligne au moment où le forfait est posé sur l'ordre — le "
             "même patron que la valeur du point du cabinet dentaire.")


class MeggaAutoPackage(models.Model):
    """Le forfait d'atelier : un gabarit de prestation — vidange, service
    annuel, pneus — fait d'heures de main-d'œuvre et de pièces. Posé sur
    un ordre de réparation, il copie ses lignes au prix du jour (taux
    horaire de la société, prix de vente des pièces) ; la copie reste
    librement modifiable — le gabarit aide, il n'enferme pas (même
    doctrine que le référentiel de médicaments du dentaire)."""
    _name = 'megga.auto.package'
    _description = "Forfait d'atelier"
    _order = 'name'

    name = fields.Char("Forfait", required=True)
    active = fields.Boolean(default=True)
    note = fields.Text("Remarques")
    line_ids = fields.One2many(
        'megga.auto.package.line', 'package_id',
        string="Contenu", copy=True)
    currency_id = fields.Many2one(
        'res.currency', compute='_compute_price_estimate')
    price_estimate = fields.Monetary(
        "Prix indicatif", compute='_compute_price_estimate',
        currency_field='currency_id',
        help="Au taux horaire et aux prix de vente d'aujourd'hui — le "
             "prix réel se fige ligne par ligne à l'application.")

    # Unicite en python plutot qu'en SQL : le message doit pouvoir dire
    # que l'homonyme est ARCHIVE — sinon l'utilisateur se heurte a un
    # refus qui designe un enregistrement qu'il ne voit nulle part.
    @api.constrains('name', 'active')
    def _check_name_unique(self):
        for package in self:
            jumeau = self.with_context(active_test=False).search(
                [('id', '!=', package.id), ('name', '=', package.name)],
                limit=1)
            if not jumeau:
                continue
            if jumeau.active:
                raise ValidationError(_(
                    "Le forfait « %s » existe déjà.") % package.name)
            raise ValidationError(_(
                "Le forfait « %s » existe déjà mais il est archivé — "
                "réactivez-le au lieu d'en créer un second.")
                % package.name)

    @api.depends('line_ids.kind', 'line_ids.hours', 'line_ids.quantity',
                 'line_ids.product_id.list_price')
    @api.depends_context('company')
    def _compute_price_estimate(self):
        company = self.env.company
        for package in self:
            total = 0.0
            for line in package.line_ids:
                if line.kind == 'labor':
                    total += line.hours * company.megga_labor_rate
                else:
                    total += line.quantity * line.product_id.list_price
            # La devise D'ABORD : un Monetary s'arrondit a la devise au
            # moment ou on l'ecrit — pose avant, il ne s'arrondit pas.
            package.currency_id = company.currency_id
            package.price_estimate = total

    def _apply_to(self, order):
        """Copie les lignes du forfait sur l'ordre, au prix du jour : la
        main-d'œuvre au taux horaire de la société DE L'ORDRE (figé sur
        la ligne — le taux peut changer demain, pas le devis remis), les
        pièces à leur prix de vente courant."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_(
                "Le forfait « %s » n'a aucune ligne — complétez son "
                "contenu avant de le poser sur un ordre.") % self.name)
        rate = order.company_id.megga_labor_rate
        labor_product = self.env.ref('megga_auto.product_labor')
        vals_list = []
        for line in self.line_ids:
            if line.kind == 'labor':
                if rate <= 0:
                    raise UserError(_(
                        "Renseignez le taux horaire atelier (fiche "
                        "Société) avant de poser un forfait avec de la "
                        "main-d'œuvre."))
                vals_list.append({
                    'workorder_id': order.id,
                    'product_id': labor_product.id,
                    'description': line.description,
                    'quantity': line.hours,
                    'price_unit': rate,
                })
            else:
                vals_list.append({
                    'workorder_id': order.id,
                    'product_id': line.product_id.id,
                    'description': line.description
                    or line.product_id.display_name,
                    'quantity': line.quantity,
                    'price_unit': line.product_id.list_price,
                })
        return self.env['megga.auto.workorder.line'].create(vals_list)


class MeggaAutoPackageLine(models.Model):
    _name = 'megga.auto.package.line'
    _description = "Ligne de forfait d'atelier"
    _order = 'package_id, sequence, id'

    package_id = fields.Many2one(
        'megga.auto.package', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection([
        ('labor', "Main-d'œuvre"),
        ('part', "Pièce"),
    ], string="Type", required=True, default='part')
    description = fields.Char(
        "Description",
        compute='_compute_description', store=True, readonly=False,
        precompute=True)
    # restrict : sans cela, supprimer un article viderait la ligne du
    # gabarit en silence — prix indicatif fausse et pose qui echoue.
    product_id = fields.Many2one(
        'product.product', string="Pièce", ondelete='restrict')
    hours = fields.Float("Heures")
    quantity = fields.Float("Quantité", default=1.0)

    @api.constrains('kind', 'product_id', 'hours', 'quantity')
    def _check_content(self):
        for line in self:
            if line.kind == 'labor' and line.hours <= 0:
                raise ValidationError(_(
                    "Une ligne de main-d'œuvre porte un nombre d'heures "
                    "strictement positif."))
            if line.kind == 'part' and not line.product_id:
                raise ValidationError(_(
                    "Une ligne de pièce renvoie à un article."))
            if line.kind == 'part' and line.quantity <= 0:
                raise ValidationError(_(
                    "La quantité d'une pièce est strictement positive."))

    @api.depends('kind', 'product_id')
    def _compute_description(self):
        for line in self:
            if line.kind == 'part':
                if line.product_id:
                    line.description = line.product_id.display_name
            # Bascule piece -> main-d'oeuvre : la designation de la piece
            # ne doit pas survivre. Elle partirait telle quelle sur la
            # facture du client (« Filtre a huile » a 156.- de l'heure).
            # Une designation saisie a la main, elle, est respectee.
            elif not line.description \
                    or line.description == line.product_id.display_name:
                line.description = _("Main-d'œuvre")


class MeggaAutoWorkorder(models.Model):
    _inherit = 'megga.auto.workorder'

    package_to_add_id = fields.Many2one(
        'megga.auto.package', string="Forfait à poser", copy=False,
        help="Choisissez un forfait puis « Poser le forfait » : ses "
             "lignes se copient au prix du jour et restent librement "
             "modifiables.")

    def action_add_package(self):
        for order in self:
            if order.state not in ('draft', 'confirmed'):
                raise UserError(_(
                    "Un ordre terminé ou annulé ne reçoit plus de "
                    "forfait."))
            if not order.package_to_add_id:
                raise UserError(_("Choisissez d'abord un forfait."))
            order.package_to_add_id._apply_to(order)
            order.package_to_add_id = False
        return True
