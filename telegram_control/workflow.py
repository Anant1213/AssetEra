from __future__ import annotations

import json
import shutil
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import re

StatusCallback = Callable[[str], None]

COMPACTION_HINT = (
    "Context tip: run /compact from Telegram when Claude starts feeling bloated, "
    "or /newclaude to start a fresh Claude chat."
)


class Workflow:
    """Coordinates Codex planning and Claude implementation for local tasks."""

    def __init__(self, workspace: Path, notify: StatusCallback) -> None:
        self.workspace = workspace
        self.state_dir = workspace / ".telegram_control"
        self.state_dir.mkdir(exist_ok=True)
        self.session_log = self.state_dir / "claude_sessions.json"
        self.notify = notify
        self.lock = threading.Lock()
        self.active_task_id: str | None = None

    def _task_dir(self, task_id: str) -> Path:
        if not re.fullmatch(r"T-[0-9]{8}-[0-9]{6}-[0-9a-f]{6}", task_id):
            raise ValueError("invalid task ID")
        path = self.state_dir / "tasks" / task_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _save(self, task_id: str, state: dict[str, str]) -> None:
        self._task_dir(task_id).joinpath("state.json").write_text(
            json.dumps(state, indent=2) + "\n", encoding="utf-8"
        )

    def _load(self, task_id: str) -> dict[str, str] | None:
        path = self._task_dir(task_id).joinpath("state.json")
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def latest(self, status: str | None = None) -> str | None:
        tasks_dir = self.state_dir / "tasks"
        if not tasks_dir.exists():
            return None
        candidates = []
        for path in tasks_dir.iterdir():
            if not path.is_dir() or not re.fullmatch(r"T-[0-9]{8}-[0-9]{6}-[0-9a-f]{6}", path.name):
                continue
            state_path = path / "state.json"
            if not state_path.exists():
                continue
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if status is None or state.get("status") == status:
                candidates.append((state_path.stat().st_mtime, path.name))
        return max(candidates)[1] if candidates else None

    def _start(self, task_id: str, target: Callable[[], None]) -> bool:
        with self.lock:
            if self.active_task_id is not None:
                return False
            self.active_task_id = task_id
        threading.Thread(target=self._run_and_clear, args=(task_id, target), daemon=True).start()
        return True

    def _run_and_clear(self, task_id: str, target: Callable[[], None]) -> None:
        try:
            target()
        finally:
            with self.lock:
                self.active_task_id = None

    def _run_claude_json(self, args: list[str]) -> tuple[subprocess.CompletedProcess[str], dict[str, Any] | None, str]:
        result = subprocess.run(args, cwd=self.workspace, capture_output=True, text=True, check=False)
        output = (result.stdout or result.stderr).strip()
        payload = None
        if result.stdout.strip():
            try:
                parsed = json.loads(result.stdout)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = None
        return result, payload, output

    def _save_claude_session(self, payload: dict[str, Any] | None, seed: str) -> str | None:
        session_id = payload.get("session_id") if payload else None
        if not isinstance(session_id, str) or not session_id:
            return None
        entries = []
        if self.session_log.exists():
            try:
                loaded = json.loads(self.session_log.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    entries = loaded
            except json.JSONDecodeError:
                entries = []
        entries.append(
            {
                "session_id": session_id,
                "seed": seed[:500],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.session_log.write_text(json.dumps(entries[-20:], indent=2) + "\n", encoding="utf-8")
        return session_id

    def _latest_claude_session_id(self) -> str | None:
        if not self.session_log.exists():
            return None
        try:
            entries = json.loads(self.session_log.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if not isinstance(entries, list):
            return None
        for entry in reversed(entries):
            session_id = entry.get("session_id") if isinstance(entry, dict) else None
            if isinstance(session_id, str) and session_id:
                return session_id
        return None

    def _usage_summary(self, payload: dict[str, Any] | None) -> str | None:
        if not payload:
            return None
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            return None
        labels = {
            "input_tokens": "input",
            "output_tokens": "output",
            "cache_creation_input_tokens": "cache write",
            "cache_read_input_tokens": "cache read",
            "total_tokens": "total",
        }
        parts = []
        for key, label in labels.items():
            value = usage.get(key)
            if isinstance(value, int):
                parts.append(f"{label}: {value:,}")
        if not parts:
            token_values = [value for key, value in usage.items() if key.endswith("tokens") and isinstance(value, int)]
            if token_values:
                parts.append(f"reported token fields total: {sum(token_values):,}")
        return ", ".join(parts) if parts else None

    def _extract_freed_tokens(self, output: str) -> str | None:
        patterns = [
            r"tokens freed\s*[:=-]\s*~?([\d,]+)",
            r"freed\s+~?([\d,]+)\s+tokens",
            r"reduced\s+from\s+~?([\d,]+)\s+to\s+~?([\d,]+)\s+tokens",
            r"~?([\d,]+)\s*->\s*~?([\d,]+)\s+tokens",
        ]
        for pattern in patterns:
            match = re.search(pattern, output, flags=re.IGNORECASE)
            if not match:
                continue
            numbers = [int(value.replace(",", "")) for value in match.groups()]
            if len(numbers) == 1:
                return f"{numbers[0]:,}"
            if numbers[0] >= numbers[1]:
                return f"{numbers[0] - numbers[1]:,}"
        return None

    def _format_claude_result(
        self,
        title: str,
        status: str,
        payload: dict[str, Any] | None,
        output: str,
        *,
        include_freed_tokens: bool = False,
    ) -> str:
        lines = [f"{title} {status}."]
        session_id = payload.get("session_id") if payload else None
        if isinstance(session_id, str) and session_id:
            lines.append(f"Session: {session_id}")
        num_turns = payload.get("num_turns") if payload else None
        if isinstance(num_turns, int):
            lines.append(f"Turns: {num_turns}")
        duration_ms = payload.get("duration_ms") if payload else None
        if isinstance(duration_ms, int):
            lines.append(f"Duration: {duration_ms / 1000:.1f}s")
        cost = payload.get("total_cost_usd") if payload else None
        if isinstance(cost, int | float):
            lines.append(f"Cost: ${cost:.4f}")
        usage = self._usage_summary(payload)
        if usage:
            lines.append(f"Usage: {usage}")
        if include_freed_tokens:
            freed = self._extract_freed_tokens(output)
            lines.append(f"Tokens freed: {freed if freed else 'not reported by Claude CLI'}")
        body = payload.get("result") if payload else output
        if isinstance(body, str) and body.strip():
            lines.append("")
            lines.append(body.strip()[-2600:])
        return "\n".join(lines)

    def create_task(self, description: str) -> str:
        description = description.strip()
        if not description or len(description) > 4000:
            raise ValueError("task description must be between 1 and 4000 characters")
        task_id = "T-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        state = {"id": task_id, "description": description, "status": "queued"}
        self._save(task_id, state)
        if not self._start(task_id, lambda: self._plan(task_id, description)):
            self._save(task_id, {**state, "status": "waiting"})
            self.notify(f"{task_id} queued. Another task is active.")
            return task_id
        self.notify(f"{task_id} received. Codex PM is preparing a read-only PRD.\n\n{COMPACTION_HINT}")
        return task_id

    def _plan(self, task_id: str, description: str) -> None:
        codex = shutil.which("codex")
        if not codex:
            self._save(task_id, {"id": task_id, "description": description, "status": "failed"})
            self.notify(f"{task_id}: Codex CLI was not found.")
            return
        prompt = f"""
You are the project manager for the local repository at {self.workspace}.
Analyze the repository read-only for this request:

{description}

Produce a concise implementation PRD with objective, assumptions, user-facing
behavior, affected files, ordered Claude tasks, acceptance criteria, tests,
security checks, and regression checks.

Do not edit files, commit, push, deploy, or request credentials. Local development only.
"""
        result = subprocess.run(
            [codex, "exec", "--cd", str(self.workspace), "--sandbox", "read-only", prompt],
            cwd=self.workspace, capture_output=True, text=True, check=False,
        )
        output = result.stdout or result.stderr
        self._task_dir(task_id).joinpath("prd.md").write_text(output, encoding="utf-8")
        status = "planned" if result.returncode == 0 else "failed"
        self._save(task_id, {"id": task_id, "description": description, "status": status})
        if status == "failed":
            self.notify(f"{task_id}: PM planning failed.\n{result.stderr[-2500:]}")
            return
        self.notify(
            f"{task_id} PRD ready.\n\n{output.strip()[-3200:]}\n\n"
            f"Approve with /approve {task_id}\n\n{COMPACTION_HINT}"
        )

    def approve(self, task_id: str) -> bool:
        state = self._load(task_id)
        if not state or state.get("status") != "planned":
            return False
        if not self._start(task_id, lambda: self._implement(task_id, state["description"])):
            return False
        state["status"] = "approved"
        self._save(task_id, state)
        self.notify(f"{task_id} approved. Claude Code is implementing locally.\n\n{COMPACTION_HINT}")
        return True

    def _implement(self, task_id: str, description: str) -> None:
        claude = shutil.which("claude")
        if not claude:
            self.notify(f"{task_id}: Claude Code was not found.")
            return
        prd = self._task_dir(task_id).joinpath("prd.md")
        prompt = f"""
Implement this local-development task in {self.workspace}:

{description}

Read the PM PRD at {prd}. Make the necessary code changes and report what
changed. Keep context usage compact: read only the files needed, avoid pasting
large file contents into the conversation, and summarize findings concisely.
Work only in this workspace. Do not commit, push, deploy, delete unrelated
files, access production systems, or expose secrets.
"""
        result = subprocess.run(
            [claude, "-p", prompt, "--permission-mode", "acceptEdits", "--allowed-tools", "Read", "Edit", "Write"],
            cwd=self.workspace, capture_output=True, text=True, check=False,
        )
        status = "completed" if result.returncode == 0 else "failed"
        self._save(task_id, {"id": task_id, "description": description, "status": status})
        output = (result.stdout or result.stderr).strip()
        self.notify(f"{task_id} Claude {status}.\n\n{output[-3500:]}\n\n{COMPACTION_HINT}")

    def compact_context(self, instructions: str = "") -> bool:
        task_id = "compact-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        if not self._start(task_id, lambda: self._compact_context(task_id, instructions)):
            return False
        self.notify(f"{task_id} started. Asking Claude to compact the latest local session.")
        return True

    def _compact_context(self, task_id: str, instructions: str) -> None:
        claude = shutil.which("claude")
        if not claude:
            self.notify(f"{task_id}: Claude Code was not found.")
            return
        prompt = (
            "/compact Please aggressively compact this session. After compaction, include "
            "a metrics block with previous context tokens, current context tokens, tokens "
            "freed, compression ratio, retained summary topics, open tasks, changed files, "
            "and test status. If exact token counts are unavailable, write 'not reported'."
        )
        instructions = instructions.strip()
        if instructions:
            prompt = f"{prompt} {instructions}"
        result, payload, output = self._run_claude_json(
            [claude, "-p", prompt, "--continue", "--permission-mode", "dontAsk", "--tools", "", "--output-format", "json"]
        )
        status = "completed" if result.returncode == 0 else "failed"
        self.notify(
            self._format_claude_result(
                f"{task_id} context compaction",
                status,
                payload,
                output,
                include_freed_tokens=True,
            )
        )

    def start_claude_session(self, seed: str = "") -> bool:
        task_id = "claude-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        if not self._start(task_id, lambda: self._start_claude_session(task_id, seed)):
            return False
        self.notify(f"{task_id} started. Opening a fresh Claude chat.")
        return True

    def _start_claude_session(self, task_id: str, seed: str) -> None:
        claude = shutil.which("claude")
        if not claude:
            self.notify(f"{task_id}: Claude Code was not found.")
            return
        seed = seed.strip()
        prompt = f"""
Start a fresh Claude Code chat for the local workspace at {self.workspace}.
Do not edit files, commit, push, deploy, delete files, access production systems,
or expose secrets. Reply with a short readiness note and the best next prompt to
continue this new session.
"""
        if seed:
            prompt += f"\nInitial user intent for this fresh session:\n{seed}\n"
        result, payload, output = self._run_claude_json(
            [
                claude,
                "-p",
                prompt,
                "--permission-mode",
                "dontAsk",
                "--allowed-tools",
                "Read",
                "--output-format",
                "json",
            ]
        )
        status = "completed" if result.returncode == 0 else "failed"
        session_id = self._save_claude_session(payload, seed) if status == "completed" else None
        message = self._format_claude_result(f"{task_id} fresh Claude chat", status, payload, output)
        if session_id:
            message += f"\n\nContinue it from Telegram with /claude your prompt."
        self.notify(message)

    def prompt_claude_session(self, prompt: str) -> bool:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Claude prompt must not be empty")
        session_id = self._latest_claude_session_id()
        if not session_id:
            raise ValueError("No saved Claude session. Start one with /newclaude first.")
        task_id = "claude-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        if not self._start(task_id, lambda: self._prompt_claude_session(task_id, session_id, prompt)):
            return False
        self.notify(f"{task_id} sent to Claude session {session_id}.")
        return True

    def _prompt_claude_session(self, task_id: str, session_id: str, prompt: str) -> None:
        claude = shutil.which("claude")
        if not claude:
            self.notify(f"{task_id}: Claude Code was not found.")
            return
        guarded_prompt = f"""
Continue this Telegram-managed Claude chat.

User prompt:
{prompt}

Stay in local-development mode. Do not edit files, commit, push, deploy, delete
files, access production systems, or expose secrets.
"""
        result, payload, output = self._run_claude_json(
            [
                claude,
                "-p",
                guarded_prompt,
                "--resume",
                session_id,
                "--permission-mode",
                "dontAsk",
                "--allowed-tools",
                "Read",
                "--output-format",
                "json",
            ]
        )
        status = "completed" if result.returncode == 0 else "failed"
        self.notify(self._format_claude_result(f"{task_id} Claude reply", status, payload, output))

    def deny(self, task_id: str) -> bool:
        state = self._load(task_id)
        if not state or state.get("status") != "planned":
            return False
        state["status"] = "denied"
        self._save(task_id, state)
        self.notify(f"{task_id} denied. No implementation was started.")
        return True

    def status(self) -> str:
        with self.lock:
            active = self.active_task_id or "none"
        session_id = self._latest_claude_session_id() or "none"
        return f"Active task: {active}\nFresh Claude session: {session_id}\nState directory: {self.state_dir}\n{COMPACTION_HINT}"
