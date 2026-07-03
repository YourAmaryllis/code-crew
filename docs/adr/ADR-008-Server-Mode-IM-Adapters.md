# ADR-008: Server Mode with IM Adapter Layer

**Status:** Proposed  
**Date:** 2026-07-03  
**Related:**
- [ADD-007: Server mode design](../add/ADD-007-Server-Mode-IM-Adapters.md)
- [ADR-007: Python flow orchestration](ADR-007-Python-Flow-Orchestration.md)
- [SAD-001: code-crew system architecture](../sad/SAD-001-code-crew.md)

---

## Context

The current CLI/REPL mode requires a developer to run `code-crew` locally in a terminal. This creates two constraints for teams operating at scale:

**Synchronous coupling.** The terminal session must remain open for the duration of a run. Full SDLC flows routinely take 30–60 minutes end-to-end. During that time, the developer's machine cannot sleep, and the flow is lost if the terminal is closed. This makes `code-crew` impractical for use during meetings, travel, or across time zones.

**Single-user access.** Only the person who started the terminal session receives flow progress updates. Other stakeholders who need to participate in human gates — the product owner approving BDD scenarios, the architect reviewing an ADD draft, the release engineer making a go/no-go call — have no visibility into an in-progress flow and cannot unblock it without asking the developer to relay messages.

Engineering teams already coordinate in IM tools: Slack for most, Telegram for smaller teams, WhatsApp and Signal for distributed or privacy-sensitive contexts. Running flows from those platforms gives teams two things:

1. Shared visibility — any team member in the channel sees flow progress and can contribute at gate points.
2. Always-on execution — the server runs continuously in a container; no laptop is required.

### Options considered

**Option A: Per-platform bots (separate implementations)**

Build a Slack app, a Telegram bot, etc., each with its own event handling, command parser, and output formatter, all wired directly to `TicketFlow`.

- Pros: can exploit platform-native components (Slack Block Kit interactive messages, Telegram inline keyboards, WhatsApp quick-reply buttons).
- Cons: each platform duplicates the command parser, gate-injection logic, output chunker, and flow context model. Adding a fifth platform requires writing all of it again. Bug fixes must be applied in four places.

**Option B: Unified adapter interface + platform adapters**

Define an abstract `IMAdapter` base class with a fixed interface (`parse_command`, `send_message`, `send_file`, `verify_request`). Implement it once per platform. The core server and flow layer calls the interface; adapters handle all platform-specific wire formats.

- Pros: command parsing, rate limiting, flow isolation, and human gate logic live once in the server layer. Adding a platform is an adapter class. Core pipeline (flows, crew, agents) is unchanged.
- Cons: the interface is the lowest common denominator — some platform features (interactive components, thread replies) require adapter-specific extensions beyond the base interface.

**Option C: Third-party multi-platform bot framework**

Use an existing platform like Botpress, Rasa, or Kommunicate to handle platform integrations.

- Pros: pre-built connectors for many platforms, visual flow editor for bot responses.
- Cons: adds a large external dependency, introduces a separate deployment and operational burden, limits output formatting control, and is architecturally mismatched (those tools are designed for conversational bots, not long-running LLM pipeline orchestration).

## Decision

Implement **Option B: server mode with a unified `IMAdapter` interface**.

The specific choices within that option:

1. **`code-crew server [--host HOST] [--port PORT]`** starts a long-running FastAPI + uvicorn process. Slash commands are the same as the REPL (e.g. `/issue PROJ-123`, `/feedback <message>`); the server dispatches them to the same flows.

2. **`IMAdapter` abstract base class** defines four methods:

   ```python
   class IMAdapter(ABC):
       @abstractmethod
       async def verify_request(self, request: Request) -> bool: ...

       @abstractmethod
       def parse_command(self, message: IMMessage) -> Command | None: ...

       @abstractmethod
       async def send_message(self, channel: str, text: str) -> None: ...

       @abstractmethod
       async def send_file(self, channel: str, path: Path, caption: str) -> None: ...
   ```

3. **Platform adapters at launch:** `SlackAdapter` (Events API webhooks + Socket Mode), `TelegramAdapter` (webhook or long-polling), `WhatsAppAdapter` (Business Cloud API webhooks), `SignalAdapter` (`signal-cli` subprocess, polling).

