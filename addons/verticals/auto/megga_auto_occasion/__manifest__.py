{
    'name': "Megga Auto — Occasions (reprise et revente, TVA CH)",
    'summary': "Commerce de véhicules d'occasion : impôt préalable "
               "fictif (art. 28a LTVA) et imposition de la marge "
               "(art. 24a) pour les pièces de collection",
    'description': """
La reprise d'un vehicule a un particulier ne porte pas de TVA — mais la
loi suisse ne taxe pas le garage sur le prix plein pour autant :

- voie ordinaire, l'IMPOT PREALABLE FICTIF (art. 28a LTVA) : le prix de
  reprise est repute TVA comprise, le garage deduit 8.1/108.1 de ce
  prix, puis revend au taux plein — la charge nette revient a taxer la
  marge. La facture de reprise porte la taxe fictive (incluse dans le
  prix), la facture de revente la TVA pleine incluse.
- pieces de collection, l'IMPOSITION DE LA MARGE (art. 24a LTVA) : TVA
  due = marge x 8.1/108.1, marge negative sans credit, pas de deduction
  fictive, et INTERDICTION de mentionner la TVA sur la facture de vente
  (la mentionner rendrait tout le montant du).

La fiche occasion suit le vehicule de la reprise a la revente (le
nouveau proprietaire entre au parc clients), calcule les deux regimes
et genere les factures en un clic. Taxes creees par societe au premier
usage (idempotent, memes xml_ids de societe que le plan comptable) ;
sans plan comptable suisse, la facturation fictive refuse proprement.
""",
    'version': '19.0.1.0.0',
    'author': "Megga",
    'license': 'LGPL-3',
    'category': 'Industries',
    'depends': [
        'megga_auto',
        'l10n_ch',
    ],
    'auto_install': True,
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/occasion_views.xml',
    ],
}
