# Socle ERP — Odoo Community 19.0 en surcouche

Phase 1 du [plan de reprise](../PLAN-REPRISE-ODOO.md). Le cœur d'Odoo est un
**sous-module figé, jamais modifié** ; tout le produit vit dans `addons/`.

## Épinglage

- Sous-module : `odoo/` → **`megga/odoo`** (notre fork de `odoo/odoo`), branche `19.0`
- SHA figé : celui du gitlink — `git ls-tree HEAD odoo` fait foi. Il n'avance
  que par le rituel mensuel (`rituel-mensuel.yml`), jamais à la main.

## Démarrer (sur votre machine)

```bash
git clone https://github.com/megga/megga-erp.git && cd megga-erp
git submodule update --init --depth 1 odoo   # ~qq minutes, plusieurs centaines de Mo
docker compose up --build
# puis http://localhost:8069 → créer la base (le master password est dans odoo.conf)
```

## Checklist « Phase 1 terminée »

- [ ] `docker compose up` démarre sans erreur
- [ ] http://localhost:8069 affiche l'écran de création de base
- [ ] Après création : les ~705 modules apparaissent dans Apps
- [ ] CRM + Ventes + Facturation s'installent
- [ ] `python scripts/check_licences.py` → OK
- [ ] `bash scripts/check_core_pristine.sh` → OK

## Les règles du socle (non négociables)

1. **`odoo/` est en lecture seule** — monté `:ro` dans Docker, vérifié par
   `check_core_pristine.sh` en CI. Tout besoin passe par un module `_inherit`
   dans `addons/`.
2. **`addons-oca/` n'accepte que du LGPL-3** — `check_licences.py` refuse
   l'AGPL (2 640 des modules OCA) et toute licence inconnue. Lire le
   `__manifest__.py` AVANT de copier un module. Nos propres modules
   (`addons/`) sont tous **« Other proprietary »** depuis le 25.08.2026 :
   modèle fermé homogène — Megga se revend à N clients (le cœur Odoo
   LGPL-3 le permet), le client ne redistribue pas nos modules.
3. **Jamais `git add -A` à la racine quand `odoo/` n'est pas matérialisé** —
   cela stagerait la suppression du gitlink. Ajouter les chemins explicitement.
4. Refactoring : uniquement `addons/` et `scripts/` (voir `/refactor`).

## Maintenance (Phase 5 du plan)

- **Mensuel** : le workflow `rituel-mensuel` (1ᵉʳ du mois, 03h17 UTC, ou à
  la demande via *Run workflow*) synchronise le fork, déplace le gitlink,
  passe les garde-fous et **la suite Megga complète** contre le nouveau
  cœur, puis pousse une branche `bump-odoo-*` et propose la pull request —
  il ne fusionne jamais seul. Cycle complet exécuté et fusionné en réel le
  23/08/2026 (`5a12710b` → `ba4315ec`). **Le fork n'avale pas les
  correctifs amont tout seul : sans ce rituel, vous ne recevez plus les
  correctifs de sécurité.** À la main, la même chose :
  `bash scripts/bump_odoo.sh` → `bash scripts/run_tests.sh` → commit.
- **Annuel** : migration majeure (rebrancher le sous-module, migrer nos modules).

### `FORK_SYNC_TOKEN` — l'autonomie complète du rituel

