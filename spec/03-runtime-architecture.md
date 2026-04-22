# Runtime architecture (target)

A JS Director-subset interpreter that plays YOUR files in a browser. This is
the architecture the implementation will follow. No more "rectangles" — every
pixel comes from YOUR bitmaps, every transition from YOUR Lingo.

```
                ┌──────────────────────────────────────────────────┐
                │                GLOBAL STATE                       │
                │  Modulart, Linkmodus, ankunft, Zahlzurueck,       │
                │  blinkzahl, Mutter*, Tochter*, disk*, etc.        │
                │  (JS Map<string, LingoValue>)                     │
                └──────────────────────────────────────────────────┘
                                     │
                ┌────────────────────┼────────────────────────────┐
                │                    ▼                             │
                │         MOVIE LOADER (per .DIR)                  │
                │                                                  │
                │  - parses VWSC score (we already have parse_vwsc)│
                │  - parses VWLB labels (fix with string-align)    │
                │  - loads CAST table (CAS_ + CASt + BITD)         │
                │  - registers all handlers from scripts           │
                └──────────────────────────────────────────────────┘
                                     │
                ┌────────────────────┼────────────────────────────┐
                │                    ▼                             │
                │              FRAME PLAYER                        │
                │                                                  │
                │  loop:                                           │
                │    applySpriteDeltasForCurrentFrame              │
                │    render()                                      │
                │    invoke on enterFrame handlers                 │
                │    wait for tempo                                │
                │    invoke on exitFrame handlers                  │
                │    advance currentFrame unless pinned            │
                └──────────────────────────────────────────────────┘
                                     │
                ┌────────────────────┼────────────────────────────┐
                │                    ▼                             │
                │         LINGO INTERPRETER                        │
                │                                                  │
                │  AST walker over the decompiled .ls source OR    │
                │  a tiny parser-combinator that handles the ~30   │
                │  primitives actually used (see 02-primitives).   │
                │                                                  │
                │  Not a full Lingo — just what YOUR scripts use.  │
                │                                                  │
                │  Resolves `rollover(N)` by hit-testing current   │
                │  sprite channels against mouse; triggers nav via │
                │  `go()` and `play frame` which reset the frame   │
                │  pointer in the player above.                    │
                └──────────────────────────────────────────────────┘
                                     │
                ┌────────────────────┼────────────────────────────┐
                │                    ▼                             │
                │              RENDERER                            │
                │                                                  │
                │  <canvas> at fixed 640×480                       │
                │  For each visible sprite (from the player's      │
                │  current channel buffer), drawImage the cast     │
                │  bitmap (BITD→PNG) at (x, y, w, h) with the ink  │
                │  mode applied via globalCompositeOperation.      │
                │                                                  │
                │  NO CSS OVERLAYS. NO APPROXIMATED RECTS.         │
                │  Just the actual 1996 art, composited in the     │
                │  same order the Director score dictates.         │
                └──────────────────────────────────────────────────┘
                                     │
                ┌────────────────────┼────────────────────────────┐
                │                    ▼                             │
                │              AUDIO BUS                           │
                │                                                  │
                │  Two <audio> elements (channel 1 narration,      │
                │  channel 2 ambient) matching                     │
                │  `sound playFile N, "x.aif"` and                 │
                │  `puppetSound channel, "x.aif"`.                 │
                │                                                  │
                │  `1.soundBusy` reads paused/ended state.         │
                └──────────────────────────────────────────────────┘
```

## What we already have that plugs in

- VWSC parse → per-frame sprite state (done, 332 scenes covered)
- CAS_ / CASt parse → cast member names + bitmap mapping (done, needs polish)
- Lingo scripts in readable form (done — all 8,523 of them)
- BITD → PNG decoder (done, 5,952 images)
- AIF → MP3 transcode (done)

## What needs to be built (in order)

### Phase 1: Faithful single-scene playback (proof it works)

1. **Proper Lingo parser** for the subset in `02-lingo-primitives.md`. Not
   regex — a real tokenizer → AST → evaluator. Lives at `runtime/lingo.ts`.

2. **Global state container** matching the semantics in `00-state-machine.md`.
   Exposes read/write to the Lingo evaluator.

3. **Frame player** that walks the score frame-by-frame, maintains the
   channel buffer, invokes `on exitFrame` on the current sprite's cast script,
   honors `go(...)` and `play frame "x"` calls from Lingo.

4. **Canvas renderer** that paints the channel buffer as bitmap sprites with
   correct ink mode. 640×480 canvas, no CSS hit-zones — use actual cast
   bitmaps and hit-test them in JS.

5. **Rollover dispatch** — on every `mousemove` inside canvas, compute which
   sprite the mouse is over; expose to Lingo's `rollover(N)` getter.

6. **Prove on AAHAUPT end-to-end** — hover a face → score jumps to that
   architect's label frame → that frame's cast bitmap (the architect's
   typeset name) becomes visible on the portrait. Click → cross-movie jump
   to the architect's own .DIR with all state carried through.

### Phase 2: Coverage (spread to all 332 scenes)

7. Handle all sound cues (`sound playFile`, `puppetSound`, `glossar.aif` —
   note this is in Shared.Cst and needs per-movie cross-reference).

8. Handle all transition frames (`play frame "glossar ex"` etc.) with
   correct visual — transitions in Director are often just short frame
   sequences with specific sprite animations.

9. Handle the menu bar (sprites 32-43) as common UI — render the back-pile
   (sprites 37..43) with the dynamic heights from `sichtbarzurueck`.

10. Handle the `zufall` idle-attract mode (60s timeout → random architect).

### Phase 3: Polish / fidelity passes

11. Typography: render text cast members (STXT chunks) with correct fonts.
    The original used specific Mac fonts; most are rasterized into BITD so
    this is mostly a non-issue, but some dynamic text needs font work.

12. Cursor states: `set the cursor of sprite N to [member("over"), member("mask")]`
    — custom cursors from specific cast bitmaps.

13. Per-scene CLUT (palette) selection — some scenes have custom palettes we
    haven't loaded.

14. QuickTime movie playback for the `.MOV` cast members (we have them as
    MP4 already).

15. Keyboard shortcuts: 1-9 for volume, Cmd-Q / Cmd-. / F10 to quit (loops to
    "quit" movie).

## Estimated size

This is ~2000-3000 lines of TypeScript for Phase 1. Per-phase roughly:
- Phase 1: 1-2 sessions of focused work
- Phase 2: 2-3 sessions spread across scenes
- Phase 3: ongoing polish

Nothing gets shipped as "complete" before Phase 1 passes end-to-end on AAHAUPT
with a real hover showing a real architect name bitmap at the real score
position.
