# ADD-007: Server Mode and IM Adapter Design

**Status:** Proposed  
**Date:** 2026-07-03  
**Related:**
- [ADR-008: Server mode with IM adapter layer](../adr/ADR-008-Server-Mode-IM-Adapters.md)
- [ADR-007: Python flow orchestration](../adr/ADR-007-Python-Flow-Orchestration.md)
- [SAD-001: code-crew system architecture](../sad/SAD-001-code-crew.md)
- [ADD-005: Ticket and sprint flow design](ADD-005-Ticket-And-Sprint-Flow.md)

---

## Purpose

This document describes the detailed design of server mode: the `code-crew server` process, the `IMAdapter` interface, per-platform adapters, flow isolation, human gate model, output formatting, configuration, and deployment.

---

## User Journey

A team has code-crew running as a container and connected to their Slack workspace.

1. Engineer types `/issue PROJ-123` in `#engineering`
2. Slack sends a webhook to the server; `SlackAdapter` parses the slash command
3. Server dispatches `TicketFlow` for `PROJ-123` as an asyncio task keyed to `(slack, C0123456)`
4. As each task completes, the adapter posts a summary to `#engineering`
5. When BDD scenarios are ready for review, the bot posts:
   > BDD scenarios ready for review. Reply `/feedback APPROVED` or `/feedback <revision notes>` to continue.
6. Product owner reads the scenarios and replies `/feedback APPROVED` in the channel
7. `SlackAdapter` routes the message to `inject_feedback()` on the active flow
8. Flow continues through implementation, code review, security review, staging
9. At `launch_decision`, bot posts the go/no-go recommendation and waits for `/feedback GO` or `/feedback NO GO`
10. On completion, bot posts a summary with links to the PR and Jira ticket

No one needed a terminal. Any team member in the channel could see status or unblock a gate.

---

## Server Process Architecture

```
code-crew server [--host 0.0.0.0] [--port 8080]
```

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI + uvicorn                                       │
│                                                          │
│  POST /webhooks/slack          → SlackAdapter            │
│  POST /webhooks/telegram       → TelegramAdapter         │
│  POST /webhooks/whatsapp       → WhatsAppAdapter         │
│  GET  /health                  → {"status":"ok","flows":N}│
│  GET  /status                  → active flow list        │
└────────────────────┬────────────────────────────────────┘
                     │ Command
          ┌──────────▼──────────┐
          │  FlowDispatcher     │
          │                     │
          │  active_flows dict  │
          │  (platform,channel) │
          │  → asyncio.Task     │
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │  TicketFlow /        │
          │  DesignFlow /        │  (unchanged from CLI)
          │  UxFlow / etc.       │
          └─────────────────────┘
```

Key design points:
- One asyncio task per active `(platform, channel_id)` — flows are independent
- `FlowDispatcher` holds the `active_flows` dict and serialises dispatch per channel (no two tasks for the same channel run simultaneously)
- Adapter instances are singletons — shared across all flows for that platform
- Signal polling adapters run as a separate background task, not a webhook handler

---

## `IMAdapter` Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Request


@dataclass
class IMMessage:
    platform: str           # "slack" | "telegram" | "whatsapp" | "signal"
    channel_id: str         # channel or chat ID
    user_id: str            # sender identity
    user_name: str          # display name
    text: str               # raw message text
    raw: dict[str, Any]     # original platform payload


@dataclass
class Command:
    name: str               # "issue" | "design" | "feedback" | "abort" | "status" | ...
    args: list[str]         # positional args after the command name
    message: IMMessage      # original message for reply routing


class IMAdapter(ABC):
    """Abstract base class for IM platform adapters."""

    @abstractmethod
    async def verify_request(self, request: Request) -> bool:
        """Verify the request's signature against the platform signing secret.
        Return False to reject with HTTP 401 before any content is processed."""

    @abstractmethod
    def parse_command(self, message: IMMessage) -> Command | None:
        """Parse a raw IM message into a Command.
        Return None if the message is not a recognised command (ignore it)."""

    @abstractmethod
    async def send_message(self, channel: str, text: str) -> None:
        """Send a text message to the channel. Text is pre-formatted (ANSI stripped,
        chunked to platform limit). May be called multiple times for long output."""

    @abstractmethod
    async def send_file(self, channel: str, path: Path, caption: str) -> None:
        """Upload a file to the channel (e.g. audit report, OTM YAML, ADD draft)."""

    async def send_long(self, channel: str, text: str) -> None:
        """Default implementation: chunk text to platform limit and send each chunk."""
        limit = self.message_length_limit
        chunks = [text[i:i+limit] for i in range(0, len(text), limit)]
        for chunk in chunks:
            await self.send_message(channel, chunk)

    @property
    def message_length_limit(self) -> int:
        """Platform message character limit. Override in each adapter."""
        return 3000
```

