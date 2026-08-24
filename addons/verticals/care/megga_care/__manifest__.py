# Quatrième verticale métier de Megga. Méta-module : l'installer tire tout
# le métier d'une conciergerie médicale suisse — le socle Megga complet
# (débranding, QR-facture à l'export, camt, pain.001, décompte TVA), le CRM
# pour les nouveaux clients, l'agenda pour les événements de mandat et le
# carnet d'adresses. À la différence des trois autres verticales (LGPL-3),
# celle-ci est propriétaire : exigence contractuelle du déploiement fondateur
# (logiciel fermé, non revendu), au même titre que les modules du socle.
{
    'name': "Megga Care",
    'summary': "Conciergerie médicale : mandats, événements à double prix, "
               "rétrocessions, garde-fou de facturation",
    'description': """
Gestion de conciergerie médicale (accompagnement de patients VIP) sur le
socle Megga.

Le mandat lie le calendrier, les contacts et les factures en un seul flux —
la fonctionnalité pour laquelle aucune solution du marché n'avait convaincu.
Chaque événement du mandat porte deux prix : le prix facturé au client et le
coût réel payé au prestataire ; la marge (rétrocession comprise) se lit par
événement, puis s'agrège par mandat, par client, par type de prestation et
par fournisseur (vues pivot et graphique).

La facture fournisseur se rattache à l'événement précis, pas seulement au
mandat. Garde-fou « rien d'oublié » : un mandat ne se clôture que lorsque
chaque événement à prix est facturé au client et chaque coût couvert par une
pièce ; un rappel quotidien signale les mandats en retard de facturation.

Dossier client sur res.partner (facturable tel quel : QR-facture et
encaissement camt du socle s'appliquent sans pont), parcours de santé
protégé par groupes nLPD.
""",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'Other proprietary',
    'application': True,
    'depends': [
        # Socle Megga (marque + normes suisses).
        'megga_base',
        'megga_qr_export',
        'megga_camt',
        'megga_pain001',
        'megga_tva_ch',
        # Briques du cœur pour le métier.
        'crm',
        'calendar',
        'contacts',
    ],
    'data': [
        'security/care_security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/care_data.xml',
        'views/care_patient_views.xml',
        'views/care_event_views.xml',
        'views/care_mandate_views.xml',
        'views/care_service_type_views.xml',
        'views/account_move_views.xml',
        'views/care_menus.xml',
    ],
    'demo': [
        'demo/care_demo.xml',
    ],
}
