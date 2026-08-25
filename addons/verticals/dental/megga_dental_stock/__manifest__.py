# Le magasin du cabinet. Ce module CONFIGURE le coeur bien plus qu'il ne
# modelise : le stock, les lots, la peremption et la sortie FEFO sont
# entierement dans Odoo Community (stock + product_expiry). Ce qu'on
# ajoute, c'est le metier du cabinet — une categorie outillee, un
# emplacement « Consomme en soins », un menu qui evite d'envoyer la
# receptionniste dans l'app Inventaire, et LA garde qui compte :
# un lot perime ne part jamais en soins.
#
# Module SEPARE de megga_dental, jamais auto_install : un cabinet peut
# vouloir le metier sans le magasin (petite structure, consommables
# gores a la main).
{
    'name': "Megga Dentaire — Stock du cabinet",
    'summary': "Consommables traces par lots et peremption, sortie FEFO, "
               "kits par acte decomptes a la cloture de seance",
    'description': """
Magasin du cabinet dentaire.

Categorie « Consommables du cabinet » outillee pour la sortie FEFO
(First Expiry First Out) : a quantites reservees, le coeur sert le lot
dont la date de retrait est la plus proche — le fond de stock ne perime
plus au fond du tiroir.

Emplacement virtuel « Consomme en soins » : tout ce qui part au fauteuil
va au meme endroit, les quantites sortent definitivement et la
valorisation suit.

Garde metier : un lot perime ne part JAMAIS vers les soins. Le refus
nomme le lot, sa date et le bon geste. Le rebut, les retours
fournisseur et les ajustements d'inventaire restent permis — un lot
perime doit pouvoir etre detruit proprement.

Menu « Stock du cabinet » : produits du cabinet, quantites en stock,
lots par urgence de peremption. Des raccourcis filtres vers les vues du
coeur, pas un doublon de l'app Inventaire.

Kits par position tarifaire : c'est l'ACTE qui sait ce qu'il consomme.
Clore une seance decompte le magasin toute seule — zero ressaisie au
fauteuil, deux actes qui partagent un produit font un seul mouvement.

Le stock ne bloque JAMAIS la clinique : rien en rayon, la consommation
part quand meme (quantite en negatif), plus rien de servable, elle part
sans lot — et une activite signale l'ecart au magasin. Le soin est
fait ; le magasin constate.

Reapprovisionnement : minimum et maximum par consommable, et le
planificateur du coeur propose de lui-meme un bon de commande chez le
fournisseur du produit des que le rayon passe sous le minimum. Aucun
cron maison — le coeur en a deja un. La reception remet des lots dates
en rayon, que le FEFO range a leur place.
""",
    'version': '19.0.1.2.0',
    'category': 'Industries',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'Other proprietary',
    'depends': [
        'megga_dental',
        'stock',
        'product_expiry',
        # Chantier 3 : le reassort passe par les bons de commande du
        # coeur. purchase_stock tire purchase ET stock, et pose la
        # route « Buy » sur l'entrepot.
        'purchase_stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/dental_stock_data.xml',
        'views/dental_replenish_views.xml',
        'views/dental_stock_views.xml',
        'views/dental_supply_views.xml',
        'views/dental_stock_menus.xml',
    ],
}
