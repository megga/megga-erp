# Reprise des données Office Maker — mode d'emploi

## Ce qu'on reprend (et ce qu'on ne reprend pas)

**Repris dans Megga Care** : les clients, les prestataires, les mandats
et leurs événements (avec prix client et coût réel) — tout ce qui fait
la valeur métier et statistique : rentabilité par client, par type de
prestation, volumes par fournisseur pour négocier les rétrocessions.

**Volontairement non repris** : les écritures comptables des dix
dernières années. La bascule comptable se fait au jour J avec la
comptable — soldes d'ouverture et factures ouvertes uniquement — et
l'historique comptable reste consultable dans Office Maker, conservé en
archive (l'abonnement peut être résilié, l'application locale continue
de consulter ses données).

## Exporter depuis Office Maker

Pour chacune des quatre tables (Contacts clients, Contacts
prestataires, Mandats, Événements de mandat) :

1. Ouvrir la liste, sélectionner toutes les fiches.
2. Exporter en **texte tabulé** (Fichier → Exporter), **UTF-8** si le
   choix est proposé — sinon n'importe quel encodage : l'assistant
   détecte BOM, UTF-8 et Windows, et Mac Roman se choisit à la main.
3. Inclure la **ligne d'en-têtes** : l'assistant rapproche les colonnes
   par leur nom (« N° », « Nom », « Prix client »… — voir les fichiers
   d'exemple de ce dossier), pas par leur position.

Colonnes indispensables : une **référence** stable pour les clients et
les mandats (le n° Office Maker), le **client** sur chaque mandat, le
**mandat** sur chaque événement. Le reste est optionnel.

## Importer dans Megga

Menu **Conciergerie → Reprise Office Maker** (rôle Coordination), un
fichier à la fois, **dans l'ordre** :

1. Clients (patients)
2. Prestataires
3. Mandats
4. Événements de mandat

L'ordre suit les liaisons : un mandat cherche son client par sa
référence, un événement cherche son mandat. Le rapport liste les lignes
créées, mises à jour et **rejetées avec leur raison** (type de
prestation absent du référentiel, date illisible, mandat introuvable…).

## Pourquoi on peut recommencer sans risque

Chaque fiche importée est rattachée à sa référence Office Maker.
Ré-importer le même export — ou un export corrigé — **met à jour** les
fiches, il n'en duplique jamais. La méthode recommandée :

1. Export d'essai aujourd'hui, import, vérification des rapports.
2. Compléter le référentiel des types de prestation si des lignes le
   réclament, relancer les fichiers rejetés.
3. Au jour de la bascule : ré-export complet, ré-import — l'écart des
   dernières semaines se met à jour tout seul.

Les mandats historiques arrivent **clôturés** : ils ne déclenchent ni le
garde-fou de facturation, ni les rappels, ni les filtres « À facturer »
— mais alimentent immédiatement les statistiques.
