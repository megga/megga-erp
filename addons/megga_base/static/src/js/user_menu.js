import { registry } from "@web/core/registry";

// Retire du menu utilisateur les entrées qui pointent vers odoo.com
// (clés vérifiées dans user_menu_items.js au SHA épinglé).
const items = registry.category("user_menuitems");
for (const key of ["odoo_account", "support"]) {
    if (items.contains(key)) {
        items.remove(key);
    }
}
