# megga_base — surcouche de marque

Phase 2 du [plan de reprise](../../../PLAN-REPRISE-ODOO.md). Aucune
modification du cœur : uniquement de l'héritage de vues, d'assets et de
services, chaque point d'ancrage ayant été vérifié dans le source 19.0
au SHA épinglé (`9188766f`).

| Surcharge | Point d'ancrage vérifié |
|---|---|
| Titre d'onglet (XML) | `web.layout` — `<title t-esc="title or 'Odoo'"/>` |
| Titre d'onglet (JS) | service `title`, remplacé via `force: true` |
| Favicon | `web.layout` — `<link rel="shortcut icon" t-att-href="x_icon or ...">` |
| Pied de connexion | `web.login_layout` — lien `utm_medium=auth` retiré, « Manage Databases » conservé |
| Promotion portail | `web.brand_promotion_message` — neutralisé |
| Pied des e-mails | `mail.mail_notification_layout` (`div t-if="show_footer"`) et `mail_notification_light` (ligne `utm_medium=email`) |
| Menu utilisateur | clés `odoo_account` et `support` retirées du registre `user_menuitems` |
| Couleur primaire | `web._assets_primary_variables`, fichier prépendu (`#0E6B4F`) |
| Logo société | `res.company.logo` de `base.main_company` (noupdate) |

Les visuels de `static/img/` sont des **placeholders générés** — à remplacer
par la vraie identité (mêmes chemins).

## Vérification au premier boot (non testable dans la session de création)

- [ ] `-i megga_base` s'installe sans erreur de vue
- [ ] Onglet « Megga », favicon vert, couleur primaire verte
- [ ] Page de connexion sans « Powered by Odoo »
- [ ] E-mail de test sans pied promotionnel
- [ ] Menu utilisateur sans « My Odoo.com account » ni « Support »
