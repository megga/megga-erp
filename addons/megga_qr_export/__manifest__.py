{
    'name': "Megga — QR-facture à l'export",
    'summary': "QR-facture pour les clients domiciliés hors de Suisse et du Liechtenstein",
    'description': """
Lève la restriction d'Odoo qui refuse d'émettre une QR-facture dès que le
client est domicilié hors CH/LI. La norme SIX (Swiss Implementation
Guidelines QR-bill) n'impose la Suisse ou le Liechtenstein qu'au compte du
CRÉANCIER ; le débiteur peut être domicilié dans n'importe quel pays.

Surcharge chirurgicale de _l10n_ch_qr_debtor_check (l10n_ch, vérifié au
SHA épinglé 9188766f) : le cas « pas de partenaire » garde le comportement
amont, un pays reste exigé sur l'adresse du débiteur (il alimente la charge
utile SPC), et la complétude d'adresse reste contrôlée en amont par
_check_for_qr_code_errors. Rien d'autre ne change.
""",
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'author': 'Megga',
    'license': 'Other proprietary',
    'depends': ['l10n_ch'],
    'data': [],
    # S'installe partout où la localisation suisse est installée : c'est un
    # correctif de conformité du produit, pas une option.
    'auto_install': True,
    'installable': True,
}
