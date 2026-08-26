Tu dessines l'UI/UX d'une section d'un ERP dentaire suisse romand : **Megga**, une
surcouche propriétaire d'Odoo 19 Community. La section s'appelle **« Intendance du
cabinet »** (libellé de navigation : « Intendance »). Elle réunit trois modules déjà
livrés en backend : le magasin, la stérilisation, le registre du matériel.

Tout ce qui suit est **réel** : ce sont les libellés, colonnes, textes de refus et
données de démonstration effectivement présents dans le produit. N'invente pas de
libellé français quand je t'en donne un : reprends-le mot pour mot. Tu peux inventer
la mise en forme, la hiérarchie visuelle, l'espace, la couleur secondaire, les icônes,
les états de survol — pas les mots.

---

# 0. LA MISSION

Une page longue, en français, qui présente la section « Intendance » en **trois actes**,
un verbe par acte. Ce n'est pas une plaquette commerciale : c'est une maquette d'UI/UX.
Chaque acte montre de vrais écrans (listes, formulaires, kanban, boîtes de dialogue),
avec de vraies données, dans une chrome d'application crédible.

Le sous-titre de la page, à afficher tel quel :

> **Le magasin compte, la stérilisation prouve, le registre entretient.**

La thèse à faire sentir d'un bout à l'autre, en une phrase :

> **Le stock ne bloque jamais la clinique — mais il refuse de mentir.**

---

# 1. LE PRODUIT, EN TROIS PHRASES

- **Le magasin** compte ce qui se consomme au fauteuil : compresses, anesthésiques,
  composites, gants. Chaque acte du catalogue porte son « kit » ; clore une séance
  décompte le magasin tout seul, en FEFO (le lot le plus proche de sa date part le
  premier). **Zéro ressaisie au fauteuil.**
- **La stérilisation** prouve. Chaque charge d'autoclave est un cycle numéroté
  (STE/2026/0001) ; les sachets qui en sortent portent ce numéro et une date de
  péremption de stérilité. Un an plus tard, le registre répond à « avec quoi m'a-t-on
  soigné ? ».
- **Le registre** entretient ce qui dure : autoclave, unit, compresseur, générateur de
  rayons X — rattachés au fauteuil qu'ils servent, avec leurs entretiens préventifs
  récurrents.

---

# 2. À QUI ÇA S'ADRESSE — TROIS RÔLES, TROIS VUES DIFFÉRENTES

| Rôle affiché | Ce qu'il voit | Ce qu'il ne voit PAS |
|---|---|---|
| **Réception** (assistante) | les cycles en lecture, le bouton « Séances servies », la case « Consommables décomptés » | le menu du magasin, le lien vers le transfert de stock |
| **Soins** (praticien) | tout le clinique, la section « Stérilisation » de la fiche séance | le registre du matériel, sauf s'il est gestionnaire d'équipements |
| **Gestionnaire d'équipements** (responsable technique) | le registre, les entretiens, la saisie des cycles | **qui a été soigné** : le bouton « Séances servies » lui est fermé |
| **Utilisateur / Responsable stock** | le magasin, les lots, les quantités | le clinique |

Deux règles d'affichage à rendre visibles dans la maquette, elles sont doctrinales :

- **« Le magasinier voit le cycle et sa conformité ; il ne voit pas qui a été soigné. »**
- **« Un compteur doit dire la même chose que l'écran qu'il ouvre. »** (un bouton
  statistique et l'écran qu'il ouvre portent toujours la même garde de droits)

---

# 3. LA CHARTE

- **Couleur de marque, unique : `#0E6B4F`** (vert sombre). C'est la seule valeur de
  marque du produit. Tu peux proposer une palette secondaire et une typographie — c'est
  précisément ce qui manque et ce que j'attends de toi. Le reste du produit est du thème
  Odoo Community 19 nu.
- **Langue : français de Suisse romande.** Montants en CHF, dates au format `31.12.2026`,
  adresses genevoises et vaudoises. Les décimales suisses s'écrivent avec une apostrophe
  de milliers (`1:100'000`).
- **Ton : sobre, affirmatif, jamais publicitaire.** Le produit écrit des phrases comme
  « Le soin est fait, le stock le constate ». Pas de superlatif, pas de « révolutionnaire ».
- **Densité : celle d'un outil de gestion**, lu debout, entre deux patients. Les listes
  sont serrées, les colonnes secondaires sont masquables (je te dis lesquelles).

## Le vocabulaire des couleurs — trois signaux, pas un de plus

C'est une charte stricte, déjà en place. Chaque décor lit un **champ réel**, jamais un
calcul de vue.

