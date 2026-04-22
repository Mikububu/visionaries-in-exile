import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

type Rollover = { sprite: number; target: string };
type Click = { target: string; script?: string };
type ImageInfo = { png: string; w?: number; h?: number; raw?: number };
type Scene = {
  side: "VIE" | "AIE";
  labels: Record<string, number>;
  backdrop: string | null;
  images: ImageInfo[];
  rollovers: Rollover[];
  clicks: Click[];
  frame_nav: string[];
};
type Content = { scenes: Record<string, Scene> };

type AudioEntry = {
  file: string;
  trigger: string;
  script: string;
  mp3: string | null;
  ref_stem: string;
};
type AudioMap = Record<"VIE" | "AIE", Record<string, AudioEntry[]>>;

type Rect = {
  top: number;
  left: number;
  bottom: number;
  right: number;
  cast_name?: string;
};
type RectsMap = Record<string, Record<string, Rect>>; // "AIE/AAHAUPT" -> { "hoffmann": Rect, ... }

function pickAudio(
  audio: AudioMap | null,
  side: string,
  scene: string
): AudioEntry | null {
  if (!audio) return null;
  const sideMap = audio[side as "VIE" | "AIE"] ?? {};
  const entries = sideMap[scene] ?? [];
  return entries.find((e) => e.mp3) ?? null;
}

function sceneUrl(side: string, scene: string, png: string): string {
  return `/bitd/${side}/${scene}/${png}`;
}

function resolveTarget(
  target: string,
  current: { side: string; name: string },
  scenes: Record<string, Scene>
): string | null {
  if (scenes[`${current.side}/${target}`]) return `${current.side}/${target}`;
  const ciKey = Object.keys(scenes).find(
    (k) =>
      k.startsWith(current.side + "/") &&
      k.split("/")[1].toLowerCase() === target.toLowerCase()
  );
  if (ciKey) return ciKey;
  const anyKey = Object.keys(scenes).find(
    (k) => k.split("/")[1].toLowerCase() === target.toLowerCase()
  );
  return anyKey ?? null;
}

