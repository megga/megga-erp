import json

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase


class TestOdontogram(TransactionCase):
    """L'odontogramme : constats par dent et par surface, alimentés à la
    main ou par les actes à la clôture du traitement, lus par la charge
    JSON du widget. Modèle 100 % clinique : la réception n'y a AUCUN
    droit (LPD), et c'est testé."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        cls.reception = Users.create({
            'name': "Réception Odonto", 'login': "odo_reception",
            'email': "odo.reception@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_reception').id)],
        })
        cls.soins = Users.create({
            'name': "Soins Odonto", 'login': "odo_soins",
            'email': "odo.soins@exemple.ch",
            'group_ids': [(4, cls.env.ref(
                'megga_dental.group_dental_praticien').id)],
        })
        cls.patient = cls.env['megga.dental.patient'].create({
            'name': "Olga Constat",
        })
        Tooth = cls.env['megga.dental.tooth']
        cls.t16 = Tooth.search([('number', '=', 16)])
        cls.t26 = Tooth.search([('number', '=', 26)])
        cls.t36 = Tooth.search([('number', '=', 36)])
        cls.t37 = Tooth.search([('number', '=', 37)])
        cls.t55 = Tooth.search([('number', '=', 55)])
        Position = cls.env['megga.dental.position']
        cls.pos_obturation = Position.create({
            'code': 'ODO-OBT', 'name': "Obturation composite",
            'points': 31.0, 'condition': 'obturation',
        })
        cls.pos_controle = Position.create({
            'code': 'ODO-CTRL', 'name': "Contrôle périodique",
            'points': 10.0,
        })

    def _record(self, tooth, condition, day, surface=False, **kw):
        return self.env['megga.dental.tooth.record'].create({
            'patient_id': self.patient.id,
            'tooth_id': tooth.id,
            'condition': condition,
            'surface': surface,
            'date': day,
            **kw,
        })

    def _payload(self):
        return json.loads(self.patient.odontogram_json)

    def test_json_vierge(self):
        payload = self._payload()
        self.assertFalse(payload['deciduous'])
        self.assertEqual(len(payload['teeth']), 52)
        self.assertIsNone(payload['teeth']['16']['tooth'])
        self.assertEqual(payload['teeth']['16']['surfaces'], {})
        carie = next(
            item for item in payload['legend'] if item['code'] == 'carie')
        self.assertEqual(carie['color'], "#C0392B")
        self.assertEqual(carie['label'], "Carie")

    def test_le_dernier_constat_gagne_par_surface(self):
        self._record(self.t16, 'carie', '2026-01-10', surface='M')
        self._record(self.t16, 'carie', '2026-01-10', surface='D')
        self._record(self.t16, 'obturation', '2026-03-01', surface='M')
        teeth = self._payload()['teeth']
        self.assertEqual(teeth['16']['surfaces']['M'], 'obturation')
        self.assertEqual(teeth['16']['surfaces']['D'], 'carie')
        self.assertIsNone(teeth['16']['tooth'])

    def test_meme_date_le_dernier_cree_gagne(self):
        self._record(self.t26, 'a_surveiller', '2026-05-02', surface='V')
        self._record(self.t26, 'carie', '2026-05-02', surface='V')
        self.assertEqual(
            self._payload()['teeth']['26']['surfaces']['V'], 'carie')

    def test_constat_dent_entiere(self):
        self._record(self.t36, 'absente', '2026-02-14')
        tooth = self._payload()['teeth']['36']
        self.assertEqual(tooth['tooth'], 'absente')
        self.assertEqual(tooth['surfaces'], {})

    def test_dent_de_lait_detectee(self):
        self.assertFalse(self._payload()['deciduous'])
        self._record(self.t55, 'carie', '2026-04-01', surface='O')
        payload = self._payload()
        self.assertTrue(payload['deciduous'])
        self.assertEqual(payload['teeth']['55']['surfaces']['O'], 'carie')

    def _treatment(self, lines):
        return self.env['megga.dental.treatment'].create({
            'patient_id': self.patient.id,
            'date': '2026-08-20',
            'line_ids': lines,
        })

    def test_acte_termine_inscrit_les_constats(self):
        treatment = self._treatment([
            Command.create({
                'position_id': self.pos_obturation.id,
                'tooth_ids': [Command.set((self.t36 + self.t37).ids)],
            }),
            # Position sans constat configuré : ne doit rien inscrire.
            Command.create({
                'position_id': self.pos_controle.id,
                'tooth_ids': [Command.set(self.t16.ids)],
            }),
        ])
        treatment.action_confirm()
        treatment.action_done()
        records = self.env['megga.dental.tooth.record'].search(
            [('patient_id', '=', self.patient.id)])
        self.assertEqual(len(records), 2)
        self.assertEqual(set(records.tooth_id.ids), set((self.t36 + self.t37).ids))
        for record in records:
            self.assertEqual(record.condition, 'obturation')
            self.assertEqual(str(record.date), '2026-08-20')
            self.assertEqual(record.line_id.treatment_id, treatment)
            self.assertEqual(record.dentist_id, treatment.dentist_id)
            self.assertFalse(record.surface)
        teeth = self._payload()['teeth']
        self.assertEqual(teeth['36']['tooth'], 'obturation')
        self.assertIsNone(teeth['16']['tooth'])

    def test_acte_sans_dent_n_inscrit_rien(self):
        treatment = self._treatment([
            Command.create({'position_id': self.pos_obturation.id}),
        ])
        treatment.action_confirm()
        treatment.action_done()
        self.assertFalse(self.env['megga.dental.tooth.record'].search(
            [('patient_id', '=', self.patient.id)]))

    def test_reception_aveugle(self):
        self._record(self.t16, 'carie', '2026-01-10', surface='M')
        Record = self.env['megga.dental.tooth.record'].with_user(
            self.reception)
        with self.assertRaises(AccessError):
            Record.search([])
        with self.assertRaises(AccessError):
            Record.create({
                'patient_id': self.patient.id,
                'tooth_id': self.t16.id,
                'condition': 'carie',
            })
        with self.assertRaises(AccessError):
            self.patient.with_user(self.reception).read(['odontogram_json'])

    def test_reception_termine_la_seance_sans_voir_les_constats(self):
        # La réception clôt une séance : l'inscription des constats est
        # un effet SYSTÈME (sudo dans le flux) — elle réussit sans le
        # moindre droit sur le modèle, et la lecture reste fermée.
        treatment = self._treatment([
            Command.create({
                'position_id': self.pos_obturation.id,
                'tooth_ids': [Command.set(self.t36.ids)],
            }),
        ])
        as_reception = treatment.with_user(self.reception)
        as_reception.action_confirm()
        as_reception.action_done()
        records = self.env['megga.dental.tooth.record'].search(
            [('patient_id', '=', self.patient.id)])
        self.assertEqual(len(records), 1)
        self.assertEqual(records.tooth_id, self.t36)
        with self.assertRaises(AccessError):
            records.with_user(self.reception).read(['condition'])

    def test_soins_tiennent_les_constats(self):
        record = self.env['megga.dental.tooth.record'].with_user(
            self.soins).create({
                'patient_id': self.patient.id,
                'tooth_id': self.t26.id,
                'condition': 'couronne',
            })
        self.assertEqual(record.display_name, "26 — Couronne")
        payload = json.loads(self.patient.with_user(
            self.soins).odontogram_json)
        self.assertEqual(payload['teeth']['26']['tooth'], 'couronne')
