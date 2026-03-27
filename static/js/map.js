/* map.js — DigiPIN frontend logic */

"use strict";

// ── Map initialisation ───────────────────────────────────────────────────────
const map = L.map("map", {
  center: [20.5937, 78.9629],   // Centre of India
  zoom: 5,
  zoomControl: true,
  attributionControl: true,
});

// Dark tile layer (CartoDB Dark Matter)
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/">CARTO</a>',
  subdomains: "abcd",
  maxZoom: 22,
}).addTo(map);

// ── Layer groups ─────────────────────────────────────────────────────────────
const pincodeLayer = L.layerGroup().addTo(map);
const gridLayer    = L.layerGroup().addTo(map);
const markerLayer  = L.layerGroup().addTo(map);

// ── State ────────────────────────────────────────────────────────────────────
let lastResult = null;

// ── Load pincode boundaries ───────────────────────────────────────────────────
async function loadBoundaries() {
  try {
    const resp = await fetch("/api/boundaries");
    if (!resp.ok) return;
    const geojson = await resp.json();

    L.geoJSON(geojson, {
      style: {
        color:       "#2a3347",
        weight:      1.2,
        opacity:     0.8,
        fillColor:   "#1e2636",
        fillOpacity: 0.25,
      },
      onEachFeature: (feature, layer) => {
        const props = feature.properties || {};
        const pin   = props.Pincode || "—";
        const name  = props.Office_Name || "";
        layer.bindTooltip(
          `<strong style="color:#00d4a8">${pin}</strong><br/>${name}`,
          { sticky: true, className: "pin-tooltip" }
        );
        layer.on("mouseover", () => {
          layer.setStyle({ fillOpacity: 0.45, color: "#4f8ef7" });
        });
        layer.on("mouseout", () => {
          layer.setStyle({ fillOpacity: 0.25, color: "#2a3347" });
        });
      },
    }).addTo(pincodeLayer);

  } catch (err) {
    console.warn("Could not load pincode boundaries:", err);
  }
}

loadBoundaries();

// ── Encode a lat/lon via the Flask API ────────────────────────────────────────
async function encodePoint(lat, lon) {
  setLoading(true);

  try {
    const resp = await fetch("/api/encode", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ lat, lon }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showError(err.error || `Server error ${resp.status}`);
      return;
    }

    const data = await resp.json();
    lastResult = data;
    renderResult(data, lat, lon);
    drawGridCell(data.cell);
    placeMarker(lat, lon);

  } catch (err) {
    showError("Network error — is the Flask server running?");
    console.error(err);
  } finally {
    setLoading(false);
  }
}

// ── Render result card ───────────────────────────────────────────────────────
function renderResult(data, lat, lon) {
  document.getElementById("result-panel").style.display = "block";
  document.getElementById("hint-panel").style.display   = "none";

  document.getElementById("res-pincode").textContent = data.pincode;
  document.getElementById("res-letters").textContent = data.grid_letters;

  document.getElementById("meta-pincode").textContent = data.pincode;
  document.getElementById("meta-letters").textContent = data.grid_letters;
  document.getElementById("meta-size").textContent    = `${data.grid_size_m} m × ${data.grid_size_m} m`;
  document.getElementById("meta-coords").textContent  =
    `${lat.toFixed(6)}, ${lon.toFixed(6)}`;

  const warn = document.getElementById("outside-warning");
  warn.style.display = data.found ? "none" : "block";

  // Reset copy button
  resetCopyBtn();
}

// ── Draw the 4 m × 4 m grid cell rectangle ───────────────────────────────────
function drawGridCell(cell) {
  gridLayer.clearLayers();

  if (!cell || !cell.sw || !cell.ne) return;

  const sw = L.latLng(cell.sw[0], cell.sw[1]);
  const ne = L.latLng(cell.ne[0], cell.ne[1]);

  // Outer glow
  L.rectangle([sw, ne], {
    color:       "#00d4a8",
    weight:      3,
    opacity:     1,
    fillColor:   "#00d4a8",
    fillOpacity: 0.18,
    dashArray:   null,
  }).addTo(gridLayer);

  // Inner dashed border for depth
  L.rectangle([sw, ne], {
    color:       "#4f8ef7",
    weight:      1,
    opacity:     0.5,
    fill:        false,
    dashArray:   "4 4",
  }).addTo(gridLayer);
}

