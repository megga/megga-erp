# Troisième verticale métier de Megga. Méta-module : l'installer tire tout
# le métier d'un garage / concessionnaire suisse — le socle Megga complet
# (débranding, QR-facture, camt, pain.001, décompte TVA), fleet du cœur
# (marques, modèles, plaques, journal de compteur) et le CRM pour la vente.
# Le module `repair` du cœur n'est PAS utilisé : il répare un produit tenu
# en stock (lot), pas le véhicule d'un client — l'atelier est un modèle
# métier propre, adossé à fleet.
{
    'name': "Megga Garage",
    'summary': "Garage / concession : parc clients, ordres de réparation, "
               "rappels d'expertise OETV, facturation QR",
    'description': """
Gestion de garage sur le socle Megga.

Parc des véhicules clients sur fleet (marques, modèles, plaques, compteur),
avec propriétaire, suivi d'expertise périodique au rythme fédéral 4-3-2
(art. 33 OETV) et plausibilité du VIN (ISO 3779). Ordres de réparation
atelier : devis, acceptation, clôture avec report du kilométrage dans le
journal de compteur, facture en un clic.
""",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'author': "Megga",
    'website': "https://github.com/megga/megga-erp",
    'license': 'LGPL-3',
    'application': True,
    'depends': [
        # Socle Megga (marque + normes suisses).
        'megga_base',
        'megga_qr_export',
        'megga_camt',
        'megga_pain001',
        'megga_tva_ch',
        # Briques du cœur pour le métier.
        'fleet',
        'crm',
        'contacts',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/auto_data.xml',
        'report/carnet_report.xml',
        'views/fleet_vehicle_views.xml',
        'views/auto_workorder_views.xml',
        'views/auto_menus.xml',
    ],
    'demo': [
        'demo/auto_demo.xml',
    ],
}
