"""Classic prefix commands for moderation, roles, and utility actions.

The bot accepts ?, ., ', ;, and ! as prefixes. These commands mirror many of
the slash tools and add common prefix-only conveniences such as ?role, ?mute,
and ?setname.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from ..helpers import (
    BRAND,
    ERROR,
    SUCCESS,
    WARNING,
    base_embed,
    hierarchy_problem_for,
    humanize_seconds,
    parse_duration,
    parse_iso,
    parse_user_id,
    reply_ctx,
    reply_error_ctx,
    reply_success_ctx,
    require_bot_perms_ctx,
    resolve_member,
    send_modlog,
    truncate,
    try_dm,
    utcnow_iso,
)

if TYPE_CHECKING:
    from ..bot import GeneralBot


def _audit_reason(ctx: commands.Context, reason: str) -> str:
    return f"{ctx.author} ({ctx.author.id}): {reason}"[:512]


def _action_embed(
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


MUTED_ROLE_NAME = "Muted"


class PrefixCommands(commands.Cog, name="PrefixCommands"):
    def __init__(self, bot: GeneralBot) -> None:
        self.bot = bot
        self._moderation_task: asyncio.Task | None = None

    async def cog_load(self) -> None:
        self._moderation_task = asyncio.create_task(self._moderation_loop())

    def cog_unload(self) -> None:
        if self._moderation_task is not None:
            self._moderation_task.cancel()
            self._moderation_task = None

    def _hierarchy_problem(
        self,
        ctx: commands.Context,
        target: discord.Member,
        *,
        allow_self: bool = False,
    ) -> str | None:
        return hierarchy_problem_for(
            ctx.guild,
            ctx.author,
            ctx.bot.user,
            target,
            allow_self=allow_self,
        )

    async def _resolve_member_targets(
        self,
        ctx: commands.Context,
        target: str,
    ) -> tuple[list[discord.Member], str | None, bool]:
        """Return (members, error, is_selector)."""
        guild = ctx.guild
        if guild is None:
            return [], "This command only works in a server.", False

        raw = (target or "").strip()
        lowered = raw.lower()
        if lowered in {"all", "everyone", "@everyone"}:
            members = [m for m in guild.members if not m.bot]
            if not members:
                return [], "No members found to target.", True
            return members, "all", True
        if lowered in {"others", "other"}:
            members = [m for m in guild.members if m.id != ctx.author.id and not m.bot]
            if not members:
                return [], "No other members found to target.", True
            return members, "others", True

        role = None
        try:
            role = await commands.RoleConverter().convert(ctx, raw)
        except commands.BadArgument:
            role = None
        if role is not None:
            members = list(role.members)
            if not members:
                return [], f"No members have {role.mention}.", True
            return members, None, True

        try:
            member = await commands.MemberConverter().convert(ctx, raw)
        except commands.BadArgument:
            return [], "Couldn't find that member, role, or selector (`all`, `others`, or a role).", False
        return [member], None, False

    async def _resolve_user_targets(
        self,
        ctx: commands.Context,
        target: str,
    ) -> tuple[list[discord.abc.User], str | None, bool]:
        guild = ctx.guild
        if guild is None:
            return [], "This command only works in a server.", False
        members, error, is_selector = await self._resolve_member_targets(ctx, target)
        if is_selector or members:
            # for selectors we can only act on members
            if not members:
                return [], error, True
            return list(members), error, is_selector
        try:
            user = await commands.UserConverter().convert(ctx, target)
        except commands.BadArgument:
            return [], "Couldn't find that user, role, or selector (`all`, `others`, or a role).", False
        return [user], None, False

    @staticmethod
    def _summary_embed(title: str, description: str, *, color: int = SUCCESS) -> discord.Embed:
        return base_embed(title, description, color=color)

    @commands.command(name="help", usage="")
    async def help_command(self, ctx: commands.Context) -> None:
        embed = base_embed(
            "⌨️ Prefix Commands",
            "I accept `?`, `.`, `'`, `;`, and `!` prefixes.\n"
            "Examples: `?ban @user`, `.kick @user`, `'timeout @user 10m`, `;mute @user 10m`, `;tempban @user 1d`, `;warn @user`.\n\n"
            "**Moderation/Channels:** `ban`, `tempban`, `unban`, `kick`, `timeout`, `mute`, `untimeout`, "
            "`unmute`, `warn`, `warnings`, `delwarn`, `clearwarnings`, `purge`, `clear`, `purgechannel`, "
            "`addchannel`, `removechannel`, `copychannel`, `slowmode`, `lock`, `unlock`, `nickname`, `setname`\n\n"
            "Selectors: `all`, `others`, and `@role` work on many member-target commands (e.g. `?mute @role 10m`).\n"
            "Durations: `0` (or `0m`/`0h`/`0d`) means infinite for `mute` and `tempban`.\n\n"
            "**Roles:** `role <member|selector> <role>` (toggle), `role add`, `role remove`, `role list`, `role info`, `addrole`, "
            "`removerole`, `createrole`, `delrole`, `rolecolor`\n\n"
            "**Utility:** `avatar`, `servericon`, `membercount`, `userinfo`, `serverinfo`, "
            "`setservername`\n\n"
            "Slash commands still work: try `/utility help`.",
            color=SUCCESS,
            footer="GeneralBot · prefix commands",
        )
        await reply_ctx(ctx, embed=embed)

    @commands.command(name="ban", usage="<user|all|others|@role> [reason]")
    @commands.guild_only()
    @commands.has_guild_permissions(ban_members=True)
    async def ban(
        self,
        ctx: commands.Context,
        target: str,
        *,
        reason: str = "No reason provided",
    ) -> None:
        if not await require_bot_perms_ctx(ctx, ban_members=True):
            return
        members, note, is_selector = await self._resolve_member_targets(ctx, target)
        if not members:
            # try single user ID/mention even if not in server
            user = None
            try:
                user = await commands.UserConverter().convert(ctx, target)
            except commands.BadArgument:
                user = None
            if user is None:
                await reply_error_ctx(ctx, note or "Couldn't find that user or selector.", title="Invalid target")
                return
            users = [user]
        else:
            users = list(members)

        reason = (reason or "No reason provided").strip() or "No reason provided"

        async def ban_one(user: discord.abc.User) -> tuple[bool, str]:
            member = user if isinstance(user, discord.Member) else await resolve_member(ctx.guild, user)
            if member is not None:
                problem = self._hierarchy_problem(ctx, member)
                if problem:
                    return False, problem
            await try_dm(
                user,
                base_embed(
                    f"You were banned from {ctx.guild.name}",
                    f"**Reason:** {reason}\n\nIf you believe this was a mistake, contact the server staff.",
                    color=ERROR,
                ),
            )
            try:
                await ctx.guild.ban(user, reason=_audit_reason(ctx, reason), delete_message_days=0)
            except discord.Forbidden:
                return False, "missing permissions"
            except discord.HTTPException:
                return False, "Discord error"
            await self.bot.db.remove_scheduled_unban(ctx.guild.id, user.id)
            return True, "banned"

        if not is_selector and len(users) == 1:
            user = users[0]
            ok, msg = await ban_one(user)
            if not ok:
                await reply_error_ctx(ctx, msg, title="Can't ban that user")
                return
            await reply_ctx(ctx, embed=_action_embed("🔨 User Banned", ERROR, user, ctx.author, reason))
            await send_modlog(self.bot, ctx.guild, _action_embed("🔨 Member Banned", ERROR, user, ctx.author, reason))
            return

        ok_count = failed = 0
        for user in users:
            ok, _ = await ban_one(user)
            ok_count += 1 if ok else 0
            failed += 0 if ok else 1
        desc = f"Banned **{ok_count}** user{'s' if ok_count != 1 else ''}."
        if failed:
            desc += f"\nSkipped/failed: **{failed}**"
        if is_selector and note in {"all", "others"}:
            desc += f"\nTarget: **{note}**"
        await reply_ctx(ctx, embed=self._summary_embed("🔨 Bulk Ban", desc, color=ERROR))
        if ok_count:
            log = base_embed("🔨 Bulk Ban", desc, color=ERROR)
            if reason.lower() != "no reason provided":
                log.add_field(name="Reason", value=truncate(reason, 1024), inline=False)
            await send_modlog(self.bot, ctx.guild, log)

    @commands.command(name="tempban", usage="<user|all|others|@role> <duration> [reason]")
    @commands.guild_only()
    @commands.has_guild_permissions(ban_members=True)
    async def tempban(
        self,
        ctx: commands.Context,
        target: str,
        duration: str,
        *,
        reason: str = "No reason provided",
    ) -> None:
        if not await require_bot_perms_ctx(ctx, ban_members=True):
            return
        members, note, is_selector = await self._resolve_member_targets(ctx, target)
        if not members:
            user = None
            try:
                user = await commands.UserConverter().convert(ctx, target)
            except commands.BadArgument:
                user = None
            if user is None:
                await reply_error_ctx(ctx, note or "Couldn't find that user or selector.", title="Invalid target")
                return
            users = [user]
        else:
            users = list(members)

        try:
            seconds = parse_duration(duration)
        except ValueError as exc:
            await reply_error_ctx(ctx, str(exc), title="Invalid duration")
            return
        reason = (reason or "No reason provided").strip() or "No reason provided"
        infinite = seconds == 0
        duration_text = "Forever" if infinite else humanize_seconds(seconds)
        until = None if infinite else discord.utils.utcnow() + timedelta(seconds=seconds)

        async def ban_one(user: discord.abc.User) -> tuple[bool, str]:
            member = user if isinstance(user, discord.Member) else await resolve_member(ctx.guild, user)
            if member is not None:
                problem = self._hierarchy_problem(ctx, member)
                if problem:
                    return False, problem
            await try_dm(
                user,
                base_embed(
                    f"You were temporarily banned from {ctx.guild.name}",
                    f"**Duration:** {duration_text}\n**Reason:** {reason}\n\nIf you believe this was a mistake, contact the server staff.",
                    color=ERROR,
                ),
            )
            try:
                await ctx.guild.ban(user, reason=_audit_reason(ctx, reason), delete_message_days=0)
            except discord.Forbidden:
                return False, "missing permissions"
            except discord.HTTPException:
                return False, "Discord error"
            if not infinite:
                unban_at = (discord.utils.utcnow() + timedelta(seconds=seconds)).isoformat()
                await self.bot.db.add_scheduled_unban(ctx.guild.id, user.id, unban_at)
            else:
                await self.bot.db.remove_scheduled_unban(ctx.guild.id, user.id)
            return True, "banned"

        if not is_selector and len(users) == 1:
            user = users[0]
            ok, msg = await ban_one(user)
            if not ok:
                await reply_error_ctx(ctx, msg, title="Can't ban that user")
                return
            embed = _action_embed("🔨 User Tempbanned", ERROR, user, ctx.author, reason)
            embed.add_field(name="Duration", value=duration_text, inline=True)
            if until is not None:
                embed.add_field(name="Expires", value=f"{discord.utils.format_dt(until, 'F')} ({discord.utils.format_dt(until, 'R')})", inline=True)
            await reply_ctx(ctx, embed=embed)
            await send_modlog(self.bot, ctx.guild, embed)
            return

        ok_count = failed = 0
        for user in users:
            ok, _ = await ban_one(user)
            ok_count += 1 if ok else 0
            failed += 0 if ok else 1
        desc = f"Tempbanned **{ok_count}** user{'s' if ok_count != 1 else ''} for **{duration_text}**."
        if failed:
            desc += f"\nSkipped/failed: **{failed}**"
        if is_selector and note in {"all", "others"}:
            desc += f"\nTarget: **{note}**"
        await reply_ctx(ctx, embed=self._summary_embed("🔨 Bulk Tempban", desc, color=ERROR))
        if ok_count:
            log = base_embed("🔨 Bulk Tempban", desc, color=ERROR)
            if reason.lower() != "no reason provided":
                log.add_field(name="Reason", value=truncate(reason, 1024), inline=False)
            await send_modlog(self.bot, ctx.guild, log)

    @commands.command(name="unban", usage="<user_id> [reason]")
    @commands.guild_only()
    @commands.has_guild_permissions(ban_members=True)
    async def unban(
        self,
        ctx: commands.Context,
        user_id: str,
        *,
        reason: str = "No reason provided",
    ) -> None:
        if not await require_bot_perms_ctx(ctx, ban_members=True):
            return

        target_id = parse_user_id(user_id)
        if target_id is None:
            await reply_error_ctx(ctx, "Provide a valid user ID or mention.", title="Invalid user")
            return
        reason = (reason or "No reason provided").strip() or "No reason provided"

        try:
            ban_entry = await ctx.guild.fetch_ban(discord.Object(id=target_id))
        except discord.NotFound:
            await reply_error_ctx(ctx, "That user is not banned in this server.", title="Not banned")
            return
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord couldn't look up that ban: `{exc}`")
            return

        try:
            await ctx.guild.unban(ban_entry.user, reason=_audit_reason(ctx, reason))
        except discord.Forbidden:
            await reply_error_ctx(ctx, "Discord denied the unban. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected the unban: `{exc}`")
            return

        await self.bot.db.remove_scheduled_unban(ctx.guild.id, ban_entry.user.id)

        await try_dm(
            ban_entry.user,
            base_embed(
                f"You were unbanned from {ctx.guild.name}",
                f"**Reason:** {reason}",
                color=SUCCESS,
            ),
        )
        embed = _action_embed("🔓 User Unbanned", SUCCESS, ban_entry.user, ctx.author, reason)
        await reply_ctx(ctx, embed=embed)
        await send_modlog(self.bot, ctx.guild, embed)

    @commands.command(name="kick", usage="<member|all|others|@role> [reason]")
    @commands.guild_only()
    @commands.has_guild_permissions(kick_members=True)
    async def kick(
        self,
        ctx: commands.Context,
        target: str,
        *,
        reason: str = "No reason provided",
    ) -> None:
        if not await require_bot_perms_ctx(ctx, kick_members=True):
            return
        members, note, is_selector = await self._resolve_member_targets(ctx, target)
        if not members:
            await reply_error_ctx(ctx, note or "No members found.", title="Invalid target")
            return
        reason = (reason or "No reason provided").strip() or "No reason provided"

        async def kick_one(member: discord.Member) -> tuple[bool, str]:
            problem = self._hierarchy_problem(ctx, member)
            if problem:
                return False, problem
            await try_dm(
                member,
                base_embed(
                    f"You were kicked from {ctx.guild.name}",
                    f"**Reason:** {reason}\n\nYou can rejoin if you have an invite.",
                    color=ERROR,
                ),
            )
            try:
                await member.kick(reason=_audit_reason(ctx, reason))
            except discord.Forbidden:
                return False, "missing permissions"
            except discord.HTTPException:
                return False, "Discord error"
            return True, "kicked"

        if not is_selector and len(members) == 1:
            member = members[0]
            ok, msg = await kick_one(member)
            if not ok:
                await reply_error_ctx(ctx, msg, title="Can't kick that member")
                return
            embed = _action_embed("👢 Member Kicked", ERROR, member, ctx.author, reason)
            await reply_ctx(ctx, embed=embed)
            await send_modlog(self.bot, ctx.guild, embed)
            return

        ok_count = failed = 0
        for member in members:
            ok, _ = await kick_one(member)
            ok_count += 1 if ok else 0
            failed += 0 if ok else 1
        desc = f"Kicked **{ok_count}** member{'s' if ok_count != 1 else ''}."
        if failed:
            desc += f"\nSkipped/failed: **{failed}**"
        if is_selector and note in {"all", "others"}:
            desc += f"\nTarget: **{note}**"
        await reply_ctx(ctx, embed=self._summary_embed("👢 Bulk Kick", desc, color=ERROR))
        if ok_count:
            log = base_embed("👢 Bulk Kick", desc, color=ERROR)
            if reason.lower() != "no reason provided":
                log.add_field(name="Reason", value=truncate(reason, 1024), inline=False)
            await send_modlog(self.bot, ctx.guild, log)

    async def _get_or_create_muted_role(self, ctx: commands.Context) -> discord.Role | None:
        guild = ctx.guild
        role = discord.utils.get(guild.roles, name=MUTED_ROLE_NAME)
        if role is None:
            if not await require_bot_perms_ctx(ctx, manage_roles=True, manage_channels=True):
                return None
            perms = discord.Permissions(
                send_messages=False,
                send_messages_in_threads=False,
                create_public_threads=False,
                create_private_threads=False,
                add_reactions=False,
                speak=False,
                stream=False,
                use_application_commands=False,
            )
            try:
                role = await guild.create_role(
                    name=MUTED_ROLE_NAME,
                    permissions=perms,
                    reason="Create muted role for ?mute",
                )
            except discord.Forbidden:
                await reply_error_ctx(ctx, "I couldn't create the Muted role. Check my permissions.")
                return None
            except discord.HTTPException as exc:
                await reply_error_ctx(ctx, f"Discord rejected creating the Muted role: `{exc}`")
                return None

            overwrite = discord.PermissionOverwrite(
                send_messages=False,
                send_messages_in_threads=False,
                create_public_threads=False,
                create_private_threads=False,
                add_reactions=False,
                speak=False,
                stream=False,
                connect=False,
                use_application_commands=False,
            )
            for channel in guild.channels:
                try:
                    await channel.set_permissions(
                        role,
                        overwrite=overwrite,
                        reason="Apply muted role permissions",
                    )
                except (discord.Forbidden, discord.HTTPException):
                    continue
        return role

    async def _moderation_loop(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self._process_due_unmutes()
                await self._process_due_unbans()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                raise

    async def _process_due_unmutes(self) -> None:
        now = discord.utils.utcnow().isoformat()
        due = await self.bot.db.get_due_scheduled_unmutes(now)
        for item in due:
            guild = self.bot.get_guild(int(item["guild_id"]))
            if guild is None:
                continue
            user_id = int(item["user_id"])
            role_id = int(item["role_id"])
            await self.bot.db.remove_scheduled_unmute(guild.id, user_id)
            role = guild.get_role(role_id)
            if role is None:
                continue
            member = guild.get_member(user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(user_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    continue
            if role not in member.roles:
                continue
            try:
                await member.remove_roles(role, reason="Automatic unmute (scheduled)")
            except (discord.Forbidden, discord.HTTPException):
                continue

    async def _process_due_unbans(self) -> None:
        now = discord.utils.utcnow().isoformat()
        due = await self.bot.db.get_due_scheduled_unbans(now)
        for item in due:
            guild = self.bot.get_guild(int(item["guild_id"]))
            if guild is None:
                continue
            user_id = int(item["user_id"])
            await self.bot.db.remove_scheduled_unban(guild.id, user_id)
            try:
                await guild.unban(discord.Object(id=user_id), reason="Automatic unban (scheduled)")
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue

    async def _apply_timeout(
        self,
        ctx: commands.Context,
        member: discord.Member,
        duration: str,
        *,
        reason: str = "No reason provided",
        action: str = "timed out",
        embed_title: str = "⏳ Member Timed Out",
        error_title: str = "Can't timeout that member",
    ) -> bool:
        if not await require_bot_perms_ctx(ctx, moderate_members=True):
            return False

        try:
            seconds = parse_duration(duration)
        except ValueError as exc:
            await reply_error_ctx(ctx, str(exc), title="Invalid duration")
            return False
        if seconds < 60:
            await reply_error_ctx(ctx, "Timeouts must be at least 60 seconds.", title="Duration too short")
            return False
        if seconds > 28 * 86400:
            await reply_error_ctx(ctx, "Timeouts can be at most 28 days.", title="Duration too long")
            return False

        problem = self._hierarchy_problem(ctx, member)
        if problem:
            await reply_error_ctx(ctx, problem, title=error_title)
            return False
        reason = (reason or "No reason provided").strip() or "No reason provided"
        until = discord.utils.utcnow() + timedelta(seconds=seconds)

        await try_dm(
            member,
            base_embed(
                f"You were {action} in {ctx.guild.name}",
                f"**Duration:** {humanize_seconds(seconds)}\n**Reason:** {reason}",
                color=ERROR,
            ),
        )

        try:
            await member.timeout(
                timedelta(seconds=seconds),
                reason=_audit_reason(ctx, reason),
            )
        except discord.Forbidden:
            await reply_error_ctx(ctx, "Discord denied the request. Check my role and permissions.")
            return False
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected the request: `{exc}`")
            return False

        embed = _action_embed(embed_title, WARNING, member, ctx.author, reason)
        embed.add_field(name="Duration", value=humanize_seconds(seconds), inline=True)
        embed.add_field(
            name="Expires",
            value=f"{discord.utils.format_dt(until, 'F')} ({discord.utils.format_dt(until, 'R')})",
            inline=True,
        )
        await reply_ctx(ctx, embed=embed)
        await send_modlog(self.bot, ctx.guild, embed)
        return True

    async def _remove_timeout(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str = "No reason provided",
        embed_title: str = "🔓 Timeout Removed",
        dm_text: str = "Your timeout in {guild} was removed",
        error_title: str = "Can't update that member",
    ) -> bool:
        if not await require_bot_perms_ctx(ctx, moderate_members=True):
            return False

        problem = self._hierarchy_problem(ctx, member)
        if problem:
            await reply_error_ctx(ctx, problem, title=error_title)
            return False
        reason = (reason or "No reason provided").strip() or "No reason provided"

        try:
            await member.timeout(None, reason=_audit_reason(ctx, reason))
        except discord.Forbidden:
            await reply_error_ctx(ctx, "Discord denied the request. Check my permissions.")
            return False
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected the request: `{exc}`")
            return False

        await try_dm(member, base_embed(dm_text.format(guild=ctx.guild.name), color=SUCCESS))
        embed = _action_embed(embed_title, SUCCESS, member, ctx.author, reason)
        await reply_ctx(ctx, embed=embed)
        await send_modlog(self.bot, ctx.guild, embed)
        return True

    @commands.command(name="timeout", usage="<member|all|others|@role> <duration> [reason]")
    @commands.guild_only()
    @commands.has_guild_permissions(moderate_members=True)
    async def timeout(
        self,
        ctx: commands.Context,
        target: str,
        duration: str,
        *,
        reason: str = "No reason provided",
    ) -> None:
        if not await require_bot_perms_ctx(ctx, moderate_members=True):
            return
        members, note, is_selector = await self._resolve_member_targets(ctx, target)
        if not members:
            await reply_error_ctx(ctx, note or "No members found.", title="Invalid target")
            return
        try:
            seconds = parse_duration(duration)
        except ValueError as exc:
            await reply_error_ctx(ctx, str(exc), title="Invalid duration")
            return
        if seconds < 60:
            await reply_error_ctx(ctx, "Timeouts must be at least 60 seconds.", title="Duration too short")
            return
        if seconds > 28 * 86400:
            await reply_error_ctx(ctx, "Timeouts can be at most 28 days.", title="Duration too long")
            return
        reason = (reason or "No reason provided").strip() or "No reason provided"
        until = discord.utils.utcnow() + timedelta(seconds=seconds)

        async def timeout_one(member: discord.Member) -> tuple[bool, str]:
            problem = self._hierarchy_problem(ctx, member)
            if problem:
                return False, problem
            await try_dm(
                member,
                base_embed(
                    f"You were timed out in {ctx.guild.name}",
                    f"**Duration:** {humanize_seconds(seconds)}\n**Reason:** {reason}",
                    color=ERROR,
                ),
            )
            try:
                await member.timeout(timedelta(seconds=seconds), reason=_audit_reason(ctx, reason))
            except discord.Forbidden:
                return False, "missing permissions"
            except discord.HTTPException:
                return False, "Discord error"
            return True, "timed out"

        if not is_selector and len(members) == 1:
            member = members[0]
            ok, msg = await timeout_one(member)
            if not ok:
                await reply_error_ctx(ctx, msg, title="Can't timeout that member")
                return
            embed = _action_embed("⏳ Member Timed Out", WARNING, member, ctx.author, reason)
            embed.add_field(name="Duration", value=humanize_seconds(seconds), inline=True)
            embed.add_field(name="Expires", value=f"{discord.utils.format_dt(until, 'F')} ({discord.utils.format_dt(until, 'R')})", inline=True)
            await reply_ctx(ctx, embed=embed)
            await send_modlog(self.bot, ctx.guild, embed)
            return

        ok_count = failed = 0
        for member in members:
            ok, _ = await timeout_one(member)
            ok_count += 1 if ok else 0
            failed += 0 if ok else 1
        desc = f"Timed out **{ok_count}** member{'s' if ok_count != 1 else ''} for **{humanize_seconds(seconds)}**."
        if failed:
            desc += f"\nSkipped/failed: **{failed}**"
        if is_selector and note in {"all", "others"}:
            desc += f"\nTarget: **{note}**"
        await reply_ctx(ctx, embed=self._summary_embed("⏳ Bulk Timeout", desc, color=WARNING))
        if ok_count:
            log = base_embed("⏳ Bulk Timeout", desc, color=WARNING)
            if reason.lower() != "no reason provided":
                log.add_field(name="Reason", value=truncate(reason, 1024), inline=False)
            await send_modlog(self.bot, ctx.guild, log)

    @commands.command(name="mute", usage="<member|all|others|@role> [duration=10m] [reason]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def mute(
        self,
        ctx: commands.Context,
        target: str,
        duration: str = "10m",
        *,
        reason: str = "No reason provided",
    ) -> None:
        if not await require_bot_perms_ctx(ctx, manage_roles=True):
            return

        members, note, is_selector = await self._resolve_member_targets(ctx, target)
        if not members:
            await reply_error_ctx(ctx, note or "No members found.", title="Invalid target")
            return

        try:
            seconds = parse_duration(duration)
        except ValueError:
            reason = f"{duration} {reason}".strip() if reason != "No reason provided" else duration
            seconds = 600
        if seconds != 0 and seconds < 60:
            await reply_error_ctx(ctx, "Mute duration must be at least 60 seconds (or `0` for infinite).", title="Duration too short")
            return
        reason = (reason or "No reason provided").strip() or "No reason provided"

        role = await self._get_or_create_muted_role(ctx)
        if role is None:
            return
        me = ctx.guild.me
        if me is not None and role.position >= me.top_role.position:
            await reply_error_ctx(
                ctx,
                f"Move my highest role above **{role.name}** so I can assign it.",
                title="Can't assign Muted role",
            )
            return

        infinite = seconds == 0
        duration_text = "Forever" if infinite else humanize_seconds(seconds)
        until = None if infinite else discord.utils.utcnow() + timedelta(seconds=seconds)

        async def mute_one(member: discord.Member) -> tuple[bool, str]:
            problem = self._hierarchy_problem(ctx, member)
            if problem:
                return False, problem
            if role in member.roles:
                return False, "already muted"
            await try_dm(
                member,
                base_embed(
                    f"You were muted in {ctx.guild.name}",
                    f"**Duration:** {duration_text}\n**Reason:** {reason}",
                    color=ERROR,
                ),
            )
            try:
                await member.add_roles(role, reason=_audit_reason(ctx, reason))
            except discord.Forbidden:
                return False, "missing permissions"
            except discord.HTTPException:
                return False, "Discord error"
            if not infinite:
                unmute_at = (discord.utils.utcnow() + timedelta(seconds=seconds)).isoformat()
                await self.bot.db.add_scheduled_unmute(ctx.guild.id, member.id, role.id, unmute_at)
            else:
                await self.bot.db.remove_scheduled_unmute(ctx.guild.id, member.id)
            return True, "muted"

        if not is_selector and len(members) == 1:
            member = members[0]
            ok, msg = await mute_one(member)
            if not ok:
                title = "Already muted" if msg == "already muted" else "Can't mute that member"
                text = f"{member.mention} is already muted." if msg == "already muted" else msg
                await reply_error_ctx(ctx, text, title=title)
                return
            embed = _action_embed("🔇 Member Muted", WARNING, member, ctx.author, reason)
            embed.add_field(name="Duration", value=duration_text, inline=True)
            if until is not None:
                embed.add_field(
                    name="Expires",
                    value=f"{discord.utils.format_dt(until, 'F')} ({discord.utils.format_dt(until, 'R')})",
                    inline=True,
                )
            embed.add_field(name="Role", value=role.mention, inline=True)
            await reply_ctx(ctx, embed=embed)
            await send_modlog(self.bot, ctx.guild, embed)
            return

        ok_count = 0
        already = 0
        failed = 0
        for member in members:
            ok, msg = await mute_one(member)
            if ok:
                ok_count += 1
            elif msg == "already muted":
                already += 1
            else:
                failed += 1

        desc = (
            f"Muted **{ok_count}** member{'s' if ok_count != 1 else ''} for **{duration_text}**.\n"
            f"Role: {role.mention}"
        )
        if already:
            desc += f"\nAlready muted: **{already}**"
        if failed:
            desc += f"\nSkipped/failed: **{failed}**"
        if is_selector and note in {"all", "others"}:
            desc += f"\nTarget: **{note}**"
        await reply_ctx(ctx, embed=self._summary_embed("🔇 Bulk Mute", desc, color=WARNING))
        if ok_count:
            log = base_embed("🔇 Bulk Mute", desc, color=WARNING)
            if reason.lower() != "no reason provided":
                log.add_field(name="Reason", value=truncate(reason, 1024), inline=False)
            await send_modlog(self.bot, ctx.guild, log)

    @commands.command(name="untimeout", usage="<member|all|others|@role> [reason]")
    @commands.guild_only()
    @commands.has_guild_permissions(moderate_members=True)
    async def untimeout(
        self,
        ctx: commands.Context,
        target: str,
        *,
        reason: str = "No reason provided",
    ) -> None:
        if not await require_bot_perms_ctx(ctx, moderate_members=True):
            return
        members, note, is_selector = await self._resolve_member_targets(ctx, target)
        if not members:
            await reply_error_ctx(ctx, note or "No members found.", title="Invalid target")
            return
        reason = (reason or "No reason provided").strip() or "No reason provided"

        async def remove_one(member: discord.Member) -> tuple[bool, str]:
            problem = self._hierarchy_problem(ctx, member)
            if problem:
                return False, problem
            try:
                await member.timeout(None, reason=_audit_reason(ctx, reason))
            except discord.Forbidden:
                return False, "missing permissions"
            except discord.HTTPException:
                return False, "Discord error"
            await try_dm(member, base_embed(f"Your timeout in {ctx.guild.name} was removed", color=SUCCESS))
            return True, "ok"

        if not is_selector and len(members) == 1:
            member = members[0]
            ok, msg = await remove_one(member)
            if not ok:
                await reply_error_ctx(ctx, msg, title="Can't update that member")
                return
            embed = _action_embed("🔓 Timeout Removed", SUCCESS, member, ctx.author, reason)
            await reply_ctx(ctx, embed=embed)
            await send_modlog(self.bot, ctx.guild, embed)
            return

        ok_count = failed = 0
        for member in members:
            ok, _ = await remove_one(member)
            ok_count += 1 if ok else 0
            failed += 0 if ok else 1
        desc = f"Removed timeout from **{ok_count}** member{'s' if ok_count != 1 else ''}."
        if failed:
            desc += f"\nSkipped/failed: **{failed}**"
        if is_selector and note in {"all", "others"}:
            desc += f"\nTarget: **{note}**"
        await reply_ctx(ctx, embed=self._summary_embed("🔓 Bulk Timeout Removed", desc, color=SUCCESS))
        if ok_count:
            log = base_embed("🔓 Bulk Timeout Removed", desc, color=SUCCESS)
            if reason.lower() != "no reason provided":
                log.add_field(name="Reason", value=truncate(reason, 1024), inline=False)
            await send_modlog(self.bot, ctx.guild, log)

    @commands.command(name="unmute", usage="<member|all|others|@role> [reason]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def unmute(
        self,
        ctx: commands.Context,
        target: str,
        *,
        reason: str = "No reason provided",
    ) -> None:
        if not await require_bot_perms_ctx(ctx, manage_roles=True):
            return

        members, note, is_selector = await self._resolve_member_targets(ctx, target)
        if not members:
            await reply_error_ctx(ctx, note or "No members found.", title="Invalid target")
            return

        role = discord.utils.get(ctx.guild.roles, name=MUTED_ROLE_NAME)
        if role is None:
            await reply_error_ctx(ctx, "No Muted role found in this server.", title="Not muted")
            return

        reason = (reason or "No reason provided").strip() or "No reason provided"

        async def unmute_one(member: discord.Member) -> tuple[bool, str]:
            problem = self._hierarchy_problem(ctx, member)
            if problem:
                return False, problem
            if role not in member.roles:
                return False, "not muted"
            await self.bot.db.remove_scheduled_unmute(ctx.guild.id, member.id)
            try:
                await member.remove_roles(role, reason=_audit_reason(ctx, reason))
            except discord.Forbidden:
                return False, "missing permissions"
            except discord.HTTPException:
                return False, "Discord error"
            await try_dm(member, base_embed(f"Your mute in {ctx.guild.name} was removed", color=SUCCESS))
            return True, "unmuted"

        if not is_selector and len(members) == 1:
            member = members[0]
            ok, msg = await unmute_one(member)
            if not ok:
                title = "Not muted" if msg == "not muted" else "Can't unmute that member"
                text = f"{member.mention} is not muted." if msg == "not muted" else msg
                await reply_error_ctx(ctx, text, title=title)
                return
            embed = _action_embed("🔊 Mute Removed", SUCCESS, member, ctx.author, reason)
            await reply_ctx(ctx, embed=embed)
            await send_modlog(self.bot, ctx.guild, embed)
            return

        ok_count = 0
        not_muted = 0
        failed = 0
        for member in members:
            ok, msg = await unmute_one(member)
            if ok:
                ok_count += 1
            elif msg == "not muted":
                not_muted += 1
            else:
                failed += 1

        desc = f"Unmuted **{ok_count}** member{'s' if ok_count != 1 else ''}."
        if not_muted:
            desc += f"\nNot muted: **{not_muted}**"
        if failed:
            desc += f"\nSkipped/failed: **{failed}**"
        if is_selector and note in {"all", "others"}:
            desc += f"\nTarget: **{note}**"
        await reply_ctx(ctx, embed=self._summary_embed("🔊 Bulk Unmute", desc, color=SUCCESS))
        if ok_count:
            log = base_embed("🔊 Bulk Unmute", desc, color=SUCCESS)
            if reason.lower() != "no reason provided":
                log.add_field(name="Reason", value=truncate(reason, 1024), inline=False)
            await send_modlog(self.bot, ctx.guild, log)

    @commands.command(name="warn", usage="<user> [reason]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def warn(
        self,
        ctx: commands.Context,
        user: discord.User,
        *,
        reason: str = "No reason provided",
    ) -> None:
        if user.id == ctx.author.id:
            await reply_error_ctx(ctx, "You can't warn yourself.", title="Nice try")
            return
        if user.bot:
            await reply_error_ctx(ctx, "Bots cannot be warned.", title="Invalid target")
            return

        reason = (reason or "No reason provided").strip() or "No reason provided"
        if len(reason) > 1000:
            await reply_error_ctx(ctx, "Keep the warning reason under 1000 characters.")
            return

        warning_id = await self.bot.db.add_warning(
            ctx.guild.id,
            user.id,
            ctx.author.id,
            reason,
            utcnow_iso(),
        )
        count = await self.bot.db.count_warnings(ctx.guild.id, user.id)
        await try_dm(
            user,
            base_embed(
                f"You received a warning in {ctx.guild.name}",
                f"**Reason:** {reason}\n**Warning ID:** {warning_id}\n**Total warnings:** {count}",
                color=WARNING,
            ),
        )

        embed = _action_embed("⚠️ Warning Issued", WARNING, user, ctx.author, reason)
        embed.add_field(name="Warning ID", value=f"`{warning_id}`", inline=True)
        embed.add_field(name="Total", value=f"{count} warning{'s' if count != 1 else ''}", inline=True)
        await reply_ctx(ctx, embed=embed)
        await send_modlog(self.bot, ctx.guild, embed)

    @commands.command(name="warnings", usage="<user>")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def warnings(self, ctx: commands.Context, user: discord.User) -> None:
        total = await self.bot.db.count_warnings(ctx.guild.id, user.id)
        if total == 0:
            await reply_success_ctx(
                ctx,
                f"No warnings for {user.display_name}",
                "This user has a clean record in this server.",
            )
            return

        warnings = await self.bot.db.get_warnings(ctx.guild.id, user.id, limit=10)
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
        await reply_ctx(ctx, embed=embed)

    @commands.command(name="delwarn", usage="<user> <warning_id>")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def delwarn(
        self,
        ctx: commands.Context,
        user: discord.User,
        warning_id: int,
    ) -> None:
        deleted = await self.bot.db.delete_warning(ctx.guild.id, user.id, warning_id)
        if not deleted:
            await reply_error_ctx(
                ctx,
                f"No warning `#{warning_id}` was found for {user.display_name}.",
                title="Warning not found",
            )
            return
        await reply_success_ctx(
            ctx,
            "Warning Deleted",
            f"Removed warning `#{warning_id}` from {user.mention}.",
        )

    @commands.command(name="clearwarnings", usage="<user>")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def clearwarnings(self, ctx: commands.Context, user: discord.User) -> None:
        count = await self.bot.db.clear_warnings(ctx.guild.id, user.id)
        if count == 0:
            await reply_error_ctx(ctx, "That user has no warnings.", title="Nothing to clear")
            return
        await reply_success_ctx(
            ctx,
            "Warnings Cleared",
            f"Removed **{count}** warning{'s' if count != 1 else ''} from {user.mention}.",
        )

    async def _purge_messages(
        self,
        ctx: commands.Context,
        amount: int | None = None,
        user: discord.User = None,
    ) -> bool:
        if amount is not None and not 1 <= amount <= 100:
            await reply_error_ctx(ctx, "Choose an amount between 1 and 100, or omit it to delete all messages.")
            return False
        if not await require_bot_perms_ctx(
            ctx, manage_messages=True, read_message_history=True
        ):
            return False
        if not isinstance(ctx.channel, discord.TextChannel):
            await reply_error_ctx(ctx, "This command only works in regular text channels.")
            return False

        check = (lambda message: message.author.id == user.id) if user else (lambda message: True)
        reason = f"Purged by {ctx.author} ({ctx.author.id})"
        deleted_count = 0
        try:
            if amount is not None:
                deleted = await ctx.channel.purge(limit=amount, check=check, reason=reason)
                deleted_count = len(deleted)
            else:
                # Delete in chunks with a small delay to avoid hammering the API.
                while True:
                    deleted = await ctx.channel.purge(limit=100, check=check, reason=reason)
                    if not deleted:
                        break
                    deleted_count += len(deleted)
                    await asyncio.sleep(1.0)
        except discord.Forbidden:
            await reply_error_ctx(ctx, "Discord denied the purge. Check my permissions.")
            return False
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected the purge: `{exc}`")
            return False

        description = f"Deleted **{deleted_count}** message{'s' if deleted_count != 1 else ''} in {ctx.channel.mention}."
        if user:
            description += f"\nFiltered to messages from {user.mention}."
        if amount is None:
            description += "\n(No amount specified — deleted available messages in chunks.)"
        await reply_success_ctx(ctx, "Messages Purged", description)

        log = base_embed("🧹 Messages Purged", color=WARNING)
        log.add_field(name="Moderator", value=f"{ctx.author.mention} (`{ctx.author.id}`)", inline=False)
        log.add_field(name="Channel", value=ctx.channel.mention, inline=True)
        log.add_field(name="Deleted", value=str(deleted_count), inline=True)
        if user:
            log.add_field(name="Filter", value=user.mention, inline=True)
        await send_modlog(self.bot, ctx.guild, log)
        return True

    @commands.command(name="purge", usage="[amount] [user]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def purge(
        self,
        ctx: commands.Context,
        amount: int | None = None,
        user: discord.User = None,
    ) -> None:
        await self._purge_messages(ctx, amount, user)

    @commands.command(name="clear", usage="[amount] [user]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def clear(
        self,
        ctx: commands.Context,
        amount: int | None = None,
        user: discord.User = None,
    ) -> None:
        await self._purge_messages(ctx, amount, user)

    @commands.command(name="slowmode", usage="<seconds> [channel]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def slowmode(
        self,
        ctx: commands.Context,
        seconds: int,
        channel: discord.TextChannel = None,
    ) -> None:
        if not 0 <= seconds <= 21600:
            await reply_error_ctx(ctx, "Slowmode must be between 0 and 21600 seconds.")
            return
        if not await require_bot_perms_ctx(ctx, manage_channels=True):
            return

        target = channel or ctx.channel
        if not isinstance(target, discord.TextChannel):
            await reply_error_ctx(ctx, "This command only works in regular text channels.")
            return
        try:
            await target.edit(
                slowmode_delay=seconds,
                reason=_audit_reason(ctx, "Slowmode update"),
            )
        except discord.Forbidden:
            await reply_error_ctx(ctx, "Discord denied the change. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected the change: `{exc}`")
            return

        if seconds:
            description = f"Slowmode in {target.mention} is now **{humanize_seconds(seconds)}**."
        else:
            description = f"Slowmode in {target.mention} has been disabled."
        await reply_success_ctx(ctx, "Slowmode Updated", description)

    @commands.command(name="lock", usage="[channel]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def lock(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel = None,
    ) -> None:
        if not await require_bot_perms_ctx(ctx, manage_channels=True):
            return
        target = channel or ctx.channel
        if not isinstance(target, discord.TextChannel):
            await reply_error_ctx(ctx, "This command only works in regular text channels.")
            return

        overwrite = target.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        try:
            await target.set_permissions(
                ctx.guild.default_role,
                overwrite=overwrite,
                reason=_audit_reason(ctx, "Channel locked"),
            )
        except discord.Forbidden:
            await reply_error_ctx(ctx, "Discord denied the change. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected the change: `{exc}`")
            return

        await reply_success_ctx(ctx, "Channel Locked", f"{target.mention} is now locked.")

    @commands.command(name="unlock", usage="[channel]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def unlock(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel = None,
    ) -> None:
        if not await require_bot_perms_ctx(ctx, manage_channels=True):
            return
        target = channel or ctx.channel
        if not isinstance(target, discord.TextChannel):
            await reply_error_ctx(ctx, "This command only works in regular text channels.")
            return

        overwrite = target.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        try:
            await target.set_permissions(
                ctx.guild.default_role,
                overwrite=overwrite,
                reason=_audit_reason(ctx, "Channel unlocked"),
            )
        except discord.Forbidden:
            await reply_error_ctx(ctx, "Discord denied the change. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected the change: `{exc}`")
            return

        await reply_success_ctx(ctx, "Channel Unlocked", f"{target.mention} is unlocked.")

    @commands.command(name="purgechannel", usage="[channel]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def purgechannel(
        self,
        ctx: commands.Context,
        channel: discord.abc.GuildChannel = None,
    ) -> None:
        if not await require_bot_perms_ctx(ctx, manage_channels=True):
            return

        target = channel or ctx.channel
        if not isinstance(target, discord.abc.GuildChannel) or target.guild != ctx.guild:
            await reply_error_ctx(ctx, "Pick a channel in this server to purge.", title="Invalid channel")
            return

        previous_overwrite = target.overwrites_for(ctx.guild.default_role)
        try:
            hidden_overwrite = discord.PermissionOverwrite.from_pair(*previous_overwrite.pair())
            hidden_overwrite.view_channel = False
            await target.set_permissions(
                ctx.guild.default_role,
                overwrite=hidden_overwrite,
                reason=_audit_reason(ctx, "Purgechannel pending confirmation (hidden)"),
            )
        except discord.Forbidden:
            await reply_error_ctx(ctx, "I don't have permission to edit that channel's permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected hiding the channel: `{exc}`")
            return

        reason = _audit_reason(ctx, "Purgechannel backup")
        try:
            backup_channel = await target.clone(reason=reason)
            try:
                await backup_channel.edit(position=target.position)
            except (discord.Forbidden, discord.HTTPException):
                pass
            # Restore backup visibility to original state (clone copied hidden overwrite).
            try:
                if previous_overwrite.is_empty():
                    await backup_channel.set_permissions(ctx.guild.default_role, overwrite=None)
                else:
                    await backup_channel.set_permissions(ctx.guild.default_role, overwrite=previous_overwrite)
            except (discord.Forbidden, discord.HTTPException):
                pass
        except (discord.Forbidden, discord.HTTPException) as exc:
            # Restore original visibility if backup creation fails
            try:
                if previous_overwrite.is_empty():
                    await target.set_permissions(ctx.guild.default_role, overwrite=None)
                else:
                    await target.set_permissions(ctx.guild.default_role, overwrite=previous_overwrite)
            except discord.HTTPException:
                pass
            if isinstance(exc, discord.Forbidden):
                await reply_error_ctx(ctx, "I don't have permission to clone that channel. Visibility restored.")
            else:
                await reply_error_ctx(ctx, f"Discord rejected creating the backup channel: `{exc}`. Visibility restored.")
            return

        from ..views import PurgeChannelView

        prompt_embed = base_embed(
            "⚠️ Purge Channel?",
            "Confirm deleting this channel?\nThere will be a copy made but the messages will be gone.",
            color=WARNING,
            footer="You have 30 seconds to confirm · GeneralBot",
        )
        view = PurgeChannelView(self.bot, ctx.guild, target, backup_channel, ctx.author, previous_overwrite, timeout=30)
        try:
            view.message = await target.send(embed=prompt_embed, view=view)
        except discord.HTTPException:
            try:
                await backup_channel.delete(reason="Purgechannel aborted (could not send prompt)")
            except discord.HTTPException:
                pass
            try:
                if previous_overwrite.is_empty():
                    await target.set_permissions(ctx.guild.default_role, overwrite=None)
                else:
                    await target.set_permissions(ctx.guild.default_role, overwrite=previous_overwrite)
            except discord.HTTPException:
                pass
            await reply_error_ctx(ctx, "Couldn't send the confirmation prompt in that channel. Backup removed and visibility restored.")
            return

    async def _change_nickname(
        self,
        ctx: commands.Context,
        member: discord.Member,
        nickname: str = None,
    ) -> bool:
        if not await require_bot_perms_ctx(ctx, manage_nicknames=True):
            return False

        problem = self._hierarchy_problem(ctx, member, allow_self=True)
        if problem:
            await reply_error_ctx(ctx, problem, title="Can't rename that member")
            return False

        new_nick = (nickname or "").strip() or None
        if new_nick is not None and len(new_nick) > 32:
            await reply_error_ctx(ctx, "Nicknames must be 32 characters or fewer.", title="Nickname too long")
            return False

        old_name = member.display_name
        try:
            await member.edit(nick=new_nick, reason=_audit_reason(ctx, "Nickname change"))
        except discord.Forbidden:
            await reply_error_ctx(ctx, "Discord denied the change. Check my permissions.")
            return False
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected the change: `{exc}`")
            return False

        if new_nick is None:
            description = f"Reset **{old_name}**'s nickname."
        else:
            description = f"Changed **{old_name}**'s nickname to **{new_nick}**."
        await reply_success_ctx(ctx, "Nickname Updated", description)
        return True

    async def _apply_nickname(
        self,
        ctx: commands.Context,
        target: str,
        nickname: str = None,
    ) -> None:
        if not await require_bot_perms_ctx(ctx, manage_nicknames=True):
            return
        members, note, is_selector = await self._resolve_member_targets(ctx, target)
        if not members:
            await reply_error_ctx(ctx, note or "No members found.", title="Invalid target")
            return
        new_nick = (nickname or "").strip() or None
        if new_nick is not None and len(new_nick) > 32:
            await reply_error_ctx(ctx, "Nicknames must be 32 characters or fewer.", title="Nickname too long")
            return

        async def change_one(member: discord.Member) -> tuple[bool, str]:
            problem = self._hierarchy_problem(ctx, member, allow_self=True)
            if problem:
                return False, problem
            old_name = member.display_name
            try:
                await member.edit(nick=new_nick, reason=_audit_reason(ctx, "Nickname change"))
            except discord.Forbidden:
                return False, "missing permissions"
            except discord.HTTPException:
                return False, "Discord error"
            return True, old_name

        if not is_selector and len(members) == 1:
            member = members[0]
            ok, msg = await change_one(member)
            if not ok:
                await reply_error_ctx(ctx, msg, title="Can't rename that member")
                return
            if new_nick is None:
                description = f"Reset **{msg}**'s nickname."
            else:
                description = f"Changed **{msg}**'s nickname to **{new_nick}**."
            await reply_success_ctx(ctx, "Nickname Updated", description)
            return

        ok_count = failed = 0
        for member in members:
            ok, _ = await change_one(member)
            ok_count += 1 if ok else 0
            failed += 0 if ok else 1
        action = "reset" if new_nick is None else f"set to **{new_nick}**"
        desc = f"Nicknames {action} for **{ok_count}** member{'s' if ok_count != 1 else ''}."
        if failed:
            desc += f"\nSkipped/failed: **{failed}**"
        if is_selector and note in {"all", "others"}:
            desc += f"\nTarget: **{note}**"
        await reply_ctx(ctx, embed=self._summary_embed("Nickname Updated", desc, color=SUCCESS))

    @commands.command(name="nickname", usage="<member|all|others|@role> [nickname]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_nicknames=True)
    async def nickname(
        self,
        ctx: commands.Context,
        target: str,
        *,
        nickname: str = None,
    ) -> None:
        await self._apply_nickname(ctx, target, nickname)

    @commands.command(name="setname", usage="<member|all|others|@role> [nickname]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_nicknames=True)
    async def setname(
        self,
        ctx: commands.Context,
        target: str,
        *,
        nickname: str = None,
    ) -> None:
        await self._apply_nickname(ctx, target, nickname)

    @commands.group(name="role", usage="<member|selector> <role> | add|remove|list|info", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def role(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is not None:
            return

        content = (ctx.message.content or "").strip()
        prefix = ctx.prefix or ""
        if content.startswith(prefix):
            content = content[len(prefix):].strip()
        invoked = ctx.invoked_with or "role"
        if content.startswith(invoked):
            content = content[len(invoked):].strip()

        if not content:
            await reply_error_ctx(
                ctx,
                "Usage: `?role <member|selector> <role>` to toggle, or `?role add|remove|list|info`.",
                title="Role help",
            )
            return

        # split into target and role; role may have spaces but prefer last token as role for names? better split from right once
        if " " not in content:
            await reply_error_ctx(
                ctx,
                "Provide both a member/selector and a role: `?role <member|all|others|@role> <role>`.",
                title="Missing role",
            )
            return

        member_text, role_text = content.rsplit(maxsplit=1)
        await self._toggle_role(ctx, member_text.strip(), role_text.strip())

    async def _toggle_role(
        self,
        ctx: commands.Context,
        member_text: str,
        role_text: str,
    ) -> bool:
        try:
            role = await commands.RoleConverter().convert(ctx, role_text)
        except commands.BadArgument:
            await reply_error_ctx(
                ctx,
                "Couldn't find that role. Usage: `?role <member|selector> <role>`.",
                title="Invalid role",
            )
            return False

        members, note, is_selector = await self._resolve_member_targets(ctx, member_text)
        if not members:
            await reply_error_ctx(
                ctx,
                note or "Couldn't find that member, role, or selector. Usage: `?role <member|selector> <role>`.",
                title="Invalid target",
            )
            return False

        if not is_selector and len(members) == 1:
            member = members[0]
            if role in member.roles:
                return await self._remove_role(ctx, member, role)
            return await self._add_role(ctx, member, role)

        if not await require_bot_perms_ctx(ctx, manage_roles=True):
            return False
        added = removed = failed = 0
        for member in members:
            if role in member.roles:
                ok = await self._remove_role(ctx, member, role, quiet=True)
                removed += 1 if ok else 0
                failed += 0 if ok else 1
            else:
                ok = await self._add_role(ctx, member, role, quiet=True)
                added += 1 if ok else 0
                failed += 0 if ok else 1
        desc = f"Toggled {role.mention} for **{len(members)}** member{'s' if len(members) != 1 else ''}."
        desc += f"\nAdded: **{added}** · Removed: **{removed}**"
        if failed:
            desc += f"\nSkipped/failed: **{failed}**"
        if is_selector and note in {"all", "others"}:
            desc += f"\nTarget: **{note}**"
        await reply_ctx(ctx, embed=self._summary_embed("Role Toggled", desc, color=SUCCESS))
        return True

    def _role_problem(
        self,
        ctx: commands.Context,
        member: discord.Member,
        role: discord.Role,
    ) -> str | None:
        problem = self._hierarchy_problem(ctx, member)
        if problem:
            return problem
        me = ctx.guild.me
        if role.is_default():
            return "You can't manage the @everyone role."
        if role.position >= me.top_role.position:
            return "That role is above or equal to my highest role."
        if ctx.author.id != ctx.guild.owner_id and role.position >= ctx.author.top_role.position:
            return "That role is above or equal to your highest role."
        return None

    async def _add_role(
        self,
        ctx: commands.Context,
        member: discord.Member,
        role: discord.Role,
        *,
        quiet: bool = False,
    ) -> bool:
        if not quiet and not await require_bot_perms_ctx(ctx, manage_roles=True):
            return False
        problem = self._role_problem(ctx, member, role)
        if problem:
            if not quiet:
                await reply_error_ctx(ctx, problem, title="Can't add that role")
            return False
        if role in member.roles:
            if not quiet:
                await reply_error_ctx(ctx, f"{member.mention} already has {role.mention}.", title="Already has role")
            return False
        try:
            await member.add_roles(role, reason=_audit_reason(ctx, "Role added"))
        except discord.Forbidden:
            if not quiet:
                await reply_error_ctx(ctx, "Discord denied the change. Check my permissions.")
            return False
        except discord.HTTPException as exc:
            if not quiet:
                await reply_error_ctx(ctx, f"Discord rejected the change: `{exc}`")
            return False
        if not quiet:
            await reply_success_ctx(
                ctx,
                "Role Added",
                f"Added {role.mention} to {member.mention}.",
            )
        return True

    async def _remove_role(
        self,
        ctx: commands.Context,
        member: discord.Member,
        role: discord.Role,
        *,
        quiet: bool = False,
    ) -> bool:
        if not quiet and not await require_bot_perms_ctx(ctx, manage_roles=True):
            return False
        problem = self._role_problem(ctx, member, role)
        if problem:
            if not quiet:
                await reply_error_ctx(ctx, problem, title="Can't remove that role")
            return False
        if role not in member.roles:
            if not quiet:
                await reply_error_ctx(ctx, f"{member.mention} doesn't have {role.mention}.", title="Role not found")
            return False
        try:
            await member.remove_roles(role, reason=_audit_reason(ctx, "Role removed"))
        except discord.Forbidden:
            if not quiet:
                await reply_error_ctx(ctx, "Discord denied the change. Check my permissions.")
            return False
        except discord.HTTPException as exc:
            if not quiet:
                await reply_error_ctx(ctx, f"Discord rejected the change: `{exc}`")
            return False
        if not quiet:
            await reply_success_ctx(
                ctx,
                "Role Removed",
                f"Removed {role.mention} from {member.mention}.",
            )
        return True

    async def _bulk_role_action(
        self,
        ctx: commands.Context,
        target: str,
        role: discord.Role,
        *,
        add: bool,
    ) -> None:
        if not await require_bot_perms_ctx(ctx, manage_roles=True):
            return
        members, note, is_selector = await self._resolve_member_targets(ctx, target)
        if not members:
            await reply_error_ctx(ctx, note or "No members found.", title="Invalid target")
            return
        if not is_selector and len(members) == 1:
            if add:
                await self._add_role(ctx, members[0], role)
            else:
                await self._remove_role(ctx, members[0], role)
            return
        ok_count = skipped = failed = 0
        for member in members:
            if add:
                if role in member.roles:
                    skipped += 1
                    continue
                ok = await self._add_role(ctx, member, role, quiet=True)
            else:
                if role not in member.roles:
                    skipped += 1
                    continue
                ok = await self._remove_role(ctx, member, role, quiet=True)
            ok_count += 1 if ok else 0
            failed += 0 if ok else 1
        verb = "Added" if add else "Removed"
        prep = "to" if add else "from"
        desc = f"{verb} {role.mention} {prep} **{ok_count}** member{'s' if ok_count != 1 else ''}."
        if skipped:
            desc += f"\nAlready {'had role' if add else 'missing role'}: **{skipped}**"
        if failed:
            desc += f"\nSkipped/failed: **{failed}**"
        if is_selector and note in {"all", "others"}:
            desc += f"\nTarget: **{note}**"
        await reply_ctx(ctx, embed=self._summary_embed(f"Role {verb}", desc, color=SUCCESS))

    @role.command(name="add", usage="<member|selector> <role>")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def role_add(
        self,
        ctx: commands.Context,
        target: str,
        role: discord.Role,
    ) -> None:
        await self._bulk_role_action(ctx, target, role, add=True)

    @role.command(name="remove", usage="<member|selector> <role>")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def role_remove(
        self,
        ctx: commands.Context,
        target: str,
        role: discord.Role,
    ) -> None:
        await self._bulk_role_action(ctx, target, role, add=False)

    @role.command(name="list", usage="[member]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def role_list(self, ctx: commands.Context, member: discord.Member = None) -> None:
        if member is None:
            roles = [role for role in ctx.guild.roles if not role.is_default()]
            roles = sorted(roles, key=lambda item: item.position, reverse=True)
            embed = base_embed(
                f"🎭 Roles in {ctx.guild.name}",
                f"**{len(roles)}** roles",
                color=BRAND,
            )
            shown = roles[:20]
            for role in shown:
                embed.add_field(
                    name=truncate(role.name, 100),
                    value=f"`{role.id}` · {len(role.members)} member{'s' if len(role.members) != 1 else ''}",
                    inline=True,
                )
            if len(roles) > len(shown):
                embed.set_footer(text=f"Showing the top {len(shown)} of {len(roles)} roles · GeneralBot")
            await reply_ctx(ctx, embed=embed)
            return

        roles = [role for role in member.roles if not role.is_default()]
        embed = base_embed(
            f"🎭 {member.display_name}'s Roles",
            f"**{len(roles)}** role{'s' if len(roles) != 1 else ''}",
            color=BRAND,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        for role in roles[:20]:
            embed.add_field(name=truncate(role.name, 100), value=f"`{role.id}`", inline=True)
        if len(roles) > 20:
            embed.set_footer(text=f"Showing 20 of {len(roles)} roles · GeneralBot")
        await reply_ctx(ctx, embed=embed)

    @role.command(name="info", usage="<role>")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def role_info(self, ctx: commands.Context, role: discord.Role) -> None:
        embed = base_embed(
            f"🎭 {role.name}",
            f"**ID:** `{role.id}`\n**Color:** `{role.color}`\n"
            f"**Position:** {role.position}\n**Members:** {len(role.members)}\n"
            f"**Mentionable:** {'Yes' if role.mentionable else 'No'}\n"
            f"**Hoisted:** {'Yes' if role.hoist else 'No'}",
            color=role.color,
        )
        embed.set_footer(text="GeneralBot · role info")
        await reply_ctx(ctx, embed=embed)

    @commands.command(name="addrole", usage="<member|selector> <role>")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def addrole(
        self,
        ctx: commands.Context,
        target: str,
        role: discord.Role,
    ) -> None:
        await self._bulk_role_action(ctx, target, role, add=True)

    @commands.command(name="removerole", usage="<member|selector> <role>")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def removerole(
        self,
        ctx: commands.Context,
        target: str,
        role: discord.Role,
    ) -> None:
        await self._bulk_role_action(ctx, target, role, add=False)

    @commands.command(name="createrole", usage="<name>")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def createrole(self, ctx: commands.Context, *, name: str) -> None:
        if not await require_bot_perms_ctx(ctx, manage_roles=True):
            return
        name = (name or "").strip()
        if not 1 <= len(name) <= 100:
            await reply_error_ctx(ctx, "Role names must be between 1 and 100 characters.")
            return
        try:
            created = await ctx.guild.create_role(
                name=name,
                reason=_audit_reason(ctx, "Role created"),
            )
        except discord.Forbidden:
            await reply_error_ctx(ctx, "Discord denied the change. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected the change: `{exc}`")
            return
        await reply_success_ctx(ctx, "Role Created", f"Created {created.mention}.")

    @commands.command(name="delrole", usage="<role>")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def delrole(self, ctx: commands.Context, role: discord.Role) -> None:
        if not await require_bot_perms_ctx(ctx, manage_roles=True):
            return
        if role.is_default():
            await reply_error_ctx(ctx, "You can't delete the @everyone role.", title="Invalid role")
            return
        if role.is_managed():
            await reply_error_ctx(ctx, "Managed roles cannot be deleted.", title="Invalid role")
            return
        me = ctx.guild.me
        if role.position >= me.top_role.position:
            await reply_error_ctx(
                ctx,
                "That role is above or equal to my highest role.",
                title="Can't delete that role",
            )
            return
        if ctx.author.id != ctx.guild.owner_id and role.position >= ctx.author.top_role.position:
            await reply_error_ctx(
                ctx,
                "That role is above or equal to your highest role.",
                title="Can't delete that role",
            )
            return
        try:
            await role.delete(reason=_audit_reason(ctx, "Role deleted"))
        except discord.Forbidden:
            await reply_error_ctx(ctx, "Discord denied the change. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected the change: `{exc}`")
            return
        await reply_success_ctx(ctx, "Role Deleted", f"Deleted **{role.name}**.")

    @commands.command(name="rolecolor", usage="<role> <color>")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def rolecolor(self, ctx: commands.Context, role: discord.Role, color: str) -> None:
        if not await require_bot_perms_ctx(ctx, manage_roles=True):
            return
        try:
            colour = discord.Colour.from_str(color)
        except ValueError:
            await reply_error_ctx(
                ctx,
                "Use a color like `#ff0000`, `0xff0000`, or `rgb(255, 0, 0)`.",
                title="Invalid color",
            )
            return
        if role.is_default():
            await reply_error_ctx(ctx, "You can't manage the @everyone role.", title="Invalid role")
            return
        me = ctx.guild.me
        if role.position >= me.top_role.position:
            await reply_error_ctx(
                ctx,
                "That role is above or equal to my highest role.",
                title="Can't edit that role",
            )
            return
        if ctx.author.id != ctx.guild.owner_id and role.position >= ctx.author.top_role.position:
            await reply_error_ctx(
                ctx,
                "That role is above or equal to your highest role.",
                title="Can't edit that role",
            )
            return
        try:
            await role.edit(colour=colour, reason=_audit_reason(ctx, "Role color changed"))
        except discord.Forbidden:
            await reply_error_ctx(ctx, "Discord denied the change. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected the change: `{exc}`")
            return
        await reply_success_ctx(ctx, "Role Color Updated", f"Set {role.mention}'s color to `{colour}`.")

    @commands.command(name="setservername", usage="<name>")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def setservername(self, ctx: commands.Context, *, name: str) -> None:
        if not await require_bot_perms_ctx(ctx, manage_guild=True):
            return
        name = (name or "").strip()
        if not 2 <= len(name) <= 100:
            await reply_error_ctx(ctx, "Server names must be between 2 and 100 characters.")
            return
        try:
            await ctx.guild.edit(name=name, reason=_audit_reason(ctx, "Server renamed"))
        except discord.Forbidden:
            await reply_error_ctx(ctx, "Discord denied the change. Check my permissions.")
            return
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected the change: `{exc}`")
            return
        await reply_success_ctx(ctx, "Server Renamed", f"The server is now called **{name}**.")

    @commands.command(name="avatar", usage="[user]")
    async def avatar(self, ctx: commands.Context, user: discord.User = None) -> None:
        target = user or ctx.author
        embed = base_embed(f"🖼️ {target.display_name}'s Avatar", color=BRAND)
        embed.set_image(url=target.display_avatar.url)
        embed.set_footer(text="GeneralBot · avatar")
        await reply_ctx(ctx, embed=embed)

    @commands.command(name="servericon")
    @commands.guild_only()
    async def servericon(self, ctx: commands.Context) -> None:
        if ctx.guild.icon is None:
            await reply_error_ctx(ctx, "This server has no icon.", title="No icon")
            return
        embed = base_embed(f"🖼️ {ctx.guild.name}'s Icon", color=BRAND)
        embed.set_image(url=ctx.guild.icon.url)
        embed.set_footer(text="GeneralBot · server icon")
        await reply_ctx(ctx, embed=embed)

    @commands.command(name="membercount")
    @commands.guild_only()
    async def membercount(self, ctx: commands.Context) -> None:
        count = ctx.guild.member_count or 0
        embed = base_embed(
            "👥 Member Count",
            f"**{count:,}** member{'s' if count != 1 else ''}",
            color=BRAND,
        )
        await reply_ctx(ctx, embed=embed)

    @commands.command(name="userinfo", usage="[user]")
    async def userinfo(self, ctx: commands.Context, user: discord.User = None) -> None:
        target = user or ctx.author
        embed = base_embed(f"👤 {target.display_name}", color=BRAND)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
        embed.add_field(name="Bot", value="Yes" if target.bot else "No", inline=True)
        embed.add_field(
            name="Account Created",
            value=discord.utils.format_dt(target.created_at, "F"),
            inline=False,
        )
        member = ctx.guild.get_member(target.id) if ctx.guild else None
        if member is not None:
            embed.add_field(
                name="Joined Server",
                value=discord.utils.format_dt(member.joined_at, "F"),
                inline=False,
            )
            embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
            role_count = len([role for role in member.roles if not role.is_default()])
            embed.add_field(name="Roles", value=str(role_count), inline=True)
        embed.set_footer(text="GeneralBot · user info")
        await reply_ctx(ctx, embed=embed)

    @commands.command(name="serverinfo")
    @commands.guild_only()
    async def serverinfo(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        embed = base_embed(f"ℹ️ {guild.name}", color=BRAND)
        if guild.icon is not None:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="ID", value=f"`{guild.id}`", inline=True)
        owner = guild.owner
        embed.add_field(name="Owner", value=owner.mention if owner else f"`{guild.owner_id}`", inline=True)
        embed.add_field(name="Members", value=f"{guild.member_count or 0:,}", inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(
            name="Created",
            value=discord.utils.format_dt(guild.created_at, "F"),
            inline=False,
        )
        embed.set_footer(text="GeneralBot · server info")
        await reply_ctx(ctx, embed=embed)

    @commands.command(name="addchannel", usage="<name> [text|voice|category] [category]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def addchannel(
        self,
        ctx: commands.Context,
        name: str,
        channel_type: str = "text",
        category: discord.CategoryChannel | None = None,
    ) -> None:
        if not await require_bot_perms_ctx(ctx, manage_channels=True):
            return

        kind = channel_type.lower()
        if kind not in {"text", "voice", "category"}:
            await reply_error_ctx(ctx, "Channel type must be `text`, `voice`, or `category`.")
            return

        reason = _audit_reason(ctx, "Channel created")
        try:
            if kind == "category":
                created = await ctx.guild.create_category(name=name, reason=reason)
            elif kind == "voice":
                created = await ctx.guild.create_voice_channel(name=name, category=category, reason=reason)
            else:
                created = await ctx.guild.create_text_channel(name=name, category=category, reason=reason)
        except discord.Forbidden:
            await reply_error_ctx(ctx, "I don't have permission to create that channel.")
            return
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected creating the channel: `{exc}`")
            return

        mention = getattr(created, "mention", f"`{created.name}`")
        await reply_success_ctx(ctx, "Channel Created", f"Created {mention} (`{created.id}`).")

    @commands.command(name="removechannel", usage="[channel]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def removechannel(
        self,
        ctx: commands.Context,
        channel: discord.abc.GuildChannel | None = None,
    ) -> None:
        if not await require_bot_perms_ctx(ctx, manage_channels=True):
            return

        target = channel or ctx.channel
        if not isinstance(target, discord.abc.GuildChannel) or target.guild != ctx.guild:
            await reply_error_ctx(ctx, "Pick a channel in this server to delete.", title="Invalid channel")
            return

        name = getattr(target, "name", "channel")
        cid = target.id
        reason = _audit_reason(ctx, "Channel deleted")
        try:
            await target.delete(reason=reason)
        except discord.Forbidden:
            await reply_error_ctx(ctx, "I don't have permission to delete that channel.")
            return
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected deleting the channel: `{exc}`")
            return

        # If we deleted the command channel, we can't reply there.
        if target.id != ctx.channel.id:
            await reply_success_ctx(ctx, "Channel Deleted", f"Deleted **#{name}** (`{cid}`).")

    @commands.command(name="copychannel", usage="[channel] [new_name]")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def copychannel(
        self,
        ctx: commands.Context,
        channel: discord.abc.GuildChannel | None = None,
        *,
        name: str | None = None,
    ) -> None:
        if not await require_bot_perms_ctx(ctx, manage_channels=True):
            return

        target = channel or ctx.channel
        if not isinstance(target, discord.abc.GuildChannel) or target.guild != ctx.guild:
            await reply_error_ctx(ctx, "Pick a channel in this server to copy.", title="Invalid channel")
            return

        reason = _audit_reason(ctx, "Channel copied")
        try:
            created = await target.clone(name=name, reason=reason) if name else await target.clone(reason=reason)
            try:
                await created.edit(position=getattr(target, "position", 0) + 1)
            except (discord.Forbidden, discord.HTTPException):
                pass
        except discord.Forbidden:
            await reply_error_ctx(ctx, "I don't have permission to copy that channel.")
            return
        except discord.HTTPException as exc:
            await reply_error_ctx(ctx, f"Discord rejected copying the channel: `{exc}`")
            return

        mention = getattr(created, "mention", f"`{getattr(created, 'name', created.id)}`")
        await reply_success_ctx(ctx, "Channel Copied", f"Copied to {mention} (`{created.id}`).")


async def setup(bot: GeneralBot) -> None:
    await bot.add_cog(PrefixCommands(bot))
