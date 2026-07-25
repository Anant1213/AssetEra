# Telegram Control Bridge

This package is the local control plane for the engineering workspace. It is
restricted to local development: no Git pushes, pull requests, deployments,
or production actions are part of this bridge.

Configure these values in `.env`:

```text
TELEGRAM_BOT_TOKEN=replace-with-the-token-from-botfather
TELEGRAM_CHAT_ID=replace-with-your-private-chat-id
TELEGRAM_WORKSPACE=/Users/anant/assetera
```

Run it from the repository root:

```bash
.venv/bin/python scripts/run_telegram_bot.py
```

Start work from Telegram with:

```text
pm your task description
```

Compact Claude's latest local session context with:

```text
/compact
/compact focus the summary on open tasks, changed files, and test status
```

Start a fresh Claude chat when compaction is not enough:

```text
/newclaude
/newclaude focus on the market data ingestion refactor
/claude what should we do next?
```

The bot stores the new Claude session ID locally in `.telegram_control` and
uses `/claude` to continue that fresh session. Compaction reports token details
when Claude Code exposes them; otherwise it marks freed tokens as not reported.

The bot uses long polling and does not expose a public HTTP endpoint. Only the
configured chat ID is accepted.

No OpenAI API key is required. Codex remains the project manager in the active
Codex session; Claude Code is the local implementation worker. The Telegram
bridge provides transport, status, and approval plumbing for the local worker.
