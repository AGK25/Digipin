import json
import folium

GEOJSON_PATH = r"C:\Users\GARV\OneDrive\Desktop\lashkar_474001.geojson"
OUT_HTML = "lashkar_boundary_map.html"

with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
    geo = json.load(f)

# Center map roughly on Lashkar
m = folium.Map(location=[26.21, 78.08], zoom_start=12)

folium.GeoJson(
    geo,
    name="Lashkar PIN 474001 Boundary",
    tooltip="PIN 474001 – Lashkar"
).add_to(m)

folium.LayerControl().add_to(m)
m.save(OUT_HTML)

print("✅ Map saved:", OUT_HTML)
