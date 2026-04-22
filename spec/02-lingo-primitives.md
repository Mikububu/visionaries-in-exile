# Lingo primitives the runtime must implement

Every Lingo call, property read, or assignment that appears in the extracted
scripts. A proper runtime needs interpreters for these. Taken from grepping
through `lingo-out/**/casts/Shared/*.ls` + `shared-lib/**/casts/External/*.ls`.

## Navigation primitives

- `go(frameSpec)` — jump within the current movie to a frame (number OR label)
- `go(frame, movieName)` — cross-movie jump; loads `movieName.dir`, starts at `frame`
- `go(the frame)` — re-trigger current frame (pin)
- `go(the frame + N)` / `go(the frame - N)` — relative jump
- `play frame "name"` — play a single named frame as transition, then return
- `play done` — return from a play-frame transition (rarely used)

## Sprite / cast property getters

- `rollover(N)` — returns 1 if mouse is over sprite channel N's rect
- `the frame` — current frame number
- `the movie` — current movie name
- `the movie contains "X"` — case-insensitive substring on `the movie`
- `the mouseCast` — cast # under mouse
- `the locV of sprite N`, `the locH of sprite N` — position in stage px
- `the height of sprite N`, `the width of sprite N`
- `the visible of sprite N` — 0/1
- `the castNum of sprite N` — cast member ID
- `the ink of sprite N` — 0..36 (copy, matte, bg-transparent, blend, etc.)
- `the number of member X` — resolve cast-member name → cast number
- `member("name")` — cast-member reference

## Sprite / cast property setters

- `set the castNum of sprite N to M`
- `set the castNum of sprite N to the number of member "name"`
- `set the visible of sprite N to 0/1`
- `set the locV of sprite N to Y`, `set the locH of sprite N to X`
- `set the height of sprite N to H`, `set the width of sprite N to W`
- `set the ink of sprite N to I`
- `set the cursor of sprite N to cursorId` or to a `[member("over"), member("mask")]` pair
- `set the cursor of sprite N to [879, 880]` — built-in cursor IDs
- `cursor(-1)` — global cursor reset to arrow

## Puppet / timing

- `puppetSprite(N, true/false)` — take/release scripted control
- `puppetSound(channel, filename)` / `puppetSound(filename)` / `puppetSound(0)` to stop
- `puppetPalette(0)` — reset palette
- `sound playFile 1, "filename.aif"` — play file in given channel
- `updateStage()` — force stage redraw
- `continue()` — resume paused movie
- `the pauseState` — 0/1
- `the timeoutLapsed` — ms since last input
- `set the timeoutLength to N`
- `set the soundLevel to N` — 0..7 master volume
- `1.soundBusy` — is sound channel 1 still playing

## Memory / lifecycle

- `clearGlobals()`
- `preload(frameRange)`
- `unload(from, to)`
- `the freeBlock` — available memory in bytes
- `the machineType` — numeric machine identifier

## UI

- `installMenu(0)` — hide classic Mac menu bar
- `when mouseUp then handler` — one-shot mouseUp binding
- `when keyDown then handler` — one-shot keyDown binding
- `the keyCode`, `the key`, `the commandDown`

## Misc

- `random(N)` — 1..N
- `value(str)` — coerce to int
- `exit` — return from handler
- `nothing()` — no-op

## Global variables (user-declared, persisted across movies)

See `00-state-machine.md`. The runtime must expose a `globals` object with
the same semantics as Director's `global` statement:
- first reference in a handler needs a `global` declaration or implicit one
- reads from unset globals return VOID (empty)
- globals persist across movie loads UNLESS `clearGlobals()` is called