---

## Platform Adapters

| Adapter | Mechanism | Auth | Msg limit | File support | Webhook verify |
|---------|-----------|------|-----------|-------------|---------------|
| `SlackAdapter` | Events API webhooks (primary); Socket Mode (firewall environments) | `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` | 3 000 chars | `files.upload` | HMAC-SHA256 signing secret |
| `TelegramAdapter` | Webhook (primary); `getUpdates` long-poll fallback | `TELEGRAM_BOT_TOKEN` | 4 096 chars | `sendDocument` | Secret token in header |
| `WhatsAppAdapter` | WhatsApp Business Cloud API webhooks | `WA_ACCESS_TOKEN`, `WA_VERIFY_TOKEN` | 4 096 chars | `media/upload` + message | Hub verify challenge + HMAC |
| `SignalAdapter` | `signal-cli` subprocess, polling loop | `SIGNAL_PHONE_NUMBER`, signal-cli registered account | 2 000 chars (recommended) | `signal-cli send --attachment` | N/A (local process) |

### SlackAdapter notes
- Socket Mode (`SLACK_APP_TOKEN` with `connections:write` scope) enables outbound WSS connection — no inbound port required; preferred for corporate firewalls
- Slash commands (`/issue`, `/feedback`, etc.) can be registered as Slack slash commands or parsed from messages prefixed with `/`
- Thread replies: flow updates posted as thread replies to the original `/issue` message to avoid noise in the main channel

### TelegramAdapter notes
- Webhook URL set via `setWebhook` API call on startup
- Bot commands registered via `setMyCommands` so Telegram surfaces them in the UI
- `/feedback` messages from any group member are accepted; private DMs also work if bot is given appropriate permissions

### WhatsAppAdapter notes
- Requires Meta Business Account with WhatsApp Business API access (approval process: 1–2 weeks)
- Webhook verification: GET request with `hub.challenge` echo during setup; POST requests with HMAC-SHA256 header
- Template messages required for first-contact outbound (24h window rule); in-flow replies are unrestricted
- Group/community messaging support varies by API version; DM-first approach recommended

### SignalAdapter notes
- `signal-cli` must be registered and linked to a phone number (`signal-cli register`, `signal-cli link`)
- Polling loop runs as a background `asyncio` task: `signal-cli receive --json`
- No official webhook support — all inbound messages require polling
- Group message support available but management is manual

---

## Command Parsing

The adapter calls `parse_command()` on every inbound message. Commands start with `/` followed by the command name.

| Command | Args | Routes to |
|---------|------|-----------|
| `/issue <KEY>` | Issue key | `TicketFlow(key)` |
| `/sprint <name>` | Sprint name | `SprintFlow(name)` |
| `/design <KEY>` | Issue key | `DesignFlow(key)` |
| `/explore [path]` | Optional path | `_run_explore(path)` |
| `/audit` | — | `build_verify_crew()` |
| `/status` | — | `FlowDispatcher.status(channel)` |
| `/feedback <message>` | Free text | `active_flow.inject_feedback(message)` |
| `/retry` | — | `active_flow.retry()` |
| `/abort` | — | `active_flow.abort()` |
| `/help` | — | Post command list |

Free text without a `/` prefix is ignored in server mode (no conversational fallback — that is a separate `chat` command if desired).

If a command is received while a flow is already active for the channel, `FlowDispatcher` rejects it with a message: "A flow is already running for this channel (`/status` to check, `/abort` to stop)."

---

## Flow Isolation

Each `(platform, channel_id)` pair is completely isolated:

```python
FlowKey = tuple[str, str]  # (platform, channel_id)

active_flows: dict[FlowKey, asyncio.Task] = {}
flow_contexts: dict[FlowKey, TicketFlow | DesignFlow] = {}
```

**Checkpoint namespacing:**
```
.code-crew/checkpoints/slack-C0123456-PROJ-123.json
.code-crew/checkpoints/telegram-987654-PROJ-456.json
```

**Flow state namespacing (async CI waits):**
```
.code-crew/flow-state-slack-C0123456.json
.code-crew/flow-state-telegram-987654.json
```

