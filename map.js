/* ============================================================
   Adaptive Satellite Grid System — map.js 
   (Standalone Frontend + Turf.js + 4-Tier System)
   ============================================================ */

'use strict';

const INDIA_CENTER = [20.5937, 78.9629];
const INIT_ZOOM = 5;
const MAX_ZOOM = 19;

// 4-Tier System matching your PDF Proposal
const TIERS = {
  zoneA: { label: 'Zone A (Urban)', minFeatures: 30, gridM: 4, color: '#00ff00' },
  zoneB: { label: 'Zone B (Peri-urban)', minFeatures: 15, gridM: 8, color: '#00aaff' },
  zoneC: { label: 'Zone C (Rural)', minFeatures: 3, gridM: 16, color: '#ffd700' },
  zoneD: { label: 'Zone D (Uninhabited)', minFeatures: 0, gridM: 64, color: '#ff5500' },
};

const ESRI_SATELLITE = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

let map = null;
let activeMarker = null;
let activeGrid = null;
let isDemoMode = false;
let isQuerying = false;
let pincodeDatabase = null;

// ── Load GeoJSON ───────────────────────────────────────────────────────────
async function loadPincodeDatabase() {
  try {
    setStatus('Loading PIN Code boundaries...', 'loading');
    const response = await fetch('All_India_pincode_Boundary-cleaned.json');
    pincodeDatabase = await response.json();
    setStatus('Click map or search coordinates', '');
  } catch (error) {
    console.error("Failed to load PIN code database:", error);
    setStatus('Error loading PIN data. Check filename.', '');
  }
}

// ── Point in Polygon Math ──────────────────────────────────────────────────
function getPincodeForLocation(lat, lon) {
  if (!pincodeDatabase) return "000000";
  const pt = turf.point([lon, lat]);
  for (let feature of pincodeDatabase.features) {
    if (feature.geometry && turf.booleanPointInPolygon(pt, feature)) {
      return feature.properties.Pincode || "XXXXXX";
    }
  }
  return "000000"; // Outside India
}

// ── Grid & Math Helpers ────────────────────────────────────────────────────
function getGridDegrees(meters, lat) {
  const LAT_DEG_PER_M = 1 / 111320;
  const LON_DEG_PER_M = 1 / (111320 * Math.cos((lat * Math.PI) / 180));
  return { dLat: meters * LAT_DEG_PER_M, dLon: meters * LON_DEG_PER_M };
}

function classifyTier(featureCount) {
  if (featureCount >= TIERS.zoneA.minFeatures) return 'zoneA';
  if (featureCount >= TIERS.zoneB.minFeatures) return 'zoneB';
  if (featureCount >= TIERS.zoneC.minFeatures) return 'zoneC';
  return 'zoneD';
}

function fmtCoord(v) { return v.toFixed(5); }

function mortonInterleave(x, y) {
  let res = 0;
  for (let i = 0; i < 16; i++) {
    res |= ((x & (1 << i)) << i) | ((y & (1 << i)) << (i + 1));
  }
  return res >>> 0;
}

function toBase26(index) {
  const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  let result = "";
  let tempIndex = index % 456976;
  for (let i = 0; i < 4; i++) {
    result = letters[tempIndex % 26] + result;
    tempIndex = Math.floor(tempIndex / 26);
  }
  return result;
}

