"""Extract audio cues from decompiled Lingo, producing a scene->[audio-file] map.

The original source called audio via:
  puppetSound("filename.aif")          -- set background channel 1
  puppetSound(1, "filename.aif")       -- set channel N
  puppetSound(0)                       -- stop sound
  sound playFile 1, "filename.aif"     -- play file on channel N

We parse every .ls script, collect the referenced filenames, and attribute
them to the scene the script belongs to. Output is merged into content.json
by rebuilding it downstream.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

PUPPET_RE = re.compile(r'puppetSound\s*\(\s*(?:\d+\s*,\s*)?"([^"\\]+)"', re.I)
PLAYFILE_RE = re.compile(r'sound\s+playFile\s+\d+\s*,\s*"([^"\\]+)"', re.I)
SOUND_MEMBER_RE = re.compile(r'sound\s+play\s+member\s*\(\s*"([^"\\]+)"', re.I)


def extract_audio(scripts_root: Path) -> dict[str, list[dict]]:
    """Walk decompiled scene folders, emit {scene: [ {file, trigger, script} ]}."""
    out: dict[str, list[dict]] = defaultdict(list)
    for scene_dir in sorted(scripts_root.iterdir()):
        if not scene_dir.is_dir():
            continue
        shared = scene_dir / "casts" / "Shared"
        if not shared.is_dir():
            continue
        scene = scene_dir.name
        seen: set[tuple[str, str]] = set()
        for ls in sorted(shared.glob("*.ls")):
            text = ls.read_text(errors="replace")
            for m in PUPPET_RE.finditer(text):
                key = ("puppetSound", m.group(1).lower())
                if key in seen:
                    continue
                seen.add(key)
                out[scene].append({
                    "file": m.group(1),
                    "trigger": "puppetSound",
                    "script": ls.stem,
                })
            for m in PLAYFILE_RE.finditer(text):
                key = ("playFile", m.group(1).lower())
                if key in seen:
                    continue
                seen.add(key)
                out[scene].append({
                    "file": m.group(1),
                    "trigger": "playFile",
                    "script": ls.stem,
                })
            for m in SOUND_MEMBER_RE.finditer(text):
                key = ("soundMember", m.group(1).lower())
                if key in seen:
                    continue
                seen.add(key)
                out[scene].append({
                    "file": m.group(1),
                    "trigger": "soundMember",
                    "script": ls.stem,
                })
    return out


def resolve_audio_files(refs: dict[str, list[dict]], media_dir: Path, side: str) -> dict[str, list[dict]]:
    """Attach a resolved mp3 path if one exists for the referenced filename.

    Original filenames are case-insensitive .aif; our transcoded copies live under
    media/aif/{SIDE}_{BASENAME}.mp3.
    """
    index: dict[str, str] = {}
    for mp3 in media_dir.glob(f"{side}_*.mp3"):
        base = mp3.stem[len(side) + 1:].lower()  # drop "VIE_" or "AIE_"
        index[base] = mp3.name

    resolved: dict[str, list[dict]] = {}
    for scene, entries in refs.items():
        new_entries = []
        for e in entries:
            fname = e["file"]
            stem = Path(fname).stem.lower()
            mp3 = index.get(stem)
            new_entries.append({
                **e,
                "mp3": f"/media/aif/{mp3}" if mp3 else None,
                "ref_stem": stem,
            })
        resolved[scene] = new_entries
    return resolved


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    media_dir = root / "media" / "aif"
    total = {}
    by_side = {}
    for side in ("VIE", "AIE"):
        scripts = root / "lingo-out" / side / "input"
        if not scripts.is_dir():
            continue
        refs = extract_audio(scripts)
        resolved = resolve_audio_files(refs, media_dir, side)
        by_side[side] = resolved
        total[side] = sum(1 for _s in resolved.values() for _e in _s)

    out = root / "content" / "audio.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(by_side, ensure_ascii=False, indent=2))

    print(f"scenes with audio: VIE={len(by_side.get('VIE',{}))}  AIE={len(by_side.get('AIE',{}))}", file=sys.stderr)
    print(f"total audio refs:  VIE={total.get('VIE',0)}  AIE={total.get('AIE',0)}", file=sys.stderr)
    resolved_count = sum(
        1
        for side in by_side.values()
        for entries in side.values()
        for e in entries
        if e["mp3"]
    )
    print(f"resolved to mp3:   {resolved_count}", file=sys.stderr)
    print(f"wrote {out} ({out.stat().st_size/1024:.1f} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
