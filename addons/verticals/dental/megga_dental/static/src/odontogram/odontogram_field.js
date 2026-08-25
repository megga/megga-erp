import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

/* Odontogramme FDI : deux arcades de 16 dents définitives (plus les
   rangées de lait quand le dossier en porte), chaque dent dessinée en
   cinq zones — quatre trapèzes (mésiale, distale, vestibulaire,
   linguale) autour du carré occlusal. Le serveur envoie l'état et la
   légende (couleurs comprises) dans la charge JSON : aucun savoir
   métier ici, seulement de la géométrie. */

const CELL = 38;      // pas horizontal d'une dent
const SQUARE = 30;    // côté du carré dessiné
const INSET = 9;      // profondeur des trapèzes de surface
const GAP = 14;       // écart supplémentaire à la ligne médiane
const ROW_H = 52;     // hauteur d'une rangée (carré + numéro)
const ARCH_GAP = 10;  // respiration entre les deux arcades

// Quadrants dont la face mésiale est à DROITE du carré (moitié gauche
// du schéma, la mésiale regarde toujours la ligne médiane).
const MESIAL_RIGHT = [1, 4, 5, 8];

const UPPER = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
const LOWER = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];
const UPPER_DECIDUOUS = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65];
const LOWER_DECIDUOUS = [85, 84, 83, 82, 81, 71, 72, 73, 74, 75];

export class OdontogramField extends Component {
    static template = "megga_dental.OdontogramField";
    static props = { ...standardFieldProps };

    setup() {
        this.action = useService("action");
    }

    get data() {
        const raw = this.props.record.data[this.props.name];
        if (!raw) {
            return null;
        }
        try {
            return JSON.parse(raw);
        } catch {
            return null;
        }
    }

    get chart() {
        const data = this.data;
        if (!data) {
            return null;
        }
        const colors = Object.fromEntries(
            data.legend.map((item) => [item.code, item.color])
        );
        const labels = Object.fromEntries(
            data.legend.map((item) => [item.code, item.label])
        );
        const rows = [{ teeth: UPPER, below: true, arch: "upper" }];
        if (data.deciduous) {
            rows.push({ teeth: UPPER_DECIDUOUS, below: true, arch: "upper" });
            rows.push({ teeth: LOWER_DECIDUOUS, below: false, arch: "lower" });
        }
        rows.push({ teeth: LOWER, below: false, arch: "lower" });

        const cells = [];
        let y = 2;
        rows.forEach((row, index) => {
            if (index > 0 && rows[index - 1].arch !== row.arch) {
                y += ARCH_GAP;
            }
            const offset = ((16 - row.teeth.length) / 2) * CELL + 4;
            const squareY = row.below ? y : y + 16;
            const numberY = row.below ? squareY + SQUARE + 13 : y + 11;
            const midIndex = row.teeth.length / 2;
            row.teeth.forEach((number, i) => {
                const x = offset + i * CELL + (i >= midIndex ? GAP : 0);
                cells.push(this.buildCell(
                    data, colors, labels, number, x, squareY, numberY, row.arch
                ));
            });
            y += ROW_H;
        });
        return {
            cells,
            legend: data.legend.filter((item) => item.code !== "saine")
                .concat(data.legend.filter((item) => item.code === "saine")),
            width: 16 * CELL + GAP + 8,
            height: y + 2,
        };
    }

    buildCell(data, colors, labels, number, x, y, numberY, arch) {
        const info = data.teeth[String(number)] || { surfaces: {} };
        const s = SQUARE;
        const i = INSET;
        const mesialRight = MESIAL_RIGHT.includes(Math.floor(number / 10));
        const codeOf = {
            top: arch === "upper" ? "V" : "L",
            bottom: arch === "upper" ? "L" : "V",
            left: mesialRight ? "D" : "M",
            right: mesialRight ? "M" : "D",
        };
        const zones = [
            [codeOf.top, `${x},${y} ${x + s},${y} ${x + s - i},${y + i} ${x + i},${y + i}`],
            [codeOf.bottom, `${x},${y + s} ${x + i},${y + s - i} ${x + s - i},${y + s - i} ${x + s},${y + s}`],
            [codeOf.left, `${x},${y} ${x + i},${y + i} ${x + i},${y + s - i} ${x},${y + s}`],
            [codeOf.right, `${x + s},${y} ${x + s},${y + s} ${x + s - i},${y + s - i} ${x + s - i},${y + i}`],
            ["O", `${x + i},${y + i} ${x + s - i},${y + i} ${x + s - i},${y + s - i} ${x + i},${y + s - i}`],
        ];
        const stateOf = (code) => info.surfaces[code] || info.tooth || null;
        const parts = [];
        if (info.tooth) {
            parts.push(labels[info.tooth] || info.tooth);
        }
        for (const [surface, condition] of Object.entries(info.surfaces)) {
            parts.push(`${surface} : ${labels[condition] || condition}`);
        }
        return {
            number,
            toothId: info.id,
            title: `${number} — ${info.name || ""}` +
                (parts.length ? `\n${parts.join(", ")}` : ""),
            polys: zones.map(([code, points]) => ({
                code,
                points,
                fill: stateOf(code) ? colors[stateOf(code)] : "transparent",
            })),
            cross: info.tooth === "absente"
                ? { x1: x + 3, y1: y + 3, x2: x + s - 3, y2: y + s - 3,
                    x3: x + s - 3, y3: y + 3, x4: x + 3, y4: y + s - 3 }
                : null,
            tx: x + s / 2,
            ty: numberY,
        };
    }

    async openTooth(cell) {
        if (!cell.toothId || !this.props.record.resId) {
            return;
        }
        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: _t("Dent %s", cell.number),
                res_model: "megga.dental.tooth.record",
                views: [[false, "list"], [false, "form"]],
                target: "new",
                domain: [
                    ["patient_id", "=", this.props.record.resId],
                    ["tooth_id", "=", cell.toothId],
                ],
                context: {
                    default_patient_id: this.props.record.resId,
                    default_tooth_id: cell.toothId,
                },
            },
            {
                onClose: async () => {
                    try {
                        await this.props.record.model.root.load();
                    } catch {
                        // au pire, l'odontogramme se rafraîchira au
                        // prochain chargement du formulaire
                    }
                },
            }
        );
    }
}

export const odontogramField = {
    component: OdontogramField,
    displayName: _t("Odontogramme"),
    supportedTypes: ["text", "char"],
};

registry.category("fields").add("megga_odontogram", odontogramField);
