# Le portail patient : une OUVERTURE DELIBEREE sur des donnees de sante.
# Ce module ne s'auto-installe jamais — un cabinet l'installe en
# conscience. Le patient connecte voit LE SIEN ET RIEN QUE LE SIEN :
# traitements et montants, ordonnances EMISES, questionnaires SIGNES
# (les brouillons ne sortent pas), factures via le portail natif. Le
# clinique profond — constats, imagerie, journal, plans, notes — reste
# hermetique : aucun droit portail dessus.
{
    'name': "Megga Dentaire — Portail patient",
    'summary': "Le patient consulte ses traitements, ordonnances "
               "émises et questionnaires signés",
    'description': """
Portail patient de la verticale dentaire.

Lecture seule, le sien seulement (règles d'enregistrement) : traitements
avec montants, ordonnances émises (PDF), questionnaires signés (PDF).
Les brouillons ne sortent jamais ; le dossier clinique profond n'est pas
exposé. Installation explicite : ouvrir un portail sur des données de
santé est une décision, pas un défaut.
""",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'Other proprietary',
    'depends': [
        'megga_dental',
        'portal',
    ],
    'data': [
        'security/portal_rules.xml',
        'security/ir.model.access.csv',
        'views/portal_templates.xml',
    ],
}
