"""Utility and information commands, grouped under /utility."""

from __future__ import annotations

import math
import platform
import time
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..helpers import (
    BRAND,
    SUCCESS,
    base_embed,
    ensure_guild,
    humanize_seconds,
    reply_error,
    resolve_member,
    respond,
    truncate,
)

if TYPE_CHECKING:
    from ..bot import GeneralBot


HELP_GROUPS = (
    "moderation",
    "fun",
    "reaction",
    "social",
    "rate",
    "utility",
    "economy",
    "level",
    "config",
)


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class Utility(commands.GroupCog, group_name="utility", group_description="Info, help, and handy server tools"):
    def __init__(self, bot: GeneralBot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="List commands or get details about a group")
    @app_commands.describe(group="The command group to inspect")
    @app_commands.choices(
        group=[
            app_commands.Choice(name=name.title(), value=name) for name in HELP_GROUPS
        ]
    )
    async def help(self, interaction: discord.Interaction, group: str | None = None) -> None:
        groups = {
            command.name: command
            for command in self.bot.tree.get_commands()
            if isinstance(command, app_commands.Group)
        }

        if group is not None:
            selected = groups.get(group)
            if selected is None:
                await reply_error(interaction, "I couldn't find that command group.", title="Unknown group")
                return
            embed = base_embed(
                f"📚 /{selected.name}",
                selected.description or "No description.",
                color=BRAND,
            )
            for command in selected.commands:
                embed.add_field(
                    name=f"/{selected.name} {command.name}",
                    value=truncate(command.description or "No description.", 250),
                    inline=False,
                )
            embed.set_footer(text="GeneralBot · all commands use slash commands")
            await respond(interaction, embed=embed)
            return

        embed = base_embed(
            "📚 GeneralBot Help",
            "Everything is organized into groups. Pick one to see its commands:\n"
            "`/utility help group:<name>`\n\n"
            "Fun, utility, economy, and level commands also work in DMs with the app.",
            color=BRAND,
        )
        for name in HELP_GROUPS:
            command_group = groups.get(name)
            if command_group is None:
                continue
            commands_list = list(command_group.commands)
            preview = "\n".join(
                f"`/{name} {command.name}`" for command in commands_list[:6]
            )
            if len(commands_list) > 6:
                preview += f"\n…and {len(commands_list) - 6} more"
            embed.add_field(
                name=f"/{name}",
                value=f"{command_group.description}\n{preview}",
                inline=False,
            )
        embed.set_footer(text="GeneralBot · /utility help group:<name> for details")
        await respond(interaction, embed=embed)

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction) -> None:
        start = time.perf_counter()
        await self.bot.db.ping()
        db_ms = (time.perf_counter() - start) * 1000
        latency = self.bot.latency
        gateway_ms = round(latency * 1000) if math.isfinite(latency) else 0
        embed = base_embed(
            "🏓 Pong",
            f"Gateway: **{gateway_ms} ms**\nDatabase: **{db_ms:.1f} ms**",
            color=SUCCESS,
        )
        await respond(interaction, embed=embed)

    @app_commands.command(name="userinfo", description="Show information about a user")
    @app_commands.describe(user="The user to inspect (defaults to you)")
    async def userinfo(
        self,
        interaction: discord.Interaction,
        user: discord.User | None = None,
    ) -> None:
        target = user or interaction.user
        member = None
        if interaction.guild is not None:
            member = await resolve_member(interaction.guild, target)

        embed = base_embed(f"👤 {target.display_name}", color=BRAND)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Username", value=f"`{target}`", inline=True)
        embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
        embed.add_field(name="Bot", value="Yes" if target.bot else "No", inline=True)
        embed.add_field(
            name="Account created",
            value=f"{discord.utils.format_dt(target.created_at, 'F')}\n"
            f"{discord.utils.format_dt(target.created_at, 'R')}",
            inline=False,
        )

        if member is not None and interaction.guild is not None:
            roles = [
                role.mention
                for role in reversed(member.roles)
                if role != interaction.guild.default_role
            ]
            role_text = " ".join(roles[:10]) if roles else "None"
            if len(roles) > 10:
                role_text += f" +{len(roles) - 10} more"
            embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
            embed.add_field(name="Top role", value=member.top_role.mention, inline=True)
            if member.joined_at is not None:
                embed.add_field(
                    name="Joined server",
                    value=f"{discord.utils.format_dt(member.joined_at, 'F')}\n"
                    f"{discord.utils.format_dt(member.joined_at, 'R')}",
                    inline=False,
                )
            embed.add_field(name=f"Roles ({len(roles)})", value=truncate(role_text, 1024), inline=False)
            if member.is_timed_out():
                until = member.timed_out_until
                if until is not None:
                    embed.add_field(
                        name="Timed out until",
                        value=discord.utils.format_dt(until, "F"),
                        inline=False,
                    )
        await respond(interaction, embed=embed)

    @app_commands.command(name="serverinfo", description="Show information about this server")
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        guild = await ensure_guild(interaction)
        if guild is None:
            return

        humans = sum(1 for member in guild.members if not member.bot)
        bots = sum(1 for member in guild.members if member.bot)
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        owner = guild.owner.mention if guild.owner else f"<@{guild.owner_id}>"

        embed = base_embed(f"🏰 {guild.name}", color=BRAND)
        if guild.icon is not None:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Owner", value=owner, inline=True)
        embed.add_field(name="ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(
            name="Created",
            value=f"{discord.utils.format_dt(guild.created_at, 'F')}\n"
            f"{discord.utils.format_dt(guild.created_at, 'R')}",
            inline=False,
        )
        embed.add_field(name="Members", value=f"{guild.member_count or 0} total\n{humans} humans · {bots} bots", inline=True)
        embed.add_field(
            name="Channels",
            value=f"{text_channels} text · {voice_channels} voice\n{categories} categories",
            inline=True,
        )
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(
            name="Boosts",
            value=f"Level {guild.premium_tier} · {guild.premium_subscription_count or 0} boosts",
            inline=True,
        )
        embed.add_field(name="Verification", value=guild.verification_level.name.title(), inline=True)
        embed.add_field(name="Locale", value=str(guild.preferred_locale), inline=True)
        if guild.banner is not None:
            embed.set_image(url=guild.banner.url)
        await respond(interaction, embed=embed)

    @app_commands.command(name="avatar", description="Show someone's avatar")
    @app_commands.describe(user="The user to inspect (defaults to you)")
    async def avatar(
        self,
        interaction: discord.Interaction,
        user: discord.User | None = None,
    ) -> None:
        target = user or interaction.user
        asset = target.display_avatar.with_size(1024)
        links = [
            f"[PNG]({target.display_avatar.replace(format='png', size=1024).url})",
            f"[JPG]({target.display_avatar.replace(format='jpg', size=1024).url})",
            f"[WEBP]({target.display_avatar.replace(format='webp', size=1024).url})",
        ]
        embed = base_embed(f"🖼️ {target.display_name}'s Avatar", " · ".join(links), color=BRAND)
        embed.set_image(url=asset.url)
        await respond(interaction, embed=embed)

    @app_commands.command(name="banner", description="Show someone's profile banner")
    @app_commands.describe(user="The user to inspect (defaults to you)")
    async def banner(
        self,
        interaction: discord.Interaction,
        user: discord.User | None = None,
    ) -> None:
        target = user or interaction.user
        banner = target.banner
        if banner is None:
            try:
                fresh = await self.bot.fetch_user(target.id)
            except discord.HTTPException:
                fresh = None
            if fresh is not None:
                target = fresh
                banner = fresh.banner
        if banner is None:
            await reply_error(interaction, f"{target.display_name} doesn't have a profile banner.", title="No banner")
            return
        embed = base_embed(f"🎨 {target.display_name}'s Banner", color=BRAND)
        embed.set_image(url=banner.with_size(1024).url)
        await respond(interaction, embed=embed)

    @app_commands.command(name="botinfo", description="Show information about the bot")
    async def botinfo(self, interaction: discord.Interaction) -> None:
        uptime = int((discord.utils.utcnow() - self.bot.start_time).total_seconds())
        command_count = len(list(self.bot.tree.walk_commands()))
        total_members = sum(guild.member_count or 0 for guild in self.bot.guilds)
        latency = self.bot.latency
        latency_ms = round(latency * 1000) if math.isfinite(latency) else 0
        embed = base_embed("🤖 GeneralBot", color=BRAND)
        if self.bot.user is not None:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Known members", value=f"{total_members:,}", inline=True)
        embed.add_field(name="Commands", value=str(command_count), inline=True)
        embed.add_field(name="Uptime", value=humanize_seconds(uptime), inline=True)
        embed.add_field(name="Latency", value=f"{latency_ms} ms", inline=True)
        embed.add_field(name="Python", value=platform.python_version(), inline=True)
        embed.add_field(name="discord.py", value=discord.__version__, inline=True)
        embed.set_footer(text="GeneralBot · moderation, fun, economy, and levels")
        await respond(interaction, embed=embed)

    @app_commands.command(name="invite", description="Get links to add the bot or install it for yourself")
    async def invite(self, interaction: discord.Interaction) -> None:
        app_id = self.bot.application_id or (self.bot.user.id if self.bot.user else None)
        if app_id is None:
            await reply_error(interaction, "I couldn't resolve my application ID yet. Try again in a moment.")
            return

        permissions = discord.Permissions(
            view_channel=True,
            send_messages=True,
            embed_links=True,
            read_message_history=True,
            manage_messages=True,
            manage_channels=True,
            manage_nicknames=True,
            manage_roles=True,
            kick_members=True,
            ban_members=True,
            moderate_members=True,
            add_reactions=True,
        )
        guild_url = (
            f"https://discord.com/oauth2/authorize?client_id={app_id}"
            f"&permissions={permissions.value}&scope=bot%20applications.commands"
        )
        user_url = (
            f"https://discord.com/oauth2/authorize?client_id={app_id}"
            "&integration_type=1&scope=applications.commands"
        )

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Add to Server", url=guild_url, emoji="🏠"))
        view.add_item(discord.ui.Button(label="Install for Me", url=user_url, emoji="👤"))

        embed = base_embed(
            "➕ Add GeneralBot",
            "**Add to Server** gives the bot its own member, permissions, and full moderation features.\n\n"
            "**Install for Me** is a user install: fun, utility, economy, and level commands work in "
            "DMs and servers, but moderation/config still need a server install.",
            color=BRAND,
        )
        embed.set_footer(text="Manage Server permission is required for the server invite · GeneralBot")
        await respond(interaction, embed=embed, view=view)


async def setup(bot: GeneralBot) -> None:
    await bot.add_cog(Utility(bot))
