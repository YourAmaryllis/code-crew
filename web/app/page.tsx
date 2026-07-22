import Link from "next/link";

const AGENTS = [
  { role: "Scrum Master", icon: "⚙️", desc: "Sprint planning, ticket decomposition, flow coordination" },
  { role: "Architect", icon: "🏛️", desc: "Design docs (ADDs/ADRs), component structure, dependency decisions" },
  { role: "Engineer", icon: "💻", desc: "Full-stack implementation: backend, frontend, migrations, tests" },
  { role: "QA Lead", icon: "🧪", desc: "BDD authoring, test strategy, acceptance criteria verification" },
  { role: "Product Owner", icon: "📋", desc: "BDD scenario review, acceptance criteria, DoD sign-off" },
  { role: "Security Lead", icon: "🔒", desc: "OWASP review, OTM threat modeling, vulnerability triage" },
  { role: "DevOps Lead", icon: "🚀", desc: "CI/CD coordination, infra changes, staging promotion" },
  { role: "Release Engineer", icon: "📦", desc: "Release notes, launch go/no-go, smoke test verification" },
];

const COMMANDS = [
  { cmd: "explore [path]", desc: "Scan project, detect stacks, build code index" },
  { cmd: "design <KEY>", desc: "Architect + security → ADD/ADR before any code" },
  { cmd: "issue <KEY>", desc: "Full SDLC: sprint planning → DoD → staging" },
  { cmd: "sprint <name>", desc: "Run all tickets in a sprint in parallel" },
  { cmd: "threat [scope]", desc: "OTM threat model + Threat Dragon JSON export" },
  { cmd: "audit", desc: "Full codebase audit: arch · security · compliance · domain" },
  { cmd: "ask <agent> <q>", desc: "Ask any agent a direct question" },
];

function CopyBlock({ code }: { code: string }) {
  return (
    <pre
      className="rounded-lg px-5 py-4 text-sm overflow-x-auto"
      style={{ background: "var(--code-bg)", color: "var(--text)", border: "1px solid var(--border)" }}
    >
      <code>{code}</code>
    </pre>
  );
}

