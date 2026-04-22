"""Extract sprite rollover rectangles by mining CASt chunks.

For each scene chunk directory, finds bitmap cast members (type=1) that have a
name matching a rollover target in the scene's Lingo, and decodes their rect
from CASt specific-data. Outputs a JSON map keyed by scene and then by target
name:

    {
      "AIE/AAHAUPT": {
        "hoffmann":  {"top": 94,  "left": 455, "bottom": 309, "right": 591},
        "schindler": {"top": 282, "left": 498, "bottom": 480, "right": 640},
        ...
      }
    }

This is fed into the React app which renders invisible <div>s at these rects,
overlaid on the backdrop PNG at native 640x480 scale. Clicking/hovering them
triggers the same navTo() as the existing pill list, but pixel-accurate.
"""
from __future__ import annotations
import json
import struct
import sys
from pathlib import Path


def parse_cast(blob: bytes, name_from_json: str = "") -> dict | None:
    """Read the CASt chunk. Returns dict with type, name, and rect if bitmap."""
    if len(blob) < 12:
        return None
    cast_type, info_len, spec_len = struct.unpack_from(">III", blob, 0)
    spec = blob[12 + info_len:12 + info_len + spec_len]
    name = name_from_json

    # Bitmap members have type 1 and a specific-data block with the stage rect.
    if cast_type != 1 or spec_len < 10:
        return {"type": cast_type, "name": name, "rect": None}

    # Specific layout for D11 bitmap: first 2 bytes = flags, next 8 = rect u16 BE.
    # The flag byte 0 should have bit 7 set (0x80+) for the newer format.
    if spec[0] < 0x80:
        # Older layout — try offset 0 directly as rect.
        rect_off = 0
    else:
        rect_off = 2
    try:
        top, left, bottom, right = struct.unpack_from(">HHHH", spec, rect_off)
    except struct.error:
        return {"type": cast_type, "name": name, "rect": None}

    if not (0 <= top < bottom <= 2048 and 0 <= left < right <= 2048):
        return {"type": cast_type, "name": name, "rect": None}

    return {
        "type": cast_type,
        "name": name,
        "rect": {"top": top, "left": left, "bottom": bottom, "right": right},
    }


def extract_scene(chunk_dir: Path) -> dict[str, dict]:
    """For each bitmap cast member, pull its name from the ProjectorRays JSON
    sidecar and its rect from the binary. Collect multiple variants of the same
    name into a list so the matcher can pick any.
    """
    out: dict[str, dict] = {}
    for cp in sorted(chunk_dir.glob("CASt-*.bin")):
        json_path = cp.with_suffix(".json")
        name = ""
        if json_path.exists():
            try:
                d = json.loads(json_path.read_text())
                name = str(d.get("info", {}).get("name", "")).strip()
            except Exception:
                pass
        if not name:
            continue
        if name.lower().startswith(("palette ", "jx", " oo", "0o")) or name.lower() == "oo":
            continue
        res = parse_cast(cp.read_bytes(), name_from_json=name)
        if not res or not res.get("rect"):
            continue

        key = name.lower()
        # If this key already exists, prefer the one with the smaller (more
        # specific) rect — the full-stage 640x480 members are usually
        # backdrops or palettes, not hotspots.
        prior = out.get(key)
        area = (res["rect"]["right"] - res["rect"]["left"]) * (res["rect"]["bottom"] - res["rect"]["top"])
        if prior is None or area < (prior["right"] - prior["left"]) * (prior["bottom"] - prior["top"]):
            out[key] = {
                **res["rect"],
                "cast_bin": cp.name,
                "cast_name": name,
            }
    return out


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    chunks_root = root / "chunks"
    nav_vie = json.loads((root / "nav-vie.json").read_text())
    nav_aie = json.loads((root / "nav-aie.json").read_text())
    navs = {"VIE": nav_vie["scenes"], "AIE": nav_aie["scenes"]}

    result: dict[str, dict] = {}
    hits = 0
    total_scenes = 0

    for side in ("VIE", "AIE"):
        side_dir = chunks_root / side
        if not side_dir.is_dir():
            continue
        for scene_dir in sorted(side_dir.iterdir()):
            if not scene_dir.is_dir():
                continue
            inner = scene_dir / "chunks"
            if not inner.is_dir():
                continue
            scene = scene_dir.name
            total_scenes += 1
            rects = extract_scene(inner)
            if not rects:
                continue

            # Filter to only rects whose name matches a rollover target in this scene
            nav_scene = navs.get(side, {}).get(scene) or navs.get(side, {}).get(scene.upper()) or {}
            targets = set()
            for b in nav_scene.get("behaviors", []) + nav_scene.get("cast_scripts", []):
                for r in b.get("rollovers", []):
                    targets.add(r["target"].lower())
                for c in b.get("clicks", []):
                    targets.add(c.get("target", "").lower())

            matched = {n: r for n, r in rects.items() if n in targets}
            if matched:
                key = f"{side}/{scene}"
                result[key] = matched
                hits += len(matched)

    out = root / "content" / "rects.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"scenes scanned: {total_scenes}", file=sys.stderr)
    print(f"scenes with matched rects: {len(result)}", file=sys.stderr)
    print(f"total matched hotspots: {hits}", file=sys.stderr)
    print(f"wrote {out} ({out.stat().st_size/1024:.1f} KB)", file=sys.stderr)

    # Print a sample for AAHAUPT to sanity-check
    sample = result.get("AIE/AAHAUPT") or result.get("VIE/AAHAUPT") or {}
    if sample:
        print(f"\nAAHAUPT rect sample:", file=sys.stderr)
        for name, r in list(sample.items())[:5]:
            w = r["right"] - r["left"]
            h = r["bottom"] - r["top"]
            print(f"  {name:14s}  at ({r['left']:3d},{r['top']:3d})  {w:3d}×{h:3d}", file=sys.stderr)


if __name__ == "__main__":
    main()
