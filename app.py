"""
app.py
------
Flask application — single point of contact between the Folium/Leaflet
frontend and the encoding back-end.

Routes
------
GET  /                   → main map UI
POST /api/encode         → lat/lon → DigiPIN + cell bounds
GET  /api/boundaries     → full GeoJSON FeatureCollection
GET  /api/boundary/<pin> → GeoJSON for one pincode
"""

from __future__ import annotations

import json

from flask import Flask, jsonify, render_template, request

from encoding import cell_bounds, encode_digipin, GRID_SIZE_M
from geo_utils import (
    all_pincodes_geojson,
    geojson_for_pincode,
    load_boundaries,
    origin_for_pincode,
    pincode_for_point,
)

app = Flask(__name__)


# ── Main page ─────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


# ── Encode endpoint ───────────────────────────────────────────────────────────


@app.route("/api/encode", methods=["POST"])
def api_encode():
    """
    Body:   { "lat": float, "lon": float }

    Happy-path response:
    {
        "digipin":      "474001-ABCD",
        "pincode":      "474001",
        "grid_letters": "ABCD",
        "grid_size_m":  4,
        "cell": {
            "sw":     [lat, lon],
            "ne":     [lat, lon],
            "center": [lat, lon]
        }
    }

    Error responses:
        400  missing / non-numeric lat or lon
        422  coordinates outside India, or point behind origin frame
        404  point outside all pincode polygons
    """
    data = request.get_json(force=True, silent=True) or {}

    # ── Parse & validate input ────────────────────────────────────────────────
    try:
        lat = float(data["lat"])
        lon = float(data["lon"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "lat and lon are required numeric fields."}), 400

    if not (6.0 <= lat <= 37.5 and 68.0 <= lon <= 97.5):
        return jsonify({"error": "Coordinates appear to be outside India."}), 422

    # ── Step 1: which pincode polygon contains this point? ────────────────────
    pincode = pincode_for_point(lat, lon)
    if pincode is None:
        return (
            jsonify(
                {"error": "The selected point is outside all known pincode boundaries."}
            ),
            404,
        )

    # ── Step 2: get origin corner from the polygon (no separate file needed) ──
    origin = origin_for_pincode(pincode)
    if origin is None:
        # Should never happen if the GeoJSON is well-formed
        return (
            jsonify({"error": f"Could not compute origin for pincode {pincode}."}),
            500,
        )

    origin_lon, origin_lat = origin

    location_name = "Unknown Area"
    for feat in load_boundaries():
        if feat["pincode"] == pincode:
            props = feat.get("properties", {})
            # Adjust 'District' or 'Office_Name' based on your GeoJSON keys
            location_name = props.get(
                "District", props.get("Office_Name", "Unknown Area")
            )
            break

    # ── Step 3: encode ────────────────────────────────────────────────────────
    try:
        digipin = encode_digipin(
            lat,
            lon,
            pincode,
            origin_lon=origin_lon,
            origin_lat=origin_lat,
            grid_size_m=GRID_SIZE_M,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    grid_letters = digipin[7:]  # "474001-ABCD" → "ABCD"
    bounds = cell_bounds(
        lat,
        lon,
        origin_lon=origin_lon,
        origin_lat=origin_lat,
        grid_size_m=GRID_SIZE_M,
    )

    return jsonify(
        {
            "digipin": digipin,
            "pincode": pincode,
            "grid_letters": grid_letters,
            "grid_size_m": GRID_SIZE_M,
            "cell": bounds,
            "location_name": location_name,
        }
    )


# ── Boundary endpoints ────────────────────────────────────────────────────────


# app.py
@app.route("/api/boundaries")
def api_boundaries():
    try:
        fc = all_pincodes_geojson()
        return jsonify(fc)
    except Exception as e:
        print(f"Error loading boundaries: {e}")
        return jsonify({"type": "FeatureCollection", "features": []}), 500


@app.route("/api/boundary/<pincode>")
def api_boundary_single(pincode: str):
    """GeoJSON Feature for a single pincode."""
    feat = geojson_for_pincode(pincode.strip())
    if feat is None:
        return jsonify({"error": f"Pincode {pincode} not found."}), 404
    return jsonify(feat)


# ── Dev server ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
