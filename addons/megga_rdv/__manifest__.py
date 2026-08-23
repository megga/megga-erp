# Chantier commun aux verticales (dentaire, garage, resto) : la prise de
# rendez-vous EN LIGNE, l'équivalent Community du module Enterprise
# `appointment`. Volontairement indépendant des verticales : il ne dépend
# que du calendrier du cœur — chaque déploiement l'installe (ou pas).
{
    'name': "Megga Rendez-vous",
    'summary': "Prise de rendez-vous en ligne sur le calendrier du cœur "
               "(créneaux, préavis, annulation par jeton)",
    'description': """
Prise de rendez-vous en ligne, sans module Enterprise.

Types de rendez-vous (durée, plages hebdomadaires, intervenants), page
publique /rdv qui ne montre que des créneaux réellement libres (l'agenda
calendar.event fait foi), choix de l'intervenant le moins chargé,
confirmation par e-mail avec lien d'annulation à jeton. Le rendez-vous
réservé devient un événement d'agenda ordinaire — qui bloque le créneau
pour les suivants.
""",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'LGPL-3',
    'application': True,
    'depends': [
        'calendar',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/mail_template.xml',
        'data/cron.xml',
        'views/rdv_views.xml',
        'views/rdv_templates.xml',
        'views/rdv_menus.xml',
    ],
    'demo': [
        'demo/rdv_demo.xml',
    ],
}