Sans ce secret, le rituel fonctionne mais s'arrête à deux guichets : la
synchronisation du fork doit avoir été faite d'avance (sinon arrêt propre
avec instructions), et GitHub interdit aux Actions d'ouvrir la pull
request (la branche testée est poussée, la PR s'ouvre à la main). Avec le
secret, tout est automatique. Seul le propriétaire du compte peut le
frapper — deux minutes :

1. **Frapper le jeton** : GitHub ▸ *Settings* ▸ *Developer settings* ▸
   *Fine-grained personal access tokens* ▸ *Generate new token*.
   - *Resource owner* : `megga` ; *Repository access* : **seulement**
     `megga/odoo` et `megga/megga-erp`.
   - *Permissions* (le minimum qui suffit) : **Contents : Read and
     write** (synchronisation du fork par `merge-upstream`) et **Pull
     requests : Read and write** (ouverture de la PR de bump) —
     *Metadata : Read* s'ajoute d'office.
   - Expiration : 1 an, et un rappel de rotation à l'agenda — un jeton
     expiré redonne simplement le comportement sans secret, rien ne casse.
2. **Poser le secret** : `megga/megga-erp` ▸ *Settings* ▸ *Secrets and
   variables* ▸ *Actions* ▸ *New repository secret* — nom exact
   `FORK_SYNC_TOKEN`, valeur = le jeton. Jamais dans un fichier, jamais
   dans le dépôt.
3. **Vérifier** : relancer `rituel-mensuel` avec l'entrée `forcer` cochée
   — le journal doit montrer « fork synchronise (merge-upstream) » et la
   PR s'ouvrir toute seule.

## Nom du produit : Megga

Décidé le 23/08/2026. Préfixe de tous les modules : `megga_`.

## Modules livrés (Phases 2 et 4 — complètes)

| Module | Rôle | Tests au boot |
|---|---|---|
| [`megga_base`](addons/megga_base/) | Surcouche de marque (titre, favicon, couleur, e-mails, menu) | checklist visuelle |
| [`megga_qr_export`](addons/megga_qr_export/) | QR-facture pour clients hors CH/LI (norme SIX) | 3 |
| [`megga_camt`](addons/megga_camt/) | Import camt.053/054 — encaissements QRR, rapprochement | 5 |
| [`megga_pain001`](addons/megga_pain001/) | Paiements fournisseurs pain.001.001.09.ch.03 | 5 |
| [`megga_tva_ch`](addons/megga_tva_ch/) | Décompte TVA AFC (rendu du rapport l10n_ch) | 4 |
| [`megga_relances`](addons/megga_relances/) | Rappels de factures impayées (`account_followup` est Enterprise) : niveaux réglables, proposition quotidienne en brouillon, envoi tracé au chatter, un même cran ne repart jamais deux fois | 35 |
| [`megga_pilotage`](addons/megga_pilotage/) | Balance âgée du poste clients (`account_reports` est Enterprise) : vue d'analyse liste/pivot/graphe par tranche d'âge, rapport imprimable pour la fiduciaire | 18 |

Validation groupée (socle + verticales) : `bash scripts/run_tests.sh`.

La paie reste hors périmètre code (voie connecteur/fiduciaire — volet 3 de
l'audit) ; la Phase 5 (bump mensuel du sous-module, migration annuelle) est
le régime permanent.

Les **rappels de factures impayées** (`megga_relances`) comblent une
absence nette du dépôt Community : `account_followup` est un module
Enterprise — le cœur n'en garde que le champ `no_followup`, un crochet
vers un module qui n'existe pas ici. L'entreprise règle ses crans (par
exemple 1er rappel à 10 jours, 2e à 30 avec frais annoncés, mise en
demeure à 45), et un cron quotidien **propose** un rappel en brouillon
par client concerné. Il n'envoie **jamais** tout seul : une relance
part sous la signature de la maison. Trois principes tiennent le
module :

- **Un client, un courrier.** Trois factures échues font un rappel qui
  les porte toutes, pas trois rappels.
- **Le cran le plus élevé gagne.** Un client à 47 jours reçoit la mise
  en demeure, pas le premier rappel qu'il a déjà eu.
- **Un même cran ne repart jamais deux fois.** Le cran servi est
  marqué sur chaque *facture* (pas sur le client : deux factures du
  même client peuvent être à des stades différents), par son
  **identité** et non par son délai — un délai se re-règle, et
  comparer des nombres mutables ferait repartir des crans déjà
  servis. L'envoi passe par le chatter : un rappel sans trace est un
  rappel qu'on ne peut pas prouver.
- **Une devise, un courrier.** On n'additionne pas des francs et des
  euros sous un même total, et le débiteur est l'entité commerciale —
  deux services du même client ne reçoivent pas deux lettres.
- **Le monde bouge entre la nuit et le geste.** L'envoi revérifie :
  une facture réglée, annulée ou mise en litige entre-temps sort du
  courrier, et s'il ne reste rien, l'envoi refuse. Le brouillon en
  attente est *mis à jour* par le cron suivant, jamais empilé ni
  jeté — il porte peut-être déjà des notes.

Les **frais de rappel** sont *annoncés* dans le texte, jamais ajoutés
d'office à la facture : des frais se contestent, ils s'ajoutent en
conscience sur une note de débit. Ne sont jamais rappelés : une
facture payée ou en cours d'encaissement, un brouillon, une facture
en **litige** (`payment_state` *blocked*, le vrai crochet du cœur),
une facture sortie du circuit par la case « Hors rappels », ni un
client dont les **avoirs ouverts couvrent** la dette échue. Le
courrier part dans la **langue du client**, montants et dates
formatés. Un client sans adresse de courriel ne fait pas
semblant d'être relancé : l'envoi refuse, et un bouton « remis hors
courriel » trace la remise postale.

La **balance âgée** (`megga_pilotage`) répond à la question que le
patron pose le lundi matin : *qui me doit quoi, et depuis combien de
temps ?* Elle manque aussi à Community — les rapports comptables
(`account_reports`) sont Enterprise. Chaque facture ouverte est rangée
par âge de créance (non échu, 1-30, 31-60, 61-90, plus de 90 jours),
en **liste, pivot et graphe**, avec le cran de rappel déjà servi en
regard : la balance et les rappels se lisent ensemble. Un **rapport
imprimable** par client — celui que réclame la fiduciaire — sort le
même tableau ventilé, la plus grosse dette en tête.

Deux partis pris : les montants sont exprimés en **devise de la
société** (un tableau de bord additionne, et on n'additionne pas des
francs avec des euros — le détail en devise d'origine reste sur la
facture) ; et le débiteur est l'**entité commerciale**, donc les
services d'un même client comptent pour un seul. La vue classe en SQL
pour que le pivot travaille en base, le rapport classe en Python : un
test compare les deux verdicts sur toute la plage, pour qu'écran et
papier ne divergent jamais en silence.

## Verticales métier (`addons/verticals/`)

Un cœur, un socle suisse, N secteurs. Chaque verticale est un répertoire
d'addons **supplémentaire** : un déploiement client assemble
`odoo/addons` + `addons` + `addons/verticals/<secteur>`, et le rituel
mensuel teste toutes les verticales contre chaque bump du cœur.

| Verticale | Méta-module | Contenu | Tests |
|---|---|---|---|
| [`dental/`](addons/verticals/dental/) | `megga_dental` | Dossier patient (délégué `res.partner`, donc facturable → QR), plans de traitement par dent (référentiel FDI/ISO 3950 complet), rappels de contrôle automatiques (cron + activités), tarif par points (positions, valeur du point du cabinet ou de la convention AA/AI/AM), facturation en un clic, groupes LPD Réception/Soins (champs médicaux protégés par l'ORM), odontogramme FDI interactif (constats par dent et par surface, alimentés par les actes), plans de traitement par phases (ordre clinique garanti, devis d'ensemble, avancement), ordonnances (émission figée, renouvellement chaîné, impression), questionnaires et consentements (gabarits, signature, anamnèse à péremption), imagerie au dossier (clichés typés par dent, galerie), journal clinique immuable (notes au stylo, rectification chaînée), fauteuils et créneaux (conflits refusés, attribution automatique, calendrier), tiers payant d'assurance (dossiers AA/AI/AM/LAMal/LCA, garanties de prise en charge, facture à l'assureur avec référence du sinistre) | 126 |
| [`resto/`](addons/verticals/resto/) | `megga_resto` | Carnet de réservations sur les tables du plan de salle (`restaurant.table` de `pos_restaurant`) : conflits de créneaux détectés, non-venus marqués par cron ; fiches techniques par plat (coût matière, marge, report du coût sur l'article) avec conversion d'unités (200 g d'un article au kilo, unité maison type cl) ; productions de cuisine (banquet, service : plats × portions) avec liste de courses agrégée multi-plats, convertie dans l'unité de l'économat, coût prévisionnel et impression pour le marché | 44 |
| [`auto/`](addons/verticals/auto/) | `megga_auto` | Parc des véhicules **clients** sur `fleet` (marques, modèles, plaques, journal de compteur) : propriétaire, rappels d'expertise au rythme fédéral 4-3-2 (art. 33 OETV), plausibilité VIN (ISO 3779) ; ordres de réparation atelier avec report du kilométrage et facture en un clic ; carnet d'entretien imprimable (PDF depuis la fiche véhicule : interventions terminées, chronologiques, sans les prix) ; forfaits d'atelier (gabarits main-d'œuvre + pièces posés sur l'ordre en un clic, au taux horaire du garage et aux prix du jour, figés à la pose) | 44 |
| [`dental/`](addons/verticals/dental/) | `megga_dental_rdv` (**auto_install**) | Pont réservation ↔ dossier : toute réservation en ligne rattache — ou crée — le dossier patient du contact (archivés compris, jamais de doublon), débrayable par type de RDV ; effet système en sudo, lien `patient_id` gardé par les groupes LPD | 9 |
| [`dental/`](addons/verticals/dental/) | `megga_dental_portal` (installation **délibérée**, jamais auto) | Portail patient : le patient connecté voit **son** dossier et rien d'autre (`ir.rule` sur `user.partner_id`) — ses traitements et montants, ses ordonnances **émises** (jamais un brouillon), ses questionnaires **signés**, avec téléchargement PDF gardé (`_document_check_access` avant tout rendu) ; lecture seule absolue, le clinique profond (constats, imagerie, notes, dossier médical) reste fermé | 11 |
| [`dental/`](addons/verticals/dental/) | `megga_dental_stock` (installation **délibérée**, jamais auto) | Magasin du cabinet : consommables tracés par lots et dates de péremption, sortie **FEFO** portée par la catégorie produit (le lot le plus proche de sa date part le premier), emplacement virtuel « Consommé en soins », et LA garde du cabinet — un lot périmé ne part **jamais** vers les soins (le cœur avertit d'un wizard qui se contourne d'un clic ; la règle du cabinet, elle, refuse), tandis que le rebut reste permis pour détruire proprement ; **kits de consommables par position tarifaire** décomptés à la clôture de séance (zéro ressaisie au fauteuil, besoins agrégés, effet système en sudo) — et le stock ne bloque **jamais** la clinique : rien en rayon, la sortie part en négatif, plus rien de servable, elle part sans lot, avec une activité au magasin dans les deux cas ; menu « Stock du cabinet » en raccourcis filtrés, gardé par les groupes stock du cœur | 47 |
| [`auto/`](addons/verticals/auto/) | `megga_auto_portal` (installation **délibérée**, jamais auto) | Portail client : le client connecté voit **ses** véhicules (échéance d'expertise, compteur) et **ses** réparations acceptées ou terminées avec le détail des travaux — jamais un devis en rédaction, jamais la voiture d'un autre (`ir.rule` sur `megga_owner_id` / `partner_id`) ; carnet d'entretien en PDF gardé (`_document_check_access` avant tout rendu) ; lecture seule, référentiel des forfaits fermé | 16 |
| [`auto/`](addons/verticals/auto/) | `megga_auto_rdv` (**auto_install**) | Pont réservation ↔ atelier : le véhicule du client est rattaché d'office quand il n'en a qu'un, et l'ordre de réparation se crée en un clic depuis la réservation (date locale du fuseau, mécanicien = intervenant, compteur) | 8 |
| [`resto/`](addons/verticals/resto/) | `megga_resto_portal` (installation **délibérée**, jamais auto) | Portail client : le client connecté suit **ses** réservations (à venir et passées) et **annule en ligne** celles qui peuvent encore l'être — seul geste d'écriture de tous les portails Megga, par action dédiée et gardée (la sienne, à venir, pas encore installée), tracée au chatter ; les notes de service ne redescendent pas (fermées par l'ORM) | 13 |
| [`resto/`](addons/verticals/resto/) | `megga_resto_rdv` (**auto_install**) | Pont réservation en ligne ↔ carnet : le type « réservation de table » demande les couverts, n'occupe pas l'agenda (`show_as='free'` — plusieurs tablées par créneau) et attribue la plus petite table suffisante ; complet = refus propre ; annulations synchronisées dans les deux sens | 11 |
| [`resto/`](addons/verticals/resto/) | `megga_resto_tva` (**auto_install**) | TVA suisse de la restauration : sur place 8.1 % (TN) / à l'emporter 2.6 % (TR, art. 25 LTVA) — position fiscale et taxe de remplacement créées par société (grille 313a conservée), reliées au preset « À l'emporter » de la caisse ; même patron que `l10n_be_pos_restaurant` du cœur | 7 |
| [`auto/`](addons/verticals/auto/) | `megga_auto_occasion` (**auto_install**) | Commerce d'occasion : reprise → stock → revente (le nouveau propriétaire entre au parc clients). Régime ordinaire = impôt préalable fictif (art. 28a LTVA, taxe incluse extraite du prix de reprise, revente TTC — la charge nette est la TVA de la marge) ; pièces de collection = imposition de la marge (art. 24a : TVA sur la marge seule, marge négative sans crédit, facture de vente **sans mention de TVA**). Factures de reprise et de vente en un clic | 15 |

Chaque méta-module tire tout son métier : socle Megga complet + les briques
du cœur (dentaire : CRM + agenda + contacts ; resto : POS restaurant +
contacts ; auto : fleet + CRM + contacts). Note d'architecture : le module
`repair` du cœur n'est PAS utilisé par `auto/` — il répare un produit tenu
en stock (product_id + lot), pas le véhicule d'un client ; l'atelier est
donc un modèle métier propre, adossé à fleet.

Côté dentaire, la prise de RDV en ligne (`megga_rdv`) et les **groupes
LPD** sont livrés : deux rôles — *Réception* (identité, coordonnées,
rendez-vous, facturation) et *Soins* (dossier médical complet, implique
Réception) — avec les champs sensibles (allergies, antécédents,
médication, notes cliniques) protégés par `groups=` **sur les champs
eux-mêmes** (appliqué par l'ORM, pas seulement par les vues) ; sans
groupe dentaire, aucun accès aux dossiers, mais l'automatisation de la
réservation en ligne continue de créer les dossiers (effet système en
sudo, lecture toujours gardée).

Le **tarif par points** est livré aussi : positions tarifaires (numéro,
libellé, points), montant d'un acte = points × valeur du point — valeur
du cabinet en privé (fiche Société), valeur de la convention aux
assurances sociales (AA/AI/AM, point à 1.00), figée sur chaque devis. Le
numéro de position figure sur la facture. Le catalogue officiel étant
une œuvre **sous licence SSO**, il n'est pas embarqué : chaque cabinet
au bénéfice d'une licence importe ses positions (CSV : `code`, `name`,
`points`, `chapter` — exemple fictif dans `megga_dental/docs/`) ou les
saisit à la main ; les lignes à produit (forfaits, fournitures) restent
possibles et se mélangent librement.

L'**odontogramme FDI** complète le dossier : chaque *constat* fixe l'état
d'une dent — ou d'une de ses surfaces (mésiale, distale, vestibulaire,
linguale, occlusale) — à une date ; le schéma (widget SVG maison, deux
arcades, rangées de lait quand le dossier en porte) lit le **dernier
constat par surface** : l'obturation posée par-dessus la carie remplace
la carie à l'écran sans réécrire l'histoire (traçabilité nLPD). Une
position tarifaire peut porter un « constat au terme de l'acte »
(obturation, extraction…) : terminer le traitement inscrit alors le
constat sur chaque dent de l'acte, en sudo — la réception peut clore une
séance, mais le modèle des constats lui est entièrement fermé (aucune
ligne `ir.model.access` : données de santé, art. 5 nLPD). Un clic sur
une dent ouvre ses constats, pré-rempli pour en saisir un nouveau.

Les **plans de traitement par phases** ordonnent le tout :
l'assainissement avant la prothèse. Un plan chapeaute des phases
ordonnées ; chaque phase porte son propre traitement (créé en devis dès
l'ajout de la phase, au tarif du plan — privé ou conventionnel), donc la
facturation, le tarif par points et les constats d'odontogramme suivent
sans rien réinventer. L'ordre clinique est **garanti par le modèle** :
une phase ne se lance que quand toutes les précédentes sont soldées.
Le plan chiffre l'ensemble (devis global), suit l'avancement, s'achève
tout seul quand tout est soldé, et l'abandon garde l'acquis (une phase
terminée reste terminée). Le diagnostic est réservé aux Soins (nLPD),
la réception voit montants et avancement — elle encaisse.

Les **ordonnances** ferment la boucle clinique : lignes de médicaments
avec posologie (référentiel du cabinet facultatif pour l'autocomplétion
— le compendium officiel est sous licence, donc pas embarqué, même
doctrine que le catalogue SSO), impression QWeb (en-tête du cabinet,
signature), et un cycle strict : l'ordonnance **émise ne se modifie
plus** (le papier remis fait foi) — elle se renouvelle (copie neuve
chaînée à l'originale, lignes comprises) ou s'annule, et ne se supprime
jamais. Bouton « Prescrire » sur la séance (pré-rempli). Données de
santé pures : modèle entièrement fermé à la réception, comme les
constats.

Les **questionnaires et consentements** ferment la porte d'entrée :
gabarits du cabinet (questions oui/non/sans objet, « précision si
oui »), l'anamnèse porte une **validité en mois** et le dossier patient
affiche son état — manquante, à jour, ou périmée (bandeau d'alerte) —
calculé par la logique pure (écrêtage de fin de mois compris). Le
patient signe à l'écran (widget de signature du cœur) ; un
questionnaire **signé ne se modifie plus** — on en refait un, la copie
repart en brouillon vierge de signature. Impression avec l'image de la
signature. Deux gabarits d'exemple sont livrés, explicitement à
adapter : l'anamnèse usuelle et le consentement au traitement des
données (nLPD) — le consentement *médical* aux soins reste à écrire par
le cabinet, son contenu engage le praticien. Réponses **et** gabarits
fermés à la réception.

L'**imagerie au dossier** archive les clichés : rétro-alvéolaire,
bitewing, panoramique, coupe CBCT exportée, téléradio, photo clinique —
typés, datés, rattachés aux dents FDI et au traitement, libellé
auto-composé (« Rétro-alvéolaire — dent 16 »), consultés en **galerie**
(kanban à vignettes). L'image vit en pièce jointe : elle suit le
filestore, donc les sauvegardes et leur expédition. Le DICOM natif
reste dans le logiciel du capteur — on archive l'export image. Modèle
entièrement fermé à la réception, comme tout le clinique.

Le **journal clinique immuable** clôt la feuille de route : des notes
qui s'écrivent **au stylo**. L'horodatage et l'auteur sont posés par le
serveur à la création (toute valeur fournie est écrasée — on n'antidate
pas, on n'écrit pas au nom d'un autre) ; ensuite **ni modification ni
suppression, jamais** — l'ACL ne donne le droit de supprimer à
personne *et* la garde python double l'interdit, `sudo` compris.
L'erreur se corrige par une **note de rectification** chaînée à
l'originale (même dossier exigé, bandeau « Rectifiée » sur la note
corrigée). Un dossier qui porte des notes ne se supprime plus
(`restrict`) : il s'**archive** — la voie de sortie prévue depuis le
premier jour. Onglet « Journal » du dossier + vue transverse, réservés
aux Soins. C'est la doctrine « signé = figé » des ordonnances et
questionnaires, poussée au cran au-dessus : figé dès la naissance.

Les **fauteuils et créneaux** posent le planning sur la ressource
réelle : un référentiel de fauteuils (ou salles), et dès qu'une séance
porte un créneau (début + durée, fin calculée), les conflits sont
**refusés par le modèle** — par fauteuil *et* par praticien, confirmés
seulement, bords adjacents permis (une séance peut commencer quand
l'autre finit) ; la planification **attribue toute seule** le premier
fauteuil libre et refuse de confirmer sans place. Vue calendrier
colorée par fauteuil. Sans créneau saisi, rien ne change : le
comportement historique au jour près reste tel quel — c'est le patron
des tables du restaurant, appliqué au cabinet.

Le **tiers payant d'assurance** ferme la boucle financière : quand un
assureur doit payer, c'est lui que le cabinet facture — directement.
Un référentiel d'assureurs (délégués `res.partner`, donc facturables
tels quels) et des **dossiers de prise en charge** par patient :
sinistre accident (LAA), décision AI/AM, garantie LAMal (art. 31) ou
complémentaire LCA. Le droit est dans les gardes : un dossier
AA/AI/AM ne se confirme pas sans **numéro de sinistre** et impose le
**tarif conventionnel** (valeur du point de la convention) ; en
LAMal/LCA, « pas de garantie écrite, pas de tiers payant » — montant
et date de la garantie exigés, sinon le dossier reste en tiers garant
et le patient avance les frais comme toujours. Rattaché à un dossier
tiers payant **confirmé**, le traitement se facture à l'assureur, la
référence du sinistre et le nom du patient en clair sur la facture
(l'assureur ne rapproche rien sans eux) ; les plans propagent le
dossier à toutes leurs phases. La chaîne du socle suit sans pont :
QR-facture à l'assureur, encaissement camt. Suivi par dossier
(traitements, total facturé) ; un dossier porteur ne se supprime pas,
il se clôt. L'administratif de facturation appartient à la réception
— les dossiers d'assurance lui sont ouverts, le clinique reste fermé.

Le **portail patient** (`megga_dental_portal`) ouvre une fenêtre — pas
une porte. Module **séparé, jamais auto-installé** : ouvrir des données
de santé sur Internet est une décision du cabinet, pas un défaut
d'installation. Le patient connecté trouve « Mon dossier dentaire » sur
son portail : ses traitements (actes et montants), ses ordonnances,
ses questionnaires — **le sien et rien que le sien** (`ir.rule` sur
`user.partner_id`, éprouvée par les tests d'étanchéité : le dossier du
voisin lève `AccessError`). Jamais un document en travail : seules les
ordonnances **émises** et les questionnaires **signés** paraissent —
un brouillon n'existe pas pour le patient. Tout est **lecture seule**
(aucun droit d'écriture, de création ni de suppression), et le
téléchargement PDF passe par `_document_check_access` **avant** tout
rendu — le rendu portail d'Odoo travaille en sudo, le contrôle d'accès
doit donc précéder l'appel, jamais s'y fier. Le clinique profond reste
fermé : constats, imagerie, notes de journal, diagnostic et dossier
médical n'ont **aucune** ACL portail — le patient a droit à ses
documents remis, pas aux notes de travail du praticien (la nLPD donne
un droit d'accès *sur demande*, art. 25 — le portail n'est pas tenu de
tout montrer en libre-service).

Le **magasin du cabinet** (`megga_dental_stock`) donne enfin au
dentaire ce qui lui manquait : de quoi compter les compresses et
surveiller les dates. Module **séparé, jamais auto-installé** — un
cabinet peut vouloir le métier sans le magasin (petite structure,
consommables gérés à la main). Il **configure le cœur** bien plus qu'il
ne modélise : le stock, les lots, la péremption et la sortie FEFO sont
entièrement dans Community (`stock` + `product_expiry`), et rien n'est
réinventé.

Ce que le module apporte tient en trois gestes. Une **catégorie
« Consommables du cabinet »** qui porte la stratégie de sortie
**FEFO** — c'est ELLE qui la rend effective (`_get_removal_strategy`
interroge la catégorie avant l'emplacement), et sans quoi le fond du
tiroir périme pendant qu'on entame la boîte du dessus. Un **emplacement
virtuel « Consommé en soins »** (`usage='customer'`, sans société ni
parent : patron exact des emplacements virtuels du cœur) : tout ce qui
part au fauteuil va au même endroit, les quantités sortent
définitivement, la valorisation suit. Et un **menu « Stock du
cabinet »** sous le menu dentaire — consommables, quantités, lots par
urgence de péremption : des **raccourcis filtrés**, pas un doublon de
l'app Inventaire.

La garde qui fait la valeur : **un lot périmé ne part jamais vers les
soins**. Le cœur, lui, se contente d'*avertir* — un wizard de
confirmation qui se contourne d'un clic. La règle du cabinet, elle,
**refuse** : le contrôle vit dans `stock.move.line._action_done` (le
modèle, jamais la vue — un bouton masqué n'est pas une garde, et un lot
périme à minuit quand la séance se clôt à 8h05), et le message nomme le
lot, sa date et le bon geste. Le refus ne vise **que** la destination
soins, sa descendance comprise : le **rebut reste permis** — sans quoi
un lot périmé s'immobiliserait en rayon pour toujours — comme les
retours fournisseur et les ajustements d'inventaire.

Le **pont acte → consommation** ferme la boucle : ce que le cabinet
consomme se déduit de ce qu'il soigne. Chaque **position tarifaire**
porte son kit (« une obturation composite : deux compresses, une paire
de gants »), et **clore la séance décompte le magasin toute seule** —
zéro ressaisie au fauteuil. Les besoins sont **agrégés** : deux actes
d'une même séance qui partagent un produit font une seule ligne de
mouvement, dans l'ordre des actes (logique pure, testée sans ORM, même
patron que la liste de courses du restaurant). Le kit se saisit dans
**son** unité — 500 g d'un article acheté au kilo — et la conversion se
fait sans arrondi par ligne.

Le décompte est un **effet système** du flux, en `sudo`, exactement
comme les constats d'odontogramme : la réception peut clore une séance
sans détenir le moindre droit sur le magasin, et elle n'en gagne aucun
pour autant. Quatre règles le tiennent, chacune avec son test :

- **Jamais deux fois.** La garde d'état de la clôture donne
  l'idempotence de premier rang ; le lien vers le transfert engendré est
  la ceinture, pour l'appel direct. Marquage par **identité**, pas par
  valeur.
- **Le stock ne bloque jamais la clinique.** Rien en rayon ? La
  consommation part quand même — le quant passe en négatif — et une
  **activité** signale l'écart. Elle vit sur le *transfert*, pas sur la
  séance : c'est le magasin qui doit réagir, et le magasinier n'a aucun
  accès au dentaire.
- **Le périmé ne sort pas, et n'arrête rien.** Le cœur écarte déjà de la
  réservation les lots dont la date de retrait est passée — mais
  **seulement** si le produit coche « utiliser la date de péremption » ;
  décochez-la après coup et un lot daté redevient réservable. Le pont le
  retire donc en ceinture, sans quoi la garde du magasin refuserait la
  sortie et la séance planterait. Plus rien de servable → la ligne part
  **sans lot** : traçabilité dégradée, choisie, signalée, jamais
  bloquante. C'est pourquoi le module se crée un **type d'opération
  dédié** (« Consommation en soins », les deux cases de lots décochées) :
  la seule configuration où le cœur laisse valider un produit tracé sans
  lot.
- **Rien ne revient tout seul.** Une séance clôturée puis annulée ne
  ré-intègre aucun stock : une compresse sortie ne se remet pas en
  boîte. Le geste inverse est un ajustement d'inventaire, tracé.

Et la nLPD tient jusqu'au magasin : le mouvement porte la **référence**
de la séance, jamais le diagnostic, jamais le détail des actes, jamais
le nom du patient (pas de `partner_id` sur le transfert — ce serait le
nommer). Un magasinier qui lit les mouvements ne lit pas le dossier
médical. Test dédié, et prouvé par mutation.

Deux points d'administration assumés, documentés ici parce qu'ils ne
s'inventent pas : le module **ne crée aucun groupe de droits** et ne
câble **aucun `implied_ids` depuis les groupes dentaires** — ce serait
ouvrir l'app Inventaire entière à toute la réception. L'attribution des
droits stock (`stock.group_stock_user` / `_manager`) reste un geste
d'administration délibéré, et sans eux le menu du cabinet ne s'affiche
pas. En revanche le module **active la fonctionnalité « lots »**
(`stock.group_production_lot` impliqué par le groupe stock du cœur) :
sans elle, ni date de péremption, ni FEFO, ni traçabilité — le module
entier serait inopérant. Cette activation ne donne accès à aucun modèle
supplémentaire, elle révèle des champs.

Le **portail client du garage** (`megga_auto_portal`) est le pendant du
portail patient, côté atelier — même doctrine, même patron. Module
séparé, jamais auto-installé. Le client connecté trouve « Mon garage » :
**ses** véhicules (prochaine expertise OETV, compteur) et **ses**
réparations, avec le détail des travaux et le montant. Jamais un devis
en cours de rédaction : un ordre n'existe pour lui qu'une fois
**accepté**. Le **carnet d'entretien** se télécharge en PDF, avec le
contrôle d'accès **avant** le rendu (le rendu portail travaille en sudo,
on ne s'y fie pas) ; le carnet lui-même reste complet et sans prix —
c'est un document qui se transmet avec la voiture. Point d'attention
assumé et testé : `fleet.vehicle` est un modèle du cœur où vit aussi le
parc de la société, donc la règle d'enregistrement est la seule
séparation — les tests vérifient qu'un client ne voit ni la voiture du
voisin, ni le véhicule de service du garage, et qu'un véhicule revendu
sort du portail de l'ancien propriétaire pour entrer dans celui du
nouveau.

Côté resto, les fiches techniques convertissent les unités : chaque
ligne se saisit dans SON unité (200 g d'un article acheté au kilo, 5 cl
d'une huile au litre — les unités maison comme le centilitre se créent
en un clic, relatives au litre), le coût est converti par l'arbre
d'unités du cœur, et seules les unités convertibles (même racine — en
19 les catégories d'unités ont disparu) sont proposées.

Le **portail client du restaurant** (`megga_resto_portal`) complète la
série — et introduit la seule **écriture** de tous les portails Megga :
le client suit ses réservations (à venir et passées, annulées
comprises — il doit voir ce qu'il a annulé) et **annule en ligne**
celles qui peuvent encore l'être. C'est la fonction utile côté salle :
une table libérée à temps se revend. L'écriture ne passe jamais par un
droit générique — les ACL du portail restent en lecture seule pure :
elle emprunte une **action dédiée** qui vérifie l'accès, puis les
gardes métier (la sienne, encore en demande ou confirmée, service à
venir — une table déjà installée ou un service passé se règlent au
téléphone), s'exécute en `sudo` et **se trace au chatter**
(« Annulée par le client depuis le portail »). Le bouton n'apparaît que
sur ce qui est annulable, mais le contrôleur revalide tout : la vue ne
protège rien. Deux réserves de conception assumées : une réservation
prise au téléphone **sans contact** n'appartient à personne au portail
et n'y figure pas ; et les **notes de service** (où la salle écrit ses
propres remarques) sont fermées au portail **par l'ORM**, pas seulement
absentes du gabarit.

La TVA de la restauration est câblée (`megga_resto_tva`, auto-installé
avec la localisation suisse) : le même sandwich est au taux normal
8.1 % sur place et au taux réduit 2.6 % à l'emporter (art. 25 LTVA) —
la caisse encaisse au bon taux en choisissant le mode de la commande
(preset « À l'emporter »), les ventes à l'emporter tombent en 313a du
décompte AFC, et les tickets distincts par mode constituent les
« mesures organisationnelles » qu'exige le taux réduit (Info TVA 08).
Une société qui reçoit son plan comptable après coup relance le
câblage via Restaurant ▸ Configuration ▸ TVA à l'emporter (CH).

L'**outillage de production** prolonge les fiches techniques : une
*production* — un banquet, un service, une semaine — aligne des plats
à fiche technique et leurs portions, et la **liste de courses** en
découle : chaque ingrédient de chaque fiche, converti dans l'unité de
l'économat (celle de l'article — la fiche pèse en grammes, la liste
parle en kilos), **agrégé multi-plats** (le beurre de l'entrecôte et
celui de la purée font une seule ligne), coûté au prix de revient du
jour. Gardes : pas de production sans plat, pas de plat sans fiche
(refus nominatif), pas de recalcul quand la production est soldée —
le marché est fait. La liste s'imprime (QWeb) : c'est le papier que
le chef emporte au marché ou envoie au fournisseur.

Les **forfaits d'atelier** outillent le quotidien du garage : les
prestations types — vidange, service annuel, roues été/hiver — se
décrivent une fois (heures de main-d'œuvre + pièces) et se posent sur
l'ordre de réparation **en un clic**, au prix du jour : la
main-d'œuvre au **taux horaire du garage** (fiche Société, même patron
que la valeur du point dentaire), les pièces à leur prix de vente
courant — et le prix se **fige sur la ligne** à la pose (le taux peut
changer demain, pas le devis remis). La copie reste librement
modifiable : le gabarit aide, il n'enferme pas — la doctrine du
référentiel de médicaments du dentaire. Gardes : pas de main-d'œuvre
sans taux horaire renseigné (refus explicite), pas de forfait sur un
ordre terminé ou annulé. La facturation existante suit sans rien
changer : la main-d'œuvre s'appuie sur un article de service livré
par le module.

Côté auto, le commerce d'occasion est livré (`megga_auto_occasion`,
auto-installé avec la localisation suisse) : la reprise à un particulier
ne porte pas de TVA, mais la loi ne taxe pas le garage sur le prix
plein — la voie ordinaire est l'**impôt préalable fictif** (art. 28a
LTVA : le prix de reprise est réputé TVA comprise, 8.1/108.1 en est
déduit, la revente porte la TVA pleine incluse — la charge nette
équivaut à taxer la marge) ; les **pièces de collection** relèvent de
l'**imposition de la marge** (art. 24a : TVA extraite de la marge
seule, marge négative sans crédit, et facture de vente sans mention de
TVA — la mentionner rendrait tout le montant dû ; la TVA de la marge se
déclare au décompte).

Le **carnet d'entretien** s'imprime depuis la fiche véhicule (menu
Imprimer) : identité du véhicule (plaque, VIN, première mise en
circulation, expertises), puis les interventions **terminées** en ordre
chronologique — date, compteur, référence, travaux. Jamais les prix :
le carnet se remet à l'acheteur, les tarifs du garage ne le suivent
pas. Le tableau auto est vide — plus de chantier ouvert ; pour
mémoire, le rythme d'expertise est le rythme fédéral, les convocations
cantonales (OCN, SAN…) peuvent s'en écarter.

## Rendez-vous en ligne (`addons/megga_rdv`)

Le chantier commun aux verticales : l'équivalent Community du module
Enterprise `appointment`. Types de rendez-vous (durée, plages
hebdomadaires, intervenants, fuseau, préavis, horizon), page publique
`/rdv` rendue côté serveur qui ne montre que des créneaux réellement
libres — l'agenda `calendar.event` du cœur fait foi, dans les deux sens :
un événement occupe le créneau, une réservation devient un événement chez
l'intervenant le moins chargé du jour. Confirmation par e-mail avec lien
d'annulation à jeton (l'annulation supprime l'événement et libère le
créneau). Rappel de la veille : un cron quotidien idempotent rappelle
par e-mail chaque réservation confirmée qui démarre dans les 24 heures
(lien d'annulation compris, débrayable par type). 24 tests, dont la
réservation de bout en bout par HTTP (CSRF compris). Indépendant des
verticales : il ne dépend que de `calendar`.

## Origine

Ce dépôt a été extrait du dépôt d'audit `megga/rdc` par `git subtree split`,
avec son historique complet (10 commits). Les documents d'analyse — audits CRM,
ERP, conformité suisse, stratégie de surcouche et plan de reprise — restent
dans `megga/rdc`.