No shared mutable state exists between keys. The LLM provider may impose its own rate limits, but CrewAI calls from different flows are independent HTTP requests.

---

## Human Gate Model

When a flow task requires human input — BDD review, Chief Architect design approval, launch decision, or `AskHumanTool` mid-task — the adapter posts a structured gate message to the channel.

**Gate message format:**
```
⏸ code-crew is waiting for human input.
Gate: bdd_finalization
Question: The QA lead has drafted BDD scenarios. Please review and reply:
  • /feedback APPROVED  — to continue the flow
  • /feedback <revision notes>  — to request changes

[scenario content as file attachment or truncated inline]
```

Any team member in the channel can reply. The adapter routes any message starting with `/feedback` (after the gate message) to `active_flow.inject_feedback(text)`. The flow resumes immediately.

**Gate timeout:** configurable (`server.gate_timeout_minutes`, default: 120). If no `/feedback` is received within the window, the bot sends a reminder. After a second timeout, the flow serialises state to disk and the asyncio task is cancelled. The flow can be resumed later with `/issue <KEY>` (checkpoint resumes from the last completed task).

---

## Output Formatting

Flow output contains Rich ANSI escape sequences, structured task summaries, code blocks, and file paths. Before sending to an IM platform, the adapter applies:

1. **ANSI stripping** — remove `\x1b[...m` sequences; IM platforms do not render them
2. **Markdown normalisation** — Rich uses slightly different markdown than Slack/Telegram; normalise bold, code blocks, and bullet formatting per platform
3. **Length chunking** — split at paragraph boundaries (not mid-word or mid-sentence) to stay within the platform limit
4. **File detection** — if output contains a file path ending in `.md`, `.yaml`, `.json`, or `.feature` and the file exists locally, send it as a `send_file` attachment alongside a short summary message

**Per-platform formatting:**