export default function App() {
  const [content, setContent] = useState<Content | null>(null);
  const [audio, setAudio] = useState<AudioMap | null>(null);
  const [rects, setRects] = useState<RectsMap | null>(null);
  const [currentKey, setCurrentKey] = useState<string>("AIE/AAHAUPT");
  const [side, setSide] = useState<"VIE" | "AIE">("AIE");
  const [query, setQuery] = useState("");
  const [hoveredTarget, setHoveredTarget] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const [entered, setEntered] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    fetch("/content/audio.json")
      .then((r) => r.json())
      .then(setAudio)
      .catch((e) => console.error("audio load failed", e));
    fetch("/content/rects.json")
      .then((r) => r.json())
      .then(setRects)
      .catch((e) => console.error("rects load failed", e));
  }, []);

  useEffect(() => {
    fetch("/content/content.json")
      .then((r) => r.json())
      .then(setContent)
      .catch((e) => console.error("content load failed", e));
  }, []);

  const scenes = content?.scenes ?? {};
  const scene = scenes[currentKey];

  const sceneKeys = useMemo(() => {
    const all = Object.keys(scenes).filter((k) => k.startsWith(side + "/"));
    const q = query.trim().toLowerCase();
    return all
      .filter((k) => (q ? k.toLowerCase().includes(q) : true))
      .sort();
  }, [scenes, side, query]);

  if (!content)
    return <div className="loading">loading content.json…</div>;
  if (!scene) {
    // Fall back to first in side
    const fallback = Object.keys(scenes).find((k) => k.startsWith(side + "/"));
    if (fallback) {
      setCurrentKey(fallback);
      return null;
    }
    return <div className="loading">no scenes found</div>;
  }

  const [curSide, curName] = currentKey.split("/");
  const backdropUrl = scene.backdrop
    ? sceneUrl(curSide, curName, scene.backdrop)
    : null;
  const audioEntry = pickAudio(audio, curSide, curName);
  const audioUrl = audioEntry?.mp3 ?? null;

  const targets = Array.from(
    new Set([
      ...scene.rollovers.map((r) => r.target),
      ...scene.clicks.map((c) => c.target),
      ...scene.frame_nav,
    ])
  );

  const navTo = (t: string) => {
    const resolved = resolveTarget(t, { side: curSide, name: curName }, scenes);
    if (resolved) {
      setHistory((h) => [...h.slice(-19), currentKey]);
      setCurrentKey(resolved);
      setSide(resolved.split("/")[0] as "VIE" | "AIE");
    } else {
      console.log(`intra-scene frame "${t}" label=${scene.labels[t]}`);
    }
  };

  const goBack = () => {
    setHistory((h) => {
      const prev = h[h.length - 1];
      if (prev) {
        setCurrentKey(prev);
        setSide(prev.split("/")[0] as "VIE" | "AIE");
        return h.slice(0, -1);
      }
      return h;
    });
  };

  // Click the backdrop: behave like Director — advance to the first target
  // that resolves to a real scene. Many scenes have single-letter frame labels
  // ("s", "b", "d") that are internal and don't map to a scene; skip them.
  const advanceFromBackdrop = () => {
    if (!entered) {
      setEntered(true);
      return;
    }
    const candidates = [
      ...scene.clicks.map((c) => c.target),
      ...scene.rollovers.map((r) => r.target),
      ...scene.frame_nav,
    ];
    for (const t of candidates) {
      if (resolveTarget(t, { side: curSide, name: curName }, scenes)) {
        navTo(t);
        return;
      }
    }
  };

  // Decide whether an image is safely rendered (our CASt-dim heuristic fails on
  // some cropped bitmaps, producing striped aspect ratios). Hide the obvious
  // failures from the gallery so the stage never looks broken.
  const looksClean = (i: ImageInfo) => {
    if (!i.w || !i.h || !i.raw) return true;
    const expect = i.w * i.h;
    if (expect === i.raw) return true;            // exact pitch match
    if (i.w === 640 && i.h >= 40 && i.h <= 480) return true;
    // Accept up to half a row of slack (RLE rarely overshoots)
    return Math.abs(expect - i.raw) <= i.w / 2;
  };

  return (
    <div className="shell">
      <aside className="sidebar">
        <header>
          <h1>VIE · AIE</h1>
          <p className="sub">Visionaries in Exile · rebuilt</p>
        </header>

        <div className="side-switch">
          <button
            className={side === "VIE" ? "on" : ""}
            onClick={() => setSide("VIE")}
          >
            VIE (DE)
          </button>
          <button
            className={side === "AIE" ? "on" : ""}
            onClick={() => setSide("AIE")}
          >
            AIE (EN)
          </button>
        </div>

        <input
          type="search"
          placeholder="filter scenes…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />

        <div className="count">{sceneKeys.length} scenes</div>

        <ul className="scene-list">
          {sceneKeys.map((k) => (
            <li
              key={k}
              className={k === currentKey ? "active" : ""}
              onClick={() => setCurrentKey(k)}
            >
              {k.split("/")[1]}
            </li>
          ))}
        </ul>
      </aside>

      <main className="stage-wrap">
        <div
          className={`stage ${entered ? "live" : "pre-enter"}`}
          onClick={advanceFromBackdrop}
        >
          {backdropUrl ? (
            <img className="backdrop" src={backdropUrl} alt={curName} />
          ) : (
            <div className="backdrop empty">no backdrop</div>
          )}

          {/* Pixel-accurate rollover hotspots from CASt specific-data */}
          {entered &&
            rects &&
            Object.entries(rects[currentKey] ?? {}).map(([target, rect]) => {
              const resolved = resolveTarget(
                target,
                { side: curSide, name: curName },
                scenes
              );
              if (!resolved) return null;
              return (
                <button
                  key={target}
                  className={[
                    "hotspot",
                    hoveredTarget === target ? "hovered" : "",
                  ].join(" ")}
                  style={{
                    top: rect.top,
                    left: rect.left,
                    width: rect.right - rect.left,
                    height: rect.bottom - rect.top,
                  }}
                  onMouseEnter={() => setHoveredTarget(target)}
                  onMouseLeave={() => setHoveredTarget(null)}
                  onClick={(e) => {
                    e.stopPropagation();
                    navTo(target);
                  }}
                  aria-label={target}
                >
                  <span className="hotspot-label">{target}</span>
                </button>
              );
            })}

          {!entered && (
            <div className="enter-overlay">
              <div className="enter-chrome">
                <div className="enter-title">Visionaries in Exile</div>
                <div className="enter-sub">
                  Science Wonder Productions · Architektur Zentrum Wien · 1996
                </div>
                <button
                  className="enter-button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setEntered(true);
                  }}
                >
                  ▶ enter
                </button>
                <div className="enter-help">
                  hover faces to reveal architects · arrows below to navigate
                </div>
              </div>
            </div>
          )}

          {entered &&
            !(rects && rects[currentKey]) &&
            (scene.clicks.length > 0 || scene.rollovers.length > 0) && (
              <div className="stage-hint">click to continue →</div>
            )}
        </div>

        {/* Menu bar — equivalent of sprites 32-43 in the original */}
        {entered && (
          <div className="menuebar">
            <button
              className="mb-btn"
              onClick={goBack}
              disabled={history.length === 0}
              title="zurück (back)"
            >
              ◂ back
            </button>
            <button
              className="mb-btn"
              onClick={() => navTo("AAHAUPT")}
              title="zum Hauptmenü (to main menu)"
            >
              ⌂ main menu
            </button>
            <div className="mb-spacer" />
            <span className="mb-crumb">
              {curSide} / {curName}
            </span>
            <div className="mb-spacer" />
            {audioUrl && (
              <button
                className={`mb-btn mb-audio ${entered && !muted ? "playing" : ""}`}
                onClick={() => setMuted((m) => !m)}
                title={audioEntry?.file}
              >
                {muted ? "🔇" : "🔊"}
              </button>
            )}
          </div>
        )}

        {audioUrl && entered && (
          <audio
            ref={audioRef}
            key={audioUrl}
            src={audioUrl}
            autoPlay
            loop
            muted={muted}
          />
        )}

        <section className="meta">
          <div className="meta-head">
            <h2>
              <span className="pill">{curSide}</span> {curName}
            </h2>
            <div className="stats">
              {history.length > 0 && (
                <>
                  <button className="back-btn" onClick={goBack}>
                    ← back
                  </button>
                  {" · "}
                </>
              )}
              {scene.images.length} img · {scene.rollovers.length} rollovers ·{" "}
              {scene.clicks.length} clicks · {Object.keys(scene.labels).length}{" "}
              labels
              {audioUrl && (
                <>
                  {" · "}
                  <button
                    className={`audio-toggle ${entered && !muted ? "playing" : ""}`}
                    onClick={() => setMuted((m) => !m)}
                    title={audioEntry?.file}
                  >
                    {muted ? "🔇" : "🔊"} {audioEntry?.file}
                  </button>
                </>
              )}
            </div>
          </div>

          {targets.length > 0 && (
            <div className="targets">
              <h3>navigation targets</h3>
              <ul>
                {targets.map((t) => {
                  const resolved = resolveTarget(
                    t,
                    { side: curSide, name: curName },
                    scenes
                  );
                  const rollover = scene.rollovers.find((r) => r.target === t);
                  return (
                    <li
                      key={t}
                      className={[
                        resolved ? "live" : "frame-label",
                        hoveredTarget === t ? "hovered" : "",
                      ].join(" ")}
                      onMouseEnter={() => setHoveredTarget(t)}
                      onMouseLeave={() => setHoveredTarget(null)}
                      onClick={() => navTo(t)}
                    >
                      <code>{t}</code>
                      {rollover && (
                        <span className="sprite">sprite {rollover.sprite}</span>
                      )}
                      {resolved ? (
                        <span className="resolved">→ {resolved}</span>
                      ) : scene.labels[t] !== undefined ? (
                        <span className="label">frame {scene.labels[t]}</span>
                      ) : (
                        <span className="unresolved">?</span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {scene.images.filter(looksClean).length > 1 && (
            <div className="gallery">
              <h3>
                scene cast members{" "}
                <span className="muted">
                  ({scene.images.filter(looksClean).length} of{" "}
                  {scene.images.length} renderable)
                </span>
              </h3>
              <div className="thumbs">
                {scene.images.filter(looksClean).map((i) => (
                  <figure key={i.png}>
                    <img
                      src={sceneUrl(curSide, curName, i.png)}
                      loading="lazy"
                      alt={i.png}
                    />
                    <figcaption>
                      {i.w}×{i.h}
                    </figcaption>
                  </figure>
                ))}
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
