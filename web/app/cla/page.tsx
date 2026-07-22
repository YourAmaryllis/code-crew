import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contributor License Agreement — code-crew",
  description: "CLA for contributors to code-crew. Signing is automated via CLA Assistant on your first pull request.",
};

export default function ClaPage() {
  return (
    <div className="min-h-screen flex flex-col" style={{ color: "var(--text)" }}>
      {/* Nav */}
      <nav
        className="flex items-center justify-between px-6 py-4"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <Link
          href="/"
          className="font-mono font-bold tracking-tight hover:opacity-80 transition-opacity"
          style={{ color: "var(--text)" }}
        >
          ← code-crew
        </Link>
      </nav>

      <main className="flex-1 px-6 py-16 max-w-2xl mx-auto w-full">
        <div className="mb-10">
          <h1 className="text-3xl font-bold mb-3">Contributor License Agreement</h1>
          <p className="text-sm leading-relaxed" style={{ color: "var(--muted)" }}>
            Before your first pull request is merged, you will be prompted to sign this agreement
            via <a href="https://cla-assistant.io" target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent)" }}>CLA Assistant</a>.
            The signing process is automated — no email or form required.
          </p>
        </div>

        <div
          className="rounded-lg p-6 mb-10 text-sm leading-relaxed"
          style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--muted)" }}
        >
          Thank you for contributing to code-crew. By submitting a pull request or otherwise
          contributing code, documentation, or other material to this repository, you agree to
          the following terms.
        </div>

        <article className="flex flex-col gap-10">
          <Section number="1" title="Grant of copyright license">
            You grant <strong style={{ color: "var(--text)" }}>Arthur Tsang / YourAmaryllis</strong> (the "Maintainer") a
            perpetual, worldwide, non-exclusive, royalty-free, irrevocable copyright license to reproduce,
            prepare derivative works of, publicly display, publicly perform, sublicense, and distribute
            your contributions and such derivative works, under any license the Maintainer chooses
            (including proprietary licenses).
          </Section>

          <Section number="2" title="Grant of patent license">
            You grant the Maintainer a perpetual, worldwide, non-exclusive, royalty-free, irrevocable
            patent license to make, use, sell, offer to sell, import, and otherwise transfer the work,
            where such license applies to patent claims licensable by you that are necessarily infringed
            by your contribution alone or by the combination of your contribution with the project.
          </Section>

          <Section number="3" title="You have the right to grant these licenses">
            <p className="mb-3">You represent that:</p>
            <ul className="flex flex-col gap-2 pl-4">
              {[
                "The contribution is your original work, or you have the right to submit it.",
                "If your employer has rights to intellectual property you create, you have received permission to make the contribution on behalf of your employer.",
                "The contribution does not include third-party material you are not licensed to contribute.",
              ].map((item) => (
                <li key={item} className="flex gap-2">
                  <span style={{ color: "var(--accent)" }} aria-hidden>—</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </Section>

          <Section number="4" title="The project remains open source">
            The AGPL-3.0 version of this project will always remain freely available. This CLA enables
            dual licensing (see{" "}
            <a href="https://github.com/arthurtsang/code-crew/blob/main/COMMERCIAL.md" target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent)" }}>
              COMMERCIAL.md
            </a>
            ) but does not affect your right to use the software under AGPL-3.0.
          </Section>
        </article>

        <div
          className="mt-16 rounded-lg p-6"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
        >
          <h2 className="font-semibold mb-3">How to sign</h2>
          <p className="text-sm leading-relaxed mb-4" style={{ color: "var(--muted)" }}>
            Signing is automated. When you open your first pull request against the{" "}
            <a href="https://github.com/arthurtsang/code-crew" target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent)" }}>
              code-crew repository
            </a>
            , CLA Assistant will post a comment asking you to sign. Click the link in that comment,
            authenticate with GitHub, and you are done — no separate form, no email.
          </p>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            Questions?{" "}
            <a href="mailto:arthur@youramaryllis.com" style={{ color: "var(--accent)" }}>
              arthur@youramaryllis.com
            </a>
          </p>
        </div>
      </main>

      <footer
        className="px-6 py-8 text-xs text-center"
        style={{ borderTop: "1px solid var(--border)", color: "var(--muted)" }}
      >
        © {new Date().getFullYear()} YourAmaryllis ·{" "}
        <Link href="/" className="hover:text-white transition-colors">code-crew</Link>
      </footer>
    </div>
  );
}

function Section({
  number,
  title,
  children,
}: {
  number: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="font-semibold mb-3 flex items-baseline gap-2">
        <span
          className="font-mono text-xs px-1.5 py-0.5 rounded"
          style={{ background: "var(--code-bg, #18181e)", color: "var(--accent)" }}
        >
          §{number}
        </span>
        {title}
      </h2>
      <div className="text-sm leading-relaxed" style={{ color: "var(--muted)" }}>
        {children}
      </div>
    </section>
  );
}