| Décor | Où | Déclencheur |
|---|---|---|
| **Rouge** (`danger`) | liste « Lots du cabinet » | date de péremption dépassée → **le lot est périmé** |
| **Orange** (`warning`) | liste « Lots du cabinet » | date d'alerte atteinte, péremption pas encore → **fenêtre d'alerte ouverte** |
| **Rouge** (`danger`) | liste « Cycles de stérilisation » | état « Non conforme » |
| **Grisé** (`muted`) | liste « Cycles de stérilisation » | état « Brouillon » |
| **Orange** (`warning`) | lignes « Sets de la charge » | pas de délai de stérilité réglé sur le produit |
| **Gras** | colonne « Lot » | toujours — le numéro de lot est la clé de lecture |

Rien d'autre n'est coloré. Un cycle « Validé » reste en noir normal.

## Les tris par défaut, qui portent le sens

- « Lots et péremption » : **par date de péremption croissante**. Parce que « la question
  du magasinier dentaire n'est pas « quel lot ai-je ? » mais « qu'est-ce qui périme
  bientôt ? » ».
- « Cycles d'autoclave » : la charge la plus récente en haut.
- « Appareils » : **déjà regroupé par fauteuil à l'ouverture**.

---

# 4. L'OSSATURE DE LA PAGE

```
En-tête ........... Intendance du cabinet
                    « Le magasin compte, la stérilisation prouve, le registre entretient. »
Acte I ............ COMPTER      — le magasin
Acte II ........... PROUVER      — la stérilisation
Acte III .......... ENTRETENIR   — le registre
Acte IV ........... LES REFUS    — ce que le produit ne fait pas
Acte V ............ QUI VOIT QUOI
Acte VI ........... SEPT ARBITRAGES DE VOCABULAIRE
```

Les deux **scènes** à mettre en récit (ce sont les seuls moments narratifs de la page,
tout le reste est écran) :

**Scène A — le lendemain matin.** L'indicateur biologique d'une charge validée hier
revient « Non conforme ». Douze sets d'examen sont déjà distribués, une séance a déjà
été servie. Changer la liste déroulante suffit : les sets encore en rayon se bloquent,
et la séance est nommée au fil de discussion. Montre l'avant/après.

**Scène B — la clôture de séance.** On clique « Terminer ». Les kits des actes
s'additionnent produit par produit, la sortie part en FEFO, et le magasin constate —
même quand il ne peut pas servir. Montre l'activité engendrée.

---

# 5. ACTE I — COMPTER (le magasin)

Menu réel : **Dentaire ▸ Intendance ▸ Stock du cabinet**, quatre entrées dans cet ordre :
« Consommables » · « À commander » · « Quantités en stock » · « Lots et péremption ».

## 5.1 Écran « Consommables »

Question : *« Qu'est-ce que le cabinet consomme au fauteuil, et à quel prix ? »*
Titre de liste : **« Consommables du cabinet »**. Édition en masse activée.

Colonnes, dans l'ordre — `[masquée]` = masquable et masquée par défaut :

`Nom` · `Référence interne` · **`En stock`** · **`Prévu`** · **`Min`** *(lecture seule)* ·
**`Max`** *(lecture seule)* · **`Règles`** `[masquée]` · `Coût` · `Unité` `[masquée]` ·
**`Fournisseurs`** *(étiquettes, lecture seule)*

Détail de design important : Min / Max / Règles s'**affichent** mais ne se saisissent pas
ici. « Les annoncer éditables serait mentir à l'écran. »

Écran vide :
> **Référencez votre premier consommable**
> Compresses, anesthésiques, composites, gants : ce que le cabinet consomme au fauteuil.
> Suivi par lot et par date de péremption.

## 5.2 Écran « À commander »

Question : *« Qu'est-ce qui va manquer, et qui me le vend ? »*
Réservé au **Responsable** du stock (le magasinier simple ne voit pas cette ligne de menu).
Liste éditable en ligne. Filtre « Non reporté » actif d'entrée.

Colonnes : `Produit` · `Disponible` · `Prévision` · *icône graphe* · `Déclencheur`
(« Automatique » / « Manuelle ») `[masquée]` · **`Min`** · **`Max`** · **`À commander`**
· `Date limite` `[masquée, rouge si dépassée]`

Boutons de ligne, textes exacts : **« Commander »** · **« Automatiser »** · **« Reporter »**.

## 5.3 Écran « Quantités en stock »

Question : *« Combien en reste-t-il, et où ? »*
Liste éditable servant d'ajustement d'inventaire. Filtre « Emplacements internes » actif.
Bouton d'en-tête **« Relocaliser »** (responsable seulement).

