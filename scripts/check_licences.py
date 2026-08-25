#!/usr/bin/env python3
"""Garde-fou licences (Phase 1 du plan de reprise).

- addons-oca/ : seuls les modules LGPL-3 sont admis. L'AGPL-3 (85 % de
  l'ecosysteme OCA) declencherait la clause reseau sur l'oeuvre combinee :
  refus systematique. Toute licence inconnue exige une revue humaine -> echec.
- addons/    : nos modules (licence de notre choix — « Other
  proprietary » depuis le 25.08.2026, modele ferme homogene), mais on bloque
  l'AGPL/GPL par inadvertance (copier-coller depuis un module OCA).
"""
import argparse
import ast
import sys
from pathlib import Path

OCA_AUTORISEES = {"LGPL-3"}
CONTAMINANTES = {
    "AGPL-3", "AGPL-3 or any later version",
    "GPL-2", "GPL-2 or any later version",
    "GPL-3", "GPL-3 or any later version",
}


def licence_de(manifest: Path) -> str:
    try:
        data = ast.literal_eval(manifest.read_text(encoding="utf-8"))
    except (SyntaxError, ValueError) as exc:
        return f"MANIFESTE ILLISIBLE ({exc})"
    return data.get("license", "ABSENTE")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path,
                        default=Path(__file__).resolve().parent.parent,
                        help="racine contenant addons/ et addons-oca/")
    base = parser.parse_args().base
    erreurs = []

    for manifest in sorted((base / "addons-oca").glob("*/__manifest__.py")):
        lic = licence_de(manifest)
        if lic not in OCA_AUTORISEES:
            motif = "interdite (clause reseau)" if lic in CONTAMINANTES \
                else "non reconnue : revue humaine requise"
            erreurs.append(f"addons-oca/{manifest.parent.name}: '{lic}' — {motif}")

    notres = sorted((base / "addons").glob("*/__manifest__.py")) + \
        sorted((base / "addons" / "verticals").glob("*/*/__manifest__.py"))
    for manifest in notres:
        lic = licence_de(manifest)
        if lic in CONTAMINANTES:
            chemin = manifest.parent.relative_to(base)
            erreurs.append(f"{chemin}: '{lic}' — "
                           "copyleft contaminant dans un module propre")

    if erreurs:
        print("REFUSE — controle de licences :")
        print("\n".join(f"  - {e}" for e in erreurs))
        return 1
    print("Controle de licences : OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
