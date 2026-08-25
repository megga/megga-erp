{
    'name': "Megga — Pilotage : balance âgée",
    'summary': "Qui doit quoi, et depuis combien de temps — "
               "l'écran et le papier",
    'description': """
La balance âgée du poste clients, absente du dépôt Community : les
rapports comptables (`account_reports`) sont Enterprise.

Une vue d'analyse (liste, pivot, graphe) qui range chaque facture
ouverte par âge de créance — non échu, 1-30, 31-60, 61-90, plus de 90
jours — et un rapport imprimable par client, celui que réclame la
fiduciaire. Compagnon direct des rappels (`megga_relances`) : la
balance montre où en est le recouvrement, facture par facture.

Les montants sont exprimés en devise de la société : un tableau de bord
additionne, et on n'additionne pas des francs avec des euros.
""",
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'Other proprietary',
    'depends': ['account', 'megga_relances'],
    'data': [
        'security/ir.model.access.csv',
        'report/balance_agee_report.xml',
        'views/pilotage_views.xml',
    ],
    'installable': True,
    'application': False,
}
