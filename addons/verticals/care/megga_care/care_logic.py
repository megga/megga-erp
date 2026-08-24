"""Logique métier pure de la verticale conciergerie médicale.

Aucune dépendance Odoo : ce fichier se teste seul, au même standard que
camt_parser (socle camt), pain001 et dental_logic. Il couvre :

- la marge d'un événement : prix facturé au client moins coût réel payé au
  prestataire (la rétrocession d'un laboratoire ou d'une pharmacie est une
  marge comme une autre) ;
- les honoraires de coordination : au forfait ou au taux horaire ;
- le garde-fou « rien d'oublié » : quels événements restent à facturer au
  client, quels coûts attendent encore leur pièce fournisseur.
"""


def margin(price_client, cost_price):
    """Marge d'un événement : 500 facturés au client, 450 payés au
    laboratoire -> 50 de rétrocession. Négative quand l'événement est
    vendu à perte — le chiffre doit rester visible, pas écrêté."""
    return price_client - cost_price


def margin_rate(price_client, cost_price):
    """Marge rapportée au prix client, en fraction (0.10 pour 10 %).
    0.0 quand rien n'est facturé au client : un coût sans prix n'a pas
    de taux, et la division par zéro n'a pas sa place en compta."""
    if not price_client:
        return 0.0
    return margin(price_client, cost_price) / price_client


def fee_total(mode, flat_amount=0.0, hourly_rate=0.0, hours=0.0):
    """Honoraires de coordination d'un mandat.

    Deux modes contractuels : « forfait » (montant convenu d'avance,
    typique du check-up) et « horaire » (taux x heures, typique des longs
    séjours). Tout autre mode est une erreur de programmation, pas un cas
    silencieux."""
    if mode == 'forfait':
        return flat_amount
    if mode == 'horaire':
        return hourly_rate * hours
    raise ValueError("mode d'honoraires invalide : %r" % (mode,))


def unbilled_indexes(events):
    """Indices des événements encore à facturer au client.

    `events` : couples (prix_client, facture_client_liée). Un événement
    compte dès qu'il porte un prix client et qu'aucune ligne de facture
    client n'y est rattachée ; un événement gratuit (prix nul) n'est
    jamais « oublié »."""
    return [
        index for index, (price_client, has_client_line) in enumerate(events)
        if price_client and not has_client_line
    ]


def uncovered_cost_indexes(events):
    """Indices des événements dont le coût attend encore sa pièce.

    `events` : couples (coût_réel, facture_fournisseur_liée). Un coût
    saisi sans facture fournisseur rattachée est une écriture qui ne
    tient que sur la mémoire — exactement ce que le mandat doit rendre
    impossible."""
    return [
        index for index, (cost_price, has_supplier_bill) in enumerate(events)
        if cost_price and not has_supplier_bill
    ]
