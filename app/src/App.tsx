import "./App.css";

const captures = [
  {
    src: "/restoration/language.png",
    title: "Language Gate",
    caption: "Original Windows projector running the DEUTSCH / ENGLISH screen.",
  },
  {
    src: "/restoration/emigration.png",
    title: "English Path",
    caption: "Original runtime advancing into the Emigration from Austria to America sequence.",
  },
  {
    src: "/restoration/scene.png",
    title: "Scene Playback",
    caption: "A live scene capture from the preserved CD-ROM playback session.",
  },
];

export default function App() {
  return (
    <main className="page">
      <section className="hero" aria-label="Visionaries in Exile online restoration check">
        <img
          className="hero-image"
          src="/restoration/emigration.png"
          alt="Original Visionaries in Exile runtime showing the Emigration from Austria to America sequence"
        />
        <div className="hero-copy">
          <p className="kicker">Visionaries in Exile</p>
          <h1>Online Restoration Check</h1>
          <p>
            Netlify-only proof from the original runtime. No Claude rebuild, no local VM stream,
            no background audio.
          </p>
        </div>
      </section>

      <section className="statement">
        <p>
          This page is intentionally static because Netlify cannot run the original Windows CD-ROM
          projector by itself. These captures document the preserved runtime working one-to-one.
        </p>
      </section>

      <section className="captures" aria-label="Runtime captures">
        {captures.map((capture) => (
          <article className="capture" key={capture.src}>
            <img src={capture.src} alt={`${capture.title} capture`} />
            <div>
              <h2>{capture.title}</h2>
              <p>{capture.caption}</p>
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}
