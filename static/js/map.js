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
const gridLayer = L.layerGroup().addTo(map);
const markerLayer = L.layerGroup().addTo(map);

// ── State ────────────────────────────────────────────────────────────────────
let lastResult = null;

// ── Encode a lat/lon via the Flask API ────────────────────────────────────────
async function encodePoint(lat, lon) {
  setLoading(true);
  try {
    const resp = await fetch("/api/encode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat, lon }),
    });

    const data = await resp.json();
    if (!resp.ok) {
        showError(data.error);
        return;
    }

    lastResult = data;
    renderResult(data, lat, lon);
    drawGridCell(data.cell);
    placeMarker(lat, lon);

    // ONLY load the boundary for the found pincode to prevent lag
    const bResp = await fetch(`/api/boundary/${data.pincode}`);
    if (bResp.ok) {
      const geom = await bResp.json();
      pincodeLayer.clearLayers(); // Remove old boundaries
      L.geoJSON(geom, {
        style: { color: "#00d4a8", weight: 2, fillOpacity: 0.1 }
      }).addTo(pincodeLayer);
    }

  } catch (err) {
    showError("Connection error.");
  } finally {
    setLoading(false);
  }
}
// ── Render result card ───────────────────────────────────────────────────────
function renderResult(data, lat, lon) {
  document.getElementById("result-panel").style.display = "block";
  document.getElementById("hint-panel").style.display = "none";

  document.getElementById("res-pincode").textContent = data.pincode;
  document.getElementById("res-letters").textContent = data.grid_letters;

  document.getElementById("meta-location").textContent = data.location_name || "N/A";
  document.getElementById("meta-pincode").textContent = data.pincode;
  document.getElementById("meta-letters").textContent = data.grid_letters;
  document.getElementById("meta-size").textContent = `${data.grid_size_m} m × ${data.grid_size_m} m`;
  document.getElementById("meta-coords").textContent =
    `${lat.toFixed(6)}, ${lon.toFixed(6)}`;

  const warn = document.getElementById("outside-warning");
  warn.style.display = data.found ? "none" : "block";

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
    color: "#00d4a8",
    weight: 3,
    opacity: 1,
    fillColor: "#00d4a8",
    fillOpacity: 0.18,
    dashArray: null,
  }).addTo(gridLayer);

  // Inner dashed border for depth
  L.rectangle([sw, ne], {
    color: "#4f8ef7",
    weight: 1,
    opacity: 0.5,
    fill: false,
    dashArray: "4 4",
  }).addTo(gridLayer);
}

// ── Place pulsing marker ──────────────────────────────────────────────────────
function placeMarker(lat, lon) {
  markerLayer.clearLayers();

  const icon = L.divIcon({
    className: "",
    html: '<div class="click-marker-pulse"></div>',
    iconSize: [14, 14],
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
const searchBtn = document.getElementById("search-btn");

searchBtn.addEventListener("click", (e) => {
  e.preventDefault(); // Prevent any default form behavior
  const query = searchInput.value;
  console.log("Button clicked, searching for:", query);
  performSearch(query);
});

searchInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault(); // Stop the browser from interfering
    performSearch(searchInput.value);
  }
});


function performSearch(query) {
  if (!query.trim()) return;

  suggestionsBox.innerHTML = "";
  setLoading(true);

  const handleResults = (results) => {
    setLoading(false);
    console.log("Search results received:", results);

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
  };

  // Execute search and handle as a Promise (v2.x) OR Callback (v1.x)
  const searchRequest = geocoder.geocode(query, handleResults);
  
  if (searchRequest && typeof searchRequest.then === "function") {
    searchRequest.then(handleResults).catch((err) => {
      console.error("Geocoding error:", err);
      setLoading(false);
    });
  }
}

// ── Copy to clipboard ─────────────────────────────────────────────────────────

const copyBtn = document.getElementById("copy-btn");
const copyLabel = document.getElementById("copy-label");

if (copyBtn) {
  copyBtn.addEventListener("click", async () => {
    // Check if a result has been generated yet
    if (!lastResult || !lastResult.digipin) {
      console.warn("No DigiPIN result available to copy.");
      return;
    }

    const textToCopy = lastResult.digipin;

    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(textToCopy);
        handleCopySuccess();
        return; 
      } catch (err) {
        console.warn("Modern Clipboard API failed, switching to fallback.");
      }
    }

    const textArea = document.createElement("textarea");
    textArea.value = textToCopy;
    
    textArea.style.position = "fixed";
    textArea.style.left = "-9999px";
    textArea.style.top = "0";
    textArea.setAttribute('readonly', ''); // Prevents keyboard from popping up on mobile
    
    document.body.appendChild(textArea);
    
    textArea.focus();
    textArea.select();
    textArea.setSelectionRange(0, 99999); // Extra support for mobile devices

    try {
      const successful = document.execCommand('copy');
      if (successful) {
        handleCopySuccess();
      } else {
        throw new Error('execCommand returned false');
      }
    } catch (err) {
      console.error('All copy methods failed:', err);
      showError("Copy failed. Please select the text manually.");
    } finally {
      document.body.removeChild(textArea);
    }
  });
}

function handleCopySuccess() {
  if (copyBtn && copyLabel) {
    copyBtn.classList.add("copied");
    copyLabel.textContent = "Copied!";
    setTimeout(resetCopyBtn, 2000);
  }
}

function resetCopyBtn() {
  if (copyBtn && copyLabel) {
    copyBtn.classList.remove("copied");
    copyLabel.textContent = "Copy";
  }
}

// ── Loading state helpers ─────────────────────────────────────────────────────
function setLoading(active) {
  const bar = document.getElementById("loading-bar");
  if (active) bar.classList.add("active");
  else bar.classList.remove("active");
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
