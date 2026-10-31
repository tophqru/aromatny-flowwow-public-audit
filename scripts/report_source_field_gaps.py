#!/usr/bin/env python3
"""Strict coverage report for original Flowwow product fields (no network access).

Runs offline against the committed master snapshot and individual product JSON.
Never treats a successful process exit as proof that missing fields are resolved.
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "catalog/public-snapshot.json"
OUT = ROOT / "source-field-coverage.json"

def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    products = data["products"]
    if not isinstance(products, list) or len(products) != data["products_count"]:
        raise SystemExit("Corrupt manifest products_count")
    missing_composition = []
    missing_description = []
    missing_dimensions = []
    for item in products:
        slug = item["slug"]
        if item["may_order"] is not False or item["may_show_publicly"] is not False:
            raise SystemExit("Unsafe retail status: " + slug)
        card = ROOT / "catalog" / "cards" / slug / "product.json"
        if json.loads(card.read_text(encoding="utf-8")) != item:
            raise SystemExit("Card is not equal to master JSON: " + slug)
        comp = item.get("composition_items")
        if not isinstance(comp, list) or not comp:
            missing_composition.append({"slug": slug, "url": item["flowwow_url"]})
        else:
            if any(not isinstance(e.get("quantity"), (int, float)) or isinstance(e.get("quantity"), bool) or e["quantity"] <= 0 or not e.get("component") or not e.get("unit") for e in comp):
                raise SystemExit("Invalid structured composition: " + slug)
        desc = item.get("description_raw_ru")
        if not isinstance(desc, str) or not desc.strip() or item.get("description_status") not in ("OBSERVED_SOURCE_TEXT", "OBSERVED_GENERIC_SOURCE_TEXT"):
            missing_description.append({"slug": slug, "url": item["flowwow_url"], "source_status": item.get("description_status")})
        dims = item.get("dimensions_cm")
        if not isinstance(dims, dict) or any(not isinstance(dims.get(k), (int, float)) or dims[k] <= 0 for k in ("width", "height")):
            missing_dimensions.append({"slug": slug, "url": item["flowwow_url"]})
    counts = {"products": len(products), "composition_complete": len(products)-len(missing_composition),
              "description_complete": len(products)-len(missing_description),
              "dimensions_complete": len(products)-len(missing_dimensions)}
    done = not (missing_composition or missing_description or missing_dimensions)
    result = {"validation": "PASS_SOURCE_STRUCTURE", "catalog_completion": "FULL_FIELDS_PRESENT_NOT_SOURCE_VERIFIED" if done else "INCOMPLETE",
              "caveat": "Source-field presence alone does not verify exact live Flowwow wording, seller inventory or gallery completeness.",
              "counts": counts, "missing": {"composition": missing_composition,
              "description": missing_description, "dimensions": missing_dimensions}}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("validation", "catalog_completion", "counts")}, ensure_ascii=False))
    if not done:
        print("INCOMPLETE source fields: inspect source-field-coverage.json; SUCCESS is not catalog completion.")
    with open(os.environ.get("GITHUB_STEP_SUMMARY", os.devnull), "a", encoding="utf-8") as summary:
        summary.write("### Flowwow source field coverage (not source verification)\n")
        summary.write("| Field | Present | Missing |\n|---|---:|---:|\n")
        for key, title in (("composition", "Exact structured composition"), ("description", "Original description"), ("dimensions", "Dimensions")):
            summary.write(f"| {title} | {len(products)-len(result['missing'][key])} | {len(result['missing'][key])} |\n")
        summary.write(f"\n**Catalog completion:** {result['catalog_completion']}\n")

if __name__ == "__main__":
    main()
