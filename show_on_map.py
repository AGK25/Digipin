import json
import math
from pathlib import Path

import folium
from shapely.geometry import shape, Point

# ----------------------------
# CONFIG
# ----------------------------
GEOJSON_PATH = r"C:\Users\GARV\OneDrive\Desktop\All_India_pincode_Boundary-19312.geojson"
ORIGINS_JSON = r"C:\Users\GARV\OneDrive\Desktop\gwalior_origins.json"

PIN = "474006"         # Morar
GRID_SIZE_M = 4        # 4m x 4m

# Replace these for another point
TEST_LAT = 26.22325257
TEST_LON = 78.22265625

# How many cells around the point to draw (radius)
# 25 => draws (2*25+1)=51 lines in each direction -> 51x51 cells shown (local window)
GRID_RADIUS_CELLS = 20   # 20 => 41x41 cells = 164m x 164m

OUT_HTML = "digipin_grid_demo_morar.html"


# ----------------------------
# HELPERS (encoding + grid)
# ----------------------------
def lonlat_to_meters_delta(lon, lat, origin_lon, origin_lat):
    meters_per_deg_lat = 111320.0
    lat_rad = math.radians(lat)
    meters_per_deg_lon = 111320.0 * math.cos(lat_rad)
    dx_m = (lon - origin_lon) * meters_per_deg_lon
    dy_m = (lat - origin_lat) * meters_per_deg_lat
    return dx_m, dy_m


def morton_interleave_16bit(x, y):
    def split_by_1bits(n):
        n &= 0xFFFF
        n = (n | (n << 8)) & 0x00FF00FF
        n = (n | (n << 4)) & 0x0F0F0F0F
        n = (n | (n << 2)) & 0x33333333
        n = (n | (n << 1)) & 0x55555555
        return n
    return split_by_1bits(x) | (split_by_1bits(y) << 1)


def to_base26_4letters(n):
    max_n = 26**4 - 1
    if n < 0 or n > max_n:
        raise ValueError(f"Index out of range for 4 letters: {n}")
    letters = []
    for power in (26**3, 26**2, 26, 1):
        digit = n // power
        n = n % power
        letters.append(chr(ord("A") + digit))
    return "".join(letters)


def encode_digipin(lat, lon, pincode, origins, grid_m):
    pincode = str(pincode).strip()
    if pincode not in origins:
        raise KeyError(f"Pincode {pincode} not found in origins JSON")

    origin_lon = float(origins[pincode]["origin_lon"])
    origin_lat = float(origins[pincode]["origin_lat"])

    dx_m, dy_m = lonlat_to_meters_delta(lon, lat, origin_lon, origin_lat)

    x = int(math.floor(dx_m / grid_m))
    y = int(math.floor(dy_m / grid_m))

    if x < 0 or y < 0:
        raise ValueError(
            f"Point outside origin frame: x={x}, y={y}. "
            f"Either point not in PIN polygon or origin needs checking."
        )

    morton = morton_interleave_16bit(x, y)
    code_index = morton % (26**4)  # demo folding
    letters = to_base26_4letters(code_index)
    return f"{pincode}-{letters}", x, y, origin_lat, origin_lon


def cell_bounds_latlon(x, y, origin_lat, origin_lon, grid_m):
    meters_per_deg_lat = 111320.0
    lat_rad = math.radians(origin_lat)
    meters_per_deg_lon = 111320.0 * math.cos(lat_rad)

    min_dx = x * grid_m
    min_dy = y * grid_m
    max_dx = (x + 1) * grid_m
    max_dy = (y + 1) * grid_m

    min_lon = origin_lon + (min_dx / meters_per_deg_lon)
    max_lon = origin_lon + (max_dx / meters_per_deg_lon)
    min_lat = origin_lat + (min_dy / meters_per_deg_lat)
    max_lat = origin_lat + (max_dy / meters_per_deg_lat)

    return min_lat, min_lon, max_lat, max_lon


def draw_local_grid(m, origin_lat, origin_lon, grid_m, x0, y0, radius_cells):
    """
    Draw a local window of grid cells around (x0, y0).
    This draws rectangles for cells in [x0-radius..x0+radius] x [y0-radius..y0+radius].
    """
    x_min = max(0, x0 - radius_cells)
    y_min = max(0, y0 - radius_cells)
    x_max = x0 + radius_cells
    y_max = y0 + radius_cells

    # Draw grid cells (lightweight rectangles)
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            min_lat, min_lon, max_lat, max_lon = cell_bounds_latlon(x, y, origin_lat, origin_lon, grid_m)

            # Default grid cell style (thin)
            folium.Rectangle(
                bounds=[[min_lat, min_lon], [max_lat, max_lon]],
                color="#444444",
                weight=1,
                fill=False,
                opacity=0.35,
            ).add_to(m)


# ----------------------------
# MAIN
# ----------------------------
def main():
    # Load origins
    with open(ORIGINS_JSON, "r", encoding="utf-8") as f:
        origins = json.load(f)

    # Load geojson
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        geo = json.load(f)

    # Find feature for PIN
    pin_feature = None
    for ft in geo.get("features", []):
        props = ft.get("properties", {}) or {}
        if str(props.get("Pincode", "")).strip() == PIN:
            pin_feature = ft
            break

    if not pin_feature:
        raise ValueError(f"PIN {PIN} not found in GeoJSON")

    pin_geom = shape(pin_feature["geometry"])

    # Point + inside check
    pt = Point(TEST_LON, TEST_LAT)
    inside = pin_geom.contains(pt)

    # Encode
    digipin_code, x, y, origin_lat, origin_lon = encode_digipin(
        TEST_LAT, TEST_LON, PIN, origins, GRID_SIZE_M
    )

    # Create map
    m = folium.Map(location=[TEST_LAT, TEST_LON], zoom_start=16, tiles="OpenStreetMap")

    # Add PIN boundary
    folium.GeoJson(pin_feature, name=f"PIN {PIN} boundary").add_to(m)

    # Draw local grid around the point (proper representation)
    draw_local_grid(m, origin_lat, origin_lon, GRID_SIZE_M, x, y, GRID_RADIUS_CELLS)

    # Highlight the EXACT cell for this point (thicker + filled)
    min_lat, min_lon, max_lat, max_lon = cell_bounds_latlon(x, y, origin_lat, origin_lon, GRID_SIZE_M)
    folium.Rectangle(
        bounds=[[min_lat, min_lon], [max_lat, max_lon]],
        color="red",
        weight=3,
        fill=True,
        fill_opacity=0.15,
        tooltip=f"Exact 4m cell: {digipin_code} (x={x}, y={y})",
    ).add_to(m)

    # Add point marker
    popup_html = (
        f"<b>Point</b><br>"
        f"Lat,Lon: {TEST_LAT}, {TEST_LON}<br>"
        f"<b>Your DigiPIN:</b> {digipin_code}<br>"
        f"Grid cell (x,y): ({x},{y})<br>"
        f"Inside PIN polygon: <b>{inside}</b>"
    )
    folium.Marker(
        location=[TEST_LAT, TEST_LON],
        popup=folium.Popup(popup_html, max_width=360),
    ).add_to(m)

    folium.LayerControl().add_to(m)
    m.save(OUT_HTML)

    print("✅ Saved map:", Path(OUT_HTML).resolve())
    print("✅ DigiPIN:", digipin_code)
    print("✅ Inside PIN polygon:", inside)
    print("✅ Grid cell (x,y):", x, y)


if __name__ == "__main__":
    main()
