"""Server configuration commands and join events, grouped under /config."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..helpers import (
    BRAND,
    SUCCESS,
    WARNING,
    base_embed,
    format_welcome,
    reply_error,
    require_bot_perms,
    require_perms,
    respond,
    truncate,
)

if TYPE_CHECKING:
    from ..bot import GeneralBot

log = logging.getLogger("generalbot.config")


def _channel_label(guild: discord.Guild, channel_id: int | None) -> str:
    if not channel_id:
        return "Not set"
    channel = guild.get_channel(channel_id)
    return channel.mention if channel is not None else f"`{channel_id}` (missing)"


def _role_label(guild: discord.Guild, role_id: int | None) -> str:
    if not role_id:
        return "Not set"
    role = guild.get_role(role_id)
    return role.mention if role is not None else f"`{role_id}` (missing)"


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class Config(commands.GroupCog, group_name="config", group_description="Set up logging, welcome messages, and autorole"):
    def __init__(self, bot: GeneralBot) -> None:
        self.bot = bot

    @app_commands.command(name="modlog", description="Set or disable the moderation log channel")
    @app_commands.describe(channel="Where to send mod logs (omit to disable)")
    async def modlog(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        guild = await require_perms(interaction, manage_guild=True)
        if guild is None:
            return

        if channel is None:
            await self.bot.db.set_config(guild.id, modlog_channel_id=None)
            await respond(
                interaction,
                embed=base_embed("🪵 Mod Log Disabled", "Moderation actions will no longer be logged.", color=WARNING),
                ephemeral=True,
            )
            return

        if guild.me is None:
            await reply_error(
                interaction,
                "I'm not a member of this server. Add me with `/utility invite` first.",
                title="Bot not in server",
            )
            return
        permissions = channel.permissions_for(guild.me)
        if not (permissions.send_messages and permissions.embed_links):
            await reply_error(
                interaction,
                f"I need **Send Messages** and **Embed Links** in {channel.mention}. Pick another channel.",
            )
            return

        await self.bot.db.set_config(guild.id, modlog_channel_id=channel.id)
        await respond(
            interaction,
            embed=base_embed(
                "🪵 Mod Log Configured",
                f"Moderation actions will be logged to {channel.mention}.",
                color=SUCCESS,
            ),
            ephemeral=True,
        )

    @app_commands.command(name="welcome", description="Set up welcome messages (omit channel to disable)")
    @app_commands.describe(
        channel="Where to send welcomes (omit to disable)",
        message="Custom message. Placeholders: {user}, {name}, {server}, {member_count}",
    )
    async def welcome(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
        message: str | None = None,
    ) -> None:
        guild = await require_perms(interaction, manage_guild=True)
        if guild is None:
            return

        if channel is None:
            if message:
                await reply_error(
                    interaction,
                    "Choose a welcome channel when providing a custom message.",
                    title="Channel required",
                )
                return
            await self.bot.db.set_config(
                guild.id, welcome_channel_id=None, welcome_message=None
            )
            await respond(
                interaction,
                embed=base_embed("👋 Welcome Disabled", "Welcome messages are now off.", color=WARNING),
                ephemeral=True,
            )
            return

        if not await require_bot_perms(interaction, send_messages=True, embed_links=True):
            return
        permissions = channel.permissions_for(guild.me)
        if not (permissions.send_messages and permissions.embed_links):
            await reply_error(
                interaction,
                f"I need **Send Messages** and **Embed Links** in {channel.mention}. Pick another channel.",
            )
            return

        template = message.strip() if message else None
        if template is not None and len(template) > 1000:
            await reply_error(interaction, "Keep the welcome message under 1000 characters.")
            return

        await self.bot.db.set_config(
            guild.id,
            welcome_channel_id=channel.id,
            welcome_message=template,
        )
        await respond(
            interaction,
            embed=base_embed(
                "👋 Welcome Configured",
                f"Welcome messages will be sent to {channel.mention}.\n\n**Preview**\n"
                f"{format_welcome(template, interaction.user, guild)}\n\n"
                "Placeholders: `{user}`, `{name}`, `{server}`, `{member_count}`",
                color=SUCCESS,
            ),
            ephemeral=True,
        )

    @app_commands.command(name="autorole", description="Set or disable a role for new members")
    @app_commands.describe(role="Role to give new members (omit to disable)")
    async def autorole(
        self,
        interaction: discord.Interaction,
        role: discord.Role | None = None,
    ) -> None:
        guild = await require_perms(interaction, manage_guild=True)
        if guild is None:
            return

        if role is None:
            await self.bot.db.set_config(guild.id, autorole_id=None)
            await respond(
                interaction,
                embed=base_embed("🎭 Autorole Disabled", "New members will no longer get a role automatically.", color=WARNING),
                ephemeral=True,
            )
            return

        if not await require_bot_perms(interaction, manage_roles=True):
            return
        if role.is_default() or role.managed:
            await reply_error(interaction, "That role can't be assigned automatically.", title="Invalid role")
            return
        if guild.me is None or role.position >= guild.me.top_role.position:
            await reply_error(interaction, "That role is above my highest role. Move my role higher first.")
            return

        await self.bot.db.set_config(guild.id, autorole_id=role.id)
        await respond(
            interaction,
            embed=base_embed(
                "🎭 Autorole Configured",
                f"New members will receive {role.mention} when they join.",
                color=SUCCESS,
            ),
            ephemeral=True,
        )

    @app_commands.command(name="settings", description="Show this server's configuration")
    async def settings(self, interaction: discord.Interaction) -> None:
        guild = await require_perms(interaction, manage_guild=True)
        if guild is None:
            return
        config = await self.bot.db.get_guild_config(guild.id)

        embed = base_embed(f"⚙️ {guild.name} Settings", color=BRAND)
        if guild.icon is not None:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(
            name="Mod log",
            value=_channel_label(guild, config.get("modlog_channel_id")),
            inline=True,
        )
        embed.add_field(
            name="Welcome channel",
            value=_channel_label(guild, config.get("welcome_channel_id")),
            inline=True,
        )
        embed.add_field(
            name="Autorole",
            value=_role_label(guild, config.get("autorole_id")),
            inline=True,
        )
        welcome_message = config.get("welcome_message")
        embed.add_field(
            name="Welcome message",
            value=truncate(format_welcome(welcome_message, interaction.user, guild), 1024),
            inline=False,
        )
        embed.set_footer(text="Use /config to change these · GeneralBot")
        await respond(interaction, embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        try:
            config = await self.bot.db.get_guild_config(member.guild.id)
        except Exception:
            log.exception("Failed to load guild config for %s", member.guild.id)
            return

        role_id = config.get("autorole_id")
        if role_id:
            role = member.guild.get_role(role_id)
            if (
                role is not None
                and not role.managed
                and member.guild.me is not None
                and role.position < member.guild.me.top_role.position
            ):
                try:
                    await member.add_roles(role, reason="Autorole")
                except (discord.Forbidden, discord.HTTPException):
                    pass

        channel_id = config.get("welcome_channel_id")
        if not channel_id:
            return
        channel = member.guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await member.guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return
        if not isinstance(channel, discord.TextChannel):
            return
        if member.guild.me is None:
            return
        permissions = channel.permissions_for(member.guild.me)
        if not (permissions.send_messages and permissions.embed_links):
            return

        embed = base_embed(
            f"👋 Welcome to {member.guild.name}!",
            format_welcome(config.get("welcome_message"), member),
            color=BRAND,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(
            text=f"Member #{member.guild.member_count or 0} · GeneralBot",
            icon_url=member.guild.icon.url if member.guild.icon else None,
        )
        try:
            await channel.send(content=member.mention, embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot: GeneralBot) -> None:
    await bot.add_cog(Config(bot))