Colonnes : `Emplacement` · `Produit` · **`Lot/numéro de série`** ·
**`Quantité inventoriée`** *(la colonne éditable, totalisée en pied)* · `Quantité réservée`
Boutons de ligne : **« Historique »** *(icône horloge)* · **« Réassort »** *(icône flèches)*
Filtres notables : **« Stock négatif »**, **« Lots périmés »**, **« Lots en alerte »**.

Écran vide :
> **Rien en rayon pour l'instant**
> Les quantités arrivent par les réceptions fournisseur et partent à la clôture des séances.

Détail à montrer : une **ligne à quantité négative** — c'est là que se lit l'écart quand
le stock a servi ce qu'il n'avait pas.

## 5.4 Écran « Lots et péremption » — L'ÉCRAN-SIGNATURE

Question : *« Qu'est-ce qui périme bientôt ? »*
Titre de liste : **« Lots du cabinet »**. **Création interdite** : un lot naît à la
réception, jamais à la main. Trié par date de péremption croissante.

Colonnes : **`Lot/numéro de série`** *(toujours en gras)* · `Produit` ·
**`Cycle de stérilisation`** · **`Cycle`** *(état du cycle)* · **`En stock`** ·
`Date d'expiration` · `Date d'alerte` · `Date d'enlèvement` `[masquée]` · **`Périmé`**
*(case en lecture)*

Filtres : **« Périmés »** · **« Péremption proche »** · **« En stock »** ·
**« Cycle non conforme »**. Regroupement : « Produit ».

Écran vide :
> **Aucun lot de consommable pour l'instant**
> Les lots naissent à la réception d'une commande fournisseur, avec leur date de
> péremption. Le cabinet sert ensuite le lot le plus proche de sa date (FEFO).

