# DigiPIN — Grid Address Encoder

A Flask + Leaflet web application that lets users click on a map (or search for an address) to generate a **10-character DigiPIN** for any 4 m × 4 m grid cell in India.

---

## DigiPIN format

```
110001  ABCD
└──┬──┘ └─┬─┘
6-digit    4-letter Morton
pincode    grid code
```

---

## Project structure

```
digipin/
├── app.py              ← Flask routes (entry point)
├── encoding.py         ← All 4 encoding functions  ← REPLACE with your impl
├── geo_utils.py        ← Pincode boundary spatial index
├── requirements.txt
├── data/
│   └── pincode_boundary.geojson   ← Drop your GeoJSON here
├── templates/
│   └── index.html      ← Jinja2 template
└── static/
    ├── css/style.css
    └── js/map.js
```

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Place your GeoJSON
cp /path/to/pincode_boundary.geojson data/pincode_boundary.geojson

# 3. Plug in your encoding functions
#    Open encoding.py and replace the bodies of:
#      lonlat_to_meters_delta()
#      morton_interleave_32bit()
#      to_base26_4letters()
#      encode_digipin()

# 4. Run
python app.py
# → http://127.0.0.1:5000
```

For production:
```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

---

## API reference

### `POST /api/encode`
**Body** `{ "lat": 28.6139, "lon": 77.2090 }`

**Response**
```json
{
  "digipin":      "110001ABCD",
  "pincode":      "110001",
  "grid_letters": "ABCD",
  "grid_size_m":  4,
  "cell": {
    "sw":     [28.613896, 77.208984],
    "ne":     [28.613932, 77.209021],
    "center": [28.613914, 77.209003]
  },
  "found": true
}
```

### `GET /api/boundaries`
Returns GeoJSON `FeatureCollection` of all pincode polygons.

### `GET /api/boundary/<pincode>`
Returns GeoJSON `Feature` for a single pincode.

---

## Replacing the encoding functions

`encoding.py` is intentionally isolated. All four functions have clearly typed
signatures and docstrings. Drop your implementations in and the rest of the app
picks them up automatically — no other file needs changing.

The only constant you may want to adjust:

```python
GRID_SIZE_M: int = 4   # metres per grid cell side
```

---

## Notes

- Point-in-polygon lookup uses **Shapely** with an `lru_cache` so the GeoJSON
  is parsed once and held in memory.
- If a clicked point falls outside all known pincode polygons the API returns
  `"found": false` and uses `"000000"` as a placeholder pincode; the UI shows a
  warning banner.
- The Leaflet geocoder uses **Nominatim** (OpenStreetMap) with `countrycodes=in`
  to bias results toward India.
