# Visionaries in Exile Hosted Runtime

This is the production direction for the public restoration.

Netlify is only the entrance page. The artwork itself must run on a server that can execute the preserved Windows/Director/QuickTime runtime and stream video, input, and audio to browsers.

## Target Architecture

1. Windows runtime host runs the original `doubleplayer.exe` / projector payload.
2. RDP is enabled in Windows so audio redirection is part of the session.
3. Apache Guacamole exposes that RDP session through a browser.
4. Netlify links to or embeds the runtime entry point.

## Why not noVNC?

noVNC is useful for diagnostics, but it carries video/input only in our current QEMU setup. Audio came from QEMU/CoreAudio on the host, which caused the loud local bleed. That is not acceptable for a narration-based artwork.

## What this server must provide

- Browser playback with synchronized narration.
- A safe default volume path controlled by the browser.
- One public visitor session at a time at first.
- Automatic launch into the original runtime.
- A reset script between sessions.
