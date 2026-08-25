from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestInsurance(AccountTestInvoicingCommon):
    """Le tiers payant : l'assureur paie le cabinet directement. AA/AI/AM
    au tarif de la convention avec numéro de sinistre obligatoire ;
    LAMal/LCA sur garantie écrite — « pas de garantie, pas de tiers
    payant ». En tiers garant, rien ne change : le patient reste le
    destinataire de la facture."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ch')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids = [(4, cls.env.ref(
            'megga_dental.group_dental_praticien').id)]
        cls.env.company.sudo().dental_point_value = 1.15
        cls.patient = cls.env['megga.dental.patient'].create({
            'name': "Ana Sinistre"})
        cls.voisin = cls.env['megga.dental.patient'].create({
            'name': "Bob Voisin"})
        cls.insurer = cls.env['megga.dental.insurer'].create({
            'name': "Assurance Helvetia Demo",
            'city': "Lausanne"})
        cls.position = cls.env['megga.dental.position'].create({
            'code': "9101", 'name': "Soin post-accident (fictif)",
            'points': 100.0, 'chapter': "Exemple"})

    def _case(self, **kw):
        vals = {
            'patient_id': self.patient.id,
            'insurer_id': self.insurer.id,
            'regime': 'aa',
        }
        vals.update(kw)
        return self.env['megga.dental.insurance.case'].create(vals)

    def _treatment(self, **kw):
        vals = {
            'patient_id': self.patient.id,
            'date': '2026-09-07',
            'line_ids': [Command.create({'position_id': self.position.id})],
        }
        vals.update(kw)
        return self.env['megga.dental.treatment'].create(vals)

    def _done(self, treatment):
        treatment.action_confirm()
        treatment.action_done()
        return treatment

    def test_assureur_est_un_partner_societe(self):
        self.assertTrue(self.insurer.partner_id)
        self.assertTrue(self.insurer.partner_id.is_company)
        self.assertEqual(self.insurer.partner_id.city, "Lausanne")

    def test_sequence_et_mode_par_defaut(self):
        cas_aa = self._case(regime='aa')
        self.assertTrue(cas_aa.name.startswith("CAS/"))
        self.assertEqual(cas_aa.payment_mode, 'payant',
                         "AA/AI/AM : tiers payant de droit")
        cas_lca = self._case(regime='lca')
        self.assertEqual(cas_lca.payment_mode, 'garant',
                         "LCA : tiers garant tant que rien n'est garanti")

    def test_activation_sociale_exige_le_numero_de_sinistre(self):
        cas = self._case(regime='aa')
        with self.assertRaises(UserError):
            cas.action_activate()
        cas.claim_number = "LAA-2026-4711"
        cas.action_activate()
        self.assertEqual(cas.state, 'active')

    def test_activation_lca_payant_exige_la_garantie(self):
        cas = self._case(regime='lca', payment_mode='payant')
        with self.assertRaises(UserError):
            cas.action_activate()
        cas.write({'guarantee_amount': 2500.0,
                   'guarantee_date': '2026-09-01'})
        cas.action_activate()
        self.assertEqual(cas.state, 'active')

    def test_activation_lca_garant_sans_garantie(self):
        cas = self._case(regime='lca')
        cas.action_activate()
        self.assertEqual(cas.state, 'active',
                         "en tiers garant le patient avance : rien à exiger")

    def test_dossier_du_voisin_refuse(self):
        cas = self._case(claim_number="LAA-1")
        with self.assertRaises(ValidationError):
            self._treatment(patient_id=self.voisin.id,
                            tariff_kind='social',
                            insurance_case_id=cas.id)

    def test_dossier_social_exige_le_tarif_conventionnel(self):
        cas = self._case(regime='aa')
        with self.assertRaises(ValidationError):
            self._treatment(tariff_kind='prive', insurance_case_id=cas.id)
        traitement = self._treatment(tariff_kind='social',
                                     insurance_case_id=cas.id)
        self.assertEqual(traitement.point_value, 1.0,
                         "valeur du point de la convention")

    def test_facture_tiers_payant_part_chez_l_assureur(self):
        cas = self._case(claim_number="LAA-2026-4711")
        cas.action_activate()
        traitement = self._done(self._treatment(
            tariff_kind='social', insurance_case_id=cas.id))
        traitement.action_create_invoice()
        facture = traitement.invoice_id
        self.assertEqual(facture.partner_id, self.insurer.partner_id,
                         "tiers payant : le destinataire est l'assureur")
        self.assertIn("LAA-2026-4711", facture.ref)
        self.assertIn("Ana Sinistre", facture.ref)
        self.assertEqual(facture.invoice_origin, traitement.name)

    def test_facture_tiers_garant_reste_au_patient(self):
        cas = self._case(regime='lca')
        cas.action_activate()
        traitement = self._done(self._treatment(insurance_case_id=cas.id))
        traitement.action_create_invoice()
        self.assertEqual(traitement.invoice_id.partner_id,
                         self.patient.partner_id,
                         "tiers garant : le patient avance les frais")
        self.assertFalse(traitement.invoice_id.ref)

    def test_facturation_bloquee_sans_prise_en_charge_confirmee(self):
        cas = self._case(claim_number="LAA-9")
        traitement = self._done(self._treatment(
            tariff_kind='social', insurance_case_id=cas.id))
        with self.assertRaises(UserError):
            traitement.action_create_invoice()
        cas.action_activate()
        cas.action_close()
        with self.assertRaises(UserError):
            traitement.action_create_invoice()

    def test_totaux_du_dossier(self):
        cas = self._case(claim_number="LAA-77")
        cas.action_activate()
        t1 = self._done(self._treatment(
            tariff_kind='social', insurance_case_id=cas.id))
        t1.action_create_invoice()
        self.assertEqual(cas.treatment_count, 1)
        self.assertEqual(cas.amount_invoiced,
                         t1.invoice_id.amount_total)

    def test_plan_propage_le_dossier(self):
        cas = self._case(claim_number="AI-2026-08")
        cas.regime = 'ai'
        plan = self.env['megga.dental.plan'].create({
            'patient_id': self.patient.id,
            'tariff_kind': 'social',
            'insurance_case_id': cas.id,
        })
        phase = self.env['megga.dental.plan.phase'].create({
            'plan_id': plan.id, 'name': "Assainissement"})
        self.assertEqual(phase.treatment_id.insurance_case_id, cas)
        self.assertEqual(phase.treatment_id.tariff_kind, 'social')

    def test_plan_dossier_du_voisin_refuse(self):
        cas = self._case()
        with self.assertRaises(ValidationError):
            self.env['megga.dental.plan'].create({
                'patient_id': self.voisin.id,
                'tariff_kind': 'social',
                'insurance_case_id': cas.id,
            })

    def test_reception_gere_les_dossiers(self):
        reception = self.env['res.users'].create({
            'name': "Réception Assurances", 'login': "assur_reception",
            'email': "assur.reception@exemple.ch",
            'group_ids': [(4, self.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        Case = self.env['megga.dental.insurance.case'].with_user(reception)
        cas = Case.create({
            'patient_id': self.patient.id,
            'insurer_id': self.insurer.id,
            'regime': 'aa',
            'claim_number': "LAA-RECEPTION",
        })
        cas.action_activate()
        self.assertEqual(cas.state, 'active',
                         "les dossiers d'assurance sont l'administratif "
                         "de la facturation : la réception les tient")

    def test_dossier_avec_traitements_ne_se_supprime_pas(self):
        cas = self._case(claim_number="LAA-DEL")
        cas.action_activate()
        self._treatment(tariff_kind='social', insurance_case_id=cas.id)
        with self.assertRaises(UserError):
            cas.unlink()
