"""Entry point for GeneralBot."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import discord
from generalbot.bot import GeneralBot


def load_env() -> None:
    env_file = Path(__file__).with_name(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def main() -> None:
    load_env()
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "DISCORD_TOKEN is not set. Copy .env.example to .env and paste your bot token."
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    bot = GeneralBot()
    try:
        bot.run(token, log_handler=None)
    except discord.PrivilegedIntentsRequired:
        raise SystemExit(
            "A required privileged intent is disabled. In the Developer Portal, enable "
            "Server Members Intent and Message Content Intent "
            "(Bot → Privileged Gateway Intents)."
        )
    except discord.LoginFailure:
        raise SystemExit(
            "Discord rejected DISCORD_TOKEN. Check that .env contains the current bot token."
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
