# Module de liaison (auto_install) : présent dès que le dentaire ET la
# prise de rendez-vous en ligne sont installés. Une réservation rattache —
# ou crée — le dossier patient du contact : la personne qui réserve son
# contrôle en ligne existe déjà comme patient quand elle passe la porte.
{
    'name': "Megga Dentaire ↔ Rendez-vous",
    'summary': "La réservation en ligne rattache ou crée le dossier patient",
    'description': """
Pont entre megga_rdv et megga_dental.

À chaque réservation (en ligne ou saisie au comptoir), le dossier patient
du contact est rattaché s'il existe — archivés compris, pas de doublon —
ou créé sinon. Débrayable par type de rendez-vous. Le patient montre ses
réservations en ligne ; la réservation montre son patient.
""",
    'version': '19.0.1.0.0',
    'category': 'Hidden',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'Other proprietary',
    'auto_install': True,
    'depends': [
        'megga_dental',
        'megga_rdv',
    ],
    'data': [
        'views/dental_rdv_views.xml',
    ],
}
