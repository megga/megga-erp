{
    'name': "Megga — Factures fournisseurs par QR (e-mail)",
    'summary': "L'e-mail crée le brouillon (alias du journal d'achat), "
               "la QR-facture le remplit : créancier, IBAN, montant, référence",
    'description': """
Le chemin le plus court entre la boîte e-mail et la facture fournisseur.

L'alias e-mail du journal d'achat (fonction du cœur : « chaque e-mail
devient une facture brouillon ») reçoit la pièce ; ce module lit la
QR-facture suisse qu'elle contient et remplit le brouillon : créancier
rapproché par IBAN — créé s'il est inconnu, avec son compte bancaire —
montant et devise en première ligne, référence QRR ou SCOR en référence
de paiement. Le compte du créancier alimente directement l'ordre
pain.001 (megga_pain001) : e-mail -> brouillon -> validation -> paiement
ISO, sans resaisie. Une saisie existante n'est JAMAIS écrasée : le
module ne touche qu'aux champs vides et raconte ce qu'il a lu dans le
fil de discussion.

Parseur pur (stdlib) de la charge utile Swiss Payment Code (SPC 0200,
Swiss Implementation Guidelines QR-bill) : IBAN contrôlé (mod 97),
cohérence QR-IBAN <-> référence QRR (mod 10 récursif), SCOR (ISO 11649),
montant, devise CHF/EUR. Toute charge non conforme est rejetée plutôt
que devinée.

Branché sur le cadre de décodage d'account (_get_edi_decoder), sous la
priorité de Factur-X/UBL : un XML complet gagne toujours contre une QR
qui ne porte que le volet paiement. Sources lues : charge SPC en texte,
images (PNG/JPEG) et pages PDF — la lecture d'images exige pyzbar
(libzbar), optionnel : absent, le module ignore silencieusement ces
pièces (l'image Docker du dépôt l'embarque).
""",
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'author': 'Megga',
    'license': 'Other proprietary',
    'depends': ['account'],
    'data': [],
    'installable': True,
}
