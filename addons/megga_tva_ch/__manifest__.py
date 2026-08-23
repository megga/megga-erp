{
    'name': "Megga — Décompte TVA suisse",
    'summary': "Décompte TVA selon le formulaire AFC, calculé sur les grilles de l10n_ch",
    'description': """
Restitution du décompte TVA suisse (rubriques 200–299, 302–399, 400–479,
500/510, 900/910) à partir du rapport de taxes que l10n_ch livre déjà en
Community — le moteur de rendu étant, lui, réservé à l'édition Enterprise
(constat du volet 3 de l'audit).

Le module ne redéfinit aucun mapping fiscal : il évalue les expressions du
rapport officiel (moteurs tax_tags et aggregation) avec la sémantique 19.0
vérifiée dans le source — un tag par formule, négation par le préfixe « - »
de la formule, plancher if_above pour les rubriques 500/510. Toute formule
non reconnue fait échouer le calcul plutôt que de publier un chiffre faux.
""",
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'author': 'Megga',
    'license': 'Other proprietary',
    'depends': ['account', 'l10n_ch'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/tva_decompte_views.xml',
        'report/decompte_templates.xml',
    ],
    'auto_install': True,
    'installable': True,
    'application': False,
}
