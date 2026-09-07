# L'ecart matiere : le chiffre qui dit ou part la marge.
#
# Module SEPARE de megga_resto, et JAMAIS auto_install. Il demande au
# restaurant un geste qu'aucun logiciel ne peut faire a sa place :
# COMPTER SES STOCKS. Sans inventaire, l'ecart ne vaut rien — c'est une
# decision, donc une installation deliberee. Meme doctrine que le
# magasin du cabinet dentaire.
#
# Il ne modelise presque rien, une fois de plus : les fiches techniques
# donnent la consommation theorique, la caisse donne les volumes
# vendus. Il ne manquait que la confrontation des deux, et le comptage
# qui la rend possible.
#
# CE QU'IL N'EST PAS : un module de stock. Il ne tient aucun mouvement,
# ne decremente rien, n'exige pas que les ingredients soient stockables.
# Le restaurant compte au debut et a la fin d'une periode, saisit ses
# entrees, et le module fait l'arithmetique — celle que tout
# restaurateur trace deja a la main sur son carnet.
{
    'name': "Megga Restaurant — Écart matière",
    'summary': "Consommation théorique (fiches × ventes) contre réelle "
               "(inventaire) : où part la marge",
    'description': """
Écart matière : théorique contre réel.

Sur une période, le module confronte deux consommations. La THÉORIQUE
vient des fiches techniques multipliées par les plats réellement
encaissés à la caisse. La RÉELLE vient de l'inventaire : stock de
départ, plus les entrées, moins le stock de fin. L'écart entre les deux
est le gaspillage, les portions trop généreuses, la casse — parfois le
vol.

Un écart POSITIF veut dire qu'on a consommé plus que la théorie : c'est
une perte. Un écart négatif n'est pas une bonne nouvelle pour autant —
ou la fiche ment, ou l'inventaire est faux.

Le total des pertes ne somme QUE les écarts positifs : additionner les
écarts signés donnerait un total rassurant et faux, où le beurre
gaspillé effacerait la farine sous-consommée.

Les bornes de période se calculent dans le fuseau du restaurant : une
commande encaissée à 00h30 le samedi est encaissée à 23h30 UTC le
vendredi, et tomberait dans le mauvais jour sans conversion.

Recalculer un relevé ne détruit JAMAIS les comptages saisis à la main :
seule la colonne théorique est réécrite.
""",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'Other proprietary',
    'depends': [
        'megga_resto',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/resto_ecart_views.xml',
        'report/ecart_report.xml',
        'views/ecart_menus.xml',
    ],
}
