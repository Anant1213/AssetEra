from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Config:
    bot_token: str
    allowed_chat_id: int
    workspace: Path
    poll_timeout: int = 30

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        workspace = Path(os.getenv("TELEGRAM_WORKSPACE", Path.cwd())).expanduser().resolve()

        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        if not chat_id or not chat_id.lstrip("-").isdigit():
            raise RuntimeError("TELEGRAM_CHAT_ID must be a numeric Telegram chat ID")
        if not workspace.is_dir():
            raise RuntimeError(f"TELEGRAM_WORKSPACE does not exist: {workspace}")

        return cls(bot_token=token, allowed_chat_id=int(chat_id), workspace=workspace)

