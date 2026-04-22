"""Decode Director BITD chunks to PNG.

Approach:
 1. RLE-decode the BITD byte stream using ScummVM's Director algorithm.
 2. Extract dimensions + bit depth by:
     a. Trying to parse the paired CASt chunk's specific-data block (primary).
     b. If that fails or yields a nonsensical rectangle, factor the decoded size
        against common Director stage widths (640, 512, 480, 320, 256, 160) and
        pick the one whose implied height is plausible.
 3. Apply an 8-bit Mac system palette (default) unless a CLUT chunk is linked.
 4. Write out as PNG using Pillow.

Invariants we rely on (documented in ScummVM 'engines/director/images.cpp'):
  - RLE byte stream: high bit set -> repeat next byte N times,
    high bit clear -> emit N+1 literal bytes.
  - Bitmaps in BITD are stored row-major with pitch padding to even width.

Known weak spots (will iterate):
  - CASt specific-data parser uses heuristics for D11 layout.
  - Only 1/4/8 bpp tested (Visionaries in Exile is 8bpp era).
  - Palette IDs that reference cast-member CLUTs are resolved with a
    system-8bit Mac palette fallback.
"""
from __future__ import annotations
import json
import struct
import sys
from pathlib import Path
from typing import Iterable

from PIL import Image


# --- Mac OS 8-bit system palette (256 entries) ---
# Assembled from Apple's canonical 8-bit system palette (the one Director used).
# Layout: 6x6x6 web-safe-ish color cube + 40 gray/primary fillers that match the
# actual Mac System Palette ordering. Index 0 = white, 255 = black is the Mac
# convention.

def build_mac_palette() -> list[tuple[int, int, int]]:
    """Produce a 256-entry palette matching Mac System 8-bit ordering."""
    levels = [0xFF, 0xCC, 0x99, 0x66, 0x33, 0x00]
    cube = [(r, g, b) for r in levels for g in levels for b in levels]

    # The remaining 40 entries = pure grayscale ramps + primaries. The exact
    # Apple order is: ramps of red, green, blue, then gray, excluding the pure
    # endpoints already in the cube.
    ramp_levels = [0xEE, 0xDD, 0xBB, 0xAA, 0x88, 0x77, 0x55, 0x44, 0x22, 0x11]
    ramps: list[tuple[int, int, int]] = []
    for v in ramp_levels:
        ramps.append((v, 0, 0))
    for v in ramp_levels:
        ramps.append((0, v, 0))
    for v in ramp_levels:
        ramps.append((0, 0, v))
    for v in ramp_levels:
        ramps.append((v, v, v))

    palette = cube + ramps
    # Mac ordering uses index 0 = white, index 255 = black; cube has white at index 0
    # (because r=g=b=0xFF) and black at index 215 (all 0x00). Append cube to 216,
    # ramps to bring to 256. Total should be 216 + 40 = 256.
    assert len(palette) == 256, len(palette)
    return palette


MAC_PALETTE = build_mac_palette()


def load_clut(path: Path) -> list[tuple[int, int, int]]:
    """Load a Director CLUT chunk (256 entries, 6 bytes each, big-endian u16 RGB)."""
    data = path.read_bytes()
    pal: list[tuple[int, int, int]] = []
    for i in range(0, min(len(data), 256 * 6), 6):
        r = data[i]       # take high byte of 16-bit value
        g = data[i + 2]
        b = data[i + 4]
        pal.append((r, g, b))
    while len(pal) < 256:
        pal.append((0, 0, 0))
    return pal


def rle_decode(data: bytes) -> bytes:
    """ScummVM-compatible BITD RLE decode."""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        i += 1
        if b & 0x80:
            run = ((b ^ 0xFF) & 0xFF) + 2
            if i >= n:
                break
            v = data[i]
            i += 1
            out.extend(bytes([v]) * run)
        else:
            run = b + 1
            chunk = data[i:i + run]
            i += run
            out.extend(chunk)
    return bytes(out)


CAST_T_BITMAP = 1


