"""Parse decompiled Lingo scripts into a JSON navigation graph.

Input layout (produced by ProjectorRays --dump-scripts):
  <root>/<SCENE>_decompiled.dir       - the unprotected .dir
  <root>/<SCENE>/casts/Shared/*.ls    - one file per script (Behavior / Cast / Movie / etc.)

Output JSON schema:
  {
    "scenes": {
      "AAHAUPT": {
        "behaviors": [
          {
            "script": "BehaviorScript 125",
            "frame_nav": [ "urban", "auge", ... ],          # direct go(...) not guarded by rollover
            "rollovers": [ {"sprite": 16, "target": "urban"}, ... ],
            "clicks":    [ {"sprite": 3, "target": "...details"}, ... ],
            "cursors":   [ {"sprite": 3, "members": ["maus", "raus"]} ],
            "sounds":    [ "puppetSound 2, \"bg_loop\"" ],
            "raw":       "...original lingo text..."
          }, ...
        ],
        "cast_scripts": [
          { "script": "CastScript 17 - behren", "targets": [...], ... }
        ]
      }, ...
    },
    "edges": [ {"from":"AAHAUPT", "to":"urban", "kind":"rollover|click|frame"} , ... ],
    "targets": { "urban": {"refs":[...], "inbound": 12}, ... }
  }
"""
from __future__ import annotations
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROLLOVER_RE  = re.compile(r"rollover\s*\(\s*(\d+)\s*\)", re.I)
# go("target")  or  go(frame, "target") or go(1, "target") or go 1, "target"
GO_STR_RE    = re.compile(r'\bgo\s*(?:\(\s*)?(?:\d+\s*,\s*)?"([^"\\]+)"', re.I)
GO_FRAME_RE  = re.compile(r'\bgo\s*(?:\(\s*)?(?:to\s+)?frame\s+"([^"\\]+)"', re.I)
GO_NUM_RE    = re.compile(r'\bgo\s*\(\s*(\d+)\s*\)', re.I)
MEMBER_RE    = re.compile(r'member\s*\(\s*"([^"\\]+)"', re.I)
SOUND_RE     = re.compile(r'puppetSound[^\n]+', re.I)
CURSOR_RE    = re.compile(r'cursor\s+of\s+sprite\s+(\d+)[^\n]*\[([^\]]+)\]', re.I)


def parse_script(text: str):
    """Extract navigation-relevant facts from one Lingo file.

    Handles the dominant pattern used in VIE/AIE:
        if rollover(N) then
            go("target")
        end if
    by walking line-by-line and carrying the nearest preceding rollover(N) as context
    through its `if ... end if` block.
    """
    rollovers = []
    clicks    = []
    frame_nav = []
    cursors   = []
    sounds    = []

    lines = text.splitlines()
    roll_stack: list[int] = []  # sprite numbers for the enclosing rollover-if blocks
    in_mouseup = False

    for raw in lines:
        line = raw.strip()
        low  = line.lower()
        if not line:
            continue

        # Track `on mouseUp ... end` blocks so go() inside = click edges
        if low.startswith("on mouseup"):
            in_mouseup = True
            continue
        if in_mouseup and low == "end":
            in_mouseup = False
            continue

        # Open a rollover-if block
        m_if = re.match(r"if\s+rollover\s*\(\s*(\d+)\s*\)\s+then", line, re.I)
        if m_if:
            roll_stack.append(int(m_if.group(1)))
            continue
        if low.startswith("end if") or low == "endif":
            if roll_stack:
                roll_stack.pop()
            continue

        # Capture go(...) inside contexts
        for m in GO_STR_RE.finditer(line):
            tgt = m.group(1)
            if roll_stack:
                rollovers.append({"sprite": roll_stack[-1], "target": tgt})
            elif in_mouseup:
                clicks.append({"target": tgt})
            else:
                frame_nav.append(tgt)
        for m in GO_FRAME_RE.finditer(line):
            tgt = m.group(1)
            if roll_stack:
                rollovers.append({"sprite": roll_stack[-1], "target": tgt})
            elif in_mouseup:
                clicks.append({"target": tgt})
            else:
                frame_nav.append(tgt)

        m_cur = CURSOR_RE.search(line)
        if m_cur:
            members = [mm.group(1) for mm in MEMBER_RE.finditer(m_cur.group(2))]
            cursors.append({"sprite": int(m_cur.group(1)), "members": members})
        if SOUND_RE.search(line):
            sounds.append(line)

    return {
        "rollovers": rollovers,
        "clicks": clicks,
        "frame_nav": frame_nav,
        "cursors": cursors,
        "sounds": sounds,
    }


