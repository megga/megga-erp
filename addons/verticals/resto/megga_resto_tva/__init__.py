from . import models


def post_init_hook(env):
    """À l'installation : câble la TVA à l'emporter pour chaque société
    déjà au plan comptable suisse. Les sociétés qui reçoivent leur plan
    plus tard passent par le menu Configuration > TVA à l'emporter (CH)
    — la méthode est idempotente."""
    for company in env['res.company'].search([]):
        company._megga_setup_takeaway_vat()
