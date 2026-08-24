# Chantier commun aux verticales (conciergerie médicale, dentaire) : les
# RÉTROCESSIONS — la marge sur volume qu'un partenaire reverse à qui lui
# apporte des affaires. Volontairement indépendant des verticales : il ne
# dépend que de la comptabilité du cœur — chaque déploiement l'installe
# (ou pas). Les deux faces de la même pièce :
#  - la conciergerie ENCAISSE (laboratoires, pharmacies, cliniques lui
#    reversent un pourcentage du volume qu'elle leur apporte) ;
#  - le cabinet VERSE (il commissionne l'apporteur d'affaires qui lui
#    amène des patients).
{
    'name': "Megga Rétrocessions",
    'summary': "Rétrocessions et commissions d'apport : accords à taux, "
               "décomptes périodiques adossés aux factures validées",
    'description': """
Rétrocessions et commissions d'apport, dans les deux sens.

Un ACCORD fixe le partenaire, le sens (à encaisser / à verser) et le taux.
Un DÉCOMPTE périodique compte les factures validées de la période — les
factures fournisseurs du partenaire quand on encaisse, les factures
clients marquées de l'apporteur quand on verse, avoirs en déduction — puis
fige le volume, le taux et le montant, et génère la pièce : facture client
au partenaire (à encaisser) ou facture fournisseur provisionnée au nom de
l'apporteur (à verser). Les factures comptées restent attachées au
décompte : le chiffre se justifie ligne à ligne, y compris en
négociation (« 50 000 de volume sur votre seule pharmacie »).

Garde-fous : périodes d'un même accord sans chevauchement, une facture
n'est jamais comptée deux fois, le taux du décompte est figé à sa
création (l'accord peut évoluer sans réécrire l'historique).

L'apporteur d'affaires se note une fois sur le contact ; ses factures
clients le proposent ensuite d'elles-mêmes.
""",
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'LGPL-3',
    'depends': [
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/retrocession_views.xml',
        'views/account_move_views.xml',
        'views/res_partner_views.xml',
        'views/retrocession_menus.xml',
    ],
    'demo': [
        'demo/retrocession_demo.xml',
    ],
    'installable': True,
}
