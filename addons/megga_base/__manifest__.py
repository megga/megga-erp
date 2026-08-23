{
    'name': 'Megga Base',
    'summary': "Surcouche de marque Megga — Phase 2 du plan de reprise",
    'description': """
Habillage Megga au-dessus d'Odoo Community, sans aucune modification du cœur :
titre de fenêtre, favicon, logo de société, couleur primaire, retrait des
liens promotionnels odoo.com (connexion, e-mails, portail, menu utilisateur).
Chaque surcharge cible un point d'ancrage vérifié dans le source 19.0
au SHA épinglé par le sous-module.
""",
    'version': '19.0.1.0.0',
    'category': 'Hidden',
    'author': 'Megga',
    'license': 'Other proprietary',
    'depends': ['web', 'mail'],
    'data': [
        'views/webclient_templates.xml',
        'views/mail_templates.xml',
        'data/company_logo.xml',
    ],
    'assets': {
        # Prépendu : défini AVANT les « !default » d'Odoo, donc prioritaire.
        'web._assets_primary_variables': [
            ('prepend', 'megga_base/static/src/scss/primary_variables.scss'),
        ],
        'web.assets_backend': [
            'megga_base/static/src/js/title_service.js',
            'megga_base/static/src/js/user_menu.js',
        ],
    },
    'installable': True,
    'application': False,
}
