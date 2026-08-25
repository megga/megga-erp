# Deuxième verticale métier de Megga. Méta-module : l'installer tire tout le
# métier d'un restaurant suisse — le socle Megga complet (débranding,
# QR-facture, camt, pain.001, décompte TVA) et le POS restaurant du cœur
# Community (plan de salle, tables, cuisine). La surcouche apporte ce qui
# n'existe qu'en Enterprise ou nulle part : le carnet de réservations sur
# les tables du plan de salle, et les fiches techniques avec coût matière.
{
    'name': "Megga Restaurant",
    'summary': "Restaurant : réservations de tables, fiches techniques "
               "et coût matière, sur le POS du cœur",
    'description': """
Gestion de restaurant sur le socle Megga.

Carnet de réservations adossé aux tables du plan de salle (pos_restaurant),
avec détection des conflits de créneaux et marquage automatique des clients
non venus. Fiches techniques par plat : ingrédients d'une portion, coût
matière, marge brute et report du coût sur l'article vendu.
""",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'Other proprietary',
    'application': True,
    'depends': [
        # Socle Megga (marque + normes suisses).
        'megga_base',
        'megga_qr_export',
        'megga_camt',
        'megga_pain001',
        'megga_tva_ch',
        # Briques du cœur pour le métier.
        'pos_restaurant',
        'contacts',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/resto_data.xml',
        'views/resto_reservation_views.xml',
        'views/resto_recipe_views.xml',
        'views/resto_production_views.xml',
        'report/shopping_report.xml',
        'views/resto_menus.xml',
    ],
    'demo': [
        'demo/resto_demo.xml',
    ],
}
