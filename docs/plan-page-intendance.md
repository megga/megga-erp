# Le plan — la page « Intendance » sur Claude Design

## 1. Le nom — arrêté

**« Intendance ».** Titre long « **Intendance du cabinet** », libellé de navigation
« **Intendance** ». Décision prise le 26.08.2026.

Ce qui l'a emporté :

- Il couvre **les trois** modules sans en étirer aucun. L'intendance, c'est la marche
  matérielle d'un lieu : ce qu'on consomme, ce qu'on entretient, ce dont on répond. Le
  magasin, le registre et la stérilisation y entrent sans forcer.
- Il épouse la convention de nommage déjà en place dans le produit : « Stock **du
  cabinet** », « Matériel **du cabinet** », « Consommables **du cabinet** », « Lots **du
  cabinet** », équipe « **Cabinet** ». « Intendance du cabinet » n'invente pas un
  registre de langue, il continue celui du dépôt.
- Il ne collisionne avec rien. Deux noms ont été écartés : **« Inventaire »**, qui est
  déjà le nom de l'application Odoo du magasinier et ne dit qu'un tiers du sujet
  (compter) ; et **« Laboratoire »**, qui pour un dentiste désigne la prothèse —
  couronnes, bridges, le prothésiste — et tromperait le lecteur le plus important.
  **« Plateau technique »** était l'alternative sérieuse : terme médical exact pour les
  moyens matériels d'un lieu de soin, mais il couvre mal les compresses et l'articaine.

**Le sous-titre fait le reste du travail** — c'est la formule du produit, déjà écrite
dans le README et les manifestes :

> **Le magasin compte, la stérilisation prouve, le registre entretient.**

Elle donne aussi l'ordre des sections, et c'est l'ordre réel des menus sous
« Intendance » (10 / 20 / 30).

### Le regroupement — tranché et livré dans le backend

Le backend porte désormais un conteneur « **Intendance** » sous « Dentaire »
(`megga_dental.menu_dental_intendance`, séquence 40 — celle qu'occupait « Stock du
cabinet », entre « Constats » (30) et « Configuration » (90)), et les trois racines y
sont reparentées dans l'ordre de la formule : « Stock du cabinet » (10),
« Stérilisation » (20), « Matériel » (30). Le nom existe donc des deux côtés.

Le conteneur ne porte **ni action ni groupe**, et c'est délibéré. `_visible_menu_ids`
part des menus porteurs d'une action accessible et remonte l'ascendance ; `load_menus`
élimine ensuite tout sous-arbre dont l'ancêtre a disparu. Un groupe posé sur
« Intendance » aurait donc fait sortir de la barre les familles qui ne le portent pas —
la stérilisation et le matériel pour le magasinier, le magasin pour le responsable
technique. La garde reste entièrement au parent « Dentaire » et au groupe de chaque
enfant ; un cabinet qui n'installe aucun des trois modules ne voit rien du tout.

Deux conséquences assumées : le niveau de profondeur supplémentaire au clic, et le fait
que « Intendance » apparaisse pour tout le personnel — « Entretiens » étant ouvert à
tout employé, exactement comme « Matériel » l'était avant le regroupement.

## 2. L'ossature de la page

Une page longue, trois actes, un verbe par acte. Pas un catalogue d'écrans : un parcours.

| | Acte | Verbe | Ce qu'on montre | La question du lecteur |
|---|---|---|---|---|
| 0 | **En-tête** | — | le nom, les trois verbes, la journée type | « à quoi ça sert ? » |
| I | **Compter** | le magasin | 4 écrans + le kit + la clôture de séance | « qu'est-ce qui périme bientôt ? » |
| II | **Prouver** | la stérilisation | la liste des cycles + la fiche de charge + le rappel | « avec quoi m'a-t-on soigné ? » |
| III | **Entretenir** | le registre | les appareils groupés par fauteuil + la fiche fauteuil + les entretiens | « qu'est-ce qui s'arrête si cet appareil part ? » |
| IV | **Les refus** | — | les quatre boîtes de dialogue, mot pour mot | « qu'est-ce que le produit refuse de faire ? » |
| V | **Qui voit quoi** | — | la matrice des trois rôles | « et la LPD ? » |
| VI | **Les arbitrages** | — | les sept divergences de vocabulaire à trancher | « quel mot gagne ? » |

### Le fil rouge, à tenir d'un bout à l'autre

Le produit a **une** thèse, et chaque acte en est une facette :

> **Le stock ne bloque jamais la clinique — mais il refuse de mentir.**

Acte I : le soin part même si le rayon est vide (le quant passe en négatif, une activité
signale l'écart). Acte II : un set non stérile ne sort pas vers les soins, mais il part
au rebut sans discuter. Acte III : un fauteuil qui porte du matériel ne se supprime plus,
il s'archive. Trois fois la même idée : **on n'empêche pas de soigner, on empêche
d'effacer.**

### Les deux moments de vérité à mettre en scène

Ce sont les deux seules scènes narratives de la page. Tout le reste est écran.

1. **Le lendemain matin.** L'indicateur biologique d'une charge validée la veille revient
   « Non conforme ». Douze sets d'examen sont déjà distribués, une séance a déjà été
   servie. Un clic sur la liste déroulante suffit : les sets encore en rayon se bloquent,
   et la séance de Camille Rochat est nommée au fil de discussion.
2. **La clôture de séance.** On clique « Terminer ». Les kits des actes s'additionnent
   produit par produit, la sortie part en FEFO, et le magasin constate — même quand il
   ne peut pas servir. L'activité s'appelle « Écart de consommation au fauteuil » et se
   pose **sur le transfert**, jamais sur la séance.

---

## 3. Ce que la page doit obtenir du designer

Trois décisions concrètes, à prendre pendant le dessin :

- **Une identité graphique.** Le dépôt n'a qu'une couleur (`#0E6B4F`) et des visuels
  explicitement marqués « placeholders générés — à remplacer par la vraie identité ».
  C'est le seul endroit du produit où une identité est attendue et absente.
- **Le mot pour « séance ».** Le modèle s'appelle `treatment`, l'écran dit « Traitement »,
  et toute la doctrine dit « séance ». Un des deux doit céder (voir Acte VI).
- **La densité.** Ce sont des listes de gestion, lues debout, entre deux patients. Les
  colonnes `optional="hide"` du relevé disent exactement ce qui doit s'effacer par défaut.

---

## 4. Comment enchaîner sur Claude Design

1. Coller le prompt (fichier `intendance-prompt.md`) tel quel.
2. Faire produire d'abord l'**Acte II** (la fiche de charge) : c'est l'écran le plus
   dense et le plus original du lot — s'il tient, les autres tiennent.
3. Puis l'**Acte I** écran par écran, en commençant par « Lots et péremption » : c'est
   l'écran-signature, le seul où les trois décors de couleur jouent ensemble.
4. Garder les **refus** pour la fin : ce sont des boîtes de dialogue, elles héritent du
   style une fois qu'il est posé.