def parse_key_table(blob: bytes) -> list[tuple[int, str, int]]:
    """Parse a KEY* chunk binary. Returns list of (sectionA, fourCC, sectionB).

    The KEY* table in Director binds each cast member's CASt section to its
    associated data sections (BITD, Thum, STXT, snd, CLUT, etc.). Layout:

        u16 entrySize      (little-endian, always 12)
        u16 headerSize     (little-endian, 12 or 20)
        u32 maxEntries     (LE)
        u32 usedEntries    (LE)
        ...entries of 12 bytes each...

    Each entry: [u32 LE sectionA, char[4] fourCC_reversed, u32 LE sectionB]

    In practice sectionA is the DATA section and sectionB is the CASt section
    for BITD/Thum entries; we return them as-written and let callers search
    both directions.
    """
    if len(blob) < 16:
        return []
    entry_size = struct.unpack_from("<H", blob, 0)[0] or 12
    header_size = struct.unpack_from("<H", blob, 2)[0] or 12
    used = struct.unpack_from("<I", blob, 8)[0]
    # Different minor versions pad the header to 16 or 20 bytes. Heuristically
    # pick whichever gives in-range entry counts.
    entries = []
    for start in (header_size, 16, 20):
        test = []
        off = start
        for _ in range(used):
            if off + entry_size > len(blob):
                break
            a = struct.unpack_from("<I", blob, off)[0]
            fourcc_raw = blob[off + 4: off + 8]
            # 4CCs are stored reversed in RIFX
            fourcc = fourcc_raw[::-1].decode("ascii", errors="replace")
            b = struct.unpack_from("<I", blob, off + 8)[0]
            test.append((a, fourcc, b))
            off += entry_size
        if len(test) >= used * 0.8 and all(fc.isalnum() or fc.strip() for _, fc, _ in test[:5]):
            entries = test
            break
    return entries


def find_bitd_dims(bitd_section: int, key_entries: list, cast_files: dict[int, Path]) -> tuple[int, int, int] | None:
    """Given a BITD section ID, look up the matching CASt via KEY_ and parse its
    specific-data for dimensions. Try both linkage directions since the KEY*
    layout (sectionA vs. sectionB) varies by minor version.
    """
    for a, fourcc, b in key_entries:
        if fourcc != "BITD":
            continue
        if a == bitd_section and b in cast_files:
            _, _, _, _, spec = parse_cast_header(cast_files[b].read_bytes())
            dims = guess_bitmap_dims_from_cast(spec)
            if dims:
                return dims
        if b == bitd_section and a in cast_files:
            _, _, _, _, spec = parse_cast_header(cast_files[a].read_bytes())
            dims = guess_bitmap_dims_from_cast(spec)
            if dims:
                return dims
    return None


def parse_cast_header(blob: bytes) -> tuple[int, int, int, bytes, bytes]:
    """Read [type, infoLen, specificLen, info, specific] from a CASt chunk binary."""
    if len(blob) < 12:
        raise ValueError("CASt too short")
    t, info_len, spec_len = struct.unpack_from(">III", blob, 0)
    info = blob[12:12 + info_len]
    specific = blob[12 + info_len:12 + info_len + spec_len]
    return t, info_len, spec_len, info, specific


def guess_bitmap_dims_from_cast(specific: bytes) -> tuple[int, int, int] | None:
    """Best-effort parse of 28-byte specific data for a D11 bitmap CASt.

    The layout varies across minor versions. We try several candidate offsets
    for the bounding rect and pick the first that yields a plausible (w, h).
    The bitDepth byte sits near the end; we search for a value in {1,2,4,8,16,32}
    in the tail bytes.
    """
    if len(specific) < 20:
        return None
    bpp = 8
    # Search for a plausible bpp in the trailing bytes.
    for off in (25, 24, 23, 26):
        if off < len(specific) and specific[off] in (1, 2, 4, 8, 16, 32):
            bpp = specific[off]
            break
    # Try candidate offsets for the bounding rect (top, left, bottom, right).
    for off in (0, 2, 4, 6):
        if off + 8 > len(specific):
            continue
        try:
            top, left, bottom, right = struct.unpack_from(">HHHH", specific, off)
        except struct.error:
            continue
        w = right - left
        h = bottom - top
        if 4 <= w <= 2048 and 4 <= h <= 2048:
            return w, h, bpp
    return None


COMMON_WIDTHS = [640, 480, 512, 320, 256, 200, 160, 128, 100, 64, 48, 32, 24, 16]


