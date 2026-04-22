# VIE / AIE — State Machine Spec

This document captures the authorial semantics of every global variable used
in the 1996 CD-ROM's Lingo, sourced from the actual code in `Shared.Cst`
(`MovieScript 92`) and per-movie `startMovie` handlers. Not paraphrased —
derived from running code.

## Global variables

| Variable | Purpose | Set where | Values |
|---|---|---|---|
| `Modulart` | What kind of scene is currently active — gates how menu buttons behave | set at the top of each movie's `startMovie` (e.g. AAHAUPT sets `"Intro"`, glossary sets `"glossar"`, architect pages set `"architekt"`) | `"Intro"`, `"architekt"`, `"glossar"` |
| `Linkmodus` | Navigation depth: "eins" = primary chain (main menu → architect → module), "zwei" = secondary chain (jumped in from hotword) | set/cleared by `ARCHITEKTENVERZWEIGUNG`, `GLOSSARVERZWEIGUNG`, `Verzweigung` | `"eins"`, `"Zwei"` (note the Z case — matches original code) |
| `ankunft` | Arrival point — "haupt" when the current scene was reached from the main menu, EMPTY otherwise | set by `GLOSSARVERZWEIGUNG` when `the movie contains "AAhaupt"`, cleared by `ARCHITEKTENVERZWEIGUNG` | `"haupt"`, `EMPTY` |
| `Zahlzurueck` | The `MODUS` argument the current menueleiste was called with — used by `sichtbarzurueck` to decide how to stack the return-path sprites | set by `menueleiste MODUS, ...` | integer 0..7 |
| `blinkzahl` | Counts `blinken()` ticks; reset to 0 on any deliberate navigation. Used to detect idle-menu timeout for `zufall` random-architect auto-advance. | set by many handlers back to 0 | integer |
| `Mutterarchitekt` | **Cast-member NAME** (not a string!) — shown on menu-bar sprite 42 as the "parent architect" crumb. Set via `set the castNum of sprite 42 to the number of member Mutterarchitekt`. | set by `GLOSSARVERZWEIGUNG` to `"EXIL"` when coming from main menu; set by per-architect startMovie to that architect's name cast (e.g. `"CO"` for Corbusier) | string name of a cast member in Shared.Cst |
| `Muttermovie` | **Cast-member NAME** shown on menu-bar sprite 41 — the "parent module" label. | set by `GLOSSARVERZWEIGUNG` to `"Visionaere#im"` (Visionäre im Exil) when coming from main menu | cast-member name |
| `Mutterframe` | Frame number (or label) in the parent movie to return to via `Verzweigung` | set by `GLOSSARVERZWEIGUNG` to `"fade"` when main-menu parent; set by architect pages to `the frame - 1` so "back" returns here | frame label string OR integer |
| `Tochtermovie1` | **Cast-member NAME** shown on menu-bar sprite 40 — the "daughter module" forward-link crumb, visible when `Linkmodus = "zwei"` | | cast-member name |
| `Tochterframe1` | Frame in `disktochter1` to return to when "back"-navigating from a deeper page | | integer |
| `disktochter1` | Movie name of the daughter module when user drilled in via a hotword | set by `GLOSSARVERZWEIGUNG` and `Moviestart`: `disktochter1 = the movie` | movie name string |
| `diskarchitekt` | Current architect's short code (e.g. `"CO"` for Corbusier, `"SC"` for Schindler). Used to construct bio movie name: `diskarchitekt & "bio"` → `"COBIO"`. | set by each architect movie's startMovie | 2-letter architect code |
| `diskmovie` | Current module movie name for `MODULRUF` return | | movie name string |
| `volkerbundverzweigung` | Special-case branching flag for Schindler's Völkerbund page (and `schindlerhauser` module) — ARCHRUF behaves differently for these | | `"schindler"`, `"schindlerhauser"`, else EMPTY |
| `pauselaenge` | Idle timeout in milliseconds before `zufall` random-architect kicks in. Set to 60000 (= 60s) in AAHAUPT. | set in startMovie | integer ms |
| `menueblinken` | Timer threshold for menu-bar blink animation. Set to 5000 (= 5s) in AAHAUPT. | set in startMovie | integer ms |

## Movie-type dispatch

Every scene sets `Modulart` in its `startMovie` and the rest of the system reads
that global to decide what menu options make sense, which helper to call on the
generic navigation buttons, and whether `blinken()` cycles run.

- `Modulart = "Intro"` → this IS the main menu (AAHAUPT); the menueleiste
  shows only the main logo, no back button.
- `Modulart = "architekt"` → architect-level page; menueleiste shows HAUPTMENÜ
  button + architect name crumb; `Verzweigung` goes back to `Mutterframe` in
  the originating movie (usually `"fade"` in AAHAUPT).
- `Modulart = "glossar"` → glossary / deep content; menueleiste shows up to
  three crumbs (main menu, parent module, and if `Linkmodus="zwei"`, the
  daughter module forward-link).

## Sprite channels (from Shared.Cst menueleiste + sichtbarzurueck)

- Channel 7: main logo (menueleiste(7) in AAHAUPT — see BehaviorScript 72)
- Channels 20..28: architect face rollovers on AAHAUPT (per scene's own Lingo)
- Channel 32..43: the menu bar sprites (common across all scenes, from Shared.Cst)
  - Sprite 32..36: assorted menu buttons (language? volume?)
  - Sprite 37: "back-pile" container, height adjusts based on Modulart + Linkmodus (21, 42, 63, 84 px tall)
  - Sprite 38: dismissible message overlay (CastScript 106 hides it on click)
  - Sprite 40: Tochtermovie1 name display (visible in "zwei" mode)
  - Sprite 41: Muttermovie name display
  - Sprite 42: Mutterarchitekt name display
  - Sprite 43: always visible back-navigation hit zone
  - Sprite 48: the full-screen message background — hidden by `menueverdecken` / `Moviestart`
