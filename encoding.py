"""
encoding.py
-----------
All geo-encoding logic lives here.
Replace the bodies of the four functions below with your own implementations
without touching anything else in the project.
"""

from typing import Tuple
import math

# ── Constants ────────────────────────────────────────────────────────────────
GRID_SIZE_M: int = 4  # metres per grid cell
EARTH_RADIUS_M: float = 6_378_137.0  # WGS-84 semi-major axis


# ── Core functions (swap these out with your real implementations) ─────────


def lonlat_to_meters_delta(
    lon: float, lat: float, origin_lon: float, origin_lat: float
) -> Tuple[float, float]:
    """
    Approx meters delta from (origin_lon, origin_lat) to (lon, lat)
    dx: east (+), dy: north (+)
    """
    meters_per_deg_lat = 111320.0
    # Use origin latitude for lon scaling (more stable)
    lat_rad = math.radians(origin_lat)
    meters_per_deg_lon = 111320.0 * math.cos(lat_rad)

    dx_m = (lon - origin_lon) * meters_per_deg_lon
    dy_m = (lat - origin_lat) * meters_per_deg_lat
    return dx_m, dy_m


def morton_interleave_32bit(x: int, y: int) -> int:
    """Interleave bits of x and y (0..2^32-1) to Morton code (64-bit result)."""
    if x < 0 or y < 0:
        raise ValueError("x and y must be non-negative")

    if x > 0xFFFFFFFF or y > 0xFFFFFFFF:
        raise ValueError(
            "x or y too large (> 2^32-1). Reduce resolution or add bigger support."
        )

    def split_by_1bits_32(n: int) -> int:
        n &= 0xFFFFFFFF
        n = (n | (n << 16)) & 0x0000FFFF0000FFFF
        n = (n | (n << 8)) & 0x00FF00FF00FF00FF
        n = (n | (n << 4)) & 0x0F0F0F0F0F0F0F0F
        n = (n | (n << 2)) & 0x3333333333333333
        n = (n | (n << 1)) & 0x5555555555555555
        return n

    return split_by_1bits_32(x) | (split_by_1bits_32(y) << 1)


def to_base26_4letters(n: int) -> str:
    max_n = 26**4 - 1
    if n < 0 or n > max_n:
        raise ValueError(f"Index out of range: {n}")

    letters = []
    for power in (26**3, 26**2, 26, 1):
        digit = n // power
        n = n % power
        letters.append(chr(ord("A") + digit))
    return "".join(letters)


def encode_digipin(
    lat: float,
    lon: float,
    pincode: str,
    origin_lon: float,
    origin_lat: float,
    grid_size_m: int = GRID_SIZE_M,
) -> str:
    """
    Encode (lat, lon) into a DigiPIN given the pincode's origin corner.

    Parameters
    ----------
    lat, lon        : clicked point
    pincode         : 6-digit string
    origin_lon/lat  : (min_lon, min_lat) of the pincode polygon outer ring
    grid_size_m     : cell side length in metres (default 4)

    Returns
    -------
    str  e.g. "474001-ABCD"

    Raises
    ------
    ValueError  if the point is behind the origin frame (shouldn't happen when
                origin is truly the polygon minimum corner)
    """
    dx_m, dy_m = lonlat_to_meters_delta(lon, lat, origin_lon, origin_lat)

    x = int(math.floor(dx_m / grid_size_m))
    y = int(math.floor(dy_m / grid_size_m))

    if x < 0 or y < 0:
        raise ValueError(
            f"Point outside origin frame (x={x}, y={y}) for pincode {pincode}."
        )

    morton = morton_interleave_32bit(x, y)
    code_index = morton % (26**4)
    return f"{pincode}-{to_base26_4letters(code_index)}"


# ── Grid cell bounding box helper (used by Flask routes) ─────────────────────


def cell_bounds(
    lat: float,
    lon: float,
    origin_lon: float,
    origin_lat: float,
    grid_size_m: int = GRID_SIZE_M,
) -> dict:
    """
    Return the lat/lon bounding box of the 4 m × 4 m grid cell that contains
    (lat, lon), snapped relative to the pincode origin.
    """
    # 1. Calculate how many meters we are from the origin
    dx_m, dy_m = lonlat_to_meters_delta(lon, lat, origin_lon, origin_lat)

    # 2. Find the grid cell index (steps of 4m from origin)
    steps_x = math.floor(dx_m / grid_size_m)
    steps_y = math.floor(dy_m / grid_size_m)

    # 3. Determine the SW corner in meters relative to origin
    sw_dx = steps_x * grid_size_m
    sw_dy = steps_y * grid_size_m

    # 4. Convert meters back to approx Lat/Lon degrees
    lat_deg_per_m = 1.0 / (111320.0)
    lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(origin_lat)))

    sw_lat = origin_lat + (sw_dy * lat_deg_per_m)
    sw_lon = origin_lon + (sw_dx * lon_deg_per_m)

    ne_lat = sw_lat + (grid_size_m * lat_deg_per_m)
    ne_lon = sw_lon + (grid_size_m * lon_deg_per_m)

    return {
        "sw": [sw_lat, sw_lon],
        "ne": [ne_lat, ne_lon],
        "center": [(sw_lat + ne_lat) / 2, (sw_lon + ne_lon) / 2],
    }
