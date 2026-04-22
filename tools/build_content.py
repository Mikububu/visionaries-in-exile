"""Build the unified content model the webapp will consume.

Inputs:
  - <rebuild>/chunks/<SIDE>/<SCENE>/chunks/*.bin,*.json   (ProjectorRays dump)
  - <rebuild>/bitd-out/<SIDE>/<SCENE>/manifest.json       (BITD decoder output)
  - <rebuild>/nav-<side>.json                              (Lingo nav graph)

Output:
  <rebuild>/content/content.json   -- a single JSON the webapp hydrates from.

Schema:
  {
    "scenes": {
      "CORBUS": {
         "side": "VIE",
         "labels": { "wohn": 10, "maler": 14, ... },      # frame name -> frame#
         "backdrop": "CORBUS/BITD-139_640x480.png",       # best guess for the main image
         "images": [ {"png":"CORBUS/BITD-139_640x480.png", "w":640, "h":480, "raw":307200}, ... ],
         "rollovers": [ {"sprite":16, "target":"urban"}, ... ],
         "clicks":    [ {"target":"...", "script":"..."}, ... ],
         "frame_nav": [ "ende", "menu", ...],
      },
      ...
    }
  }

Notes on guesses that will tighten later with VWSC:
  - "backdrop" is currently the largest 640x480 PNG (or largest PNG if none is full-screen).
  - Sprite numbers in rollovers aren't yet mapped to pixel positions (needs VWSC).
"""
from __future__ import annotations
import json
import struct
import sys
from pathlib import Path


def parse_vwlb(blob: bytes) -> dict[str, int]:
    """Decode a VWLB chunk (frame labels) into {label_name: frame_number}."""
    if len(blob) < 4:
        return {}
    # Offset-pairs table: each pair is (frame_number, string_offset).
    # ProjectorRays writes VWLB in big-endian u16.
    try:
        count = struct.unpack_from(">H", blob, 0)[0]
    except struct.error:
        return {}
    # Some files prepend a second count; skip it if the first pair of u16s at offset 4
    # looks like a valid (frame, offset) entry.
    offsets_start = 4
    table = []
    off = offsets_start
    # Walk the table until we hit the termination where offset_next <= offset_cur
    # (signals end of label block - last entry).
    last_offset = -1
    for _ in range(count + 2):
        if off + 4 > len(blob):
            break
        frame, str_off = struct.unpack_from(">HH", blob, off)
        table.append((frame, str_off))
        off += 4
        if str_off < last_offset and last_offset >= 0:
            break
        last_offset = str_off

    if not table:
        return {}

    # Strings area begins right after the offsets table.
    strings_start = off
    result: dict[str, int] = {}
    # Each label's string span is [current.str_off, next.str_off).
    for i in range(len(table) - 1):
        frame, start = table[i]
        _, end = table[i + 1]
        if start >= end or strings_start + end > len(blob):
            continue
        name = blob[strings_start + start: strings_start + end].decode("latin-1", errors="replace").strip("\x00")
        if name:
            result[name] = frame
    return result


def scene_labels(chunk_dir: Path) -> dict[str, int]:
    labels: dict[str, int] = {}
    for vp in chunk_dir.glob("VWLB-*.bin"):
        labels.update(parse_vwlb(vp.read_bytes()))
    return labels


def scene_images(bitd_dir: Path) -> list[dict]:
    manifest = bitd_dir / "manifest.json"
    if not manifest.is_file():
        return []
    return json.loads(manifest.read_text())


def pick_backdrop(images: list[dict]) -> str | None:
    """Heuristic: prefer the largest 640x480 image; else the largest overall."""
    if not images:
        return None
    fullscreen = [i for i in images if i.get("w") == 640 and i.get("h") == 480]
    pool = fullscreen if fullscreen else images
    best = max(pool, key=lambda i: i.get("raw_bytes", 0))
    return best.get("png")


def scene_name_from_path(path: Path) -> str:
    # ProjectorRays creates folders named like "CORBUS" (the source .DIR name without extension).
    return path.name


def build(root: Path) -> dict:
    scenes: dict[str, dict] = {}

    for side in ("VIE", "AIE"):
        chunk_root = root / "chunks" / side
        bitd_root = root / "bitd-out" / side
        if not chunk_root.is_dir():
            continue

        nav = json.loads((root / f"nav-{side.lower()}.json").read_text())
        side_nav_scenes = nav.get("scenes", {})

        for scene_dir in sorted(chunk_root.iterdir()):
            if not scene_dir.is_dir():
                continue
            chunks_sub = scene_dir / "chunks"
            if not chunks_sub.is_dir():
                continue
            name = scene_name_from_path(scene_dir)

            labels = scene_labels(chunks_sub)
            images = scene_images(bitd_root / name)
            backdrop = pick_backdrop(images)

            nav_scene = side_nav_scenes.get(name) or side_nav_scenes.get(name.upper()) or {}
            rollovers: list[dict] = []
            clicks: list[dict] = []
            frame_nav: set[str] = set()
            for b in nav_scene.get("behaviors", []) + nav_scene.get("cast_scripts", []) + nav_scene.get("movie_scripts", []):
                for r in b.get("rollovers", []):
                    rollovers.append(r)
                for c in b.get("clicks", []):
                    clicks.append({"target": c.get("target"), "script": b.get("script")})
                for t in b.get("frame_nav", []):
                    frame_nav.add(t)

            # Dedupe rollovers by (sprite, target)
            seen = set()
            unique_rollovers = []
            for r in rollovers:
                key = (r.get("sprite"), r.get("target"))
                if key in seen:
                    continue
                seen.add(key)
                unique_rollovers.append(r)

            scenes[f"{side}/{name}"] = {
                "side": side,
                "labels": labels,
                "backdrop": backdrop,
                "images": [
                    {
                        "png": i["png"],
                        "w": i.get("w"),
                        "h": i.get("h"),
                        "raw": i.get("raw_bytes"),
                    }
                    for i in images
                ],
                "rollovers": unique_rollovers,
                "clicks": clicks,
                "frame_nav": sorted(frame_nav),
            }

    return {"scenes": scenes}


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    out = root / "content" / "content.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = build(root)
    scenes = data["scenes"]

    by_side = {"VIE": 0, "AIE": 0}
    w_labels = 0
    w_backdrop = 0
    total_images = 0
    for s in scenes.values():
        by_side[s["side"]] = by_side.get(s["side"], 0) + 1
        if s["labels"]:
            w_labels += 1
        if s["backdrop"]:
            w_backdrop += 1
        total_images += len(s["images"])

    print(f"scenes={len(scenes)}  by_side={by_side}", file=sys.stderr)
    print(f"  with labels={w_labels}  with backdrop={w_backdrop}  total images={total_images}", file=sys.stderr)

    out.write_text(json.dumps(data, ensure_ascii=False))
    print(f"wrote {out} ({out.stat().st_size/1024:.1f} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
