"""Combine VWSC score + CAS_ cast list + CASt metadata + nav graph into a single
runtime model the browser consumes.

For each scene we produce:
  {
    "frames": { "1": [ {ch, castBitmap, castName, x, y, w, h, ink}, ... ] },
    "castTable": { "26": {"name": "kiesler", "bitmap": "BITD-157_..."} , ... },
    "rolloverMap": { "16": "urban", "17": "auge", ... },  # from Lingo
    "clickMap":    { ... },
    "sounds":      [ {file, trigger, script, mp3}, ... ],
    "labels":      { "haupt": 1, "fade": 7, ... },
    "backdrop":    "BITD-344_640x480.png"
  }

Director castMember IDs are 1-indexed and translate to mmap section IDs via
the CAS_ chunk. We parse CAS_ + CASt JSON sidecars to build castTable.
"""
from __future__ import annotations
import json
import struct
import sys
from pathlib import Path


def parse_cas(blob: bytes) -> list[int]:
    """CAS_ chunk is a flat array of big-endian u32s: cast-index N -> section ID."""
    out = []
    for i in range(0, len(blob), 4):
        if i + 4 > len(blob):
            break
        out.append(struct.unpack(">I", blob[i:i + 4])[0])
    return out


def scene_cast_table(chunk_dir: Path, bitd_manifest: list[dict]) -> dict[int, dict]:
    """Return { castMemberId : {name, bitmap_png_filename, section} } for all
    cast members with parseable metadata."""
    # Parse CAS_: maps castMemberIdx (1..N) to mmap section id
    cas_files = list(chunk_dir.glob("CAS_-*.bin"))
    if not cas_files:
        return {}
    section_by_idx = parse_cas(cas_files[0].read_bytes())

    # Build section -> filename map from BITD manifest
    bitd_section_to_png: dict[int, dict] = {}
    for item in bitd_manifest:
        try:
            sec = int(item["bitd"].replace("BITD-", "").replace(".bin", ""))
        except Exception:
            continue
        bitd_section_to_png[sec] = item

    out: dict[int, dict] = {}
    for idx, sec in enumerate(section_by_idx):
        entry: dict = {"section": sec}
        # Try to pull name + type from CASt JSON
        cast_json = chunk_dir / f"CASt-{sec}.json"
        if cast_json.exists():
            try:
                cj = json.loads(cast_json.read_text())
                entry["name"] = cj.get("info", {}).get("name", "").strip()
                entry["type"] = cj.get("type", 0)
            except Exception:
                pass
        # Try to find a nearby BITD. Cast member's BITD is typically section+2
        # (CASt then BITD follow one another in mmap). Check sec, sec+1, sec+2.
        for probe in (sec, sec + 1, sec + 2, sec - 1, sec + 3):
            if probe in bitd_section_to_png:
                entry["bitmap"] = bitd_section_to_png[probe]["png"]
                entry["w"] = bitd_section_to_png[probe].get("w")
                entry["h"] = bitd_section_to_png[probe].get("h")
                break
        # castMember is 1-indexed in Director (CAS_[0] = castMember 1)
        out[idx + 1] = entry
    return out


def build_scene_runtime(
    scene: str,
    side: str,
    chunk_dir: Path,
    bitd_dir: Path,
    score: dict,
    nav_scene: dict,
    audio_entries: list[dict],
    content_scene: dict,
) -> dict:
    # BITD manifest
    manifest_path = bitd_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else []

    cast_table = scene_cast_table(chunk_dir, manifest)

    # Rollover + click maps from Lingo
    rollovers: dict[str, str] = {}
    clicks: list[dict] = []
    frame_nav: list[str] = []
    for b in nav_scene.get("behaviors", []) + nav_scene.get("cast_scripts", []) + nav_scene.get("movie_scripts", []):
        for r in b.get("rollovers", []):
            rollovers[str(r["sprite"])] = r["target"]
        for c in b.get("clicks", []):
            if c.get("target"):
                clicks.append({"target": c["target"], "script": b.get("script")})
        for t in b.get("frame_nav", []):
            frame_nav.append(t)

    # Find the SINGLE best frame to represent the scene's rollover layout:
    # the one that maximises coverage of this scene's declared rollover channels.
    rollover_channels = {int(k) for k in rollovers.keys()}
    best_frame: str | None = None
    best_coverage = -1
    best_sprite_count = 0
    for fk, sprites in score.get("frames", {}).items():
        chans = {s["channel"] for s in sprites}
        cov = len(chans & rollover_channels)
        if cov > best_coverage or (cov == best_coverage and len(sprites) > best_sprite_count):
            best_coverage = cov
            best_sprite_count = len(sprites)
            best_frame = fk

    frames_out: dict[str, list] = {}
    if best_frame is not None:
        enriched = []
        for s in score["frames"][best_frame]:
            # Drop zero-sized channels entirely — saves bytes.
            if s["w"] <= 0 or s["h"] <= 0:
                continue
            cm = s["castMember"]
            c = cast_table.get(cm, {})
            enriched.append({
                "ch": s["channel"],
                "cm": cm,
                "castName": c.get("name", ""),
                "bitmap": c.get("bitmap"),
                "x": s["x"],
                "y": s["y"],
                "w": s["w"],
                "h": s["h"],
                "ink": s["ink"],
            })
        if enriched:
            frames_out[best_frame] = enriched

    # Only ship the slice of castTable actually referenced on the kept frame.
    refd_casts = {s["cm"] for sprites in frames_out.values() for s in sprites}
    slim_cast_table = {cm: cast_table[cm] for cm in refd_casts if cm in cast_table}

    return {
        "side": side,
        "backdrop": content_scene.get("backdrop"),
        "labels": content_scene.get("labels", {}),
        "rolloverMap": rollovers,
        "clicks": clicks,
        "frame_nav": frame_nav,
        "sounds": audio_entries,
        "frames": frames_out,
        "castTable": slim_cast_table,
    }


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

    score_all = json.loads((root / "content" / "score.json").read_text())
    audio_all = json.loads((root / "content" / "audio.json").read_text())
    content_all = json.loads((root / "content" / "content.json").read_text())["scenes"]
    navs = {
        "VIE": json.loads((root / "nav-vie.json").read_text())["scenes"],
        "AIE": json.loads((root / "nav-aie.json").read_text())["scenes"],
    }

    runtime: dict[str, dict] = {}
    emitted = 0
    for key, score in score_all.items():
        side, scene = key.split("/", 1)
        chunk_dir = root / "chunks" / side / scene / "chunks"
        bitd_dir = root / "bitd-out" / side / scene
        if not chunk_dir.is_dir() or not bitd_dir.is_dir():
            continue
        nav_scene = navs.get(side, {}).get(scene, {})
        audio_entries = audio_all.get(side, {}).get(scene, [])
        content_scene = content_all.get(key, {})
        try:
            rt = build_scene_runtime(scene, side, chunk_dir, bitd_dir, score, nav_scene, audio_entries, content_scene)
        except Exception as e:
            print(f"FAIL {key}: {e}", file=sys.stderr)
            continue
        runtime[key] = rt
        emitted += 1

    out = root / "content" / "runtime.json"
    out.write_text(json.dumps(runtime, ensure_ascii=False, separators=(",", ":")))
    print(f"scenes emitted: {emitted}", file=sys.stderr)
    print(f"wrote {out} ({out.stat().st_size/1024/1024:.1f} MB)", file=sys.stderr)


if __name__ == "__main__":
    main()
