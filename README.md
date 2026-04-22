# Visionaries in Exile · Architects in Exile — 1:1 web restoration

A restoration of the 1996 Macromedia Director CD-ROM **Visionaries in Exile /
Architects in Exile** (Science Wonder Productions / Interactive Media Group
Perin-Wogenburg Ges.m.b.H / Architektur Zentrum Wien) as a modern desktop-class
web application.

The hard constraint for this project is **pixel-fidelity to the original**, not
a modern reinterpretation.

## Live

Deployed at: https://visionaries-in-exile.netlify.app

## What lives where

```
rebuild/
├── app/                    # Vite 5 + React 19 + TypeScript scene viewer
│   ├── src/App.tsx         # single-file scene + rollover + audio UI
│   ├── public/             # symlinks to bitd-out / media / content at dev time
│   └── dist/               # production build, deployed to Netlify
│
├── tools/                  # Python extraction + build tools
│   ├── decode_bitd.py      # Director RLE + CLUT + KEY_ + CASt → PNG
│   ├── parse_lingo.py      # nav graph from decompiled Lingo
│   ├── parse_audio.py      # puppetSound / playFile → audio.json
│   └── build_content.py    # join nav + images + labels → content.json
│
├── content/                # the webapp's runtime data
│   ├── content.json        # 332 scenes × images × rollovers × clicks × labels
│   └── audio.json          # per-scene audio cues from Lingo
│
├── qa/                     # Playwright end-to-end bug-test suite
│   └── test.mjs            # 10-step flow: enter → audio → nav → back
│
└── (gitignored, regeneratable from source DIR files)
    ├── bitd-out/           # 5,952 decoded PNGs, 711 MB
    ├── media/              # transcoded MP4 + MP3
    ├── lingo-out/          # 8,523 decompiled Lingo scripts
    ├── chunks/             # raw RIFX chunks per-scene
    └── ProjectorRays/      # built from upstream
```

## To rebuild the extraction from scratch

You need the original `.DIR` files in a folder structure:
`VIE-AIE/VIE/EXILE/*.DIR` and `VIE-AIE/AIE/EXILE/*.DIR`.

```bash
# 1. Build ProjectorRays (needs boost + mpg123 + zlib)
brew install boost mpg123 zlib cmake
git clone https://github.com/ProjectorRays/ProjectorRays.git
make -C ProjectorRays

# 2. Decompile every .DIR -> Lingo + chunks
find VIE-AIE -iname '*.dir' -print0 | xargs -0 -I% \
  ./ProjectorRays/projectorrays decompile "%" \
    --dump-scripts --dump-chunks --dump-json

# 3. Python extraction pipeline
pip install pillow
python3 tools/parse_lingo.py    lingo-out/VIE/input nav-vie.json
python3 tools/parse_lingo.py    lingo-out/AIE/input nav-aie.json
python3 tools/parse_audio.py    .
python3 tools/decode_bitd.py    chunks/VIE/<SCENE>/chunks bitd-out/VIE/<SCENE>
python3 tools/build_content.py  .

# 4. Transcode media
ffmpeg ...   # see git log for exact flags
```

## Development

```bash
cd app
# Use Homebrew node, NOT Codex's bundled node (hardened-runtime blocks rollup)
/opt/homebrew/opt/node@22/bin/npm install
/opt/homebrew/opt/node@22/bin/npm run dev
# → http://localhost:5173
```

## Testing

```bash
cd qa
node test.mjs
```

Runs a real Chromium and a 10-step end-to-end flow. Screenshots land in
`qa/out/*.png`, full report in `qa/out/report.json`.

## Credits

- **Original CD-ROM**: Science Wonder Productions · Interactive Media Group
  Perin-Wogenburg Ges.m.b.H · Architektur Zentrum Wien · 1995–1998
- **Author**: Michael Perin-Wogenburg
- **Extraction toolchain**: [ProjectorRays](https://github.com/ProjectorRays/ProjectorRays)
  by Debby Servilla · [ScummVM Director engine](https://www.scummvm.org/) reference

## License

The web application code in `app/` and `tools/` is released as MIT.
The underlying content (bitmaps, audio, Lingo scripts) remains the intellectual
property of the original authors and Architektur Zentrum Wien.
