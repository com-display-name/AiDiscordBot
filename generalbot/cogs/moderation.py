"""Moderation commands, grouped under /moderation."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..helpers import (
    ERROR,
    SUCCESS,
    WARNING,
    base_embed,
    hierarchy_problem,
    humanize_seconds,
    parse_duration,
    parse_iso,
    parse_user_id,
    reply_error,
    require_bot_perms,
    require_perms,
    resolve_member,
    respond,
    send_modlog,
    truncate,
    try_dm,
)

if TYPE_CHECKING:
    from ..bot import GeneralBot


def audit_reason(interaction: discord.Interaction, reason: str) -> str:
    return f"{interaction.user} ({interaction.user.id}): {reason}"[:512]


def action_embed(
    title: str,
    color: int,
    target: discord.abc.User,
    moderator: discord.abc.User,
    reason: str,
) -> discord.Embed:
    embed = base_embed(title, color=color)
    embed.add_field(name="User", value=f"{target.mention} (`{target.id}`)", inline=False)
    reason_text = (reason or "").strip()
    if reason_text and reason_text.lower() != "no reason provided":
        embed.add_field(name="Reason", value=truncate(reason_text, 1024), inline=False)
    embed.set_thumbnail(url=target.display_avatar.url)
    return embed


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class Moderation(commands.GroupCog, group_name="moderation", group_description="Moderation tools for keeping your server in order"):
    def __init__(self, bot: GeneralBot) -> None:
        self.bot = bot

    @app_commands.command(name="ban", description="Ban a user from the server")
    @app_commands.describe(
        user="The user to ban",
        reason="Why they are being banned",
        delete_messages="Days of recent messages to delete (0-7)",
    )
    async def ban(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str | None = None,
        delete_messages: app_commands.Range[int, 0, 7] = 0,
    ) -> None:
        guild = await require_perms(interaction, ban_members=True)
        if guild is None:
            return
        if not await require_bot_perms(interaction, ban_members=True):
            return

        reason = (reason or "No reason provided").strip() or "No reason provided"
        await interaction.response.defer(ephemeral=True)

        member = await resolve_member(guild, user)
        if member is not None:
            problem = hierarchy_problem(interaction, member)
            if problem:
                await reply_error(interaction, problem, title="Can't ban that user")
                return

        await try_dm(
            user,
            base_embed(
                f"You were banned from {guild.name}",
                f"**Reason:** {reason}\n\nIf you believe this was a mistake, contact the server staff.",
                color=ERROR,
            ),
        )

        try:
            await guild.ban(
                user,
                reason=audit_reason(interaction, reason),
                delete_message_days=delete_messages,
            )
        except discord.Forbidden:
            await reply_error(interaction, "Discord denied the ban. Check my role and permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error(interaction, f"Discord rejected the ban: `{exc}`")
            return

        embed = action_embed("🔨 User Banned", ERROR, user, interaction.user, reason)
        await respond(interaction, embed=embed, ephemeral=True)
        await send_modlog(self.bot, guild, action_embed("🔨 Member Banned", ERROR, user, interaction.user, reason))

    @app_commands.command(name="unban", description="Unban a user by ID")
    @app_commands.describe(user_id="The ID (or mention) of the banned user", reason="Why they are being unbanned")
    async def unban(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: str | None = None,
    ) -> None:
        guild = await require_perms(interaction, ban_members=True)
        if guild is None:
            return
        if not await require_bot_perms(interaction, ban_members=True):
            return

        target_id = parse_user_id(user_id)
        if target_id is None:
            await reply_error(interaction, "Provide a valid user ID or mention.", title="Invalid user")
            return
        reason = (reason or "No reason provided").strip() or "No reason provided"
        await interaction.response.defer(ephemeral=True)

        try:
            ban_entry = await guild.fetch_ban(discord.Object(id=target_id))
        except discord.NotFound:
            await reply_error(interaction, "That user is not banned in this server.", title="Not banned")
            return
        except discord.HTTPException as exc:
            await reply_error(interaction, f"Discord couldn't look up that ban: `{exc}`")
            return

        try:
            await guild.unban(ban_entry.user, reason=audit_reason(interaction, reason))
        except discord.Forbidden:
            await reply_error(interaction, "Discord denied the unban. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error(interaction, f"Discord rejected the unban: `{exc}`")
            return

        await try_dm(
            ban_entry.user,
            base_embed(
                f"You were unbanned from {guild.name}",
                f"**Reason:** {reason}",
                color=SUCCESS,
            ),
        )
        embed = action_embed("🔓 User Unbanned", SUCCESS, ban_entry.user, interaction.user, reason)
        await respond(interaction, embed=embed, ephemeral=True)
        await send_modlog(self.bot, guild, embed)

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(user="The member to kick", reason="Why they are being kicked")
    async def kick(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str | None = None,
    ) -> None:
        guild = await require_perms(interaction, kick_members=True)
        if guild is None:
            return
        if not await require_bot_perms(interaction, kick_members=True):
            return

        reason = (reason or "No reason provided").strip() or "No reason provided"
        await interaction.response.defer(ephemeral=True)
        member = await resolve_member(guild, user)
        if member is None:
            await reply_error(interaction, "That user isn't a member of this server.", title="Member not found")
            return

        problem = hierarchy_problem(interaction, member)
        if problem:
            await reply_error(interaction, problem, title="Can't kick that member")
            return

        await try_dm(
            member,
            base_embed(
                f"You were kicked from {guild.name}",
                f"**Reason:** {reason}\n\nYou can rejoin if you have an invite.",
                color=ERROR,
            ),
        )

        try:
            await member.kick(reason=audit_reason(interaction, reason))
        except discord.Forbidden:
            await reply_error(interaction, "Discord denied the kick. Check my role and permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error(interaction, f"Discord rejected the kick: `{exc}`")
            return

        embed = action_embed("👢 Member Kicked", ERROR, member, interaction.user, reason)
        await respond(interaction, embed=embed, ephemeral=True)
        await send_modlog(self.bot, guild, embed)

    @app_commands.command(name="timeout", description="Timeout a member for a duration")
    @app_commands.describe(
        user="The member to timeout",
        duration="Duration like 10m, 2h, or 7d (max 28 days)",
        reason="Why they are being timed out",
    )
    async def timeout(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        duration: str,
        reason: str | None = None,
    ) -> None:
        guild = await require_perms(interaction, moderate_members=True)
        if guild is None:
            return
        if not await require_bot_perms(interaction, moderate_members=True):
            return

        try:
            seconds = parse_duration(duration)
        except ValueError as exc:
            await reply_error(interaction, str(exc), title="Invalid duration")
            return
        if seconds < 60:
            await reply_error(interaction, "Timeouts must be at least 60 seconds.", title="Duration too short")
            return
        if seconds > 28 * 86400:
            await reply_error(interaction, "Timeouts can be at most 28 days.", title="Duration too long")
            return

        reason = (reason or "No reason provided").strip() or "No reason provided"
        await interaction.response.defer(ephemeral=True)
        member = await resolve_member(guild, user)
        if member is None:
            await reply_error(interaction, "That user isn't a member of this server.", title="Member not found")
            return

        problem = hierarchy_problem(interaction, member)
        if problem:
            await reply_error(interaction, problem, title="Can't timeout that member")
            return

        until = discord.utils.utcnow() + timedelta(seconds=seconds)
        await try_dm(
            member,
            base_embed(
                f"You were timed out in {guild.name}",
                f"**Duration:** {humanize_seconds(seconds)}\n**Reason:** {reason}",
                color=ERROR,
            ),
        )

        try:
            await member.timeout(timedelta(seconds=seconds), reason=audit_reason(interaction, reason))
        except discord.Forbidden:
            await reply_error(interaction, "Discord denied the timeout. Check my role and permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error(interaction, f"Discord rejected the timeout: `{exc}`")
            return

        embed = action_embed("⏳ Member Timed Out", WARNING, member, interaction.user, reason)
        embed.add_field(name="Duration", value=humanize_seconds(seconds), inline=True)
        embed.add_field(
            name="Expires",
            value=f"{discord.utils.format_dt(until, 'F')} ({discord.utils.format_dt(until, 'R')})",
            inline=True,
        )
        await respond(interaction, embed=embed, ephemeral=True)
        await send_modlog(self.bot, guild, embed)

    @app_commands.command(name="untimeout", description="Remove a member's timeout")
    @app_commands.describe(user="The member whose timeout to remove", reason="Why the timeout is being removed")
    async def untimeout(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str | None = None,
    ) -> None:
        guild = await require_perms(interaction, moderate_members=True)
        if guild is None:
            return
        if not await require_bot_perms(interaction, moderate_members=True):
            return

        reason = (reason or "No reason provided").strip() or "No reason provided"
        await interaction.response.defer(ephemeral=True)
        member = await resolve_member(guild, user)
        if member is None:
            await reply_error(interaction, "That user isn't a member of this server.", title="Member not found")
            return
        problem = hierarchy_problem(interaction, member)
        if problem:
            await reply_error(interaction, problem, title="Can't update that member")
            return

        try:
            await member.timeout(None, reason=audit_reason(interaction, reason))
        except discord.Forbidden:
            await reply_error(interaction, "Discord denied the request. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error(interaction, f"Discord rejected the request: `{exc}`")
            return

        await try_dm(
            member,
            base_embed(f"Your timeout in {guild.name} was removed", color=SUCCESS),
        )
        embed = action_embed("🔓 Timeout Removed", SUCCESS, member, interaction.user, reason)
        await respond(interaction, embed=embed, ephemeral=True)
        await send_modlog(self.bot, guild, embed)

    @app_commands.command(name="warn", description="Warn a user")
    @app_commands.describe(user="The user to warn", reason="Why they are being warned")
    async def warn(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str,
    ) -> None:
        guild = await require_perms(interaction, manage_messages=True)
        if guild is None:
            return
        if user.id == interaction.user.id:
            await reply_error(interaction, "You can't warn yourself.", title="Nice try")
            return
        if user.bot:
            await reply_error(interaction, "Bots cannot be warned.", title="Invalid target")
            return

        reason = reason.strip() or "No reason provided"
        if len(reason) > 1000:
            await reply_error(interaction, "Keep the warning reason under 1000 characters.")
            return

        warning_id = await self.bot.db.add_warning(
            guild.id,
            user.id,
            interaction.user.id,
            reason,
            discord.utils.utcnow().isoformat(),
        )
        count = await self.bot.db.count_warnings(guild.id, user.id)

        await try_dm(
            user,
            base_embed(
                f"You received a warning in {guild.name}",
                f"**Reason:** {reason}\n**Warning ID:** {warning_id}\n**Total warnings:** {count}",
                color=WARNING,
            ),
        )

        embed = action_embed("⚠️ Warning Issued", WARNING, user, interaction.user, reason)
        embed.add_field(name="Warning ID", value=f"`{warning_id}`", inline=True)
        embed.add_field(name="Total", value=f"{count} warning{'s' if count != 1 else ''}", inline=True)
        await respond(interaction, embed=embed, ephemeral=True)
        await send_modlog(self.bot, guild, embed)

    @app_commands.command(name="warnings", description="List a user's warnings")
    @app_commands.describe(user="The user to look up")
    async def warnings(self, interaction: discord.Interaction, user: discord.User) -> None:
        guild = await require_perms(interaction, manage_messages=True)
        if guild is None:
            return

        total = await self.bot.db.count_warnings(guild.id, user.id)
        if total == 0:
            await respond(
                interaction,
                embed=base_embed(
                    f"✅ No warnings for {user.display_name}",
                    "This user has a clean record in this server.",
                    color=SUCCESS,
                ),
                ephemeral=True,
            )
            return

        warnings = await self.bot.db.get_warnings(guild.id, user.id, limit=10)
        embed = base_embed(
            f"⚠️ Warnings for {user.display_name}",
            f"**Total:** {total} warning{'s' if total != 1 else ''}",
            color=WARNING,
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        for warning in warnings:
            created = parse_iso(warning["created_at"])
            when = discord.utils.format_dt(created, "f") if created else warning["created_at"]
            embed.add_field(
                name=f"#{warning['id']} · {when}",
                value=(
                    f"**Moderator:** <@{warning['moderator_id']}>\n"
                    f"**Reason:** {truncate(warning['reason'], 500)}"
                ),
                inline=False,
            )
        if total > len(warnings):
            embed.set_footer(text=f"Showing the latest {len(warnings)} of {total} · GeneralBot")
        await respond(interaction, embed=embed, ephemeral=True)

    @app_commands.command(name="delwarn", description="Delete a specific warning")
    @app_commands.describe(user="The user the warning belongs to", warning_id="The warning ID")
    async def delwarn(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        warning_id: int,
    ) -> None:
        guild = await require_perms(interaction, manage_messages=True)
        if guild is None:
            return
        deleted = await self.bot.db.delete_warning(guild.id, user.id, warning_id)
        if not deleted:
            await reply_error(
                interaction,
                f"No warning `#{warning_id}` was found for {user.display_name}.",
                title="Warning not found",
            )
            return
        await respond(
            interaction,
            embed=base_embed(
                "🗑️ Warning Deleted",
                f"Removed warning `#{warning_id}` from {user.mention}.",
                color=SUCCESS,
            ),
            ephemeral=True,
        )

    @app_commands.command(name="clearwarnings", description="Clear every warning for a user")
    @app_commands.describe(user="The user whose warnings to clear")
    async def clearwarnings(self, interaction: discord.Interaction, user: discord.User) -> None:
        guild = await require_perms(interaction, manage_messages=True)
        if guild is None:
            return
        count = await self.bot.db.clear_warnings(guild.id, user.id)
        if count == 0:
            await reply_error(interaction, "That user has no warnings.", title="Nothing to clear")
            return
        await respond(
            interaction,
            embed=base_embed(
                "🧹 Warnings Cleared",
                f"Removed **{count}** warning{'s' if count != 1 else ''} from {user.mention}.",
                color=SUCCESS,
            ),
            ephemeral=True,
        )

    @app_commands.command(name="purge", description="Bulk delete recent messages")
    @app_commands.describe(
        amount="How many messages to scan/delete (1-100). Omit to delete all available messages in chunks.",
        user="Only delete messages from this user",
    )
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100] | None = None,
        user: discord.User | None = None,
    ) -> None:
        guild = await require_perms(interaction, manage_messages=True)
        if guild is None:
            return
        if not await require_bot_perms(interaction, manage_messages=True, read_message_history=True):
            return
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await reply_error(interaction, "This command only works in regular text channels.")
            return

        await interaction.response.defer(ephemeral=True)
        check = (lambda message: message.author.id == user.id) if user else None
        reason = f"Purged by {interaction.user} ({interaction.user.id})"
        deleted_count = 0
        try:
            if amount is not None:
                deleted = await channel.purge(limit=amount, check=check, reason=reason)
                deleted_count = len(deleted)
            else:
                # Delete in chunks with a small delay to avoid hammering the API.
                while True:
                    deleted = await channel.purge(limit=100, check=check, reason=reason)
                    if not deleted:
                        break
                    deleted_count += len(deleted)
                    await asyncio.sleep(1.0)
        except discord.Forbidden:
            await reply_error(interaction, "Discord denied the purge. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error(interaction, f"Discord rejected the purge: `{exc}`")
            return

        description = f"Deleted **{deleted_count}** message{'s' if deleted_count != 1 else ''} in {channel.mention}."
        if user:
            description += f"\nFiltered to messages from {user.mention}."
        if amount is None:
            description += "\n(No amount specified — deleted available messages in chunks.)"
        await respond(
            interaction,
            embed=base_embed("🧹 Messages Purged", description, color=SUCCESS),
            ephemeral=True,
        )

        log = base_embed("🧹 Messages Purged", color=WARNING)
        log.add_field(name="Moderator", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        log.add_field(name="Channel", value=channel.mention, inline=True)
        log.add_field(name="Deleted", value=str(deleted_count), inline=True)
        if user:
            log.add_field(name="Filter", value=user.mention, inline=True)
        await send_modlog(self.bot, guild, log)

    @app_commands.command(name="slowmode", description="Set a channel's slowmode")
    @app_commands.describe(
        seconds="Slowmode in seconds (0-21600, 0 disables it)",
        channel="Channel to update (defaults to this one)",
    )
    async def slowmode(
        self,
        interaction: discord.Interaction,
        seconds: app_commands.Range[int, 0, 21600],
        channel: discord.TextChannel | None = None,
    ) -> None:
        guild = await require_perms(interaction, manage_channels=True)
        if guild is None:
            return
        if not await require_bot_perms(interaction, manage_channels=True):
            return
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await reply_error(interaction, "This command only works in regular text channels.")
            return

        try:
            await target.edit(slowmode_delay=seconds, reason=audit_reason(interaction, "Slowmode update"))
        except discord.Forbidden:
            await reply_error(interaction, "Discord denied the change. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error(interaction, f"Discord rejected the change: `{exc}`")
            return

        if seconds:
            description = f"Slowmode in {target.mention} is now **{humanize_seconds(seconds)}**."
        else:
            description = f"Slowmode in {target.mention} has been disabled."
        await respond(
            interaction,
            embed=base_embed("🐢 Slowmode Updated", description, color=SUCCESS),
            ephemeral=True,
        )

    @app_commands.command(name="lock", description="Stop members from sending messages in a channel")
    @app_commands.describe(channel="Channel to lock (defaults to this one)")
    async def lock(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        guild = await require_perms(interaction, manage_channels=True)
        if guild is None:
            return
        if not await require_bot_perms(interaction, manage_channels=True):
            return
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await reply_error(interaction, "This command only works in regular text channels.")
            return

        overwrite = target.overwrites_for(guild.default_role)
        overwrite.send_messages = False
        try:
            await target.set_permissions(
                guild.default_role,
                overwrite=overwrite,
                reason=audit_reason(interaction, "Channel locked"),
            )
        except discord.Forbidden:
            await reply_error(interaction, "Discord denied the change. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error(interaction, f"Discord rejected the change: `{exc}`")
            return

        await respond(
            interaction,
            embed=base_embed("🔒 Channel Locked", f"{target.mention} is now locked.", color=SUCCESS),
            ephemeral=True,
        )

    @app_commands.command(name="unlock", description="Let members send messages in a channel again")
    @app_commands.describe(channel="Channel to unlock (defaults to this one)")
    async def unlock(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        guild = await require_perms(interaction, manage_channels=True)
        if guild is None:
            return
        if not await require_bot_perms(interaction, manage_channels=True):
            return
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await reply_error(interaction, "This command only works in regular text channels.")
            return

        overwrite = target.overwrites_for(guild.default_role)
        overwrite.send_messages = None
        try:
            await target.set_permissions(
                guild.default_role,
                overwrite=overwrite,
                reason=audit_reason(interaction, "Channel unlocked"),
            )
        except discord.Forbidden:
            await reply_error(interaction, "Discord denied the change. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error(interaction, f"Discord rejected the change: `{exc}`")
            return

        await respond(
            interaction,
            embed=base_embed("🔓 Channel Unlocked", f"{target.mention} is unlocked.", color=SUCCESS),
            ephemeral=True,
        )

    @app_commands.command(name="purgechannel", description="Delete and recreate a channel with the same properties")
    @app_commands.describe(channel="The channel to purge (defaults to this channel)")
    async def purgechannel(
        self,
        interaction: discord.Interaction,
        channel: discord.abc.GuildChannel | None = None,
    ) -> None:
        guild = await require_perms(interaction, manage_channels=True)
        if guild is None:
            return
        if not await require_bot_perms(interaction, manage_channels=True):
            return

        target = channel or interaction.channel
        if not isinstance(target, discord.abc.GuildChannel) or target.guild != guild:
            await reply_error(interaction, "Pick a channel in this server to purge.", title="Invalid channel")
            return

        await interaction.response.defer(ephemeral=True)
        reason = audit_reason(interaction, "Channel purge/recreate")
        try:
            new_channel = await target.clone(reason=reason)
            try:
                await new_channel.edit(position=target.position)
            except (discord.Forbidden, discord.HTTPException):
                pass
            await target.delete(reason=reason)
        except discord.Forbidden:
            await reply_error(interaction, "I don't have permission to clone or delete that channel.")
            return
        except discord.HTTPException as exc:
            await reply_error(interaction, f"Discord rejected the channel purge: `{exc}`")
            return

        if isinstance(new_channel, discord.TextChannel):
            try:
                await new_channel.send(
                    embed=base_embed(
                        "♻️ Channel Purged",
                        f"This channel was recreated by {interaction.user.mention}.",
                        color=WARNING,
                    )
                )
            except discord.HTTPException:
                pass

        try:
            await respond(
                interaction,
                embed=base_embed(
                    "♻️ Channel Purged",
                    f"Recreated {new_channel.mention} (`{new_channel.id}`).",
                    color=SUCCESS,
                ),
                ephemeral=True,
            )
        except discord.HTTPException:
            pass

        log = base_embed("♻️ Channel Purged", color=WARNING)
        log.add_field(name="Moderator", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        log.add_field(name="Old Channel", value=f"#{target.name} (`{target.id}`)", inline=True)
        log.add_field(name="New Channel", value=getattr(new_channel, "mention", f"`{new_channel.id}`"), inline=True)
        await send_modlog(self.bot, guild, log)

    @app_commands.command(name="nickname", description="Change or reset a member's nickname")
    @app_commands.describe(user="The member to update", nickname="New nickname (leave empty to reset)")
    async def nickname(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        nickname: str | None = None,
    ) -> None:
        guild = await require_perms(interaction, manage_nicknames=True)
        if guild is None:
            return
        if not await require_bot_perms(interaction, manage_nicknames=True):
            return
        member = await resolve_member(guild, user)
        if member is None:
            await reply_error(interaction, "That user isn't a member of this server.", title="Member not found")
            return

        problem = hierarchy_problem(interaction, member, allow_self=True)
        if problem:
            await reply_error(interaction, problem, title="Can't rename that member")
            return

        new_nick = (nickname or "").strip() or None
        if new_nick is not None and len(new_nick) > 32:
            await reply_error(interaction, "Nicknames must be 32 characters or fewer.", title="Nickname too long")
            return

        old_name = member.display_name
        try:
            await member.edit(nick=new_nick, reason=audit_reason(interaction, "Nickname change"))
        except discord.Forbidden:
            await reply_error(interaction, "Discord denied the change. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error(interaction, f"Discord rejected the change: `{exc}`")
            return

        if new_nick is None:
            description = f"Reset **{old_name}**'s nickname."
        else:
            description = f"Changed **{old_name}**'s nickname to **{new_nick}**."
        await respond(
            interaction,
            embed=base_embed("📝 Nickname Updated", description, color=SUCCESS),
            ephemeral=True,
        )


async def setup(bot: GeneralBot) -> None:
    await bot.add_cog(Moderation(bot))
