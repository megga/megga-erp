# La declaration legale de la carte : allergenes et provenance.
#
# Module SEPARE de megga_resto, et JAMAIS auto_install. La loi cree
# l'obligation, pas ce module — mais l'outiller demande du travail
# (renseigner chaque ingredient), et ce travail est une decision du
# restaurant. Meme doctrine que le magasin et la sterilisation du
# cabinet dentaire : installation deliberee.
#
# Il ne modelise presque rien : la fiche technique de megga_resto porte
# DEJA la liste des ingredients. Il suffit de dire, sur l'article
# ingredient, ce qu'il apporte d'allergene et d'ou il vient — et la
# declaration de chaque plat se calcule seule. Le champ « notes » de la
# fiche invitait a ecrire les allergenes en toutes lettres ; ils
# deviennent ici une donnee qui se cherche, se recoupe et s'imprime.
#
# Il ne BLOQUE rien, jamais : une fiche incomplete se sauve, se cuisine
# et se vend. Elle est seulement signalee, et le rapport refuse de la
# faire passer pour declarable — meme doctrine que le magasin du
# cabinet, qui ne bloque jamais la clinique.
{
    'name': "Megga Restaurant — Déclaration (allergènes, provenance)",
    'summary': "Allergènes et pays de production déclarés depuis les "
               "fiches techniques, et imprimés pour la carte",
    'description': """
Déclaration légale de la carte, sur les fiches techniques du restaurant.

Le droit alimentaire suisse impose de renseigner le client sur les
allergènes de ce qu'il mange, et — pour la viande et le poisson — sur le
pays de production. Les deux se déclarent ici sur l'ARTICLE INGRÉDIENT,
une fois : chaque plat qui l'emploie hérite de la déclaration, et un
changement de fournisseur se propage à toute la carte.

Le référentiel des allergènes à déclaration obligatoire est livré. Sur
chaque fiche technique paraissent les allergènes réunis du plat, l'état
de sa déclaration, et — nommément — ce qui manque encore. La règle qui
tient tout : une liste d'allergènes vide ne vaut pas déclaration tant
que personne n'a coché « vérifié ». Rien de moins ne se signe.

La déclaration s'imprime (QWeb) pour l'affichage en salle ou le
classeur du service. Un plat incomplet y figure barré d'un
avertissement plutôt que passé sous silence.

Hors périmètre à ce stade : la déclaration des méthodes de production
interdites en Suisse (hormones, antibiotiques comme stimulateurs de
performance), qui demande son propre référentiel de mentions.
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
        'data/megga.resto.allergen.csv',
        'views/resto_allergen_views.xml',
        'views/product_views.xml',
        'views/resto_recipe_views.xml',
        'report/declaration_report.xml',
        'views/declaration_menus.xml',
    ],
    'demo': [
        'demo/declaration_demo.xml',
    ],
}
