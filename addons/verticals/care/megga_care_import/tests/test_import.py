import base64
from datetime import datetime

from odoo import Command
from odoo.tests import TransactionCase
from odoo.tools import file_path


class TestImport(TransactionCase):
    """La reprise de bout en bout, sur les fichiers d'exemple LIVRÉS
    dans docs/ : la documentation reste vraie par construction. Ordre
    des liaisons : clients, prestataires, mandats, événements."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Le fuseau décide de la conversion locale -> UTC des événements.
        cls.env.user.tz = 'Europe/Zurich'

    def _run(self, kind, content):
        wizard = self.env['megga.care.import'].create({
            'kind': kind,
            'file_data': base64.b64encode(content.encode('utf-8')),
            'filename': "%s.tsv" % kind,
        })
        wizard.action_import()
        return wizard

    def _run_doc(self, kind, basename):
        with open(file_path('megga_care_import/docs/%s' % basename),
                  'rb') as handle:
            content = handle.read().decode('utf-8')
        return self._run(kind, content)

    def _reprise_complete(self):
        self._run_doc('patients', 'clients_exemple.tsv')
        self._run_doc('providers', 'prestataires_exemple.tsv')
        self._run_doc('mandates', 'mandats_exemple.tsv')
        return self._run_doc('events', 'evenements_exemple.tsv')

    def test_import_clients_idempotent(self):
        wizard = self._run_doc('patients', 'clients_exemple.tsv')
        self.assertIn("2 créée(s)", wizard.result)
        karim = self.env.ref('__megga_om__.patient_c_001')
        self.assertEqual(karim._name, 'megga.care.patient')
        self.assertEqual(karim.name, "Karim Al-Mansouri")
        self.assertEqual(karim.country_id.code, 'AE')
        self.assertEqual(karim.phone, "+971501234567")
        avant = self.env['megga.care.patient'].search_count([])
        # Ré-import avec un téléphone corrigé : mise à jour, pas de
        # doublon.
        corrige = (
            "N°\tNom\tPrénom\tTéléphone\n"
            "C-001\tAl-Mansouri\tKarim\t+971509999999\n")
        wizard = self._run('patients', corrige)
        self.assertIn("1 mise(s) à jour", wizard.result)
        self.assertEqual(
            self.env['megga.care.patient'].search_count([]), avant)
        self.assertEqual(karim.phone, "+971509999999")

    def test_import_prestataires(self):
        wizard = self._run_doc('providers', 'prestataires_exemple.tsv')
        self.assertIn("2 créée(s)", wizard.result)
        labo = self.env.ref('__megga_om__.provider_p_001')
        self.assertEqual(labo._name, 'res.partner')
        self.assertEqual(labo.supplier_rank, 1)
        self.assertEqual(labo.city, "Genève")

    def test_import_mandats(self):
        self._run_doc('patients', 'clients_exemple.tsv')
        wizard = self._run_doc('mandates', 'mandats_exemple.tsv')
        self.assertIn("2 créée(s)", wizard.result)
        historique = self.env.ref('__megga_om__.mandate_m_2024_018')
        self.assertEqual(historique.state, 'done',
                         "l'historique arrive clôturé")
        self.assertEqual(historique.kind, 'ambulatoire')
        self.assertAlmostEqual(historique.fee_flat, 4500.0)
        self.assertEqual(str(historique.date_start), '2024-07-02')
        en_cours = self.env.ref('__megga_om__.mandate_m_2026_004')
        self.assertEqual(en_cours.state, 'confirmed')
        self.assertEqual(en_cours.kind, 'hospitalise')
        # Client inconnu : rejet motivé, rien de créé.
        rejet = self._run('mandates',
                          "N°\tClient\tDébut\nM-X\tC-999\t01.01.2026\n")
        self.assertIn("1 rejetée(s)", rejet.result)
        self.assertIn("C-999", rejet.result)
        self.assertFalse(self.env.ref(
            '__megga_om__.mandate_m_x', raise_if_not_found=False))

    def test_import_evenements(self):
        wizard = self._reprise_complete()
        self.assertIn("3 créée(s)", wizard.result)
        labo = self.env.ref(
            '__megga_om__.event_m_2024_018_2024_07_08_'
            'petit_laboratoire_de_check_up')
        self.assertEqual(labo.service_type_id.code, 'LABO')
        self.assertAlmostEqual(labo.price_client, 500.0)
        self.assertAlmostEqual(labo.cost_price, 450.0)
        self.assertAlmostEqual(labo.margin, 50.0)
        # 08:00 à Genève un 8 juillet (heure d'été) = 06:00 UTC.
        self.assertEqual(labo.date, datetime(2024, 7, 8, 6, 0, 0))
        self.assertEqual(labo.provider_id.name,
                         "Laboratoire Central Genève",
                         "le prestataire importé en amont est rapproché")
        radio = self.env.ref(
            '__megga_om__.event_m_2024_018_2024_07_08_'
            'trois_examens_de_base')
        self.assertAlmostEqual(radio.duration, 1.5)
        self.assertIn("Institut de Radiologie", wizard.result,
                      "prestataire inconnu : créé et signalé au rapport")
        # Ré-import : clés dérivées stables, tout en mise à jour.
        rejoue = self._run_doc('events', 'evenements_exemple.tsv')
        self.assertIn("0 créée(s), 3 mise(s) à jour", rejoue.result)

    def test_rejets_motives(self):
        self._reprise_complete()
        entete = "Mandat\tDate\tLibellé\tType\tPrix client\n"
        rejets = self._run('events', entete + "\n".join((
            "M-2024-018\t31.02.2024\tDate impossible\tLABO\t100",
            "M-2024-018\t01.08.2024\tType inconnu\tOSTEO\t100",
            "M-2024-018\t01.08.2024\tMontant illisible\tLABO\tcent",
            "M-2024-018\t01.08.2024\t\tLABO\t100",
        )) + "\n")
        self.assertIn("4 rejetée(s)", rejets.result)
        self.assertIn("date impossible", rejets.result.lower())
        self.assertIn("OSTEO", rejets.result)
        self.assertIn("référentiel", rejets.result)
        self.assertIn("montant illisible", rejets.result.lower())
        self.assertIn("libellé manquant", rejets.result.lower())

    def test_historique_ne_pollue_pas(self):
        """Le mandat repris clôturé porte des événements à prix sans
        facture re-migrée : il ne doit compter ni dans « à facturer »
        ni dans les pièces attendues — un mandat en cours, si."""
        self._reprise_complete()
        historique = self.env.ref('__megga_om__.mandate_m_2024_018')
        self.assertTrue(historique.event_ids)
        self.assertEqual(historique.unbilled_event_count, 0)
        self.assertEqual(historique.uncovered_cost_count, 0)
        vivant = self.env['megga.care.mandate'].create({
            'patient_id': self.env.ref('__megga_om__.patient_c_001').id,
            'state': 'confirmed',
            'event_ids': [Command.create({
                'name': "Consultation à facturer",
                'service_type_id': self.env.ref(
                    'megga_care.service_type_consultation').id,
                'date': '2026-08-24 08:00:00',
                'price_client': 800.0,
                'cost_price': 760.0,
            })],
        })
        self.assertEqual(vivant.unbilled_event_count, 1)
        self.assertEqual(vivant.uncovered_cost_count, 1)
