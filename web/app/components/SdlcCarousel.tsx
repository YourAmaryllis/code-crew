'use client';

import { useState, useEffect, useCallback } from 'react';

// ─── SVG Illustrations ────────────────────────────────────────────────────────

function IdeaToReqSvg() {
  return (
    <svg viewBox="0 0 480 300" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden className="w-full h-full">
      {/* Dot grid background */}
      <pattern id="dots1" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
        <circle cx="1" cy="1" r="1" fill="#2a2a30" />
      </pattern>
      <rect width="480" height="300" fill="url(#dots1)" />

      {/* Idea bubble — left */}
      <rect x="20" y="50" width="150" height="200" rx="12" fill="#141418" stroke="#242428" strokeWidth="1.5" />
      <text x="95" y="80" textAnchor="middle" fill="#64647a" fontSize="10" fontFamily="monospace">PROJ-123</text>
      <rect x="38" y="95" width="114" height="8" rx="4" fill="#242428" />
      <rect x="38" y="111" width="90" height="8" rx="4" fill="#242428" />
      <rect x="38" y="127" width="104" height="8" rx="4" fill="#1e1e26" />
      <rect x="38" y="151" width="60" height="8" rx="4" fill="#242428" />
      <rect x="38" y="167" width="80" height="8" rx="4" fill="#1e1e26" />
      <rect x="38" y="183" width="70" height="8" rx="4" fill="#242428" />
      {/* Ticket icon */}
      <rect x="38" y="210" width="114" height="24" rx="6" fill="#1e1e26" stroke="#2a2a30" strokeWidth="1" />
      <text x="95" y="226" textAnchor="middle" fill="#64647a" fontSize="9" fontFamily="monospace">vague brief…</text>

      {/* Agents doing work — center */}
      <g transform="translate(195, 100)">
        <circle cx="45" cy="50" r="32" fill="#141418" stroke="#7c6aff" strokeWidth="1.5" strokeDasharray="4 3" />
        <text x="45" y="44" textAnchor="middle" fill="#7c6aff" fontSize="9" fontFamily="monospace">PO +</text>
        <text x="45" y="58" textAnchor="middle" fill="#7c6aff" fontSize="9" fontFamily="monospace">Scrum</text>
        {/* spinning dots */}
        <circle cx="45" cy="15" r="3" fill="#7c6aff" opacity="0.9" />
        <circle cx="72" cy="28" r="3" fill="#7c6aff" opacity="0.6" />
        <circle cx="18" cy="28" r="3" fill="#7c6aff" opacity="0.3" />
      </g>

      {/* Arrow */}
      <path d="M 188 150 L 200 150" stroke="#7c6aff" strokeWidth="1.5" />
      <path d="M 285 150 L 300 150" stroke="#7c6aff" strokeWidth="1.5" />
      <polygon points="300,145 310,150 300,155" fill="#7c6aff" />

      {/* Spec doc — right */}
      <rect x="315" y="50" width="150" height="200" rx="12" fill="#141418" stroke="#7c6aff" strokeWidth="1.5" />
      <text x="390" y="78" textAnchor="middle" fill="#7c6aff" fontSize="10" fontFamily="monospace">requirements</text>

      {/* Checkbox rows */}
      {[96, 118, 140, 162].map((y, i) => (
        <g key={y}>
          <rect x="333" y={y - 7} width="12" height="12" rx="3" fill="#4ade80" opacity={i < 3 ? 1 : 0.4} />
          {i < 3 && <path d={`M${336} ${y} l3 3 6 -6`} stroke="#0b0b0d" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />}
          <rect x="353" y={y - 4} width={[80, 70, 90, 60][i]} height="7" rx="3.5" fill={i < 3 ? "#242428" : "#1e1e26"} />
        </g>
      ))}

      {/* BDD block */}
      <rect x="327" y="185" width="124" height="50" rx="6" fill="#18181e" stroke="#2a2a30" strokeWidth="1" />
      <text x="339" y="200" fill="#4ade80" fontSize="8" fontFamily="monospace">Given</text>
      <text x="339" y="213" fill="#64647a" fontSize="8" fontFamily="monospace">  user submits…</text>
      <text x="339" y="225" fill="#7c6aff" fontSize="8" fontFamily="monospace">When / Then</text>

      {/* Human gate badge */}
      <rect x="145" y="260" width="190" height="26" rx="13" fill="#141418" stroke="#4ade80" strokeWidth="1.5" />
      <circle cx="162" cy="273" r="5" fill="#4ade80" />
      <text x="172" y="277" fill="#4ade80" fontSize="9" fontFamily="monospace">Human gate: approve spec</text>
    </svg>
  );
}

