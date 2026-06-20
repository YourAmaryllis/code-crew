# Decision: openclaude — Not Adopted

**Date:** 2026-06-19
**Decision:** Not adopted. No further evaluation planned unless scope changes materially.

---

## What openclaude is

openclaude (github.com/Gitlawb/openclaude) is an open-source coding-agent CLI built in Node.js. It provides a terminal-first workflow — prompts, tools, agents, MCP, slash commands, streaming output — and works across multiple LLM providers: OpenAI-compatible APIs, Gemini, GitHub Models, Codex, Ollama, and others. It is MIT-licensed and positioned as an open alternative to Claude Code that isn't locked to the Anthropic API.

It has a VS Code extension, a provider profile system, BDD-style agents, and a ClawHub marketplace for community skills. It spawns Claude Code sessions via ACP, meaning gstack skills work inside it when Claude Code is installed.

---

## Why it was evaluated

The code-crew REPL (`code_crew/repl.py`) handles the terminal UI: profile loading, slash commands, streaming task status. We evaluated whether openclaude could replace or underpin this layer — providing a maintained, community-backed TUI instead of a custom prompt_toolkit implementation.

---

## Why it was not adopted

**It is not a library.** openclaude is a standalone CLI application written in TypeScript/Node.js. It has no Python API, no importable module, no embedding interface. Integrating it with code-crew would require spawning a child process and communicating over stdin/stdout — an IPC layer with no obvious benefit over the current Python implementation.

**Wrong runtime.** code-crew is a Python application using CrewAI, Bedrock, and the Python AWS SDK. openclaude is Node.js. A Python → Node.js → Python bridge (to call CrewAI agents from an openclaude shell) adds a process boundary, a serialisation layer, and a second runtime to install and version-manage. The cost is concrete; the benefit is aesthetic.

**The existing REPL does what we need.** `code_crew/repl.py` with prompt_toolkit handles slash commands, streaming output, profile selection, and ANSI rendering. The specific problems it has had (cursor flicker, verbose CrewAI output, ContextVar propagation) were all resolved without replacing the framework. There is no remaining UX gap that openclaude fills.

**Different target user.** openclaude is designed for developers who want to use multiple AI providers from one CLI — it solves provider lock-in. code-crew is Bedrock-only by design (IAM auth, consolidated billing, Bedrock Guardrails, no API key sprawl). The provider-agnostic positioning of openclaude is not a feature we want.

---

## What would change this decision

If code-crew ever needs to support multiple LLM providers simultaneously (e.g. routing some agents to OpenAI, others to Bedrock), openclaude's provider abstraction layer becomes relevant — but that's a CrewAI `LLM` configuration problem, not a REPL problem.

If the requirements-crew or post-launch-crew needs a conversational interface that is closer to a general-purpose AI assistant than a pipeline runner, openclaude's chat-first design might be a better fit than extending the current REPL. At that point, a fresh evaluation is warranted.

---

## Related

- [code-crew design doc](code-crew.md)
- [comparison-gstack](comparison-gstack.md) — gstack also integrates with openclaude via ACP; relevant if gstack adoption is reconsidered
