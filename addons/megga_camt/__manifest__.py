{
    'name': "Megga — Import camt.053/054",
    'summary': "Rapprochement bancaire suisse : relevés camt.053 et avis de crédit camt.054 (références QRR)",
    'description': """
Import des relevés ISO 20022 camt.053 et des avis de crédit camt.054 — le
successeur du fichier ESR/V11 — dans les relevés bancaires d'Odoo, fonction
absente du dépôt Community (constat du volet 3 de l'audit).

Parseur pur (stdlib), indépendant de la version de schéma (.001.02/.04/.08,
variantes suisses .ch.02 comprises). Les lots d'encaissements QR sont éclatés
en une ligne par transaction, avec la référence QRR dans le champ référence
de la ligne pour le rapprochement automatique. Garde-fous : devise du
journal, IBAN du compte, déduplication au niveau du relevé et de la
transaction (ré-imports et recouvrement 053/054 sans doublons).
""",
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'author': 'Megga',
    'license': 'Other proprietary',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/camt_import_views.xml',
    ],
    'installable': True,
    'application': False,
}
