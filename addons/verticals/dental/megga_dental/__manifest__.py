# Première verticale métier de Megga. Méta-module : l'installer tire tout le
# métier d'un cabinet dentaire suisse — le socle Megga complet (débranding,
# QR-facture, camt, pain.001, décompte TVA), le CRM pour les nouveaux
# patients, l'agenda pour les séances et le carnet d'adresses.
{
    'name': "Megga Dentaire",
    'summary': "Cabinet dentaire : patients, plans de traitement, "
               "rappels de contrôle, facturation QR",
    'description': """
Gestion de cabinet dentaire sur le socle Megga.

Dossier patient (identité déléguée à res.partner, donc facturable tel quel),
plans de traitement avec actes, dents FDI et facturation en un clic,
rappels de contrôle périodiques automatiques (activité au praticien),
référentiel des 52 dents en notation FDI / ISO 3950,
odontogramme interactif (constats par dent et par surface, alimenté
automatiquement par les actes, réservé au groupe Soins — nLPD),
plans de traitement par phases (ordre clinique garanti, devis
d'ensemble, avancement, achèvement automatique),
ordonnances (émission qui fige, renouvellement chaîné, impression,
référentiel de médicaments du cabinet — réservées au groupe Soins),
questionnaires et consentements (gabarits du cabinet, signature qui
fige, anamnèse à péremption avec indicateur au dossier, impression).
""",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'LGPL-3',
    'application': True,
    'depends': [
        # Socle Megga (marque + normes suisses).
        'megga_base',
        'megga_qr_export',
        'megga_camt',
        'megga_pain001',
        'megga_tva_ch',
        # Briques du cœur pour le métier.
        'crm',
        'calendar',
        'contacts',
    ],
    'data': [
        'security/dental_security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/megga.dental.tooth.csv',
        'data/dental_data.xml',
        'data/questionnaire_data.xml',
        'views/dental_patient_views.xml',
        'views/dental_treatment_views.xml',
        'views/dental_position_views.xml',
        'views/dental_tooth_record_views.xml',
        'views/dental_plan_views.xml',
        'views/dental_prescription_views.xml',
        'views/dental_questionnaire_views.xml',
        'report/prescription_report.xml',
        'report/questionnaire_report.xml',
        'views/dental_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'megga_dental/static/src/odontogram/**/*',
        ],
    },
    'demo': [
        'demo/dental_demo.xml',
    ],
}
