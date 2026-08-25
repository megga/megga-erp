# Module de liaison (auto_install) : présent dès que le garage ET la prise
# de rendez-vous en ligne sont installés. Le client réserve son passage à
# l'atelier en ligne ; son véhicule est rattaché automatiquement quand il
# n'en a qu'un, et l'ordre de réparation se crée en un clic, pré-rempli.
{
    'name': "Megga Garage ↔ Rendez-vous",
    'summary': "La réservation en ligne rattache le véhicule du client "
               "et ouvre l'ordre de réparation en un clic",
    'description': """
Pont entre megga_rdv et megga_auto.

À chaque réservation, le contact est garanti (rattaché ou créé par
e-mail) et, si le client ne possède qu'un véhicule au parc, celui-ci est
rattaché d'office — plusieurs véhicules : le comptoir choisit. Depuis la
réservation confirmée, un bouton crée l'ordre de réparation pré-rempli
(véhicule, client, date locale du rendez-vous, mécanicien, compteur).
Débrayable par type de rendez-vous.
""",
    'version': '19.0.1.0.0',
    'category': 'Hidden',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'Other proprietary',
    'auto_install': True,
    'depends': [
        'megga_auto',
        'megga_rdv',
    ],
    'data': [
        'views/auto_rdv_views.xml',
    ],
}
