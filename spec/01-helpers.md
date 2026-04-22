# Helper function catalog

Every Lingo helper the VIE / AIE runtime uses. Sourced from
`Shared.Cst/External/MovieScript 92.ls` (the shared cast library) and the
per-scene movie scripts that call them.

The runtime must implement each of these as a JS function with faithful
semantics — these are the ONLY navigation primitives your CD-ROM uses.

---

## `on ARCHITEKTENVERZWEIGUNG WELCHESFRAME, WELCHESMOVIE`

Navigate to an architect's own movie, or to a specific frame within the current
movie if it happens to already be that architect.

```
set the visible of sprite 20 to 0
blinkzahl = 0
ankunft = EMPTY
if the movie contains WELCHESMOVIE then
  puppetsetzen(25, 30, 0)    -- release channels 25-30 from puppet mode
  go(WELCHESFRAME)            -- jump within current movie
else
  puppetsetzen(25, 30, 0)
  play frame "glossar ex"     -- play the exit transition frame of current movie
  go(WELCHESFRAME, WELCHESMOVIE)  -- cross-movie jump
end if
```

Called from AAHAUPT's randomizer (`zufall`) and from each architect's menu click.

---

## `on MovieVERZWEIGUNG WELCHESMOVIE, WELCHERSOUND`

Same as ARCHITEKTENVERZWEIGUNG but always jumps to frame 1 and optionally fires
a sound file:

```
if the movie contains WELCHESMOVIE then
  go(1)
  if WELCHERSOUND <> "0" then sound playFile 1, WELCHERSOUND
  puppetsetzen(25, 30, 0)
else
  puppetsetzen(25, 30, 0)
  play frame "glossar ex"
  if WELCHERSOUND <> "0" then sound playFile 1, WELCHERSOUND
  go(1, WELCHESMOVIE)
end if
```

---

## `on GLOSSARVERZWEIGUNG name, Sprache, frameposition`

Navigate to a glossary movie with language selection. Maintains the
`Mutterarchitekt` / `Muttermovie` / `Mutterframe` return-path globals so
`Verzweigung` can come back later.

Key logic: if coming from AAHAUPT (`the movie contains "AAhaupt"`), set
`Linkmodus = "eins"` and `ankunft = "haupt"`. Otherwise (already in a
glossar), promote to `"zwei"` so the menu-bar shows the daughter crumb.

`Sprache` is a `.aif` filename (e.g. `"kl001.aif"`) or `"0"` for silence.
If `"0"`, plays `"shared.aif"` (a shared cast sound).

Always does `puppetsetzen(25, 30, 0)` + `play frame "glossar ex"` + transition.

---

## `on Verzweigung`

Back-navigation from a glossar page, depending on `ankunft` and `Linkmodus`.

```
if ankunft = "haupt" then
  if Linkmodus = "eins": go(1, "AAhaupt")
  if Linkmodus = "zwei": Linkmodus = "eins"; go(Tochterframe1, disktochter1)
else
  if Linkmodus = "eins": go(Mutterframe, diskmovie)
  if Linkmodus = "zwei": Linkmodus = "eins"; go(Tochterframe1, disktochter1)
```

---

## `on MODULRUF`

Return to the current module (diskmovie) from a deeper page. Plays
`glossar.aif` ambient if leaving the current movie, else just `go(1)`.

Used by the `MODUL` menu-bar button.

---

## `on ARCHRUF`

Return to the current architect's bio page. Constructs movie name as
`diskarchitekt & "bio"` (e.g. `"COBIO"` for Corbusier).

Special case: when `volkerbundverzweigung = "schindler"` or
`"schindlerhauser"`, always goes to `"Scbio"` instead.

Used by the architect's name sprite in the menu bar.

---

## `on HOTRUF`

Forward-navigate to a daughter module via an in-text hotword link. If already
in that movie (`the movie contains disktochter1`), do nothing. Otherwise play
`glossar.aif` and jump to `(Tochterframe1, disktochter1)`.

---

## `on zurueck` (back one step)

If paused, resume. Else: `go(the frame - 11)` — jumps back 11 frames. Used by
the general-purpose back-navigation button on frame-based timeline scenes.