def build(root: Path) -> dict:
    scenes: dict[str, dict] = {}
    edges: list[dict] = []
    targets: dict[str, dict] = defaultdict(lambda: {"inbound": 0, "refs": []})

    for scene_dir in sorted(root.iterdir()):
        if not scene_dir.is_dir():
            continue
        shared = scene_dir / "casts" / "Shared"
        if not shared.is_dir():
            continue
        scene = scene_dir.name
        behaviors = []
        cast_scripts = []
        movie_scripts = []

        for ls in sorted(shared.glob("*.ls")):
            name = ls.stem  # e.g. "BehaviorScript 125"
            text = ls.read_text(errors="replace")
            facts = parse_script(text)
            entry = {
                "script": name,
                "raw": text,
                **facts,
            }
            if name.lower().startswith("behaviorscript"):
                behaviors.append(entry)
            elif name.lower().startswith("castscript"):
                cast_scripts.append(entry)
            elif name.lower().startswith("moviescript"):
                movie_scripts.append(entry)
            else:
                behaviors.append(entry)

            # Build edges
            for r in facts["rollovers"]:
                edges.append({"from": scene, "to": r["target"], "kind": "rollover", "sprite": r["sprite"], "script": name})
                targets[r["target"]]["inbound"] += 1
                targets[r["target"]]["refs"].append({"scene": scene, "script": name, "kind": "rollover"})
            for c in facts["clicks"]:
                edges.append({"from": scene, "to": c["target"], "kind": "click", "script": name})
                targets[c["target"]]["inbound"] += 1
                targets[c["target"]]["refs"].append({"scene": scene, "script": name, "kind": "click"})
            for t in facts["frame_nav"]:
                edges.append({"from": scene, "to": t, "kind": "frame", "script": name})
                targets[t]["inbound"] += 1
                targets[t]["refs"].append({"scene": scene, "script": name, "kind": "frame"})

        scenes[scene] = {
            "behaviors": behaviors,
            "cast_scripts": cast_scripts,
            "movie_scripts": movie_scripts,
            "counts": {
                "behaviors": len(behaviors),
                "cast_scripts": len(cast_scripts),
                "movie_scripts": len(movie_scripts),
                "rollovers": sum(len(b["rollovers"]) for b in behaviors + cast_scripts + movie_scripts),
                "clicks":    sum(len(b["clicks"])    for b in behaviors + cast_scripts + movie_scripts),
                "frame_nav": sum(len(b["frame_nav"]) for b in behaviors + cast_scripts + movie_scripts),
            },
        }

    return {"scenes": scenes, "edges": edges, "targets": targets}


def main():
    root = Path(sys.argv[1])
    out  = Path(sys.argv[2])
    data = build(root)

    # Summary to stderr so stdout stays pure JSON if piped
    total_edges = len(data["edges"])
    scenes = data["scenes"]
    total_rollovers = sum(s["counts"]["rollovers"] for s in scenes.values())
    total_clicks = sum(s["counts"]["clicks"] for s in scenes.values())
    print(f"scenes={len(scenes)}  rollovers={total_rollovers}  clicks={total_clicks}  total_edges={total_edges}", file=sys.stderr)
    top = sorted(data["targets"].items(), key=lambda kv: -kv[1]["inbound"])[:15]
    print("top targets by inbound:", file=sys.stderr)
    for tgt, info in top:
        print(f"  {tgt!r:30s}  inbound={info['inbound']}", file=sys.stderr)

    out.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"wrote {out} ({out.stat().st_size/1024:.1f} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