function ArchDesignSvg() {
  return (
    <svg viewBox="0 0 480 300" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden className="w-full h-full">
      <pattern id="dots2" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
        <circle cx="1" cy="1" r="1" fill="#2a2a30" />
      </pattern>
      <rect width="480" height="300" fill="url(#dots2)" />

      {/* Frontend box */}
      <rect x="30" y="40" width="110" height="56" rx="8" fill="#141418" stroke="#7c6aff" strokeWidth="1.5" />
      <text x="85" y="62" textAnchor="middle" fill="#7c6aff" fontSize="9" fontFamily="monospace">Frontend</text>
      <text x="85" y="78" textAnchor="middle" fill="#64647a" fontSize="8" fontFamily="monospace">React / Next.js</text>

      {/* API Gateway box — center */}
      <rect x="185" y="120" width="110" height="56" rx="8" fill="#1a1420" stroke="#7c6aff" strokeWidth="2" />
      <text x="240" y="142" textAnchor="middle" fill="#9585ff" fontSize="9" fontFamily="monospace">API Gateway</text>
      <text x="240" y="158" textAnchor="middle" fill="#64647a" fontSize="8" fontFamily="monospace">auth · routing</text>

      {/* Auth Service */}
      <rect x="340" y="40" width="110" height="56" rx="8" fill="#141418" stroke="#242428" strokeWidth="1.5" />
      <text x="395" y="62" textAnchor="middle" fill="#e6e6f0" fontSize="9" fontFamily="monospace">Auth Service</text>
      <text x="395" y="78" textAnchor="middle" fill="#64647a" fontSize="8" fontFamily="monospace">JWT · OAuth</text>

      {/* Database */}
      <rect x="185" y="215" width="110" height="56" rx="8" fill="#141418" stroke="#242428" strokeWidth="1.5" />
      <text x="240" y="237" textAnchor="middle" fill="#e6e6f0" fontSize="9" fontFamily="monospace">Database</text>
      <text x="240" y="253" textAnchor="middle" fill="#64647a" fontSize="8" fontFamily="monospace">Postgres · Redis</text>

      {/* Arrows */}
      {/* Frontend → API */}
      <path d="M 140 70 Q 185 70 185 148" stroke="#7c6aff" strokeWidth="1.5" strokeDasharray="4 2" markerEnd="url(#arr)" />
      {/* Auth → API */}
      <path d="M 340 68 Q 295 68 295 120" stroke="#7c6aff" strokeWidth="1.5" strokeDasharray="4 2" />
      {/* API → DB */}
      <path d="M 240 176 L 240 215" stroke="#7c6aff" strokeWidth="1.5" markerEnd="url(#arr)" />

      <defs>
        <marker id="arr" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="#7c6aff" />
        </marker>
      </defs>

      {/* Security shield */}
      <g transform="translate(390, 195)">
        <path d="M25 5 L45 13 L45 30 C45 42 25 50 25 50 C25 50 5 42 5 30 L5 13 Z" fill="#141418" stroke="#4ade80" strokeWidth="1.5" />
        <path d="M17 28 l5 5 10 -10" stroke="#4ade80" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <text x="25" y="60" textAnchor="middle" fill="#4ade80" fontSize="8" fontFamily="monospace">threat</text>
        <text x="25" y="71" textAnchor="middle" fill="#4ade80" fontSize="8" fontFamily="monospace">modeled</text>
      </g>

      {/* ADD/ADR doc stack */}
      <g transform="translate(22, 185)">
        <rect x="4" y="4" width="90" height="64" rx="6" fill="#1e1e26" stroke="#242428" strokeWidth="1" />
        <rect x="0" y="0" width="90" height="64" rx="6" fill="#141418" stroke="#7c6aff" strokeWidth="1.5" />
        <text x="45" y="20" textAnchor="middle" fill="#7c6aff" fontSize="8" fontFamily="monospace">ADD-042.md</text>
        <rect x="10" y="28" width="70" height="5" rx="2.5" fill="#242428" />
        <rect x="10" y="38" width="55" height="5" rx="2.5" fill="#1e1e26" />
        <rect x="10" y="48" width="65" height="5" rx="2.5" fill="#242428" />
        <text x="45" y="76" textAnchor="middle" fill="#64647a" fontSize="7" fontFamily="monospace">ADR · ADD · SOP</text>
      </g>

      {/* Human gate */}
      <rect x="115" y="268" width="250" height="26" rx="13" fill="#141418" stroke="#4ade80" strokeWidth="1.5" />
      <circle cx="132" cy="281" r="5" fill="#4ade80" />
      <text x="142" y="285" fill="#4ade80" fontSize="9" fontFamily="monospace">Human gate: approve architecture</text>
    </svg>
  );
}

