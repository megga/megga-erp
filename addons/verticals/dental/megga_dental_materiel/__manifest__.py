# Le registre du materiel du cabinet. Autoclave, compresseur,
# radiographie, fauteuils : ce qui se revise, se calibre et se prouve.
#
# Module SEPARE du magasin (megga_dental_stock) : le magasin COMPTE ce
# qui se consomme, le registre ENTRETIENT ce qui dure. Un cabinet peut
# vouloir l'un sans l'autre. Jamais auto_install.
#
# Et comme le magasin, il configure le coeur plus qu'il ne modelise :
# le module `maintenance` de Community tient deja les equipements
# (numero de serie, garantie, fournisseur, cout, technicien, MTBF) et
# l'entretien preventif periodique. Il ne manquait qu'une chose au
# cabinet : savoir a QUEL FAUTEUIL un appareil est rattache.
{
    'name': "Megga Dentaire — Materiel du cabinet",
    'summary': "Registre du materiel rattache aux fauteuils, entretien "
               "preventif et correctif",
    'description': """
Registre du materiel du cabinet dentaire.

Chaque appareil — autoclave, compresseur, generateur de rayons X,
fauteuil lui-meme — est un equipement du coeur : numero de serie,
fournisseur, date de mise en service, fin de garantie, technicien
responsable, historique des pannes et temps moyen entre defaillances.
Le module n'en reecrit aucun.

Ce qu'il ajoute : le RATTACHEMENT AU FAUTEUIL. Un cabinet ne cherche
pas « l'autoclave 3 », il cherche « ce qu'il y a autour du fauteuil 2 »
— pour savoir ce qui s'arrete quand l'appareil part en reparation. Un
fauteuil qui porte du materiel ne se supprime plus : il s'archive.

L'entretien preventif est celui du coeur : une demande recurrente
(trimestrielle pour la validation d'un autoclave, annuelle pour la
revision d'un compresseur) engendre la suivante des qu'on la cloture.
Aucun cron maison, aucune periodicite maison.

Menu « Materiel » sous le menu du cabinet : les equipements groupes par
fauteuil, et les demandes d'entretien. Des raccourcis filtres vers les
ecrans du coeur, pas un doublon de l'app Maintenance.
""",
    'version': '19.0.1.0.1',
    'category': 'Industries',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'Other proprietary',
    'depends': [
        'megga_dental',
        'maintenance',
    ],
    'data': [
        'data/dental_materiel_data.xml',
        'views/dental_materiel_views.xml',
        'views/dental_materiel_menus.xml',
    ],
}