## `on vor` (forward one step)

Mirror of `zurueck`: `go(the frame + 1)` or resume.

---

## `on blinken lange`

Ticking animation handler. Sets timeoutLength to 120, puts sprites 25..30 in
puppet mode, and alternates their `ink` between 4 (matte) and 8 (copy) once
`timeoutLapsed > 60`. When `blinkzahl > lange`, resets blinkzahl and advances
to next frame.

This is what gives the menu "blinking" idle-attract behavior.

---

## `on menueleiste MODUS, plaene, JAHR`

The ONE handler called from every scene's `on exitFrame`. Responsibilities:

1. `go(the frame)` — pin current frame (so animations hold)
2. If free memory is tight, unload old frame assets
3. Set `Zahlzurueck = MODUS` for `sichtbarzurueck` to consume later
4. For sprite channels 32..43: hover detection — set ink to 4 (matte) if
   mouse is over, 8 (copy) if not
5. If not hovering 37, call `unsichtbarzurueck` (hide back-pile)
6. If hovering 36, call `sichtbarzurueck` (show back-pile)
7. `when mouseUp then unsichtbarzurueck` — on any click, hide back-pile
8. `when keyDown then lautstaerke` — keyboard volume + quit
9. Preload next 10 frames
10. Dispatch on MODUS value (0..7) for blinking behavior:
    - 0: `blinken("400")` between background music
    - 1: `go(the frame + 1)` when music stops
    - 3, 5: `blinken("6000")`
    - 4: `blinken("400")`
    - 6: advance frame
    - 7 (used in AAHAUPT): no special action

---

## `on unsichtbarzurueck` / `on sichtbarzurueck`

Show/hide the back-pile stack of sprites 37..43 by moving them on/off-stage.

`sichtbarzurueck` layout depends on `(ankunft, Modulart, Linkmodus, Zahlzurueck)`
and positions sprites vertically:
- main-menu glossar + eins: 21px-tall pile at y=420
- main-menu glossar + zwei: 42px at y=399, sprite 40 at y=420
- sub glossar + eins: 63px at y=378, sprites 41/42/43 laddered
- sub glossar + zwei: 84px at y=357, all four sprites visible
- architekt + Zahlzurueck=2: 21px at y=420
- architekt normal: 42px at y=399, sprites 42/43 visible

---

## `on lautstaerke` (keyboard handler)

- Keys "1"–"9": `set the soundLevel to value(the key)` — volume control
- Cmd-Q: `play frame "glossar ex"` + `go(1, "quit")`
- Cmd-.: same quit sequence
- F10 (keyCode 118): same quit sequence

---

## `on musikkontrolle`

Set sound channel 2 volume based on machine type:
- machineType 256 (PPC? modern?): volume 256 (full)
- Otherwise: volume 220 (slightly dimmed)

Called from many scenes at startup and on return.

---

## `on puppetsetzen von, bis, status`

Simple helper: `puppetSprite(x, status)` for x in von..bis, plus `installMenu(0)`
to hide the native menu bar. Used everywhere to toggle scripted control of
sprite channels.

---

## `on zufall` (random architect — idle attract mode)

Random integer 1..20 → ARCHITEKTENVERZWEIGUNG(1, "<Aubio|Babio|...|Wlbio>").
Triggered when idle timeout (pauselaenge = 60s) fires in AAHAUPT.

---

## `on Moviestart`

Setup handler that runs when each architect's movie loads:

- If sprite 48 is visible, hide it (clear the message-overlay)
- Set `Modulart = "glossar"`, `blinkzahl = 0`
- Set the display casts: sprite 42 ← Mutterarchitekt, 41 ← Muttermovie, 40 ← Tochtermovie1
- If `Linkmodus = "eins"`, save `disktochter1 = the movie`, `Tochterframe1 = the frame`
- `puppetsetzen(32, 43, 1)` — take puppet control of menu bar
- `unsichtbarzurueck()` — hide back-pile by default

---

## `on keineaktion`

Literally empty. Used as the idle handler to suppress default Director behavior.