function ImplTestDeploySvg() {
  return (
    <svg viewBox="0 0 480 300" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden className="w-full h-full">
      <pattern id="dots3" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
        <circle cx="1" cy="1" r="1" fill="#2a2a30" />
      </pattern>
      <rect width="480" height="300" fill="url(#dots3)" />

      {/* Stage 1: Code */}
      <rect x="20" y="60" width="120" height="160" rx="10" fill="#141418" stroke="#242428" strokeWidth="1.5" />
      <text x="80" y="84" textAnchor="middle" fill="#e6e6f0" fontSize="9" fontFamily="monospace">{ } Code</text>
      <rect x="34" y="96" width="50" height="5" rx="2.5" fill="#7c6aff" opacity="0.8" />
      <rect x="34" y="107" width="76" height="5" rx="2.5" fill="#242428" />
      <rect x="34" y="118" width="60" height="5" rx="2.5" fill="#242428" />
      <rect x="46" y="129" width="68" height="5" rx="2.5" fill="#7c6aff" opacity="0.4" />
      <rect x="46" y="140" width="56" height="5" rx="2.5" fill="#242428" />
      <rect x="34" y="151" width="72" height="5" rx="2.5" fill="#242428" />
      <rect x="34" y="162" width="44" height="5" rx="2.5" fill="#7c6aff" opacity="0.6" />
      {/* Agent badges */}
      <rect x="28" y="185" width="104" height="22" rx="11" fill="#1e1e26" stroke="#242428" strokeWidth="1" />
      <text x="80" y="200" textAnchor="middle" fill="#64647a" fontSize="8" fontFamily="monospace">Engineer · DevOps</text>

      {/* Arrow 1→2 */}
      <path d="M 144 140 L 164 140" stroke="#4ade80" strokeWidth="2" />
      <polygon points="164,135 174,140 164,145" fill="#4ade80" />
      <circle cx="159" cy="128" r="8" fill="#141418" stroke="#4ade80" strokeWidth="1.5" />
      <text x="159" y="132" textAnchor="middle" fill="#4ade80" fontSize="9">✓</text>

      {/* Stage 2: Test */}
      <rect x="178" y="60" width="124" height="160" rx="10" fill="#141418" stroke="#7c6aff" strokeWidth="2" />
      <text x="240" y="84" textAnchor="middle" fill="#e6e6f0" fontSize="9" fontFamily="monospace">✓ Test</text>
      {/* BDD rows */}
      {[
        { y: 96, label: "Given…", c: "#4ade80" },
        { y: 112, label: "  When…", c: "#64647a" },
        { y: 128, label: "  Then…", c: "#7c6aff" },
        { y: 148, label: "Given…", c: "#4ade80" },
        { y: 164, label: "  When…", c: "#64647a" },
        { y: 180, label: "  Then…", c: "#7c6aff" },
      ].map(({ y, label, c }) => (
        <text key={y} x="192" y={y} fill={c} fontSize="8" fontFamily="monospace">{label}</text>
      ))}
      <rect x="186" y="190" width="108" height="18" rx="9" fill="#0f2818" stroke="#4ade80" strokeWidth="1" />
      <text x="240" y="203" textAnchor="middle" fill="#4ade80" fontSize="8" fontFamily="monospace">all scenarios green</text>

      {/* Arrow 2→3 */}
      <path d="M 306 140 L 326 140" stroke="#4ade80" strokeWidth="2" />
      <polygon points="326,135 336,140 326,145" fill="#4ade80" />
      <circle cx="321" cy="128" r="8" fill="#141418" stroke="#4ade80" strokeWidth="1.5" />
      <text x="321" y="132" textAnchor="middle" fill="#4ade80" fontSize="9">✓</text>

      {/* Stage 3: Deploy */}
      <rect x="340" y="60" width="120" height="160" rx="10" fill="#141418" stroke="#242428" strokeWidth="1.5" />
      <text x="400" y="84" textAnchor="middle" fill="#e6e6f0" fontSize="9" fontFamily="monospace">↑ Deploy</text>
      {/* Pipeline stages */}
      {[
        { y: 105, label: "build", done: true },
        { y: 128, label: "staging", done: true },
        { y: 151, label: "smoke test", done: true },
        { y: 174, label: "production", done: false },
      ].map(({ y, label, done }) => (
        <g key={y}>
          <circle cx="360" cy={y - 4} r="6" fill={done ? "#0f2818" : "#1e1e26"} stroke={done ? "#4ade80" : "#7c6aff"} strokeWidth="1.5" />
          {done
            ? <path d={`M${357} ${y - 4} l2 2.5 4.5 -4.5`} stroke="#4ade80" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            : <circle cx="360" cy={y - 4} r="2.5" fill="#7c6aff" />
          }
          <text x="374" y={y} fill={done ? "#64647a" : "#9585ff"} fontSize="8" fontFamily="monospace">{label}</text>
        </g>
      ))}

      {/* Human gate badge */}
      <rect x="110" y="260" width="260" height="26" rx="13" fill="#141418" stroke="#7c6aff" strokeWidth="1.5" />
      <circle cx="127" cy="273" r="5" fill="#7c6aff" />
      <text x="137" y="277" fill="#7c6aff" fontSize="9" fontFamily="monospace">Human gate: approve production</text>
    </svg>
  );
}

