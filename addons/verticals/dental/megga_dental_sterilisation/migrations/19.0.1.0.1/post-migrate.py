from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Re-parente la categorie des sets sous les consommables du cabinet.

    Le correctif a ete pose dans les DONNEES du module, a l'interieur
    d'un bloc `noupdate="1"` : une base deja installee ne l'aurait donc
    jamais recu — la mise a jour saute l'enregistrement, et les tests,
    eux, installent a neuf et passent. Les sets seraient restes
    invisibles des ecrans du magasin et du selecteur de kit, exactement
    le defaut que le correctif pretend fermer.

    Le bloc reste `noupdate` : un cabinet qui renomme sa categorie ne
    doit pas la voir revenir a chaque montee de version. C'est donc ici,
    une fois, que le parentage se rattrape.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    categorie = env.ref(
        'megga_dental_sterilisation.product_category_dental_sets',
        raise_if_not_found=False)
    consommables = env.ref(
        'megga_dental_stock.product_category_dental_supplies',
        raise_if_not_found=False)
    if categorie and consommables and not categorie.parent_id:
        categorie.parent_id = consommables.id