4. **Flow isolation** by `(platform, channel_id)`: each channel context gets its own `TicketFlow` / `DesignFlow` instance, asyncio task, and checkpoint namespace. Flows in different channels run concurrently without interference.

5. **Human gate model**: when a flow pauses for human input (`AskHumanTool`), the adapter posts a message in the IM channel describing what is needed. Any team member in the channel replies with `/feedback <message>` to unblock the flow. This broadens the pool of people who can participate in gates beyond the original flow initiator.

6. **Auth model**: IM user identity is checked against per-platform allow-lists (`allowed_channels` for channel-based platforms, `allowed_user_ids` for DM-based platforms). Messages from unlisted sources receive a rejection reply and are not processed. No credentials are accepted via IM — the server runs with a pre-configured profile.

7. **Output formatting**: Rich ANSI escape sequences are stripped from flow output before sending. Text is chunked to each platform's message-length limit (Slack: 3 000 chars; Telegram: 4 096 chars; WhatsApp: 4 096 chars). File outputs (audit reports, design doc drafts, OTM YAML) are sent as file attachments via `send_file`.

8. **Webhook security**: all inbound webhook requests are verified against platform-provided signing secrets before any content is processed. Requests that fail verification return HTTP 401 immediately.

9. **Core pipeline unchanged**: `TicketFlow`, `DesignFlow`, `crew.py`, agent definitions, task definitions, and all tools are identical between CLI and server mode. The server is an I/O adapter, not a pipeline change.

## Consequences

**Positive:**

- Any team member in an authorised channel can trigger, observe, or unblock a flow — no terminal access or installation required.
- Human gates are visible to the team, not locked to a single developer's terminal. This closes the gap where a flow was stalled waiting for a product owner who had no way to know a response was needed.
- The server runs continuously in a container — flows are not lost if a developer's machine goes to sleep or disconnects.
- Adding a new IM platform requires only implementing the `IMAdapter` interface; the server, dispatcher, flow logic, and agents require no changes.
- Phased rollout is straightforward: ship Slack support in Phase 1, add Telegram in Phase 2, WhatsApp and Signal in Phase 3.

**Negative / Risks:**

- Webhook endpoints for Slack, Telegram, and WhatsApp must be publicly reachable via HTTPS. For Slack in firewall environments, Socket Mode (WSS outbound) can replace the inbound webhook, but the other platforms have no equivalent.
- IM platform APIs change. Each adapter requires maintenance when platforms deprecate API versions or change webhook schemas.
- WhatsApp Business API requires a verified business account and Meta app approval — setup takes 1–2 weeks and involves business verification, which is a barrier for small teams.
- `signal-cli` is a community-maintained tool with no official API. The `SignalAdapter` depends on a subprocess interface that can break on `signal-cli` updates or when the Signal protocol changes.
- Multi-user flows create ambiguity at human gates: any channel member can reply `/feedback`, which means a careless message can inadvertently unblock a gate. Mitigation: only messages beginning with `/feedback` (parsed as a `FeedbackCommand`) are routed to the flow; free-text messages in the channel are ignored.
- In-progress flows lose their asyncio task on container restart. Flows in the `AWAITING CI` state (serialised to `flow-state.json`) survive restart via `/resume`, but flows mid-task do not. The adapter posts a "flow interrupted" message to the channel on reconnect.

**Operational:**

- `code-crew server` starts the service. `GET /health` returns `{"status": "ok", "active_flows": N}`.
- `shared/adapters/` — `IMAdapter` base class (`base.py`) + per-platform modules (`slack.py`, `telegram.py`, `whatsapp.py`, `signal.py`).
- `server.auth` config section controls channel and user allow-lists and profile mapping per channel.
- All platform tokens stored as environment variables (`SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `TELEGRAM_BOT_TOKEN`, `WA_ACCESS_TOKEN`, `SIGNAL_PHONE_NUMBER`). These are never committed to git, logged, or transmitted via IM.
- `/status` command in IM returns the list of active flows in the channel and their current task.
- The `[server]` pip extra installs FastAPI, uvicorn, and adapter-specific dependencies; the core package does not depend on them.
