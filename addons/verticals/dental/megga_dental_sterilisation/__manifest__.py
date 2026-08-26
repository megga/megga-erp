# La tracabilite de sterilisation : la preuve que l'instrument pose
# dans la bouche du patient sortait d'un cycle d'autoclave conforme.
#
# Troisieme module du magasin dentaire, et il n'invente presque rien :
# le CYCLE se rattache a l'autoclave du registre (megga_dental_materiel)
# et les SETS steriles sont des lots dates du magasin
# (megga_dental_stock). La peremption de sterilite est la meme mecanique
# que la peremption d'un consommable — donc le meme FEFO, et la meme
# garde : un set perime ne part pas en soins.
#
# Ce qu'il ajoute, c'est le lien qui manquait dans les deux sens : du
# cycle vers les seances qu'il a servies (le RAPPEL, quand l'indicateur
# biologique revient non conforme le lendemain), et de la seance vers
# les cycles qui l'ont servie (la PREUVE, quand un patient la demande).
#
# Module SEPARE, jamais auto_install : un cabinet qui sterilise a
# l'exterieur, ou qui tient son registre au classeur, n'en veut pas.
{
    'name': "Megga Dentaire — Stérilisation",
    'summary': "Cycles d'autoclave, sets stérilisés tracés par lot, "
               "rappel par séance",
    'description': """
Traçabilité de stérilisation pour cabinet dentaire.

Chaque CHARGE d'autoclave est un cycle numéroté : l'appareil (celui du
registre du matériel), la date, l'opérateur, le programme, le test
Helix et l'indicateur biologique. Le rapport de cycle s'attache au fil
de discussion — c'est la preuve, et elle se garde.

Valider le cycle fait entrer ses SETS en stock, chacun avec son lot,
son numéro de cycle et sa date de péremption de stérilité (le délai du
produit). À partir de là, tout est déjà connu du magasin : le FEFO sort
le set dont la stérilité expire en premier, la garde du cabinet refuse
un set périmé en soins, et la clôture de séance décompte les sets comme
n'importe quel consommable.

Ce que le module ajoute vraiment, c'est le lien dans les deux sens :

- LE RAPPEL. L'indicateur biologique revient non conforme le
  lendemain : marquer le cycle non conforme bloque immédiatement ses
  sets encore en rayon, et nomme les séances qui en ont déjà consommé.
  C'est la question que le cabinet doit pouvoir répondre en une minute.
- LA PREUVE. Depuis une séance, les cycles qui l'ont servie.

Aucun cycle ne s'efface : un registre de stérilisation est un document
de preuve. Un cycle validé est figé, comme une ordonnance émise.
""",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'Other proprietary',
    'depends': [
        'megga_dental_stock',
        'megga_dental_materiel',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/dental_sterilisation_security.xml',
        'data/dental_sterilisation_data.xml',
        'views/dental_sterilisation_views.xml',
        'views/dental_sterilisation_menus.xml',
    ],
}
