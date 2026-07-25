from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any

import requests
from dotenv import load_dotenv

from .config import Config
from .workflow import Workflow


class TelegramBot:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.api_url = f"https://api.telegram.org/bot{config.bot_token}"
        self.next_update_id: int | None = None
        self.workflow = Workflow(config.workspace, self.send)
        self.awaiting_task = False

    def call(self, method: str, **payload: Any) -> Any:
        response = requests.post(
            f"{self.api_url}/{method}",
            json=payload,
            timeout=self.config.poll_timeout + 10,
        )
        response.raise_for_status()
        body = response.json()
        if not body.get("ok"):
            raise RuntimeError(body.get("description", f"Telegram {method} failed"))
        return body.get("result")

    def send(self, text: str) -> None:
        self.call("sendMessage", chat_id=self.config.allowed_chat_id, text=text)

    def status(self) -> str:
        git_status = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=self.config.workspace,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        claude = shutil.which("claude") or "not found"
        return (
            "Telegram bridge is online.\n\n"
            f"Workspace: {self.config.workspace}\n"
            f"Claude: {claude}\n"
            f"Git: {git_status or 'unavailable'}"
        )

    def handle_message(self, message: dict[str, Any]) -> None:
        chat = message.get("chat", {})
        if chat.get("id") != self.config.allowed_chat_id:
            return

        text = (message.get("text") or "").strip()
        command, _, argument = text.partition(" ")
        normalized_command = command.lower().lstrip("/").split("@", 1)[0]
        if normalized_command in {"start", "help"}:
            self.send(
                "Remote engineering bridge is connected.\n\n"
                "/status - show workspace and Claude state\n"
                "pm - start a task with Codex PM\n"
                "/approve - approve the latest PRD\n"
                "/deny - reject the latest PRD\n"
                "/compact - compact Claude's latest local session context\n"
                "/newclaude - start a fresh Claude chat\n"
                "/claude - continue the fresh Claude chat\n"
                "/help - show this message\n\n"
                "Local development only: no push, deployment, or production actions."
            )
        elif normalized_command == "status":
            self.send(self.status() + "\n\n" + self.workflow.status())
        elif self.awaiting_task and not text.startswith("/"):
            self.awaiting_task = False
            try:
                self.workflow.create_task(text)
            except ValueError as exc:
                self.send(f"Task rejected: {exc}")
        elif normalized_command in {"pm", "claude_work", "task"}:
            if argument.strip():
                try:
                    self.workflow.create_task(argument.strip())
                except ValueError as exc:
                    self.send(f"Task rejected: {exc}")
            else:
                self.awaiting_task = True
                self.send("What should Codex PM and Claude work on?")
        elif normalized_command == "approve":
            task_id = argument.strip() or self.workflow.latest("planned")
            try:
                approved = bool(task_id) and self.workflow.approve(task_id)
            except ValueError:
                approved = False
            if not approved:
                self.send("No pending PRD is ready for approval, or another task is active.")
        elif normalized_command == "deny":
            task_id = argument.strip() or self.workflow.latest("planned")
            try:
                denied = bool(task_id) and self.workflow.deny(task_id)
            except ValueError:
                denied = False
            if not denied:
                self.send("No pending PRD is waiting for denial.")
        elif normalized_command == "compact":
            if not self.workflow.compact_context(argument.strip()):
                self.send("Claude context compaction could not start because another task is active.")
        elif normalized_command in {"newclaude", "new_claude", "newchat"}:
            if not self.workflow.start_claude_session(argument.strip()):
                self.send("A fresh Claude chat could not start because another task is active.")
        elif normalized_command == "claude":
            try:
                started = self.workflow.prompt_claude_session(argument.strip())
            except ValueError as exc:
                self.send(str(exc))
            else:
                if not started:
                    self.send("Claude could not respond because another task is active.")
        elif text.startswith("/"):
            self.send("Unknown command. Send /help to see available commands.")

    def run(self) -> None:
        self.call("getMe")
        self.send("Telegram bridge connected to the assetera test workspace.")
        while True:
            updates = self.call(
                "getUpdates",
                offset=self.next_update_id,
                timeout=self.config.poll_timeout,
                allowed_updates=["message"],
            )
            for update in updates:
                self.next_update_id = update["update_id"] + 1
                self.handle_message(update.get("message", {}))
            time.sleep(0.5)


def main() -> None:
    load_dotenv()
    config = Config.from_env()
    TelegramBot(config).run()


if __name__ == "__main__":
    main()
