import { registry } from "@web/core/registry";

// Réimplémentation du service de titre de web (contrat identique, vérifié
// au SHA épinglé) : seul le repli change — « Megga » au lieu de « Odoo ».
export const meggaTitleService = {
    start() {
        const titleCounters = {};
        const titleParts = {};

        function getParts() {
            return Object.assign({}, titleParts);
        }

        function setCounters(counters) {
            for (const key in counters) {
                const val = counters[key];
                if (!val) {
                    delete titleCounters[key];
                } else {
                    titleCounters[key] = val;
                }
            }
            updateTitle();
        }

        function setParts(parts) {
            for (const key in parts) {
                const val = parts[key];
                if (!val) {
                    delete titleParts[key];
                } else {
                    titleParts[key] = val;
                }
            }
            updateTitle();
        }

        function updateTitle() {
            const counter = Object.values(titleCounters).reduce((acc, count) => acc + count, 0);
            const name = Object.values(titleParts).join(" - ") || "Megga";
            if (!counter) {
                document.title = name;
            } else {
                document.title = `(${counter}) ${name}`;
            }
        }

        return {
            get current() {
                return document.title;
            },
            getParts,
            setCounters,
            setParts,
        };
    },
};

registry.category("services").add("title", meggaTitleService, { force: true });
