# Le portail client du garage : le pendant du portail patient, cote
# atelier. Le client connecte voit SES vehicules et SES reparations
# engagees — jamais un devis interne, jamais le vehicule d'un autre —
# et telecharge le carnet d'entretien de sa voiture. Module separe,
# jamais auto-installe : ouvrir un portail est une decision du garage.
{
    'name': "Megga Garage — Portail client",
    'summary': "Le client suit ses véhicules, ses réparations et "
               "télécharge son carnet d'entretien",
    'description': """
Portail client de la verticale garage.

Lecture seule, le sien seulement (règles d'enregistrement) : ses
véhicules (avec l'échéance d'expertise OETV), ses ordres de réparation
acceptés ou terminés avec le détail des travaux, et le carnet
d'entretien en PDF. Les devis en cours de rédaction ne sortent pas.
Installation explicite : c'est une décision du garage, pas un défaut.
""",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'Other proprietary',
    'depends': [
        'megga_auto',
        'portal',
    ],
    'data': [
        'security/portal_rules.xml',
        'security/ir.model.access.csv',
        'views/portal_templates.xml',
    ],
}
