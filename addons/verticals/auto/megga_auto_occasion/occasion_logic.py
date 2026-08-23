"""Arithmétique TVA du commerce d'occasion — fonctions pures.

Les deux régimes suisses de l'occasion reprise sans TVA :

- impôt préalable fictif (art. 28a LTVA) : le prix payé au particulier
  est réputé TVA comprise — la part déductible en est extraite
  (taux/(100+taux)), la revente porte la TVA pleine, la charge nette
  vaut la différence, soit la TVA de la marge ;
- imposition de la marge (art. 24a LTVA, pièces de collection) : la TVA
  due est extraite de la marge elle-même ; une marge nulle ou négative
  ne doit rien et ne crée aucun crédit.

Arrondis au centime, comme le décompte.
"""


def vat_from_gross(gross, rate):
    """Part de TVA contenue dans un montant réputé TVA comprise."""
    return round(gross * rate / (100.0 + rate), 2)


def fictive_input_tax(buy_price, rate):
    """Impôt préalable fictif sur une reprise (art. 28a LTVA)."""
    if buy_price <= 0:
        return 0.0
    return vat_from_gross(buy_price, rate)


def margin_vat(buy_price, sale_price, rate):
    """TVA due sous imposition de la marge (art. 24a LTVA).

    Marge nulle ou négative : rien — et jamais de crédit."""
    margin = sale_price - buy_price
    if margin <= 0:
        return 0.0
    return vat_from_gross(margin, rate)