// ── Place pulsing marker ──────────────────────────────────────────────────────
function placeMarker(lat, lon) {
  markerLayer.clearLayers();

  const icon = L.divIcon({
    className: "",
    html: '<div class="click-marker-pulse"></div>',
    iconSize:   [14, 14],
    iconAnchor: [7, 7],
  });

  L.marker([lat, lon], { icon }).addTo(markerLayer);
}

// ── Map click handler ─────────────────────────────────────────────────────────
map.on("click", (e) => {
  const { lat, lng } = e.latlng;
  encodePoint(lat, lng);
});

// ── Address search ────────────────────────────────────────────────────────────
const geocoder = L.Control.Geocoder.nominatim({
  geocodingQueryParams: { countrycodes: "in", limit: 5 },
});

const searchInput = document.getElementById("address-input");
const suggestionsBox = document.getElementById("search-suggestions");

function performSearch(query) {
  if (!query.trim()) return;

  suggestionsBox.innerHTML = "";
  setLoading(true);

  geocoder.geocode(query, (results) => {
    setLoading(false);

    if (!results || results.length === 0) {
      suggestionsBox.innerHTML =
        '<div class="suggestion-item" style="color:var(--text-muted);cursor:default">No results found</div>';
      return;
    }

    results.slice(0, 5).forEach((r) => {
      const item = document.createElement("div");
      item.className = "suggestion-item";
      item.textContent = r.name;

      item.addEventListener("click", () => {
        suggestionsBox.innerHTML = "";
        searchInput.value = r.name;

        const { lat, lng } = r.center;
        map.setView([lat, lng], 18);
        encodePoint(lat, lng);
      });

      suggestionsBox.appendChild(item);
    });
  });
}

document.getElementById("search-btn").addEventListener("click", () => {
  performSearch(searchInput.value);
});

searchInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") performSearch(searchInput.value);
});

// Dismiss suggestions on outside click
document.addEventListener("click", (e) => {
  if (!e.target.closest("#search-panel")) {
    suggestionsBox.innerHTML = "";
  }
});

// ── Copy to clipboard ─────────────────────────────────────────────────────────
const copyBtn   = document.getElementById("copy-btn");
const copyLabel = document.getElementById("copy-label");

copyBtn.addEventListener("click", async () => {
  if (!lastResult) return;

  const text = lastResult.digipin;

  try {
    await navigator.clipboard.writeText(text);
  } catch (_) {
    // Fallback for non-HTTPS
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity  = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
  }

  copyBtn.classList.add("copied");
  copyLabel.textContent = "Copied!";
  setTimeout(resetCopyBtn, 2000);
});

function resetCopyBtn() {
  copyBtn.classList.remove("copied");
  copyLabel.textContent = "Copy";
}

// ── Loading state helpers ─────────────────────────────────────────────────────
function setLoading(active) {
  const bar = document.getElementById("loading-bar");
  if (active) bar.classList.add("active");
  else        bar.classList.remove("active");
}

function showError(msg) {
  // Briefly flash the hint panel with error text
  const hint = document.getElementById("hint-panel");
  hint.style.display = "block";
  hint.querySelector(".hint").innerHTML =
    `<span class="hint-icon" style="color:var(--warn)">⚠</span>
     <span style="color:var(--warn)">${msg}</span>`;
  setTimeout(() => {
    hint.querySelector(".hint").innerHTML =
      `<span class="hint-icon">👆</span>
       Click anywhere on the map to select a 4 m × 4 m grid cell and generate its DigiPIN.`;
  }, 4000);
}
