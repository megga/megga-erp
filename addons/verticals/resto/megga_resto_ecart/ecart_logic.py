"""Logique métier pure de l'écart matière.

Aucune dépendance Odoo : ce fichier se teste seul, au même standard que
resto_logic (créneaux et coût matière), declaration_logic (allergènes)
et dental_logic (le cabinet).

L'écart matière est le chiffre qui dit où part la marge d'un restaurant.
Il confronte deux consommations sur une même période :

- la RÉELLE, que l'inventaire mesure — ce qu'il y avait au début, plus
  ce qui est entré, moins ce qu'il reste à la fin ;
- la THÉORIQUE, que les fiches techniques calculent — ce que les plats
  réellement vendus auraient dû consommer.

CONVENTION DE SIGNE, et tout le module en dépend : un écart POSITIF
veut dire qu'on a consommé PLUS que la théorie. C'est une perte —
gaspillage, portions trop généreuses, casse, vol. Un écart NÉGATIF veut
dire qu'on a consommé moins que prévu, ce qui n'est pas une bonne
nouvelle non plus : ou la fiche technique ment, ou l'inventaire est
faux. Dans les deux sens, un écart qui s'écarte de zéro est une
question, jamais un résultat.
"""


def consommation_reelle(stock_initial, achats, stock_final):
    """Ce que l'inventaire mesure : ce qui était là, plus ce qui est
    entré, moins ce qui reste. Aucune magie — c'est la formule que tout
    restaurateur trace à la main sur son carnet."""
    return stock_initial + achats - stock_final


def ecart(reelle, theorique):
    """L'écart en quantité. Positif = consommé en trop (perte)."""
    return reelle - theorique


def ecart_pct(reelle, theorique):
    """L'écart en pour cent de la consommation théorique.

    None si la théorie n'est pas strictement positive : sans
    consommation attendue, un écart n'a pas de pourcentage — et
    l'appelant décide de l'affichage plutôt que de subir une division
    par zéro cachée. Même doctrine que food_cost_pct.
    """
    if theorique <= 0:
        return None
    return (reelle - theorique) / theorique * 100.0


def valorisation(ecart_quantite, prix_unitaire):
    """L'écart en francs, au prix de revient. C'est le seul chiffre que
    le patron regarde vraiment."""
    return ecart_quantite * prix_unitaire


def perte(valeur):
    """La part d'un écart valorisé qui est une PERTE : un écart négatif
    ne se compense pas avec les pertes des autres ingrédients.

    Sommer les écarts signés donnerait un total rassurant et faux — le
    beurre qu'on gaspille effacerait la farine qu'on sous-consomme. Le
    total des pertes se calcule donc sur les seuls écarts positifs.
    """
    return valeur if valeur > 0 else 0.0
