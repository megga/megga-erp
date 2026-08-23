from odoo import _, api, fields, models


class MeggaRdvType(models.Model):
    _inherit = 'megga.rdv.type'

    dental_patient_creation = fields.Boolean(
        "Créer le dossier patient", default=True,
        help="À la réservation, rattache (ou crée) le dossier patient du "
             "contact. À décocher pour les rendez-vous qui ne sont pas "
             "des soins (réunion d'information, entretien d'embauche…).")


class MeggaRdvBooking(models.Model):
    _inherit = 'megga.rdv.booking'

    patient_id = fields.Many2one(
        'megga.dental.patient', string="Patient", readonly=True,
        copy=False, index=True,
        groups="megga_dental.group_dental_reception")

    @api.model_create_multi
    def create(self, vals_list):
        bookings = super().create(vals_list)
        bookings._dental_link_patient()
        return bookings

    def _dental_link_patient(self):
        """Rattache — ou crée — le dossier patient de chaque réservation.

        - le contact vient de la réservation (créé par e-mail au comptoir
          si la saisie interne n'en a pas fourni) ;
        - la recherche de dossier ignore le filtre d'archivage : un
          patient archivé qui re-réserve est rattaché, jamais dupliqué ;
        - annuler la réservation ne touche évidemment pas au dossier ;
        - en sudo : depuis les groupes LPD, seuls Réception/Soins voient
          les dossiers — mais l'automatisation (réservation publique, ou
          saisie par un utilisateur sans groupe dentaire) doit continuer
          de créer le dossier. Le rattachement est un effet système ; sa
          LECTURE reste gardée par les groupes (champ patient_id compris).
        """
        Patient = self.env['megga.dental.patient'].sudo()
        for booking in self:
            booking_sudo = booking.sudo()
            if booking_sudo.patient_id \
                    or not booking.type_id.dental_patient_creation:
                continue
            booking_sudo._ensure_partner()
            partner = booking_sudo.partner_id
            patient = Patient.with_context(active_test=False).search(
                [('partner_id', '=', partner.id)], limit=1)
            if not patient:
                patient = Patient.create({'partner_id': partner.id})
            booking_sudo.patient_id = patient


class MeggaDentalPatient(models.Model):
    _inherit = 'megga.dental.patient'

    rdv_booking_ids = fields.One2many(
        'megga.rdv.booking', 'patient_id',
        string="Réservations en ligne")
    rdv_booking_count = fields.Integer(
        compute='_compute_rdv_booking_count')

    @api.depends('rdv_booking_ids')
    def _compute_rdv_booking_count(self):
        for patient in self:
            patient.rdv_booking_count = len(patient.rdv_booking_ids)

    def action_view_rdv_bookings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Réservations en ligne"),
            'res_model': 'megga.rdv.booking',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
        }