| Platform | Bold | Code block | Bullet | Max chunk |
|----------|------|-----------|--------|-----------|
| Slack | `*text*` | ` ```code``` ` | `•` | 3 000 |
| Telegram | `**text**` (MarkdownV2) | ` ```code``` ` | `•` | 4 096 |
| WhatsApp | `*text*` | No native code block (use ` ``` ` for monospace) | `•` | 4 096 |
| Signal | Plain text only | No formatting | `-` | 2 000 |

---

## Configuration Schema

```yaml
server:
  host: 0.0.0.0
  port: 8080
  gate_timeout_minutes: 120

  adapters:
    slack:
      enabled: true
      bot_token: ${SLACK_BOT_TOKEN}
      app_token: ${SLACK_APP_TOKEN}        # Socket Mode; omit to use webhook mode
      signing_secret: ${SLACK_SIGNING_SECRET}
      allowed_channels:
        - "#engineering"
        - "#code-crew"
      thread_replies: true                 # post flow updates as thread replies

    telegram:
      enabled: false
      bot_token: ${TELEGRAM_BOT_TOKEN}
      secret_token: ${TELEGRAM_SECRET_TOKEN}
      allowed_user_ids:
        - 123456789
      webhook_url: https://your-server.example.com/webhooks/telegram

    whatsapp:
      enabled: false
      access_token: ${WA_ACCESS_TOKEN}
      verify_token: ${WA_VERIFY_TOKEN}
      phone_number_id: ${WA_PHONE_NUMBER_ID}
      allowed_numbers:
        - "+15551234567"

    signal:
      enabled: false
      signal_cli_path: /usr/local/bin/signal-cli
      phone_number: ${SIGNAL_PHONE_NUMBER}
      allowed_numbers:
        - "+15557654321"
      poll_interval_seconds: 5

  auth:
    default_profile: default
    channel_profiles:
      "#engineering": prod
      "#staging-review": staging
```

All sensitive values (`*_TOKEN`, `*_SECRET`, `*_KEY`) are read from environment variables — never hardcoded in the YAML file.

---

## Security

### Webhook verification
All inbound POST requests are verified before any content is read or processed:
- **Slack**: HMAC-SHA256 of request body with `SLACK_SIGNING_SECRET`; timestamp checked within 5 minutes to prevent replay
- **Telegram**: `X-Telegram-Bot-Api-Secret-Token` header matched against `TELEGRAM_SECRET_TOKEN`
- **WhatsApp**: GET hub challenge echoed during setup; POST body HMAC-SHA256 with app secret
- **Signal**: no network-facing endpoint — local subprocess polling only

### Channel allow-lists
Messages from channels or users not in the allow-list receive a rejection reply and are not processed. Allow-lists are checked before command parsing.

### No credentials via IM
No token, API key, password, or credential of any kind is accepted as a command argument. If a message contains what looks like a secret (`nvapi-`, `sk-`, `pk-lf-`), the adapter logs a warning and discards the message without processing.

### Rate limiting
Per-channel rate limiting: maximum 1 command per 10 seconds per channel to prevent accidental or deliberate flow spamming. Rejected commands receive a "rate limit" reply.

### Prompt injection via IM
IM messages are user-supplied text that is injected into flow context (via `/feedback`). The `inject_feedback()` method prepends the feedback to `sprint_input["human_feedback"]` — it does not append to agent system prompts. Bedrock Guardrails (`BEDROCK_GUARDRAIL_ID`) can be applied to catch injection attempts at the LLM layer.

---

## Deployment

### Container

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -e ".[server]"

HEALTHCHECK --interval=30s --timeout=5s \
  CMD curl -f http://localhost:8080/health || exit 1

CMD ["code-crew", "server", "--host", "0.0.0.0", "--port", "8080"]
```

### Environment variables (server mode)

| Variable | Required | Purpose |
|----------|----------|---------|
| `SLACK_BOT_TOKEN` | If Slack enabled | Bot OAuth token (`xoxb-…`) |
| `SLACK_APP_TOKEN` | No | Socket Mode app token (`xapp-…`) |
| `SLACK_SIGNING_SECRET` | If Slack webhook | Request signing secret |
| `TELEGRAM_BOT_TOKEN` | If Telegram enabled | Bot API token |
| `TELEGRAM_SECRET_TOKEN` | If Telegram enabled | Webhook secret token |
| `WA_ACCESS_TOKEN` | If WhatsApp enabled | Business API access token |
| `WA_VERIFY_TOKEN` | If WhatsApp enabled | Webhook hub verify token |
| `WA_PHONE_NUMBER_ID` | If WhatsApp enabled | Business phone number ID |
| `SIGNAL_PHONE_NUMBER` | If Signal enabled | Registered Signal number |
| Standard LLM vars | Yes | `BEDROCK_MODEL_ID` or `LLM_CONFIG` etc. |
| Standard issue tracker vars | Yes | `JIRA_URL`, `JIRA_TOKEN` etc. |

### Health endpoint

```
GET /health
→ 200 {"status": "ok", "active_flows": 3, "adapters": ["slack", "telegram"]}

GET /status
→ 200 {"flows": [
    {"platform": "slack", "channel": "C0123456", "key": "PROJ-123", "task": "implementation", "started": "2026-07-03T14:22:00Z"},
    ...
  ]}
```

---

## Phased Rollout

### Phase 1 — Slack (MVP)
- `SlackAdapter` with Events API webhook + Socket Mode
- `/issue`, `/design`, `/feedback`, `/abort`, `/status` commands
- Thread reply mode: flow updates as threads on the original command message
- Basic ANSI stripping and chunking

### Phase 2 — Telegram
- `TelegramAdapter` with webhook + polling fallback
- Same command set
- Per-user allow-list (user IDs)

### Phase 3 — WhatsApp and Signal
- `WhatsAppAdapter` — requires Meta Business verification; document setup process
- `SignalAdapter` — polling only; flag as experimental (signal-cli dependency)

---

## Key Files

| File | Purpose |
|------|---------|
| `code_crew/server.py` | FastAPI app, `/webhooks/*` routes, `/health`, `/status` |
| `code_crew/dispatcher.py` | `FlowDispatcher` — `active_flows` dict, asyncio task management, per-channel serialisation |
| `shared/adapters/base.py` | `IMAdapter` ABC, `IMMessage`, `Command` dataclasses |
| `shared/adapters/slack.py` | `SlackAdapter` — Events API + Socket Mode |
| `shared/adapters/telegram.py` | `TelegramAdapter` — webhook + long-poll |
| `shared/adapters/whatsapp.py` | `WhatsAppAdapter` — Business Cloud API |
| `shared/adapters/signal.py` | `SignalAdapter` — signal-cli subprocess |
| `shared/adapters/formatter.py` | `format_for_platform(text, platform)` — ANSI strip, markdown normalise, chunk |
| `pyproject.toml` | `[server]` extra: `fastapi`, `uvicorn`, `slack-sdk`, `python-telegram-bot`, etc. |