def guess_dims_by_factoring(decoded_size: int, bpp: int = 8) -> tuple[int, int]:
    """Fallback when CASt parse fails.

    Strategy: find all exact divisor pairs (w, h) with sane aspect/size and
    pick the width closest to a typical Director stage (640 / 480 / 512 / 320).
    """
    bytes_per_px = max(1, bpp // 8)
    cap = decoded_size // bytes_per_px
    if cap <= 0:
        return 640, 1

    # Collect all (w, h) pairs where w * h == cap and both are in sane range.
    pairs: list[tuple[int, int]] = []
    w = 16
    while w <= 1600:
        if cap % w == 0:
            h = cap // w
            if 8 <= h <= 2048:
                pairs.append((w, h))
        w += 1

    # Prefer: widest factor in the stage-friendly band [160, 720]; then fall
    # back to anything reasonable. This handles both 640x480 full screens and
    # non-standard cropped bitmaps like 598x444.
    band = [p for p in pairs if 160 <= p[0] <= 640 and 40 <= p[1] <= 640]
    if band:
        band.sort(key=lambda p: (-p[0], p[1]))  # widest first
        return band[0]
    if pairs:
        pairs.sort(key=lambda p: (-p[0], p[1]))
        return pairs[0]

    # No exact factoring: fall back to 640 with truncation.
    return 640, max(1, decoded_size // 640)


def render_palette_indexed(pixels: bytes, w: int, h: int, palette: list[tuple[int, int, int]]) -> Image.Image:
    """Build an RGB image from 8-bit palette indices."""
    pitch = w + (w & 1)  # even stride
    rows = []
    for y in range(h):
        start = y * pitch
        row = pixels[start:start + w]
        if len(row) < w:
            row = row + bytes([0] * (w - len(row)))
        rows.append(row)
    flat = b"".join(rows)

    img = Image.frombytes("P", (w, h), flat)
    flat_pal = []
    for r, g, b in palette:
        flat_pal.extend([r, g, b])
    img.putpalette(flat_pal)
    return img.convert("RGB")


def render_grayscale(pixels: bytes, w: int, h: int) -> Image.Image:
    pitch = w + (w & 1)
    rows = []
    for y in range(h):
        start = y * pitch
        row = pixels[start:start + w]
        if len(row) < w:
            row = row + bytes([0] * (w - len(row)))
        rows.append(row)
    flat = b"".join(rows)
    return Image.frombytes("L", (w, h), flat)


def decode_bitd_file(path: Path, dims: tuple[int, int, int] | None = None) -> tuple[bytes, int, int, int]:
    """Decode a single BITD chunk. Returns (raw_pixels, w, h, bpp)."""
    raw = path.read_bytes()
    pixels = rle_decode(raw)
    # If dims known, trust them
    if dims:
        w, h, bpp = dims
    else:
        w, h = guess_dims_by_factoring(len(pixels), bpp=8)
        bpp = 8
    return pixels, w, h, bpp


def main():
    if len(sys.argv) < 3:
        print("Usage: decode_bitd.py <chunks-dir> <out-dir> [--grayscale]", file=sys.stderr)
        sys.exit(2)
    chunks_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    grayscale = "--grayscale" in sys.argv
    out_dir.mkdir(parents=True, exist_ok=True)

    bitd_files = sorted(chunks_dir.glob("BITD-*.bin"))
    cast_files = {int(p.stem.split("-")[1]): p for p in chunks_dir.glob("CASt-*.bin")}

    clut_files = sorted(chunks_dir.glob("CLUT-*.bin"))
    palette = load_clut(clut_files[0]) if clut_files else MAC_PALETTE

    # Parse KEY_ table once so we can link BITD sections to CASt sections.
    key_entries: list = []
    for kp in chunks_dir.glob("KEY_-*.bin"):
        key_entries.extend(parse_key_table(kp.read_bytes()))

    ok = 0
    fail = 0
    manifest = []
    for bp in bitd_files:
        bitd_id = int(bp.stem.split("-")[1])
        dims = find_bitd_dims(bitd_id, key_entries, cast_files)
        try:
            pixels, w, h, bpp = decode_bitd_file(bp, dims=dims)
            if grayscale or bpp != 8:
                img = render_grayscale(pixels, w, h)
            else:
                img = render_palette_indexed(pixels, w, h, palette)
            out = out_dir / f"{bp.stem}_{w}x{h}.png"
            img.save(out)
            manifest.append({"bitd": bp.name, "png": out.name, "w": w, "h": h, "bpp": bpp, "raw_bytes": len(pixels)})
            ok += 1
        except Exception as e:
            print(f"FAIL {bp.name}: {e}", file=sys.stderr)
            fail += 1

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"decoded {ok} / {ok+fail}  -> {out_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