// ── Aggressive Overpass API ────────────────────────────────────────────────
async function fetchFeatureCount(lat, lon) {
  // Checks buildings, roads, residential areas, and amenities
  const query = `[out:json][timeout:5];(
    nwr["building"](around:450,${lat},${lon});
    nwr["highway"](around:450,${lat},${lon});
    nwr["landuse"="residential"](around:450,${lat},${lon});
    nwr["amenity"](around:450,${lat},${lon});
  );out count;`;

  const url = `https://overpass-api.de/api/interpreter?data=${encodeURIComponent(query)}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 7000);

  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (data && data.elements && data.elements.length > 0) {
      return parseInt(data.elements[0].tags.total || data.elements[0].tags.ways || '0', 10);
    }
    return 0;
  } finally {
    clearTimeout(timeoutId);
  }
}

// ── Drawing & UI ───────────────────────────────────────────────────────────
function drawGridCell(lat, lon, gridM, color) {
  if (activeGrid) { map.removeLayer(activeGrid); activeGrid = null; }

  const { dLat, dLon } = getGridDegrees(gridM, lat);

  const swLat = Math.floor(lat / dLat) * dLat;
  const swLon = Math.floor(lon / dLon) * dLon;
  const neLat = swLat + dLat;
  const neLon = swLon + dLon;

  activeGrid = L.rectangle([[swLat, swLon], [neLat, neLon]], {
    color, weight: 2, dashArray: '6 4', fillColor: color, fillOpacity: 0.3
  }).addTo(map);

  map.flyToBounds(activeGrid.getBounds(), { padding: [80, 80], maxZoom: MAX_ZOOM, duration: 1.2 });

  // Calculate local coordinates and Base-26 code
  const localX = Math.floor((swLon % 0.1) / dLon);
  const localY = Math.floor((swLat % 0.1) / dLat);
  const mIndex = mortonInterleave(Math.abs(localX), Math.abs(localY));

  return toBase26(mIndex);
}

function placeMarker(lat, lon) {
  if (activeMarker) { map.removeLayer(activeMarker); activeMarker = null; }
  const icon = L.divIcon({ className: '', html: '<div class="pulse-marker"></div>', iconSize: [14, 14], iconAnchor: [7, 7] });
  activeMarker = L.marker([lat, lon], { icon }).addTo(map);
}

function setStatus(msg, klass = '') {
  const el = document.getElementById('status-bar');
  el.textContent = msg;
  el.className = klass;
}

function updatePanel({ lat, lon, featureCount, tierKey, fullDigiPin }) {
  const tier = TIERS[tierKey];

  document.getElementById('coord-value').textContent = `${fmtCoord(lat)}, ${fmtCoord(lon)}`;
  document.getElementById('buildings-value').textContent = featureCount;
  document.getElementById('grid-value').textContent = `${tier.gridM}m × ${tier.gridM}m`;
  document.getElementById('base26-value').textContent = fullDigiPin;

  const badge = document.getElementById('tier-badge');
  badge.className = `tier-badge ${tierKey}`;
  badge.style.color = tier.color;
  badge.style.borderColor = tier.color;
  badge.innerHTML = `<span class="tier-dot" style="background:${tier.color}"></span>${tier.label}`;

  setStatus(`Grid computed · ${tier.gridM}m resolution`);
}

// ── Main Controller ────────────────────────────────────────────────────────
async function processCoordinates(lat, lon) {
  if (isQuerying) return;
  isQuerying = true;
  setStatus('Scanning area infrastructure…', 'loading');

  placeMarker(lat, lon);

  document.getElementById('coord-value').textContent = `${fmtCoord(lat)}, ${fmtCoord(lon)}`;
  document.getElementById('buildings-value').textContent = '—';
  document.getElementById('grid-value').textContent = '—';
  document.getElementById('base26-value').textContent = '—';
  document.getElementById('tier-badge').innerHTML = '—';
  document.getElementById('tier-badge').className = 'tier-badge';

  let featureCount = 0;

  try {
    if (isDemoMode) {
      await new Promise(r => setTimeout(r, 800));
      featureCount = Math.floor(Math.random() * 60);
    } else {
      featureCount = await fetchFeatureCount(lat, lon);
    }
  } catch (err) {
    console.warn('Overpass query failed:', err.message);
    setStatus('API timeout — fallback to Zone D', '');
    featureCount = 0;
  }

  const tierKey = classifyTier(featureCount);
  const color = TIERS[tierKey].color;

  // 1. Draw Grid and Get 4-Letter Code
  const base26Code = drawGridCell(lat, lon, TIERS[tierKey].gridM, color);

  // 2. Get PIN Code from GeoJSON
  const localPin = getPincodeForLocation(lat, lon);

  // 3. Combine to create "474011 - BCDE"
  const fullDigiPin = `${localPin} - ${base26Code}`;

  updatePanel({ lat, lon, featureCount, tierKey, fullDigiPin });

  isQuerying = false;
}

// ── Search & Init ──────────────────────────────────────────────────────────
document.getElementById('search-btn')?.addEventListener('click', () => {
  const lat = parseFloat(document.getElementById('lat-input').value);
  const lon = parseFloat(document.getElementById('lon-input').value);
  if (!isNaN(lat) && !isNaN(lon)) {
    processCoordinates(lat, lon);
  } else {
    alert("Please enter valid numeric coordinates.");
  }
});

function initDemoToggle() {
  const toggle = document.getElementById('demo-toggle');
  toggle.addEventListener('change', () => {
    isDemoMode = toggle.checked;
    setStatus(isDemoMode ? '⚡ Demo Mode active — random counts' : 'Click the map to begin');
  });
}

function initMap() {
  map = L.map('map', {
    center: INDIA_CENTER, zoom: INIT_ZOOM, zoomControl: false, attributionControl: false,
  });

  L.tileLayer(ESRI_SATELLITE, { maxZoom: MAX_ZOOM, attribution: 'Tiles © Esri' }).addTo(map);
  L.control.zoom({ position: 'bottomleft' }).addTo(map);
  L.control.attribution({ position: 'bottomleft', prefix: false })
    .addAttribution('Map © Esri | OSM © OpenStreetMap')
    .addTo(map);

  map.on('click', (e) => processCoordinates(e.latlng.lat, e.latlng.lng));
}

window.addEventListener('DOMContentLoaded', () => {
  initMap();
  initDemoToggle();
  // Ensure the geojson is loaded in the background
  loadPincodeDatabase();
});