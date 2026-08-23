from odoo.addons.megga_rdv.controllers.main import MeggaRdvController


class MeggaRestoRdvController(MeggaRdvController):

    def _reserver_extra_vals(self, rdv_type, kw):
        """Pour un type « réservation de table », le formulaire public
        porte les couverts : on ne laisse passer que cet entier, borné —
        jamais de passage aveugle de kw vers la base."""
        vals = super()._reserver_extra_vals(rdv_type, kw)
        if rdv_type.resto_reservation:
            try:
                couverts = int(kw.get('couverts', 2))
            except (TypeError, ValueError):
                couverts = 2
            vals['resto_party_size'] = max(1, min(couverts, 50))
        return vals
