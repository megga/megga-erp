from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase


class TestPlan(TransactionCase):
    """Plans de traitement par phases : chaque phase porte son
    traitement (créé en devis à l'ajout), l'ordre clinique est garanti
    (une phase ne se lance que quand les précédentes sont soldées),
    le plan chiffre l'ensemble, suit l'avancement et s'achève tout
    seul. Diagnostic réservé aux Soins (LPD)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        cls.reception = Users.create({
            'name': "Réception Plan", 'login': "plan_reception",
            'email': "plan.reception@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        cls.soins = Users.create({
            'name': "Soins Plan", 'login': "plan_soins",
            'email': "plan.soins@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_praticien').id)],
        })
        cls.patient = cls.env['megga.dental.patient'].create({
            'name': "Pierre Phasé",
        })
        Position = cls.env['megga.dental.position']
        cls.pos_50 = Position.create({
            'code': 'PLAN-50', 'name': "Assainissement", 'points': 50.0})
        cls.pos_30 = Position.create({
            'code': 'PLAN-30', 'name': "Prothèse", 'points': 30.0})

    def _plan(self, **kw):
        return self.env['megga.dental.plan'].create({
            'patient_id': self.patient.id, **kw})

    def _phase(self, plan, name, sequence):
        return self.env['megga.dental.plan.phase'].create({
            'plan_id': plan.id, 'name': name, 'sequence': sequence})

    def _line(self, phase, position):
        return self.env['megga.dental.treatment.line'].create({
            'treatment_id': phase.treatment_id.id,
            'position_id': position.id,
        })

    def test_sequence_et_phase_cree_son_traitement(self):
        plan = self._plan()
        self.assertTrue(plan.name.startswith("PLAN/"))
        phase = self._phase(plan, "Assainissement", 10)
        treatment = phase.treatment_id
        self.assertTrue(treatment)
        self.assertEqual(treatment.state, 'draft')
        self.assertEqual(treatment.patient_id, self.patient)
        self.assertEqual(treatment.dentist_id, plan.dentist_id)
        self.assertEqual(phase.state, 'draft')
        self.assertEqual(treatment.plan_id, plan)

    def test_tarif_social_propage(self):
        plan = self._plan(tariff_kind='social')
        phase = self._phase(plan, "Chirurgie AA", 10)
        self.assertEqual(phase.treatment_id.tariff_kind, 'social')
        self.assertEqual(phase.treatment_id.point_value, 1.0)

    def test_devis_global_et_avancement(self):
        plan = self._plan()
        p1 = self._phase(plan, "Assainissement", 10)
        p2 = self._phase(plan, "Prothèse", 20)
        self._line(p1, self.pos_50)
        self._line(p2, self.pos_30)
        self.assertEqual(plan.amount_total, 80.0)
        self.assertEqual(plan.progress, 0)
        plan.action_accept()
        p1.action_start()
        p1.treatment_id.action_done()
        self.assertEqual(plan.progress, 50)

    def test_ordre_clinique(self):
        plan = self._plan()
        p1 = self._phase(plan, "Assainissement", 10)
        p2 = self._phase(plan, "Prothèse", 20)
        self._line(p1, self.pos_50)
        self._line(p2, self.pos_30)
        plan.action_accept()
        with self.assertRaises(UserError) as capture:
            p2.action_start()
        self.assertIn("Assainissement", str(capture.exception))
        p1.action_start()
        with self.assertRaises(UserError):
            p2.action_start()
        p1.treatment_id.action_done()
        p2.action_start()
        self.assertEqual(p2.state, 'confirmed')

    def test_plan_non_accepte_ne_se_lance_pas(self):
        plan = self._plan()
        phase = self._phase(plan, "Assainissement", 10)
        self._line(phase, self.pos_50)
        with self.assertRaises(UserError):
            phase.action_start()

    def test_accepter_exige_une_phase(self):
        plan = self._plan()
        with self.assertRaises(UserError):
            plan.action_accept()

    def test_phase_annulee_ne_bloque_pas(self):
        plan = self._plan()
        p1 = self._phase(plan, "Option refusée", 10)
        p2 = self._phase(plan, "Prothèse", 20)
        self._line(p1, self.pos_50)
        self._line(p2, self.pos_30)
        plan.action_accept()
        p1.treatment_id.action_cancel()
        p2.action_start()
        self.assertEqual(p2.state, 'confirmed')

    def test_achevement_automatique(self):
        plan = self._plan()
        p1 = self._phase(plan, "Assainissement", 10)
        p2 = self._phase(plan, "Prothèse", 20)
        self._line(p1, self.pos_50)
        self._line(p2, self.pos_30)
        plan.action_accept()
        p1.action_start()
        p1.treatment_id.action_done()
        self.assertEqual(plan.state, 'accepted')
        # La seconde phase est abandonnée : tout est soldé, une phase a
        # été menée au bout -> le plan s'achève tout seul.
        p2.treatment_id.action_cancel()
        self.assertEqual(plan.state, 'done')

    def test_abandon_garde_l_acquis(self):
        plan = self._plan()
        p1 = self._phase(plan, "Assainissement", 10)
        p2 = self._phase(plan, "Prothèse", 20)
        self._line(p1, self.pos_50)
        self._line(p2, self.pos_30)
        plan.action_accept()
        p1.action_start()
        p1.treatment_id.action_done()
        plan.action_cancel()
        self.assertEqual(plan.state, 'cancelled')
        self.assertEqual(p1.treatment_id.state, 'done')
        self.assertEqual(p2.treatment_id.state, 'cancelled')

    def test_suppressions_gardees(self):
        plan = self._plan()
        phase = self._phase(plan, "Assainissement", 10)
        self._line(phase, self.pos_50)
        plan.action_accept()
        phase.action_start()
        with self.assertRaises(UserError):
            phase.unlink()
        with self.assertRaises(UserError):
            plan.unlink()
        # Un plan encore au stade de la proposition se supprime, lui.
        brouillon = self._plan()
        self._phase(brouillon, "Idée", 10)
        brouillon.unlink()
        self.assertFalse(brouillon.exists())

    def test_lpd_diagnostic_reserve_aux_soins(self):
        plan = self._plan()
        phase = self._phase(plan, "Assainissement", 10)
        self._line(phase, self.pos_50)
        plan.with_user(self.soins).diagnosis = "Parodontite généralisée"
        vu = plan.with_user(self.reception)
        self.assertEqual(vu.amount_total, 50.0)   # la réception chiffre
        with self.assertRaises(AccessError):
            vu.read(['diagnosis'])
        with self.assertRaises(AccessError):
            vu.unlink()
