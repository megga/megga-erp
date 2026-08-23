# Module de liaison (auto_install) : présent dès que le restaurant ET la
# prise de rendez-vous en ligne sont installés. Le carnet de réservations
# s'expose sur le moteur de créneaux public — avec une bascule de
# sémantique : on réserve des TABLES, pas des personnes. L'événement
# d'agenda passe en « libre », un même créneau accepte donc plusieurs
# tablées, et c'est l'attribution automatique de table qui devient le
# vrai contrôle de capacité (complet = refus propre).
{
    'name': "Megga Restaurant ↔ Rendez-vous",
    'summary': "Le carnet de tables s'expose en réservation en ligne "
               "(couverts, attribution de table, refus quand complet)",
    'description': """
Pont entre megga_rdv et megga_resto.

Un type de rendez-vous marqué « réservation de table » demande les
couverts sur le formulaire public, n'occupe pas l'agenda (plusieurs
tablées par créneau) et crée l'entrée du carnet confirmée avec la plus
petite table suffisante libre — plus de table : la réservation est
refusée proprement. Les annulations se synchronisent dans les deux sens
(lien public à jeton compris).
""",
    'version': '19.0.1.0.0',
    'category': 'Hidden',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'LGPL-3',
    'auto_install': True,
    'depends': [
        'megga_resto',
        'megga_rdv',
    ],
    'data': [
        'views/resto_rdv_views.xml',
    ],
}