export default function Home() {
  return (
    <div className="flex flex-col min-h-screen" style={{ color: "var(--text)" }}>
      {/* Nav */}
      <nav
        className="sticky top-0 z-50 flex items-center justify-between px-6 py-4"
        style={{ background: "rgba(11,11,13,0.85)", backdropFilter: "blur(12px)", borderBottom: "1px solid var(--border)" }}
      >
        <span className="font-mono font-bold tracking-tight" style={{ color: "var(--text)" }}>
          code-crew
        </span>
        <div className="flex items-center gap-6 text-sm" style={{ color: "var(--muted)" }}>
          <a href="#agents" className="hover:text-white transition-colors">Agents</a>
          <a href="#commands" className="hover:text-white transition-colors">Commands</a>
          <a href="#quickstart" className="hover:text-white transition-colors">Quick start</a>
          <Link href="/cla" className="hover:text-white transition-colors">CLA</Link>
          <a
            href="https://github.com/YourAmaryllis/code-crew"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 hover:text-white transition-colors"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.745 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
            GitHub
          </a>
        </div>
      </nav>

      <main className="flex-1">
        {/* Hero */}
        <section className="flex flex-col items-center text-center px-6 pt-28 pb-24 max-w-4xl mx-auto">
          <div
            className="inline-block font-mono text-xs px-3 py-1 rounded-full mb-8"
            style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--muted)" }}
          >
            Open source · AGPL-3.0
          </div>
          <h1 className="text-5xl sm:text-6xl font-bold tracking-tight mb-6 leading-[1.1]">
            Your AI{" "}
            <span style={{ color: "var(--accent)" }}>Development Team</span>
          </h1>
          <p className="text-lg max-w-2xl mb-10 leading-relaxed" style={{ color: "var(--muted)" }}>
            Eight specialised AI agents — Scrum Master, Architect, Engineer, QA Lead, Product Owner,
            Security Lead, DevOps Lead, and Release Engineer — covering the full SDLC from ticket to production.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 mb-12 items-center">
            <a
              href="https://github.com/YourAmaryllis/code-crew"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 font-medium px-6 py-3 rounded-lg transition-colors"
              style={{ background: "var(--accent)", color: "#fff" }}
            >
              View on GitHub
            </a>
            <a
              href="#quickstart"
              className="flex items-center gap-2 font-medium px-6 py-3 rounded-lg transition-colors"
              style={{ background: "var(--surface)", color: "var(--text)", border: "1px solid var(--border)" }}
            >
              Quick start ↓
            </a>
          </div>
          <CopyBlock code="pip install code-crew" />
        </section>

        {/* What it does */}
        <section
          className="px-6 py-20"
          style={{ background: "var(--surface)", borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}
        >
          <div className="max-w-4xl mx-auto grid sm:grid-cols-3 gap-8">
            {[
              {
                title: "Issue tracker → code",
                body: "Point it at a Jira, Linear, or GitHub Issue ticket. The crew reads the ticket, plans the sprint, designs the solution, writes the code, and gets it through review.",
              },
              {
                title: "Your knowledge base",
                body: "Agents load your ADRs, ADDs, and SOPs from a designs/ directory. Design decisions and compliance requirements shape every output, not just the LLM's prior knowledge.",
              },
              {
                title: "Human stays in control",
                body: "Agents never push to main, apply Terraform, or promote to production. Every gate requires a human decision. The crew prepares; you approve.",
              },
            ].map((f) => (
              <div key={f.title}>
                <h3 className="font-semibold mb-2" style={{ color: "var(--text)" }}>{f.title}</h3>
                <p className="text-sm leading-relaxed" style={{ color: "var(--muted)" }}>{f.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Agents */}
        <section id="agents" className="px-6 py-24 max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold mb-2 text-center">The crew</h2>
          <p className="text-center mb-12 text-sm" style={{ color: "var(--muted)" }}>
            Each agent has a distinct role, goal, and knowledge set — no monolithic "do everything" prompt.
          </p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {AGENTS.map((a) => (
              <div
                key={a.role}
                className="rounded-lg p-5"
                style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
              >
                <div className="text-2xl mb-3">{a.icon}</div>
                <div className="font-semibold text-sm mb-1">{a.role}</div>
                <div className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>{a.desc}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Commands */}
        <section
          id="commands"
          className="px-6 py-24"
          style={{ background: "var(--surface)", borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}
        >
          <div className="max-w-3xl mx-auto">
            <h2 className="text-3xl font-bold mb-2 text-center">Commands</h2>
            <p className="text-center mb-12 text-sm" style={{ color: "var(--muted)" }}>
              Every command works as a CLI call or a <code style={{ color: "var(--accent)" }}>/slash</code> command inside the interactive REPL.
            </p>
            <div className="rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)" }}>
              {COMMANDS.map((c, i) => (
                <div
                  key={c.cmd}
                  className="flex items-start gap-4 px-5 py-4"
                  style={{
                    borderTop: i === 0 ? "none" : "1px solid var(--border)",
                    background: i % 2 === 0 ? "var(--surface)" : "var(--bg)",
                  }}
                >
                  <code className="text-sm shrink-0 w-40" style={{ color: "var(--accent)", fontFamily: "var(--font-geist-mono)" }}>
                    {c.cmd}
                  </code>
                  <span className="text-sm" style={{ color: "var(--muted)" }}>{c.desc}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Quick start */}
        <section id="quickstart" className="px-6 py-24 max-w-3xl mx-auto">
          <h2 className="text-3xl font-bold mb-2 text-center">Quick start</h2>
          <p className="text-center mb-12 text-sm" style={{ color: "var(--muted)" }}>
            From install to first implementation run in five steps.
          </p>
          <div className="flex flex-col gap-6">
            {[
              { n: "1", label: "Install", code: "pip install code-crew" },
              { n: "2", label: "Configure LLM and issue tracker", code: "cp .config.example.yaml ~/.code-crew/config.yaml\n# edit: bedrock.model_id, bedrock.region, issue_tracker" },
              { n: "3", label: "Add designs/ as a submodule", code: "cd /path/to/your-platform-repo\ngit submodule add git@github.com:your-org/designs.git designs" },
              { n: "4", label: "Initialise the project", code: "code-crew init" },
              { n: "5", label: "Explore, design, implement", code: "code-crew explore\ncode-crew design PROJ-123\ncode-crew issue PROJ-123" },
            ].map((s) => (
              <div key={s.n} className="flex gap-4">
                <div
                  className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
                  style={{ background: "var(--accent-dim, #3d3480)", color: "var(--accent)" }}
                  aria-hidden
                >
                  {s.n}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium mb-2">{s.label}</div>
                  <CopyBlock code={s.code} />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* License */}
        <section
          className="px-6 py-20"
          style={{ background: "var(--surface)", borderTop: "1px solid var(--border)" }}
        >
          <div className="max-w-3xl mx-auto grid sm:grid-cols-2 gap-10">
            <div>
              <h3 className="font-semibold mb-3">Open source — AGPL-3.0</h3>
              <p className="text-sm leading-relaxed" style={{ color: "var(--muted)" }}>
                Use, modify, and distribute freely. Any modified version you run as a network service
                must also be made available under AGPL-3.0.
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-3">Commercial license</h3>
              <p className="text-sm leading-relaxed" style={{ color: "var(--muted)" }}>
                Need to embed code-crew in a proprietary product or offer it as a hosted service without
                the copyleft obligation?{" "}
                <a href="mailto:arthur@youramaryllis.com" style={{ color: "var(--accent)" }}>
                  Get in touch.
                </a>
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer
        className="px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs"
        style={{ borderTop: "1px solid var(--border)", color: "var(--muted)" }}
      >
        <span>© {new Date().getFullYear()} YourAmaryllis. code-crew is released under AGPL-3.0.</span>
        <div className="flex items-center gap-5">
          <a href="https://github.com/YourAmaryllis/code-crew" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">GitHub</a>
          <Link href="/cla" className="hover:text-white transition-colors">CLA</Link>
          <a href="mailto:arthur@youramaryllis.com" className="hover:text-white transition-colors">Contact</a>
        </div>
      </footer>
    </div>
  );
}
