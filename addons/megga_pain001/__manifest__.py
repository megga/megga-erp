{
    'name': "Megga — Export pain.001 (Suisse)",
    'summary': "Paiements fournisseurs au format pain.001.001.09.ch.03 (Swiss Payment Standards)",
    'description': """
Génération des ordres de virement ISO 20022 pain.001.001.09.ch.03 depuis les
paiements fournisseurs d'Odoo, fonction absente du dépôt Community (le module
account_iso20022 est réservé à l'édition Enterprise — constat du volet 3 de
l'audit).

Générateur pur (stdlib), validé contre le schéma XSD officiel de SIX à la
création du module. Références QRR (mod10r) et RF/SCOR (ISO 11649) détectées
dans le mémo du paiement et validées ; un créancier en QR-IBAN exige une
référence QRR, et réciproquement. Garde anti double envoi : les paiements
exportés portent le MsgId du fichier.
""",
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'author': 'Megga',
    'license': 'Other proprietary',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/pain001_export_views.xml',
    ],
    'installable': True,
    'application': False,
}
