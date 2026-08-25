{
    'name': "Megga — Rappels de factures",
    'summary': "Relances des factures impayées : niveaux, proposition "
               "quotidienne, envoi tracé",
    'description': """
Le suivi des impayés, absent du dépôt Community (`account_followup` est
un module Enterprise — le cœur n'en garde que le champ `no_followup`).

Des niveaux de rappel réglés par l'entreprise (jours après l'échéance,
texte, frais annoncés), un cron quotidien qui PROPOSE un rappel en
brouillon par client concerné — jamais d'envoi automatique : une
relance part sous la signature de la maison —, et un envoi qui trace :
le courriel passe par le chatter, et chaque facture rappelée porte le
cran servi. Un même cran ne repart donc jamais deux fois.

Un client qui doit trois factures reçoit UN rappel qui les porte toutes.
""",
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'Other proprietary',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'security/relance_rules.xml',
        'data/relance_data.xml',
        'views/relance_views.xml',
    ],
    'installable': True,
    'application': False,
}
