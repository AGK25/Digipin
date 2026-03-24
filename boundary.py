import json
import os
from typing import Any, Dict, List, Optional, Tuple

# ----------------------------
# Config
# ----------------------------
INPUT_GEOJSON = r"C:\Users\GARV\OneDrive\Desktop\All_India_pincode_Boundary-19312.geojson"
OUTPUT_JSON = r"C:\Users\GARV\OneDrive\Desktop\gwalior_origins.json"
DIVISION_KEYWORD = "Gwalior"
PRINT_EVERY = 2000


# ----------------------------
# Geometry helpers (Polygon only)
# ----------------------------
def iter_ring_from_polygon(geom: Dict[str, Any]) -> Optional[List[List[float]]]:
    """Return the outer ring (list of [lon, lat]) from a Polygon geometry."""
    if not geom or geom.get("type") != "Polygon":
        return None

    coords = geom.get("coordinates")
    if not isinstance(coords, list) or not coords or not isinstance(coords[0], list):
        return None

    outer_ring = coords[0]
    if not isinstance(outer_ring, list) or not outer_ring:
        return None

    return outer_ring


def min_lon_lat_from_ring(ring: List[List[float]]) -> Optional[Tuple[float, float]]:
    """Compute min_lon, min_lat from a polygon outer ring."""
    min_lon = float("inf")
    min_lat = float("inf")
    found = False

    for pt in ring:
        if not isinstance(pt, list) or len(pt) < 2:
            continue

        lon, lat = pt[0], pt[1]
        if lon is None or lat is None:
            continue

        found = True
        if lon < min_lon:
            min_lon = lon
        if lat < min_lat:
            min_lat = lat

    if not found:
        return None

    return (min_lon, min_lat)


# ----------------------------
# Main extraction logic
# ----------------------------
def extract_division_origins(
    geojson_path: str,
    division_keyword: str,
) -> Dict[str, Dict[str, Any]]:
    """
    Extract a lookup:
      pincode -> { origin_lon, origin_lat, office, division }
    Only for features where properties['Division'] contains division_keyword.
    Assumes geometry is Polygon.
    """
    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    out: Dict[str, Dict[str, Any]] = {}

    total = len(features)
    print(f"Loaded {total} features. Filtering Division contains: '{division_keyword}'")

    for idx, feature in enumerate(features, start=1):
        if PRINT_EVERY and idx % PRINT_EVERY == 0:
            print(f"Processed {idx}/{total}... (kept {len(out)})")

        props = feature.get("properties") or {}
        division = (props.get("Division") or "").strip()

        # Filter by division keyword (case-insensitive)
        if not division or division_keyword.lower() not in division.lower():
            continue

        pincode = props.get("Pincode")
        if pincode is None:
            continue

        pincode_key = str(pincode).strip()
        if not pincode_key:
            continue

        geom = feature.get("geometry")
        ring = iter_ring_from_polygon(geom)
        if not ring:
            continue

        origin = min_lon_lat_from_ring(ring)
        if not origin:
            continue

        min_lon, min_lat = origin

        out[pincode_key] = {
            "origin_lon": min_lon,
            "origin_lat": min_lat,
            "office": props.get("Office_Name"),
            "division": division,
        }

    return out


def main():
    if not os.path.exists(INPUT_GEOJSON):
        raise FileNotFoundError(f"GeoJSON not found at: {INPUT_GEOJSON}")

    results = extract_division_origins(INPUT_GEOJSON, DIVISION_KEYWORD)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n✅ Extraction complete!")
    print(f"✅ Found {len(results)} PIN codes in Division containing '{DIVISION_KEYWORD}'.")
    print(f"✅ Saved: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
