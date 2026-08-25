from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestRelance(AccountTestInvoicingCommon):
    """Le cycle des rappels : la proposition quotidienne, le
    regroupement par client, le marquage qui empêche le doublon, et
    l'envoi qui trace.

    Décor comptable GÉNÉRIQUE, à dessein : relancer un impayé n'a rien
    de suisse. Un décor `setup_country('ch')` aurait porté le tag
    `post_install_l10n`, et ces tests auraient été ignorés en silence
    partout où la localisation n'est pas installée (vécu au premier
    run : 6 tests sur 23, rattrapé par le garde-fou du harnais)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Niveau = cls.env['megga.relance.niveau']
        cls.premier = Niveau.create({
            'name': "1er rappel", 'delay_days': 10,
            'subject': "Rappel de facture",
            'body': "Sauf erreur, la facture ci-dessous reste ouverte."})
        cls.second = Niveau.create({
            'name': "2e rappel", 'delay_days': 30,
            'subject': "2e rappel",
            'body': "Malgré notre premier rappel, la facture reste due.",
            'fees': 20.0})
        cls.mise_en_demeure = Niveau.create({
            'name': "Mise en demeure", 'delay_days': 45,
            'subject': "Mise en demeure",
            'body': "Sans paiement sous dix jours, nous engagerons "
                    "le recouvrement."})
        cls.client_a = cls.env['res.partner'].create({
            'name': "Bovet SA", 'email': "compta@bovet.example.ch"})
        cls.client_b = cls.env['res.partner'].create({
            'name': "Perret Sàrl", 'email': "info@perret.example.ch"})
        cls.produit = cls.env['product.product'].create({
            'name': "Prestation", 'type': 'service', 'list_price': 500.0})
        cls.Relance = cls.env['megga.relance']

    def _facture(self, partner, jours_de_retard, montant=500.0,
                 poster=True):
        echeance = fields.Date.subtract(
            fields.Date.context_today(self.env.user), days=jours_de_retard)
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': echeance,
            'invoice_date_due': echeance,
            'invoice_line_ids': [Command.create({
                'product_id': self.produit.id,
                'quantity': 1, 'price_unit': montant})],
        })
        if poster:
            move.action_post()
        return move

    def test_rien_avant_le_premier_cran(self):
        self._facture(self.client_a, 5)
        self.assertFalse(self.Relance._cron_megga_relances())

    def test_propose_au_premier_cran(self):
        facture = self._facture(self.client_a, 12)
        relances = self.Relance._cron_megga_relances()
        self.assertEqual(len(relances), 1)
        self.assertEqual(relances.partner_id, self.client_a)
        self.assertEqual(relances.niveau_id, self.premier)
        self.assertEqual(relances.move_ids, facture)
        self.assertEqual(relances.state, 'draft',
                         "le cron propose, il n'envoie pas")

    def test_un_seul_rappel_pour_trois_factures(self):
        f1 = self._facture(self.client_a, 12)
        f2 = self._facture(self.client_a, 15, montant=300.0)
        f3 = self._facture(self.client_a, 20, montant=200.0)
        relances = self.Relance._cron_megga_relances()
        self.assertEqual(len(relances), 1,
                         "un client qui doit trois factures reçoit "
                         "un courrier, pas trois")
        self.assertEqual(relances.move_ids, f1 | f2 | f3)
        # Le montant rappelé est ce que le client DOIT, taxes comprises :
        # on ne réclame pas un hors-taxes que personne ne paie.
        self.assertAlmostEqual(
            relances.amount_due,
            sum((f1 | f2 | f3).mapped('amount_total')))
        self.assertGreater(relances.amount_due, 1000.0,
                           "TTC, donc au-dessus du hors-taxes")

    def test_deux_clients_deux_rappels(self):
        self._facture(self.client_a, 12)
        self._facture(self.client_b, 12)
        relances = self.Relance._cron_megga_relances()
        self.assertEqual(len(relances), 2)
        self.assertEqual(relances.mapped('partner_id'),
                         self.client_a | self.client_b)

    def test_le_cran_le_plus_eleve(self):
        self._facture(self.client_a, 50)
        relances = self.Relance._cron_megga_relances()
        self.assertEqual(relances.niveau_id, self.mise_en_demeure)

    def test_pas_de_doublon_tant_que_le_brouillon_attend(self):
        self._facture(self.client_a, 12)
        self.Relance._cron_megga_relances()
        self.assertFalse(self.Relance._cron_megga_relances(),
                         "le brouillon en attente n'est pas doublé")

    def test_le_meme_cran_ne_repart_pas_apres_envoi(self):
        self._facture(self.client_a, 12)
        relance = self.Relance._cron_megga_relances()
        relance.action_send()
        self.assertFalse(self.Relance._cron_megga_relances())

    def test_le_cran_suivant_repart(self):
        facture = self._facture(self.client_a, 12)
        self.Relance._cron_megga_relances().action_send()
        # Le temps passe : la meme facture atteint le 2e cran.
        facture.write({'invoice_date_due': fields.Date.subtract(
            fields.Date.context_today(self.env.user), days=35)})
        suivante = self.Relance._cron_megga_relances()
        self.assertEqual(suivante.niveau_id, self.second)
        self.assertEqual(suivante.move_ids, facture)

    def test_l_envoi_trace_et_marque(self):
        facture = self._facture(self.client_a, 12)
        relance = self.Relance._cron_megga_relances()
        relance.action_send()
        self.assertEqual(relance.state, 'sent')
        self.assertTrue(relance.sent_on)
        self.assertEqual(facture.megga_relance_niveau_id, self.premier)
        self.assertEqual(facture.megga_relance_date, relance.date)
        message = relance.message_ids[0]
        self.assertIn("facture", (message.body or "").lower())
        self.assertIn(self.client_a, message.partner_ids,
                      "le client est destinataire du message")

    def test_les_frais_annonces_figurent_au_texte(self):
        facture = self._facture(self.client_a, 35)
        du_avant = facture.amount_residual
        relance = self.Relance._cron_megga_relances()
        self.assertEqual(relance.niveau_id, self.second)
        relance.action_send()
        corps = relance.message_ids[0].body
        self.assertIn("Frais de rappel", corps,
                      "les frais annoncés sont dans le rappel")
        self.assertRegex(corps, r"Frais de rappel[^<]*20",
                         "et c'est bien le montant du niveau")
        self.assertAlmostEqual(
            facture.amount_residual, du_avant,
            msg="Megga n'ajoute AUCUN frais à la facture tout seul")
        self.assertEqual(len(facture.invoice_line_ids), 1,
                         "aucune ligne de frais n'est apparue")

    def test_sans_courriel_on_ne_pretend_pas_avoir_envoye(self):
        muet = self.env['res.partner'].create({'name': "Sans courriel"})
        self._facture(muet, 12)
        relance = self.Relance._cron_megga_relances()
        with self.assertRaises(UserError):
            relance.action_send()
        self.assertEqual(relance.state, 'draft')

    def test_remise_hors_courriel(self):
        muet = self.env['res.partner'].create({'name': "Sans courriel"})
        facture = self._facture(muet, 12)
        relance = self.Relance._cron_megga_relances()
        relance.action_mark_sent()
        self.assertEqual(relance.state, 'sent')
        self.assertEqual(facture.megga_relance_niveau_id, self.premier)

    def test_la_facture_payee_sort_du_circuit(self):
        facture = self._facture(self.client_a, 12)
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=facture.ids
        ).create({}).action_create_payments()
        self.assertFalse(self.Relance._cron_megga_relances())

    def test_le_brouillon_n_est_jamais_rappele(self):
        self._facture(self.client_a, 30, poster=False)
        self.assertFalse(self.Relance._cron_megga_relances())

    def test_facture_sortie_du_circuit(self):
        """Litige, arrangement, recouvrement confié : le comptable coche
        « Hors rappels » et on n'y touche plus. Notre drapeau, pas le
        `no_followup` du coeur — inerte en Community."""
        facture = self._facture(self.client_a, 30)
        facture.megga_relance_exclue = True
        self.assertFalse(self.Relance._cron_megga_relances())
        facture.megga_relance_exclue = False
        self.assertTrue(self.Relance._cron_megga_relances(),
                        "en décochant, le suivi reprend")

    def test_rappel_sans_facture_refuse(self):
        relance = self.Relance.create({
            'partner_id': self.client_a.id,
            'niveau_id': self.premier.id,
        })
        with self.assertRaises(UserError):
            relance.action_send()

    def test_abandon(self):
        self._facture(self.client_a, 12)
        relance = self.Relance._cron_megga_relances()
        relance.action_cancel()
        self.assertEqual(relance.state, 'cancelled')
        with self.assertRaises(UserError):
            relance.action_send()

    # --- ce que la revue adversariale a trouvé, et qui ne doit plus
    # --- jamais repasser

    def test_deux_crans_le_meme_jour_font_UN_courrier(self):
        """Le défaut reproduit en base : une facture à 12 jours et une à
        50 jours donnaient DEUX lettres le même matin — dont une mise en
        demeure sous-évaluée."""
        jeune = self._facture(self.client_a, 12)
        vieille = self._facture(self.client_a, 50, montant=3000.0)
        relances = self.Relance._cron_megga_relances()
        self.assertEqual(len(relances), 1, "un client, un courrier")
        self.assertEqual(relances.niveau_id, self.mise_en_demeure,
                         "au cran le plus élevé")
        self.assertEqual(relances.move_ids, jeune | vieille,
                         "et il porte TOUTE la dette")

    def test_chaque_facture_garde_son_propre_cran(self):
        """La lettre monte le ton, mais ne fait pas sauter des crans à
        une facture jeune : sinon elle n'aurait plus jamais de 1er ni
        de 2e rappel."""
        jeune = self._facture(self.client_a, 12)
        vieille = self._facture(self.client_a, 50, montant=3000.0)
        self.Relance._cron_megga_relances().action_send()
        self.assertEqual(jeune.megga_relance_niveau_id, self.premier)
        self.assertEqual(vieille.megga_relance_niveau_id,
                         self.mise_en_demeure)

    def test_le_marquage_ne_redescend_jamais(self):
        """Envoyer un vieux brouillon après un rappel plus sévère ne
        doit pas rouvrir un cran déjà servi."""
        facture = self._facture(self.client_a, 12)
        brouillon = self.Relance._cron_megga_relances()
        self.assertEqual(brouillon.niveau_id, self.premier)
        facture.write({'invoice_date_due': fields.Date.subtract(
            fields.Date.context_today(self.env.user), days=50)})
        # Le brouillon en attente est MIS A JOUR — meme enregistrement,
        # cran releve : le comptable retrouve ses eventuelles notes.
        rejoue = self.Relance._cron_megga_relances()
        self.assertEqual(rejoue, brouillon)
        self.assertEqual(brouillon.niveau_id, self.mise_en_demeure)
        brouillon.action_send()
        self.assertEqual(facture.megga_relance_niveau_id,
                         self.mise_en_demeure)
        self.assertFalse(self.Relance._cron_megga_relances(),
                         "et plus rien ne repart")

    def test_changer_le_delai_d_un_cran_ne_le_fait_pas_repartir(self):
        """Le marquage porte l'IDENTITÉ du niveau : re-régler « le 2e
        rappel, finalement à 25 jours » ne doit pas relancer tout le
        monde une seconde fois."""
        facture = self._facture(self.client_a, 35)
        self.Relance._cron_megga_relances().action_send()
        self.assertEqual(facture.megga_relance_niveau_id, self.second)
        self.second.delay_days = 25
        self.assertFalse(self.Relance._cron_megga_relances())

    def test_une_seule_lettre_par_devise(self):
        """On n'additionne pas des francs et des euros sous un total."""
        euro = self.env.ref('base.EUR')
        euro.active = True
        facture_ch = self._facture(self.client_a, 12)
        facture_eu = self._facture(self.client_a, 12)
        facture_eu.button_draft()
        facture_eu.currency_id = euro
        facture_eu.action_post()
        relances = self.Relance._cron_megga_relances()
        self.assertEqual(len(relances), 2, "une lettre par devise")
        self.assertEqual(
            set(relances.mapped('currency_id')),
            {facture_ch.currency_id, euro})

    def test_l_entite_commerciale_recoit_une_seule_lettre(self):
        """Deux contacts de facturation du même client, une seule
        dette : un seul courrier."""
        service = self.env['res.partner'].create({
            'name': "Bovet SA — service achats",
            'parent_id': self.client_a.id,
            'type': 'invoice'})
        self._facture(self.client_a, 12)
        self._facture(service, 12, montant=200.0)
        relances = self.Relance._cron_megga_relances()
        self.assertEqual(len(relances), 1)
        self.assertEqual(relances.partner_id, self.client_a)

    def test_facture_payee_entre_la_proposition_et_l_envoi(self):
        """Rien n'est plus gênant qu'un rappel pour une facture réglée
        la veille."""
        facture = self._facture(self.client_a, 12)
        relance = self.Relance._cron_megga_relances()
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=facture.ids
        ).create({}).action_create_payments()
        with self.assertRaises(UserError):
            relance.action_send()
        self.assertEqual(relance.state, 'draft')

    def test_facture_en_litige_non_relancee(self):
        """payment_state 'blocked' : le litige du cœur se respecte."""
        facture = self._facture(self.client_a, 30)
        facture.payment_state = 'blocked'
        self.assertFalse(self.Relance._cron_megga_relances())

    def test_avoir_qui_couvre_la_dette(self):
        """Un client dont l'avoir ouvert couvre l'échu ne doit rien :
        on ne lui écrit pas."""
        facture = self._facture(self.client_a, 20)
        avoir = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': self.client_a.id,
            'invoice_date': fields.Date.context_today(self.env.user),
            'invoice_line_ids': [Command.create({
                'product_id': self.produit.id,
                'quantity': 1, 'price_unit': 500.0})],
        })
        avoir.action_post()
        self.assertGreaterEqual(abs(avoir.amount_residual),
                                facture.amount_residual)
        self.assertFalse(self.Relance._cron_megga_relances())

    def test_le_corps_part_en_html_lisible(self):
        """message_post échappe toute chaîne non-Markup : un « <br/> »
        écrit à la main partirait en toutes lettres."""
        self._facture(self.client_a, 12)
        relance = self.Relance._cron_megga_relances()
        relance.action_send()
        corps = relance.message_ids[0].body
        self.assertNotIn("&lt;br", corps, "pas de balise en toutes lettres")
        self.assertIn("<", corps, "c'est bien du HTML")

    def test_le_texte_du_niveau_ne_casse_pas_le_message(self):
        """Une esperluette dans le texte du cabinet ne doit ni casser
        le message ni s'injecter dedans."""
        self.premier.body = "Maison Dupont & Fils <cher client>"
        self._facture(self.client_a, 12)
        relance = self.Relance._cron_megga_relances()
        relance.action_send()
        corps = relance.message_ids[0].body
        self.assertIn("&amp;", corps, "l'esperluette est échappée")
        self.assertNotIn("<cher client>", corps,
                         "et le faux tag ne devient pas du balisage")

    def test_un_cran_a_zero_jour_part_le_jour_de_l_echeance(self):
        """Un cabinet strict règle son premier rappel à 0 jour : la
        sentinelle « jamais rappelé » ne doit pas l'avaler."""
        self.env['megga.relance.niveau'].search([]).unlink()
        immediat = self.env['megga.relance.niveau'].create({
            'name': "Le jour même", 'delay_days': 0,
            'subject': "Facture échue", 'body': "Votre facture est échue."})
        self._facture(self.client_a, 0)
        relances = self.Relance._cron_megga_relances()
        self.assertEqual(relances.niveau_id, immediat)
