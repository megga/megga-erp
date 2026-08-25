# Le portail client du restaurant. Le client connecte suit SES
# reservations — et peut annuler celles a venir, seul geste d'ecriture
# de tous les portails Megga : c'est LA fonction utile cote salle (une
# table annulee a temps se revend). L'annulation passe par une action
# dediee et gardee, jamais par un droit d'ecriture : les ACL du portail
# restent en lecture seule.
{
    'name': "Megga Restaurant — Portail client",
    'summary': "Le client suit ses réservations et annule celles à venir",
    'description': """
Portail client de la verticale restaurant.

Lecture seule, les siennes seulement (règles d'enregistrement) : toutes
ses réservations, passées comme à venir, avec leur état. Une réservation
encore annulable (demande ou confirmée, dans le futur) porte un bouton
d'annulation : action dédiée, gardée, tracée au chatter — jamais un
droit d'écriture générique. Les notes de service ne redescendent pas.
Installation explicite : c'est une décision du restaurant.
""",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'Other proprietary',
    'depends': [
        'megga_resto',
        'portal',
    ],
    'data': [
        'security/portal_rules.xml',
        'security/ir.model.access.csv',
        'views/portal_templates.xml',
    ],
}