// ─── Slide data ───────────────────────────────────────────────────────────────

const SLIDES = [
  {
    phase: "Phase 1",
    phaseLabel: "Idea → Requirement",
    title: "Turn any idea into a testable specification",
    bullets: [
      "The crew reads your ticket, brief, or rough idea and gets to work immediately.",
      "The Product Owner and Scrum Master decompose it into user stories, acceptance criteria, and BDD scenarios — backed by your SOPs and domain glossary.",
      "Dependencies are mapped, ambiguities surfaced, and edge cases documented before a single line of design or code is written.",
      "The output is a structured requirement spec you can read, question, and refine.",
    ],
    gate: "You review and approve the requirement spec. Nothing moves to architecture until you sign off.",
    agents: ["Product Owner", "Scrum Master"],
    Visual: IdeaToReqSvg,
  },
  {
    phase: "Phase 2",
    phaseLabel: "Requirement → Architecture",
    title: "Design guided by your team's history and best practices",
    bullets: [
      "The Architect reads every ADR, ADD, and SOP in your designs/ directory — it knows what decisions your team has already made and why.",
      "Component boundaries, data flows, API contracts, and database schemas are designed to fit your existing system, not a generic template.",
      "The Security Lead threat-models the design before any code is written, producing an OTM threat model and flagging risks early.",
      "Every decision is committed as an ADD or ADR document, visible in your PR diff alongside the code it governs.",
    ],
    gate: "You review the architecture documents. The crew writes no code until you approve the design.",
    agents: ["Architect", "Security Lead", "Chief Architect (you)"],
    Visual: ArchDesignSvg,
  },
  {
    phase: "Phase 3",
    phaseLabel: "Implementation → Testing → Deployment",
    title: "Full-stack delivery with every best practice enforced",
    bullets: [
      "The Engineer implements across the full stack — backend, frontend, migrations, and infra changes — guided by the approved design and your coding standards.",
      "QA Lead authors and runs BDD scenarios. The suite must be green before the crew proceeds; no exceptions.",
      "Security Lead audits code for OWASP vulnerabilities. Compliance Lead checks regulatory requirements. Release Engineer issues a formal go/no-go.",
      "DevOps Lead coordinates CI/CD. The crew promotes to staging, runs smoke tests, and prepares everything for production — then stops and waits for you.",
    ],
    gate: "You make the final call to promote to production. The crew does everything up to that moment.",
    agents: ["Engineer", "QA Lead", "Security Lead", "DevOps Lead", "Release Engineer"],
    Visual: ImplTestDeploySvg,
  },
];

// ─── Carousel ─────────────────────────────────────────────────────────────────