**Fiche de lot** (au clic) : deux pastilles flottantes en haut à droite —
**« Bientôt périmé »** *(orange)* et **« Périmé »** *(rouge)*. Boutons statistiques
« Transferts », « Traçabilité ». Groupes « Informations », « Inventaire », « Dates »
(« Expiration », « Alerte à partir du/de », « À consommer de préférence avant »,
« Date d'enlèvement »).

## 5.5 Le kit — onglet « Consommables » de la position tarifaire

Question : *« Qu'est-ce qu'un acte emporte, pour ne plus jamais le ressaisir ? »*
Chemin : Dentaire ▸ Configuration ▸ « Tarif par points ».

Formulaire **« Position tarifaire »** — pas d'en-tête, pas de statusbar, pas de chatter.
Titre : label « Numéro », en h1 le code, placeholder `4.0100`.
À gauche : `Libellé`, `Points tarifaires (PT)`. À droite : `Chapitre`,
`Constat au terme de l'acte`, `Actif`.

Un seul onglet, **« Consommables »**, liste éditable :
*poignée de réordonnancement* · **`Consommable`** · **`Quantité par acte`** · **`Unité`**

Aide du champ « Quantité par acte », à afficher :
> Ce qu'un acte consomme. Deux actes de la même séance additionnent leurs besoins.

Paragraphe gris sous la liste, texte exact :
> Ce qu'un acte consomme au fauteuil. La clôture de la séance le décompte du magasin —
> deux actes qui partagent un produit additionnent leurs besoins.

## 5.6 Ce que la clôture de séance ajoute à la fiche de traitement

En-tête de la séance : **« Planifier »** · **« Terminer »** · **« Créer la facture »** ·
**« Annuler »** · **« Prescrire »**. Statusbar : **Devis → Planifié → Terminé**.

Deux champs apparaissent après « Facture » :
1. **« Consommables décomptés »** — case en lecture, invisible tant qu'elle est fausse,
   **visible de tous** (la réception doit savoir que le décompte a eu lieu).
2. **« Consommation »** — lien vers le transfert (ex. `WH/SOINS/00001`), **réservé au
   groupe stock**. Aide : « Le mouvement de stock engendré par la clôture de cette
   séance. Sa présence interdit un second décompte. »

Le transfert ne porte que la **référence** de la séance (`TRT/2026/0001`) — jamais le
patient, jamais le diagnostic, jamais le détail des actes. C'est une règle nLPD, testée :
> **Un magasinier qui lit les mouvements ne lit pas le dossier médical.**

**L'activité engendrée quand le magasin n'a pas pu servir** — à dessiner comme une carte
d'activité posée **sur le transfert**, jamais sur la séance :

> **Écart de consommation au fauteuil**
>
> La séance TRT/2026/0001 a été close alors que le magasin ne pouvait pas la servir
> complètement :
> - Compresses stériles 5x5 cm : CMP-2024-07 écarté(s), périmé(s).
> - Gants nitrile taille M : 3 Unités sortie(s) sans lot — stock insuffisant ou plus rien
>   de servable.
>
> **Le soin est fait, le stock le constate** — vérifiez les quantités en rayon.

---

# 6. ACTE II — PROUVER (la stérilisation)

Menu réel : **Dentaire ▸ Intendance ▸ Stérilisation ▸ Cycles d'autoclave**.

## 6.1 Liste « Cycles d'autoclave »

Question : *« Quelles charges sont passées à l'autoclave, et laquelle pose problème ? »*
La plus récente en haut.

Colonnes : **`Numéro de cycle`** · `Début du cycle` · `Autoclave` · `Opérateur` *(avatar)*
· `Programme` `[masquée]` · `Test Helix conforme` `[masquée]` · **`Indicateur biologique`**
· **`État`**

Décors : **rouge** si « Non conforme », **grisé** si « Brouillon ».

Filtres : « Brouillon » · « Validé » · « Non conforme » — *séparateur* —
**« Indicateur en attente »**. Ce dernier est décrit dans le code comme
**« le geste du matin »** : mets-le en avant, c'est le filtre le plus utilisé.
Regroupements : « Autoclave », « État », « Mois ».

Écran vide :
> **Aucun cycle enregistré**
> Une charge d'autoclave par cycle : l'appareil, les contrôles, et les sets qui en
> sortent. C'est ce registre qui répond, un an plus tard, à « avec quoi m'a-t-on
> soigné ? ».

## 6.2 Fiche de charge — L'ÉCRAN LE PLUS DENSE DU LOT

Question : *« Cette charge est-elle conforme, qu'en est-il sorti, et où sont partis ces
sachets ? »*

**En-tête**, trois boutons dans cet ordre :
1. **« Valider la charge »** *(primaire, seulement à l'état Brouillon)*
   Info-bulle : « Les sets entrent en rayon, chacun avec son numéro de cycle et sa date
   de péremption de stérilité. »
2. **« Marquer non conforme »** *(secondaire)* — confirmation obligatoire, texte exact :
   > Les sets de cette charge encore en rayon seront bloqués, et les séances déjà servies
   > seront nommées. **Continuer ?**
3. **« Remettre en brouillon »** *(seulement si non conforme ET aucune entrée en stock)*

**Statusbar : Brouillon → Validé.** « Non conforme » est un état de sortie, pas une étape
du parcours : il n'apparaît dans la barre que lorsqu'il est atteint.

**Bouton statistique unique**, icône silhouette de médecin, libellé sur deux lignes :
**« Séances / servies »**. Sans compteur chiffré. Invisible avant l'entrée en stock.
**Réservé au groupe Réception** — motif à écrire dans la maquette :
> Le rappel nomme des séances, donc des patients. Le magasinier voit le cycle et sa
> conformité ; il ne voit pas qui a été soigné.

Au clic, une fenêtre intitulée **« Séances servies par STE/2026/0002 »**.

**Titre de la feuille** : label « Cycle », en h1 le numéro (`STE/2026/0002`), en lecture seule.

**Groupe « La charge »** :
`Autoclave` *(obligatoire)* — aide : « L'appareil du registre du matériel. Son historique
d'entretien et ses validations périodiques sont **la moitié de la preuve**. » ·
`Fauteuil desservi` *(invisible si vide)* · `Début du cycle` · `Opérateur` *(avatar)*

**Groupe « Les contrôles »** :
- `Programme` — trois valeurs aux libellés longs, à afficher tels quels :
  « Cycle B — charge creuse, poreuse ou emballée » / « Cycle S — charge définie par le
  fabricant » / « Cycle N — instruments massifs nus »
- `Palier (°C)` — défaut 134.0
- `Durée du palier (min)` — défaut 18.0
- `Test Helix conforme` — **interrupteur**, pas une case
- **`Indicateur biologique`** — « Sans objet » / « En attente » / « Conforme » /
  « Non conforme ». **Seul contrôle qui reste modifiable après validation** — les
  « Observations » restent saisissables elles aussi. Aide :
  > Le résultat arrive souvent le **LENDEMAIN**, une fois les sachets déjà distribués :
  > c'est précisément pour ce cas-là que le rappel existe.

  Effet caché majeur, à mettre en scène : passer ce champ à « Non conforme » sur une
  charge validée déclenche **tout seul** le blocage et le rappel. La liste déroulante
  fait basculer l'état sans qu'on ait touché à un bouton.

Tous les autres champs se **figent visuellement** à la validation.

**Onglet « Sets de la charge »** — liste éditable :
`Set` · `Sachets` · `Unité` · `Stérilité jusqu'au` *(lecture seule, calculée)*
**Ligne orange** si « Stérilité jusqu'au » est vide.
Paragraphe gris sous la liste, texte exact :
> Chaque ligne devient un lot à la validation : le sachet porte le numéro de cycle, et sa
> stérilité expire au délai réglé sur le produit. Une ligne **en orange** est un set SANS
> délai réglé : il entrera en rayon, mais sans date de stérilité — ni FEFO, ni garde.

**Onglet « Sets produits »** — réservé au groupe stock, absent avant validation.
`Lot/numéro de série` · `Produit` · `Stérilité jusqu'au`, puis le champ **« Entrée en stock »**.

**Onglet « Observations »** — placeholder :
« Anomalie relevée, charge reprise, remarque du technicien… »
Paragraphe gris :
> Le rapport de cycle imprimé par l'autoclave s'attache au fil de discussion ci-dessous :
> c'est lui, la preuve.

**Fil de discussion** en pied : c'est là qu'atterrit le rappel et qu'on attache le rapport
imprimé par l'autoclave.

## 6.3 Le rappel — le message posté au fil de discussion

Avec séances servies (texte exact) :
> **Charge marquée NON CONFORME.** 1 séance(s) ont déjà consommé des sets de ce cycle :
> **TRT/2026/0001**
>
> Ce relevé suit les sorties passées par la clôture de séance. **Un set sorti à la main,
> hors séance, n'y figure pas** : vérifiez aussi ce qui manque en rayon.

Sans séance servie :
> Charge marquée NON CONFORME. Aucune séance n'a encore consommé de set de ce cycle ;
> **ceux qui restent en rayon sont bloqués.**

## 6.4 Ce que la stérilisation ajoute ailleurs

- **Sur la fiche de séance** : une section **« Stérilisation »** en fin de feuille,
  réservée au groupe Soins, invisible si la séance n'a consommé aucun set. Liste en
  lecture : `Numéro de cycle` · `Début du cycle` · `Autoclave` · `Indicateur biologique`
  · `État`. Paragraphe gris : « Les charges d'autoclave dont sont sortis les sets
  consommés par cette séance. »
- **Sur les lots du magasin** : les deux colonnes « Cycle de stérilisation » et « Cycle »,
  plus le filtre « Cycle non conforme ».
- **Nommage des lots** : une charge à une seule ligne donne un lot au numéro de cycle nu
  (`STE/2026/0002`) ; plusieurs lignes donnent le rang (`STE/2026/0005-1`,
  `STE/2026/0005-2`).

---

# 7. ACTE III — ENTRETENIR (le registre)

Menu réel : **Dentaire ▸ Intendance ▸ Matériel ▸ « Appareils » · « Entretiens »**.

## 7.1 Écran « Appareils » — le registre groupé par fauteuil

Question, et c'est la meilleure accroche de la section :
> Un cabinet ne cherche pas « l'autoclave 3 », il cherche **ce qu'il y a autour du
> fauteuil 2** — pour savoir **ce qui s'arrête quand un appareil part en réparation.**

Titre de liste : **« Matériel du cabinet »**. **L'écran s'ouvre déjà regroupé par fauteuil.**

Colonnes : `Nom de l'équipement` · **`Fauteuil`** · `Catégorie d'équipement` · `Numéro de série` · `Technicien`
*(avatar)* · `Date d'assignation` `[masquée]` · `Date d'expiration de garantie` ·
**`Entretiens en cours`**

Filtres : **« Rattaché à un fauteuil »** · **« Local technique »** — *séparateur* —
**« Sous garantie »** — *séparateur* — **« Archivé »**.
Regroupements : **« Fauteuil »** et **« Famille »**.

Écran vide :
> **Aucun appareil au registre**
> Autoclave, compresseur, générateur de rayons X, unit : inscrivez ce qui se révise et se
> prouve, et rattachez-le au fauteuil qu'il sert.

En vue kanban : badge **rouge** portant le nombre d'entretiens ouverts, barre de
progression en tête de colonne (vert = planifié, orange = aujourd'hui, rouge = en retard).

## 7.2 Fiche fauteuil — l'écran phare du module

Question : *« Ce fauteuil, qu'est-ce qu'il porte — et donc que perd-on quand on
l'immobilise ? »*

Bouton statistique unique, icône clé plate, libellé **« Appareils »**. Il ouvre une
fenêtre intitulée **« Matériel de Fauteuil 2 »**.
Titre : label « Fauteuil », h1, placeholder « Fauteuil 1 ».
Champs : `Séquence` — aide : « Ordre d'attribution automatique : à créneau libre égal, le
premier de la liste gagne. » · `Actif` *(interrupteur)* · `Note` — placeholder
« Étage, équipement particulier… »

Onglet **« Matériel »**, liste en lecture seule, puis ce paragraphe gris, texte exact :
> Ce qui est installé autour de ce fauteuil. **Un fauteuil qui porte du matériel ne se
> supprime plus : il s'archive.**

## 7.3 Écran « Entretiens »

Question : *« Qu'est-ce qui est en panne, et qu'est-ce qui doit être révisé ? »*
**Kanban par défaut**, colonnes = les étapes :
**« Nouvelle demande » → « En cours » → « Réparé » / « Rebut »** (les deux dernières
repliées). Les demandes annulées sont masquées d'entrée.

Carte : nom en gras, ligne « Demandé par : » + demandeur, l'appareil et sa catégorie,
la date planifiée. En pied : étoiles de priorité, badge **orange « Annulé »** si archivée,
pastille d'état (gris « En cours » / **rouge** « Bloqué » / **vert** « Prêt pour la
prochaine étape »), avatar du technicien.

Sur le formulaire : **« Type de maintenance »** en boutons radio — **« Corrective »** /
**« Préventive »** ; et si préventive, le bloc **« Récurrente »** :
« Répéter tou(te)s les [n] [Jours/Semaines/Mois/Ans] [Pour toujours / Jusqu'au] ».

Écran vide :
> **Aucune demande d'entretien**
> Une panne se signale ici, et un entretien périodique (validation d'autoclave, révision
> du compresseur) se règle en demande *récurrente* : clore celle du trimestre engendre
> celle du suivant.

---

# 8. ACTE IV — LES REFUS

Quatre boîtes de dialogue à dessiner, **mot pour mot**. Ce sont des textes de produit,
pas des erreurs techniques : traite-les comme du contenu, avec de l'air et de la
typographie, pas comme des toasts d'erreur.

**1. Le lot périmé ne part pas en soins.**
> Le lot **CMP-2024-07** de **Compresses stériles 5x5 cm** est périmé depuis le
> **05.08.2026** : il ne peut pas partir en soins.
>
> Sortez-le du rayon et détruisez-le proprement (rebut) — **le rebut, lui, reste permis.**

**2. Le set non stérile ne part pas en soins.**
> Le set **STE/2026/0002** de **Set d'examen stérilisé** ne peut pas partir en soins :
> **le cycle STE/2026/0002 a été marqué NON CONFORME**.
>
> Sortez-le du rayon et **repassez-le à l'autoclave** — le rebut, lui, reste permis.

**3. Un cycle ne s'efface pas.**
> Un cycle de stérilisation ne se supprime pas : c'est un document de preuve.
> Une charge qui n'a pas abouti se marque **NON CONFORME**.

**4. Un cycle clos est figé.**
> Le cycle **STE/2026/0003** est clos : son relevé ne se modifie plus.
> Un registre de stérilisation est un document de preuve. Si le résultat d'un contrôle
> change, marquez le cycle **NON CONFORME** — ses sets seront bloqués et les séances
> servies seront nommées.

**La doctrine à afficher à côté**, c'est l'argument central :
> Le refus ne vise **QUE** la destination soins. Le rebut, le retour fournisseur et
> l'ajustement d'inventaire restent permis : un lot périmé doit pouvoir être détruit
> proprement, et l'interdire l'immobiliserait en rayon pour toujours.
>
> **Le cœur, lui, se contente d'avertir — un wizard de confirmation qui se contourne d'un
> clic. La règle du cabinet, elle, refuse.**

Quelques refus plus courts, utilisables en vignettes :
- « Le cycle **%s** est un cycle B : sans test Helix conforme, **la pénétration de vapeur
  n'est pas prouvée**. »
- « **%s n'est pas tracé par lot** : sans lot, aucun numéro de cycle ne peut être porté
  par le sachet, et **la traçabilité n'existe pas**. »
- « La quantité consommée par un acte doit être strictement positive — **un kit à zéro ne
  consomme rien, autant retirer la ligne.** »
- « **Rien ne revient tout seul.** Une séance clôturée puis annulée ne ré-intègre aucun
  stock : une compresse sortie ne se remet pas en boîte. »

---

# 9. LES VRAIES DONNÉES — utilise celles-ci, pas des inventions

## Consommables (péremption 540 j, alerte 60 j)
Fournisseur : **Dentaire Diffusion SA**, Route de Chêne 12, 1208 Genève — délai 4 jours.

| Produit | Conditionnement | Prix | Min / Max |
|---|---|---|---|
| Compresses stériles 5x5 cm | boîte de 100 | 12.50 | 60 / 200 |
| Articaine 4% adrénaline 1:100'000 | cartouche 1.7 ml | 1.35 | 100 / 400 |
| Composite photopolymérisable A2 | seringue 4 g | 38.00 | 10 / 40 |
| Gants nitrile taille M | boîte de 100 | 9.90 | 40 / 120 |

## Lots — les dates racontent l'écran (deux rouges, deux oranges, le reste sain)

| Lot | Péremption | En stock | Décor |
|---|---|---|---|
| CMP-2024-07 | il y a 21 jours | 6 | **rouge — périmé** |
| ART-25-118 | il y a 4 jours | 30 | **rouge — périmé** |
| CMP-A2-9911 | dans 51 jours | 12 | **orange — alerte** |
| CMP-2026-02 | dans 34 jours | 40 | **orange — alerte** |
| CMP-2026-05 | dans 210 jours | 60 | normal |
| ART-26-042 | dans 96 jours | 250 | normal |
| CMP-A2-1207 | dans 320 jours | 18 | normal |
| GNT-4471 | dans 275 jours | 24 | normal |

## Positions tarifaires et leurs kits

| Code | Libellé | PT | Kit |
|---|---|---|---|
| 4.0000 | Examen et bilan | 35 | 1 Set d'examen stérilisé |
| 4.0100 | Obturation composite une face | 40 | 2 compresses + 1 composite + 1 gants |
| 4.0200 | Détartrage complet | 25 | 3 compresses + 1 gants |
| 4.0300 | Anesthésie locale | 12 | 2 articaine + 1 gants |

Patiente de démonstration : **Camille Rochat**. Fauteuils : **Fauteuil 1**, **Fauteuil 2**,
**Salle de chirurgie**.

## Registre du matériel — 12 appareils
Fournisseur : **Technic Dentaire Sarl**, Chemin du Closel 5, 1020 Renens.

| Appareil | Fauteuil | N° de série | Modèle | Coût |
|---|---|---|---|---|
| Autoclave classe B 18 l | — | AC-B18-77421 | Statim 18B | 8 900.00 |
| Thermosoudeuse à rouleaux | — | TS-3300-118 | SealPro 330 | 1 450.00 *(garantie expirée)* |
| Bac à ultrasons 5 l | — | BU-5-9080 | SonoClean 5 | 890.00 |
| Unit dentaire complet | Fauteuil 1 | UD-A200-4417 | Anthos A200 | 32 500.00 |
| Scialytique LED | Fauteuil 1 | SC-LED-2291 | Luxia 5000 | 3 200.00 |
| Radiographie rétro-alvéolaire | Fauteuil 1 | RX-RA-5514 | Focus X | 6 400.00 |
| Unit dentaire complet | Fauteuil 2 | UD-A200-4418 | Anthos A200 | 33 900.00 |
| Caméra intra-orale | Fauteuil 2 | CIO-7712 | SoproCare | 4 700.00 |
| Aspiration chirurgicale | Salle de chirurgie | ASP-CH-3312 | Turbo Smart | 5 100.00 |
| Panoramique dentaire | — | PAN-88213 | OrthoPantomo 3D | 48 000.00 |
| Compresseur sans huile 50 l | — | CP-50-1102 | SilentAir 50 | 4 300.00 |
| Pompe à salive centralisée | — | PS-CTR-6640 | Cattani Uni-Jet | 2 700.00 |

Quatre familles d'appareils : **Stérilisation**, **Imagerie**, **Unit et fauteuil**,
**Local technique**. La note de la famille « Local technique », à citer quelque part :
> Compresseur, pompe à salive, aspiration, adoucisseur — ce qui sert tous les fauteuils à
> la fois, et dont la panne arrête le cabinet entier.

## Entretiens de démonstration
- **« Validation trimestrielle de l'autoclave »** — préventif, récurrent 3 mois, déjà clos
  (le suivant a été engendré tout seul).
- **« Révision annuelle du compresseur »** — préventif, récurrent 1 an, priorité 2.
- **« Déclenchement intermittent au fauteuil 1 »** — correctif, priorité 3, **bloqué**
  (pastille rouge). « Deux clichés perdus ce matin. Fournisseur prévenu, pièce commandée. »

## Sets stérilisés et cycles
Trois produits : **Set d'examen stérilisé** (sachet pelable, 180 j, 14.00) · **Set de
détartrage stérilisé** (sachet pelable, 180 j, 18.00) · **Set de chirurgie stérilisé**
(double sachet, 90 j, 46.00). Alerte à 21 jours.

Quatre cycles — palier **134.0 °C**, **18.0 min**, programme **B**, Helix conforme :

Dans l'ordre où l'écran les affiche (la plus récente en haut). Attention : les numéros
ne suivent pas la chronologie — ils sont attribués à la création, et la charge d'hier a
été saisie avant celle d'il y a trois jours.

| Cycle | Quand | Contenu | État |
|---|---|---|---|
| STE/2026/0004 | aujourd'hui | 10 sets de détartrage | **Brouillon** *(ligne grisée)* |
| STE/2026/0002 | hier | 12 sets d'examen | **Non conforme** *(ligne rouge)* — l'indicateur est revenu ce matin ; une séance déjà servie |
| STE/2026/0003 | il y a 3 j | 4 sets de chirurgie | **Validé**, indicateur « Conforme » |
| STE/2026/0001 | il y a 165 j | 8 sets de détartrage | **Validé** — dans la fenêtre d'alerte de stérilité (165/180) |

Emplacements virtuels nommés, à montrer dans le fil d'un mouvement :
**« Stérilisation »** → le rayon → **« Consommé en soins »**. Le magasin lit donc une
histoire complète : **sorti de l'autoclave, entré en rayon, parti au fauteuil.**

---

# 10. PHRASES DU PRODUIT, RÉUTILISABLES TELLES QUELLES

Prends-les comme accroches de section, légendes ou citations. Elles sont toutes écrites
dans le produit.

- **Le magasin compte, la stérilisation prouve, le registre entretient.**
- **C'est l'ACTE qui sait ce qu'il consomme**, pas le praticien qui ressaisit au fauteuil.
- **Zéro ressaisie au fauteuil.**
- **Le soin est fait ; le magasin constate.**
- **Le stock ne bloque JAMAIS la clinique.**
- **Un lot périmé ne part jamais vers les soins.**
- **Un registre de stérilisation est un document de preuve.**
- **Un cycle validé est figé, comme une ordonnance émise.**
- **On repasse la charge, on ne réécrit pas l'histoire.**
- **On n'efface pas, on archive.**
- **Un compteur doit dire la même chose que l'écran qu'il ouvre.**
- **Une case de trop vaut mieux qu'un registre qu'on ne peut plus tenir.**
- **Rien n'est réinventé, et c'est le propos.**

---

# 11. SEPT ARBITRAGES DE VOCABULAIRE — à trancher dans la maquette

Le produit hésite entre deux mots à sept endroits. Chaque fois, **choisis-en un et
tiens-le sur toute la page** ; affiche le choix dans une petite section de fin, pour que
je puisse le répercuter en backend.

1. **« séance » ou « traitement » ?** Le modèle et les menus disent « Traitement » ; toute
   la doctrine, tous les messages et tous les boutons disent « séance ». *(Ma
   recommandation : « séance » gagne, et l'écran suit.)*
2. **« rayon » ou « stock » ?** Les messages disent « en rayon », les colonnes disent
   « En stock ».
3. **« cycle » ou « charge » ?** La charge est ce qu'on met dans l'autoclave, le cycle est
   le document numéroté. La distinction est voulue mais pas tenue partout.
4. **« set », « sachet » ou « lot » ?** Trois mots pour le même objet selon l'écran.
5. **« Matériel », « Appareils » ou « Équipement » ?** Le menu racine, le sous-menu et le
   groupe de droits utilisent les trois.
6. **« Famille » ou « Catégorie » ?** Le regroupement dit « Famille », la colonne juste à
   côté dit « Catégorie » — sur le même écran.
7. **« kit », « Consommables » ou « Position tarifaire » ?** Le mot « kit » est central
   dans la doctrine et **ne porte aucun libellé à l'écran** — ni onglet, ni colonne, ni
   menu ; il n'y apparaît que dans un message de refus (« un kit à zéro ne consomme
   rien »).

---

# 12. CE QUE TU NE FAIS PAS

- **Pas de quatrième couleur de signal.** Rouge / orange / gris, c'est tout.
- **Pas de badge « nouveau », pas de gamification, pas de score.** C'est un registre de
  preuve, pas un tableau de bord de performance.
- **Pas de photo de patient, pas de nom de patient hors du bouton « Séances servies ».**
  La séparation est la règle du produit, pas une contrainte de maquette.
- **Pas de bouton grisé pour dire non.** Le produit refuse **au moment de la validation**,
  avec une phrase, jamais en désactivant un bouton par avance.
- **Pas de traduction anglaise.** Tout en français.
- **N'invente aucun libellé de champ ou de menu.** Si tu as besoin d'un mot que je ne t'ai
  pas donné, signale-le plutôt que de le fabriquer.
