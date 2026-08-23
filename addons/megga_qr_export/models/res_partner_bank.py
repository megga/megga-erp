from odoo import _, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    def _l10n_ch_qr_debtor_check(self, debtor_partner):
        """Norme SIX (Implementation Guidelines QR-bill) : seul le compte du
        CRÉANCIER doit être en CH/LI ; le débiteur peut être domicilié dans
        n'importe quel pays. La restriction CH/LI d'Odoo sur le débiteur est
        plus stricte que la norme : on la lève.

        Ce qu'on conserve :
        - sans partenaire, le comportement amont (la méthode reste
          sélectionnable avant choix du client, l'impression reste bloquée) ;
        - un pays est exigé sur l'adresse : son code alimente le champ
          « Ultimate Debtor Country » de la charge utile SPC ;
        - la complétude d'adresse (rue, NPA, localité, pays) reste contrôlée
          par _check_for_qr_code_errors, en amont de cet appel.
        """
        if not debtor_partner:
            return super()._l10n_ch_qr_debtor_check(debtor_partner)
        if not debtor_partner.country_id:
            return _("The debtor partner must have a country set on their address.")
        return False
