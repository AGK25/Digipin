import json
import math
from typing import Tuple

ORIGINS_JSON = r"C:\Users\GARV\OneDrive\Desktop\gwalior_origins.json"
GRID_SIZE_M = 4

with open(ORIGINS_JSON, "r", encoding="utf-8") as f:
    PIN_ORIGINS = json.load(f)


def lonlat_to_meters_delta(lon: float, lat: float, origin_lon: float, origin_lat: float) -> Tuple[float, float]:
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
        raise ValueError("x or y too large (> 2^32-1). Reduce resolution or add bigger support.")

    def split_by_1bits_32(n: int) -> int:
        n &= 0xFFFFFFFF
        n = (n | (n << 16)) & 0x0000FFFF0000FFFF
        n = (n | (n << 8))  & 0x00FF00FF00FF00FF
        n = (n | (n << 4))  & 0x0F0F0F0F0F0F0F0F
        n = (n | (n << 2))  & 0x3333333333333333
        n = (n | (n << 1))  & 0x5555555555555555
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


def encode_digipin(lat: float, lon: float, pincode: str, grid_size_m: int = GRID_SIZE_M) -> str:
    pincode = str(pincode).strip()
    if pincode not in PIN_ORIGINS:
        raise KeyError(f"Pincode {pincode} not found in origins JSON")

    origin_lon = float(PIN_ORIGINS[pincode]["origin_lon"])
    origin_lat = float(PIN_ORIGINS[pincode]["origin_lat"])

    dx_m, dy_m = lonlat_to_meters_delta(lon, lat, origin_lon, origin_lat)

    x = int(math.floor(dx_m / grid_size_m))
    y = int(math.floor(dy_m / grid_size_m))

    if x < 0 or y < 0:
        raise ValueError(
            f"Point outside origin frame (x={x}, y={y}). "
            f"Either wrong PIN or point outside that PIN polygon."
        )

    morton = morton_interleave_32bit(x, y)

    # Demo folding to fit 4 letters
    code_index = morton % (26**4)

    return f"{pincode}-{to_base26_4letters(code_index)}"


if __name__ == "__main__":
    lat = 26.22325257
    lon = 78.22265625
    pin = "474006"
    print("Your DigiPIN:", encode_digipin(lat, lon, pin))
