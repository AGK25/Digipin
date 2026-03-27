"""
geo_utils.py
------------
Spatial helpers: load pincode boundaries and do point-in-polygon lookups.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Optional

from shapely.geometry import Point, shape

# ── Load GeoJSON ──────────────────────────────────────────────────────────────

GEOJSON_PATH = os.path.join(os.path.dirname(__file__), "data", "pincode_boundary.geojson")


@lru_cache(maxsize=1)
def load_boundaries() -> list[dict]:
    """
    Load pincode boundary features once and cache them.
    Returns a list of dicts, each with keys:
      'pincode'  : str
      'geometry' : shapely geometry object
      'properties': original GeoJSON properties dict
    """
    if not os.path.exists(GEOJSON_PATH):
        return []

    with open(GEOJSON_PATH, "r", encoding="utf-8") as fh:
        fc = json.load(fh)

    features = []
    for feat in fc.get("features", []):
        props = feat.get("properties", {})
        pincode = str(props.get("Pincode", "")).strip()
        try:
            geom = shape(feat["geometry"])
        except Exception:
            continue
        features.append({
            "pincode": pincode,
            "geometry": geom,
            "properties": props,
        })
    return features


def pincode_for_point(lat: float, lon: float) -> Optional[str]:
    """
    Return the pincode string for the feature whose polygon contains (lat, lon),
    or None if no match is found.
    """
    pt = Point(lon, lat)          # shapely uses (x=lon, y=lat)
    for feat in load_boundaries():
        if feat["geometry"].contains(pt):
            return feat["pincode"]
    return None


def geojson_for_pincode(pincode: str) -> Optional[dict]:
    """
    Return the raw GeoJSON Feature dict for the given pincode, or None.
    """
    for feat in load_boundaries():
        if feat["pincode"] == pincode:
            props = feat["properties"]
            return {
                "type": "Feature",
                "properties": props,
                "geometry": feat["geometry"].__geo_interface__,
            }
    return None


def all_pincodes_geojson() -> dict:
    """
    Return a GeoJSON FeatureCollection of all loaded pincode boundaries.
    """
    features = []
    for feat in load_boundaries():
        features.append({
            "type": "Feature",
            "properties": feat["properties"],
            "geometry": feat["geometry"].__geo_interface__,
        })
    return {"type": "FeatureCollection", "features": features}

 
# ── Origin helper (used by app.py encode route) ───────────────────────────────
 
def origin_for_pincode(pincode: str):
    """
    Return (origin_lon, origin_lat) — the (min_lon, min_lat) corner of the
    pincode polygon's outer ring — or None if the pincode is not found.
 
    This is the same origin derivation used by generate_origins.py, but
    computed on-the-fly from the already-loaded boundary data so no separate
    origins file is needed.
    """
    for feat in load_boundaries():
        if feat["pincode"] != pincode:
            continue
 
        # Pull coordinates straight from the shapely geometry
        geom = feat["geometry"]
        try:
            # Works for both Polygon and MultiPolygon
            if geom.geom_type == "Polygon":
                coords = list(geom.exterior.coords)
            elif geom.geom_type == "MultiPolygon":
                # Use the largest sub-polygon's exterior
                largest = max(geom.geoms, key=lambda g: g.area)
                coords  = list(largest.exterior.coords)
            else:
                return None
        except Exception:
            return None
 
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        return (min(lons), min(lats))
 
    return None
