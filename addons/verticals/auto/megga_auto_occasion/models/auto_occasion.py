from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from ..occasion_logic import fictive_input_tax, margin_vat, vat_from_gross


class MeggaAutoOccasion(models.Model):
    """Une occasion, de la reprise à la revente.

    Le véhicule est repris (souvent à un particulier, donc sans TVA),
    entre au stock, puis se revend — et le nouveau propriétaire entre au
    parc clients. Deux régimes de TVA, choisis à la fiche :

    - fictif (défaut, art. 28a LTVA) : reprise avec impôt préalable
      fictif extrait du prix, revente TTC au taux plein — la charge
      nette est la TVA de la marge ;
    - marge (art. 24a LTVA, pièces de collection) : TVA due sur la
      marge seule, pas de déduction fictive, facture de vente SANS
      mention de TVA (la mentionner rendrait tout le montant dû) — la
      TVA de la marge se déclare au décompte (prix de vente au
      chiffre 200, prix d'achat en déduction).
    """
    _name = 'megga.auto.occasion'
    _description = "Véhicule d'occasion (reprise et revente)"
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(
        "Référence", readonly=True, copy=False, default='/')
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string="Véhicule", required=True,
        ondelete='restrict', index=True)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    regime = fields.Selection([
        ('fictif', "Impôt préalable fictif (art. 28a LTVA)"),
        ('marge', "Imposition de la marge (art. 24a LTVA)"),
    ], string="Régime TVA", default='fictif', required=True,
        tracking=True,
        help="Fictif : la voie ordinaire de l'occasion reprise à un "
             "particulier. Marge : réservée aux pièces de collection "
             "(véhicules de collection) — TVA sur la marge seule et "
             "facture de vente sans mention de TVA.")
    state = fields.Selection([
        ('draft', "Reprise à négocier"),
        ('stock', "Au stock"),
        ('sold', "Vendu"),
    ], string="État", default='draft', required=True, copy=False,
        tracking=True)

    seller_id = fields.Many2one(
        'res.partner', string="Vendeur (reprise)")
    buy_date = fields.Date("Date de reprise")
    buy_price = fields.Monetary(
        "Prix de reprise", currency_field='currency_id',
        help="Prix payé au vendeur — réputé TVA comprise en régime "
             "fictif.")
    purchase_bill_id = fields.Many2one(
        'account.move', string="Facture de reprise", readonly=True,
        copy=False)

    buyer_id = fields.Many2one(
        'res.partner', string="Acheteur")
    sale_date = fields.Date("Date de vente")
    sale_price = fields.Monetary(
        "Prix de revente", currency_field='currency_id',
        help="En régime fictif : TTC. En régime de la marge : montant "
             "facturé sans mention de TVA.")
    sale_invoice_id = fields.Many2one(
        'account.move', string="Facture de vente", readonly=True,
        copy=False)

    fictive_tax_amount = fields.Monetary(
        "Impôt préalable fictif", compute='_compute_vat_amounts',
        currency_field='currency_id')
    sale_vat_amount = fields.Monetary(
        "TVA due à la revente", compute='_compute_vat_amounts',
        currency_field='currency_id')
    net_vat_amount = fields.Monetary(
        "Charge nette de TVA", compute='_compute_vat_amounts',
        currency_field='currency_id',
        help="TVA due à la revente moins l'impôt préalable fictif : la "
             "TVA de la marge, par construction.")
    margin_amount = fields.Monetary(
        "Marge", compute='_compute_vat_amounts',
        currency_field='currency_id')
    margin_vat_amount = fields.Monetary(
        "TVA sur la marge", compute='_compute_vat_amounts',
        currency_field='currency_id',
        help="À déclarer au décompte (art. 24a LTVA) — marge négative : "
             "rien, et jamais de crédit.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'megga.auto.occasion') or '/'
        return super().create(vals_list)

    def _vat_rate(self):
        self.ensure_one()
        tax = self.env['account.chart.template'].with_company(
            self.company_id).ref('vat_sale_81', raise_if_not_found=False)
        return tax.amount if tax else 8.1

    @api.depends('buy_price', 'sale_price', 'regime')
    def _compute_vat_amounts(self):
        for occasion in self:
            rate = occasion._vat_rate()
            buy = occasion.buy_price
            sale = occasion.sale_price
            if occasion.regime == 'fictif':
                occasion.fictive_tax_amount = fictive_input_tax(buy, rate)
                occasion.sale_vat_amount = (
                    vat_from_gross(sale, rate) if sale > 0 else 0.0)
                occasion.net_vat_amount = (
                    occasion.sale_vat_amount - occasion.fictive_tax_amount)
                occasion.margin_amount = 0.0
                occasion.margin_vat_amount = 0.0
            else:
                occasion.fictive_tax_amount = 0.0
                occasion.sale_vat_amount = 0.0
                occasion.net_vat_amount = 0.0
                occasion.margin_amount = sale - buy
                occasion.margin_vat_amount = margin_vat(buy, sale, rate)

    def _occasion_taxes(self):
        """(taxe de vente TTC, taxe fictive) — UserError sans plan CH."""
        self.ensure_one()
        taxes = self.company_id._megga_setup_occasion_taxes()
        if not taxes:
            raise UserError(_(
                "Le plan comptable suisse manque sur la société %s : "
                "installez la localisation (pays Suisse) avant de "
                "facturer des occasions.") % self.company_id.name)
        return taxes

    def _vehicle_label(self):
        self.ensure_one()
        label = self.vehicle_id.display_name
        if self.vehicle_id.vin_sn:
            label = "%s — châssis %s" % (label, self.vehicle_id.vin_sn)
        return label

    def action_buy(self):
        for occasion in self:
            if occasion.state != 'draft':
                raise UserError(_("Cette occasion est déjà au stock."))
            if not occasion.seller_id or occasion.buy_price <= 0:
                raise UserError(_(
                    "Renseignez le vendeur et le prix de reprise."))
            occasion.write({
                'state': 'stock',
                'buy_date': occasion.buy_date
                or fields.Date.context_today(occasion),
            })

    def action_sell(self):
        for occasion in self:
            if occasion.state != 'stock':
                raise UserError(_(
                    "Seule une occasion au stock peut être vendue."))
            if not occasion.buyer_id or occasion.sale_price <= 0:
                raise UserError(_(
                    "Renseignez l'acheteur et le prix de revente."))
            occasion.write({
                'state': 'sold',
                'sale_date': occasion.sale_date
                or fields.Date.context_today(occasion),
            })
            # Effet système en sudo : le nouveau propriétaire entre au
            # parc clients, quel que soit le droit fleet du vendeur.
            occasion.vehicle_id.sudo().megga_owner_id = occasion.buyer_id
            occasion.message_post(body=_(
                "Vendu à %s — le véhicule change de propriétaire au "
                "parc.") % occasion.buyer_id.display_name)

    def action_create_purchase_bill(self):
        self.ensure_one()
        if self.state == 'draft':
            raise UserError(_("Entrez d'abord l'occasion au stock."))
        if self.purchase_bill_id:
            raise UserError(_(
                "La reprise est déjà facturée (%s).")
                % self.purchase_bill_id.display_name)
        if self.regime == 'fictif':
            _sale_ttc, fictive = self._occasion_taxes()
            tax_commands = [Command.set(fictive.ids)]
        else:
            # Art. 24a : pas de déduction de l'impôt préalable fictif.
            tax_commands = []
        move = self.env['account.move'].with_company(self.company_id).create({
            'move_type': 'in_invoice',
            'partner_id': self.seller_id.id,
            'invoice_date': self.buy_date
            or fields.Date.context_today(self),
            'invoice_origin': self.name,
            'invoice_line_ids': [Command.create({
                'name': _("Reprise %s") % self._vehicle_label(),
                'quantity': 1.0,
                'price_unit': self.buy_price,
                'tax_ids': tax_commands,
            })],
        })
        self.purchase_bill_id = move
        self.message_post(
            body=_("Facture de reprise %s créée.") % move.display_name)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
        }

    def action_create_sale_invoice(self):
        self.ensure_one()
        if self.state != 'sold':
            raise UserError(_("Vendez d'abord l'occasion."))
        if self.sale_invoice_id:
            raise UserError(_(
                "La vente est déjà facturée (%s).")
                % self.sale_invoice_id.display_name)
        vals = {
            'move_type': 'out_invoice',
            'partner_id': self.buyer_id.id,
            'invoice_date': self.sale_date
            or fields.Date.context_today(self),
            'invoice_origin': self.name,
        }
        if self.regime == 'fictif':
            sale_ttc, _fictive = self._occasion_taxes()
            tax_commands = [Command.set(sale_ttc.ids)]
        else:
            # Art. 24a : la facture NE MENTIONNE PAS la TVA.
            tax_commands = []
            vals['narration'] = _(
                "Imposition de la marge (art. 24a LTVA) : la présente "
                "facture ne mentionne pas la TVA.")
        vals['invoice_line_ids'] = [Command.create({
            'name': _("Véhicule d'occasion — %s") % self._vehicle_label(),
            'quantity': 1.0,
            'price_unit': self.sale_price,
            'tax_ids': tax_commands,
        })]
        move = self.env['account.move'].with_company(
            self.company_id).create(vals)
        self.sale_invoice_id = move
        self.message_post(
            body=_("Facture de vente %s créée.") % move.display_name)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
        }