export function SdlcCarousel() {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);

  const prev = useCallback(() => setActive((a) => (a - 1 + SLIDES.length) % SLIDES.length), []);
  const next = useCallback(() => setActive((a) => (a + 1) % SLIDES.length), []);

  useEffect(() => {
    if (paused) return;
    const t = setInterval(next, 7000);
    return () => clearInterval(t);
  }, [paused, next]);

  const slide = SLIDES[active];

  return (
    <section
      className="px-6 py-24"
      style={{ background: "var(--surface)", borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="max-w-6xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-3">The full SDLC, automated</h2>
        <p className="text-center text-sm mb-12" style={{ color: "var(--muted)" }}>
          From raw idea to production — agents do the heavy lifting at every stage, humans make the calls that matter.
        </p>

        {/* Phase tabs */}
        <div className="flex gap-2 mb-10 justify-center flex-wrap">
          {SLIDES.map((s, i) => (
            <button
              key={s.phase}
              onClick={() => { setActive(i); setPaused(true); }}
              className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all"
              style={{
                background: i === active ? "var(--accent)" : "var(--bg)",
                color: i === active ? "#fff" : "var(--muted)",
                border: `1px solid ${i === active ? "var(--accent)" : "var(--border)"}`,
              }}
            >
              <span
                className="text-xs font-mono opacity-70"
                style={{ color: i === active ? "rgba(255,255,255,0.7)" : "var(--muted)" }}
              >
                {s.phase}
              </span>
              {s.phaseLabel}
            </button>
          ))}
        </div>

        {/* Slide */}
        <div
          className="rounded-2xl overflow-hidden grid lg:grid-cols-2 gap-0"
          style={{ border: "1px solid var(--border)", background: "var(--bg)" }}
        >
          {/* Text panel */}
          <div className="p-8 lg:p-12 flex flex-col justify-between">
            <div>
              <div
                className="inline-block text-xs font-mono px-2 py-0.5 rounded mb-5"
                style={{ background: "var(--surface)", color: "var(--accent)", border: "1px solid var(--border)" }}
              >
                {slide.phaseLabel}
              </div>
              <h3 className="text-2xl font-bold mb-6 leading-tight">{slide.title}</h3>
              <ul className="flex flex-col gap-3 mb-8">
                {slide.bullets.map((b) => (
                  <li key={b} className="flex gap-3 text-sm leading-relaxed" style={{ color: "var(--muted)" }}>
                    <span style={{ color: "var(--accent)", flexShrink: 0, marginTop: 2 }}>→</span>
                    {b}
                  </li>
                ))}
              </ul>
            </div>

            {/* Human gate */}
            <div
              className="rounded-lg p-4 text-sm"
              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span
                  className="text-xs px-2 py-0.5 rounded font-mono"
                  style={{ background: "#0f2818", color: "#4ade80", border: "1px solid #1a4028" }}
                >
                  Human gate
                </span>
              </div>
              <p style={{ color: "var(--muted)" }}>{slide.gate}</p>
            </div>

            {/* Agents involved */}
            <div className="flex flex-wrap gap-2 mt-4">
              {slide.agents.map((a) => (
                <span
                  key={a}
                  className="text-xs px-2.5 py-1 rounded-full"
                  style={{ background: "var(--surface)", color: "var(--muted)", border: "1px solid var(--border)" }}
                >
                  {a}
                </span>
              ))}
            </div>
          </div>

          {/* Visual panel */}
          <div
            className="relative flex items-center justify-center p-6 lg:p-8 min-h-[280px]"
            style={{ background: "#0e0e12", borderLeft: "1px solid var(--border)" }}
          >
            <div className="w-full max-w-md">
              <slide.Visual />
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-center gap-6 mt-8">
          <button
            onClick={prev}
            className="w-9 h-9 rounded-full flex items-center justify-center transition-colors hover:bg-white/10"
            style={{ border: "1px solid var(--border)", color: "var(--muted)" }}
            aria-label="Previous slide"
          >
            ←
          </button>
          <div className="flex gap-2">
            {SLIDES.map((_, i) => (
              <button
                key={i}
                onClick={() => { setActive(i); setPaused(true); }}
                className="rounded-full transition-all"
                style={{
                  width: i === active ? 24 : 8,
                  height: 8,
                  background: i === active ? "var(--accent)" : "var(--border)",
                }}
                aria-label={`Go to slide ${i + 1}`}
              />
            ))}
          </div>
          <button
            onClick={next}
            className="w-9 h-9 rounded-full flex items-center justify-center transition-colors hover:bg-white/10"
            style={{ border: "1px solid var(--border)", color: "var(--muted)" }}
            aria-label="Next slide"
          >
            →
          </button>
        </div>
      </div>
    </section>
  );
}
