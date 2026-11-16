"""GeneralBot client setup, command syncing, and global error handling."""

from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from .database import Database
from .helpers import reply_error, reply_error_ctx

log = logging.getLogger("generalbot")

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "generalbot.db"
PREFIXES = ("?", ".", "'", ";", "!")

COGS = (
    "generalbot.cogs.moderation",
    "generalbot.cogs.fun",
    "generalbot.cogs.utility",
    "generalbot.cogs.config",
    "generalbot.cogs.economy",
    "generalbot.cogs.levels",
    "generalbot.cogs.social",
    "generalbot.cogs.reaction",
    "generalbot.cogs.rate",
    "generalbot.cogs.prefix",
)


class GeneralBot(commands.Bot):
    def __init__(self, db_path: str | Path | None = None) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(
            command_prefix=commands.when_mentioned_or(*PREFIXES),
            intents=intents,
            help_command=None,
        )
        self.db = Database(db_path or DEFAULT_DB_PATH)
        self.start_time = discord.utils.utcnow()
        self.tree.on_error = self.on_app_command_error

    async def setup_hook(self) -> None:
        await self.db.setup()
        for extension in COGS:
            await self.load_extension(extension)
            log.info("Loaded %s", extension)

        try:
            synced = await self.tree.sync()
        except Exception:
            log.exception("Failed to sync application commands")
        else:
            log.info("Synced %s top-level command group(s)", len(synced))

    async def on_ready(self) -> None:
        log.info(
            "Logged in as %s (%s) · %s guild(s)",
            self.user,
            self.user.id if self.user else "?",
            len(self.guilds),
        )
        await self._update_presence()

    async def _update_presence(self) -> None:
        # Presence can only be changed once the gateway connection exists.
        if self.ws is None:
            return

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"/utility help · {len(self.guilds)} servers",
        )
        try:
            await self.change_presence(activity=activity)
        except (discord.HTTPException, RuntimeError):
            pass

    async def on_guild_join(self, guild: discord.Guild) -> None:
        log.info("Joined guild %s (%s)", guild.name, guild.id)
        await self._update_presence()

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        log.info("Left guild %s (%s)", guild.name, guild.id)
        await self._update_presence()

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        original = error.original if isinstance(error, app_commands.CommandInvokeError) else error

        if isinstance(original, app_commands.MissingPermissions):
            permissions = ", ".join(original.missing_permissions).replace("_", " ").title()
            title, description = "Missing permissions", f"You need: **{permissions}**."
        elif isinstance(original, app_commands.BotMissingPermissions):
            permissions = ", ".join(original.missing_permissions).replace("_", " ").title()
            title, description = "I'm missing permissions", f"I need: **{permissions}**."
        elif isinstance(original, app_commands.CommandOnCooldown):
            title, description = "Slow down", f"Try again in **{original.retry_after:.1f}s**."
        elif isinstance(original, discord.Forbidden):
            title, description = "Permission denied", "Discord wouldn't let me do that. Check my role and permissions."
        elif isinstance(original, discord.NotFound):
            title, description = "Not found", "That user, message, or channel no longer exists."
        else:
            title, description = "Something went wrong", "The error was logged. Please try again."
            log.error(
                "Unhandled command error in /%s",
                getattr(interaction.command, "qualified_name", "unknown"),
                exc_info=(type(original), original, original.__traceback__),
            )

        try:
            await reply_error(interaction, description, title=title)
        except discord.HTTPException:
            log.exception("Failed to send error response")

    async def on_command_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ) -> None:
        if isinstance(error, commands.CommandNotFound):
            return

        original = error.original if isinstance(error, commands.CommandInvokeError) else error
        command = ctx.command

        if isinstance(original, commands.MissingRequiredArgument):
            usage = ""
            if command is not None:
                usage = f"{ctx.prefix}{command.qualified_name} {command.usage or ''}".strip()
            title, description = "Missing argument", f"Usage: `{usage or 'see ?help'}`"
        elif isinstance(original, commands.BadArgument):
            title, description = "Invalid argument", str(original)
        elif isinstance(original, commands.MissingPermissions):
            permissions = ", ".join(original.missing_permissions).replace("_", " ").title()
            title, description = "Missing permissions", f"You need: **{permissions}**."
        elif isinstance(original, commands.BotMissingPermissions):
            permissions = ", ".join(original.missing_permissions).replace("_", " ").title()
            title, description = "I'm missing permissions", f"I need: **{permissions}**."
        elif isinstance(original, commands.CommandOnCooldown):
            title, description = "Slow down", f"Try again in **{original.retry_after:.1f}s**."
        elif isinstance(original, commands.NoPrivateMessage):
            title, description = "Server only", "This command only works inside a server."
        elif isinstance(original, commands.CheckFailure):
            title, description = "Not allowed", "You can't use this command here."
        elif isinstance(original, discord.Forbidden):
            title, description = "Permission denied", "Discord wouldn't let me do that. Check my role and permissions."
        elif isinstance(original, discord.NotFound):
            title, description = "Not found", "That user, message, or channel no longer exists."
        else:
            title, description = "Something went wrong", "The error was logged. Please try again."
            log.error(
                "Unhandled prefix command error in %s%s",
                ctx.prefix,
                getattr(command, "qualified_name", "unknown"),
                exc_info=(type(original), original, original.__traceback__),
            )

        try:
            await reply_error_ctx(ctx, description, title=title)
        except discord.HTTPException:
            log.exception("Failed to send prefix command error response")
