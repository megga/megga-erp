{
    'name': "Megga Resto — TVA à l'emporter (CH)",
    'summary': "Sur place 8.1% / à l'emporter 2.6% : position fiscale "
               "suisse câblée sur la caisse",
    'description': """
Le meme sandwich ne paie pas la meme TVA selon qu'il se mange sur place
(prestation de la restauration, taux normal 8.1%) ou s'emporte
(livraison de denrees alimentaires, taux reduit 2.6% — art. 25 LTVA).

Ce module cree, pour chaque societe au plan comptable suisse, la
position fiscale « Vente a l'emporter (TVA 2.6%) » et sa taxe de
remplacement (copie de la TVA due a 2.6% TR, grille 313a conservee,
remplacant la TVA due a 8.1% TN), puis la relie au preset « A
l'emporter » de la caisse pos_restaurant : le service encaisse au bon
taux en choisissant le mode de la commande.

Attention : le taux reduit a l'emporter suppose des mesures
organisationnelles appropriees (tickets distincts par mode de vente —
ce que fait la caisse ainsi configuree) ; a defaut, tout est du au taux
normal. Voir l'Info TVA 08 « Hotellerie et restauration » de l'AFC.

Meme patron que le module l10n_be_pos_restaurant du coeur (la Belgique
a la meme dualite sur place / a emporter).
""",
    'version': '19.0.1.0.0',
    'author': "Megga",
    'license': 'LGPL-3',
    'category': 'Sales/Point of Sale',
    'depends': [
        'megga_resto',
        'l10n_ch',
    ],
    'auto_install': True,
    'post_init_hook': 'post_init_hook',
    'data': [
        'data/actions.xml',
    ],
}
