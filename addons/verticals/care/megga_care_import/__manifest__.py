# Module de reprise, co-localisé avec la verticale (patron
# megga_dental_rdv) : il vit le temps de la bascule depuis Office Maker
# et peut être désinstallé ensuite — les données importées et leurs
# références externes (__megga_om__) restent.
{
    'name': "Megga Care — Reprise Office Maker",
    'summary': "Import idempotent des exports texte Office Maker : "
               "clients, prestataires, mandats et événements",
    'description': """
La reprise des données Office Maker, en autant de répétitions qu'il en
faut.

Office Maker exporte ses fiches en texte (tabulé ou point-virgule,
encodages variés) ; l'assistant lit ces exports — détection d'encodage
et de séparateur, dates, heures et montants suisses (1'949.75) — et
importe dans l'ordre : clients, prestataires, mandats, événements.

Chaque fiche est rattachée à sa référence Office Maker par un
identifiant externe (espace __megga_om__) : ré-importer le même export
MET À JOUR au lieu de dupliquer. On peut donc s'entraîner sur un export
d'essai, vérifier, corriger dans Office Maker, ré-exporter — et refaire
l'import complet au jour de la bascule sans un doublon.

Toute ligne illisible est REJETÉE avec sa raison (ligne et cause au
rapport), jamais devinée : type de prestation inconnu du référentiel,
mandat introuvable, date ou montant illisibles. Les mandats historiques
arrivent clôturés sans passer par le garde-fou de facturation — c'est
une reprise d'historique, pas un flux — et ne polluent ni le tableau de
bord ni les rappels.

Volontairement HORS module : la bascule comptable (soldes d'ouverture,
factures ouvertes, TVA) se décide au jour J avec la comptable ;
l'historique comptable reste consultable dans Office Maker, en archive.
Voir docs/reprise_office_maker.md pour le mode d'emploi complet.
""",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'Other proprietary',
    'depends': [
        'megga_care',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/care_import_views.xml',
    ],
    'installable': True,
}
