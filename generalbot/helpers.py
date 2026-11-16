"""Shared embeds, permission checks, and small utilities."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

BRAND = 0x5865F2
SUCCESS = 0x57F287
ERROR = 0xED4245
WARNING = 0xFEE75C
GOLD = 0xF1C40F
DARK = 0x232428

PERMISSION_LABELS = {
    "administrator": "Administrator",
    "ban_members": "Ban Members",
    "kick_members": "Kick Members",
    "manage_channels": "Manage Channels",
    "manage_guild": "Manage Server",
    "manage_messages": "Manage Messages",
    "manage_nicknames": "Manage Nicknames",
    "manage_roles": "Manage Roles",
    "moderate_members": "Moderate Members",
    "read_message_history": "Read Message History",
    "send_messages": "Send Messages",
    "embed_links": "Embed Links",
}


def utcnow_iso() -> str:
    return discord.utils.utcnow().isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def cooldown_end(last_used: str | None, seconds: int) -> datetime | None:
    """Return when a cooldown ends, or None if it is already over."""
    last = parse_iso(last_used)
    if last is None:
        return None
    end = last + timedelta(seconds=seconds)
    return end if end > discord.utils.utcnow() else None


def base_embed(
    title: str | None = None,
    description: str | None = None,
    *,
    color: int = BRAND,
    footer: str | None = "GeneralBot",
    footer_icon: str | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow(),
    )
    if footer:
        embed.set_footer(text=footer, icon_url=footer_icon)
    return embed


def truncate(text: str, length: int) -> str:
    if len(text) <= length:
        return text
    return text[: max(0, length - 1)] + "…"


async def respond(
    interaction: discord.Interaction,
    *,
    embed: discord.Embed | None = None,
    content: str | None = None,
    view: discord.ui.View | None = None,
    ephemeral: bool = False,
):
    kwargs = {
        "embed": embed,
        "content": content,
        "ephemeral": ephemeral,
    }
    if view is not None:
        kwargs["view"] = view
    if interaction.response.is_done():
        return await interaction.followup.send(**kwargs)
    return await interaction.response.send_message(**kwargs)


async def reply_error(
    interaction: discord.Interaction,
    description: str,
    *,
    title: str = "Something went wrong",
    ephemeral: bool = True,
):
    embed = base_embed(f"❌ {title}", description, color=ERROR)
    return await respond(interaction, embed=embed, ephemeral=ephemeral)


async def reply_success(
    interaction: discord.Interaction,
    title: str,
    description: str,
    *,
    ephemeral: bool = True,
):
    embed = base_embed(f"✅ {title}", description, color=SUCCESS)
    return await respond(interaction, embed=embed, ephemeral=ephemeral)


async def reply_ctx(
    ctx: commands.Context,
    *,
    content: str | None = None,
    embed: discord.Embed | None = None,
    view: discord.ui.View | None = None,
    mention_author: bool = False,
):
    """Reply to a classic prefix command, falling back to a normal send."""
    reply_kwargs = {
        "content": content,
        "embed": embed,
        "mention_author": mention_author,
    }
    send_kwargs = {
        "content": content,
        "embed": embed,
    }
    if view is not None:
        reply_kwargs["view"] = view
        send_kwargs["view"] = view
    try:
        return await ctx.reply(**reply_kwargs)
    except discord.HTTPException:
        return await ctx.send(**send_kwargs)


async def reply_error_ctx(
    ctx: commands.Context,
    description: str,
    *,
    title: str = "Something went wrong",
):
    return await reply_ctx(
        ctx,
        embed=base_embed(f"❌ {title}", description, color=ERROR),
    )


async def reply_success_ctx(
    ctx: commands.Context,
    title: str,
    description: str,
):
    return await reply_ctx(
        ctx,
        embed=base_embed(f"✅ {title}", description, color=SUCCESS),
    )


async def ensure_guild(interaction: discord.Interaction) -> discord.Guild | None:
    if interaction.guild is None:
        await reply_error(
            interaction,
            "This command only works inside a server. Try `/fun` or `/economy` in DMs instead.",
            title="Server only",
        )
        return None
    return interaction.guild


def missing_permissions(member: discord.Member, required: dict[str, bool]) -> list[str]:
    if member.guild_permissions.administrator:
        return []
    missing = []
    for name, needed in required.items():
        if needed and not getattr(member.guild_permissions, name, False):
            missing.append(PERMISSION_LABELS.get(name, name.replace("_", " ").title()))
    return missing


async def require_perms(
    interaction: discord.Interaction,
    **required: bool,
) -> discord.Guild | None:
    """Check the invoking member's permissions and reply nicely if they are missing."""
    guild = await ensure_guild(interaction)
    if guild is None:
        return None

    member = interaction.user
    if not isinstance(member, discord.Member):
        member = guild.get_member(interaction.user.id)
        if member is None:
            try:
                member = await guild.fetch_member(interaction.user.id)
            except (discord.NotFound, discord.HTTPException):
                member = None
    if member is None:
        await reply_error(interaction, "I couldn't verify your permissions in this server.")
        return None

    missing = missing_permissions(member, required)
    if missing:
        await reply_error(
            interaction,
            f"You need: **{', '.join(missing)}**.",
            title="Missing permissions",
        )
        return None
    return guild


async def require_bot_perms(
    interaction: discord.Interaction,
    **required: bool,
) -> bool:
    guild = interaction.guild
    if guild is None:
        return False
    me = guild.me
    if me is None:
        await reply_error(
            interaction,
            "I'm not a member of this server. Add me with `/utility invite` "
            "to use moderation and configuration tools here.",
            title="Bot not in server",
        )
        return False

    missing = missing_permissions(me, required)
    if missing:
        await reply_error(
            interaction,
            f"I need: **{', '.join(missing)}** to do that. Please check my role permissions.",
            title="I'm missing permissions",
        )
        return False
    return True


async def require_bot_perms_ctx(
    ctx: commands.Context,
    **required: bool,
) -> bool:
    guild = ctx.guild
    if guild is None:
        await reply_error_ctx(ctx, "This command only works in a server.", title="Server only")
        return False
    me = guild.me
    if me is None:
        await reply_error_ctx(
            ctx,
            "I'm not a member of this server. Add me with `/utility invite` first.",
            title="Bot not in server",
        )
        return False

    missing = missing_permissions(me, required)
    if missing:
        await reply_error_ctx(
            ctx,
            f"I need: **{', '.join(missing)}** to do that. Please check my role permissions.",
            title="I'm missing permissions",
        )
        return False
    return True


async def resolve_member(guild: discord.Guild, user: discord.abc.User) -> discord.Member | None:
    member = guild.get_member(user.id)
    if member is not None:
        return member
    try:
        return await guild.fetch_member(user.id)
    except (discord.NotFound, discord.HTTPException):
        return None


def hierarchy_problem_for(
    guild: discord.Guild,
    actor: discord.abc.User,
    bot_user: discord.abc.User | None,
    target: discord.Member,
    *,
    allow_self: bool = False,
) -> str | None:
    """Return a user-facing reason if the target cannot be moderated."""
    if bot_user is not None and target.id == bot_user.id:
        return "I can't moderate myself."
    if target.id == actor.id and not allow_self:
        return "You can't use this on yourself."
    if target.id == guild.owner_id:
        return "The server owner can't be moderated."

    actor_member = guild.get_member(actor.id) or actor
    same_actor = target.id == actor.id and allow_self
    if (
        not same_actor
        and isinstance(actor_member, discord.Member)
        and actor_member.id != guild.owner_id
    ):
        if target.top_role >= actor_member.top_role:
            return "You can't moderate someone with an equal or higher role."

    me = guild.me
    if me is not None and target.top_role >= me.top_role:
        return "My role is below or equal to theirs, so I can't act on them."
    return None


def hierarchy_problem(
    interaction: discord.Interaction,
    target: discord.Member,
    *,
    allow_self: bool = False,
) -> str | None:
    """Return a user-facing reason if the target cannot be moderated."""
    guild = interaction.guild
    if guild is None:
        return "This only works in a server."
    return hierarchy_problem_for(
        guild,
        interaction.user,
        interaction.client.user,
        target,
        allow_self=allow_self,
    )


async def try_dm(user: discord.abc.User, embed: discord.Embed) -> bool:
    try:
        await user.send(embed=embed)
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


def parse_user_id(value: str) -> int | None:
    value = value.strip()
    match = re.fullmatch(r"<@!?(\d{15,20})>", value)
    if match:
        return int(match.group(1))
    if re.fullmatch(r"\d{15,20}", value):
        return int(value)
    return None


def parse_duration(value: str) -> int:
    """Parse 30s, 10m, 2h, or 7d into seconds.

    A value of 0 with any suffix (0, 0s, 0m, 0h, 0d) returns 0, which callers
    can treat as an infinite duration where supported.
    """
    match = re.fullmatch(
        r"\s*(\d+)\s*(s|sec|secs|m|min|mins|h|hr|hrs|d|day|days)?\s*",
        value,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError("Use a duration like `10m`, `2h`, or `7d`.")
    amount = int(match.group(1))
    unit = (match.group(2) or "s")[0].lower()
    if amount == 0:
        return 0
    seconds = amount * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    if seconds <= 0:
        raise ValueError("Duration must be greater than zero.")
    return seconds


def humanize_seconds(seconds: int) -> str:
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def parse_dice(expression: str) -> tuple[int, int, int]:
    """Parse NdS+M (or a bare number) into (count, sides, modifier)."""
    expression = expression.strip().lower().replace(" ", "")
    if expression.isdigit():
        count, sides, modifier = 1, int(expression), 0
    else:
        match = re.fullmatch(r"(\d{1,3})d(\d{1,4})([+-]\d{1,4})?", expression)
        if not match:
            raise ValueError("Use dice notation like `1d6`, `2d20`, or `3d8+2`.")
        count = int(match.group(1) or 1)
        sides = int(match.group(2))
        modifier = int(match.group(3) or 0)

    if not 1 <= count <= 100:
        raise ValueError("You can roll between 1 and 100 dice at once.")
    if not 2 <= sides <= 1000:
        raise ValueError("Dice must have between 2 and 1000 sides.")
    if not -1000 <= modifier <= 1000:
        raise ValueError("The modifier must be between -1000 and 1000.")
    return count, sides, modifier


def progress_bar(value: int, maximum: int, length: int = 10) -> str:
    if maximum <= 0:
        filled = 0
    else:
        filled = round(min(max(value, 0), maximum) / maximum * length)
    return "█" * filled + "░" * (length - filled)


def level_progress(xp: int) -> tuple[int, int, int]:
    """Return (level, xp into level, xp needed for next level)."""
    level = 0
    remaining = max(0, xp)
    needed = 100
    while remaining >= needed:
        remaining -= needed
        level += 1
        needed = 100 + level * 50
    return level, remaining, needed


def xp_for_level(level: int) -> int:
    """Total XP required to reach a level."""
    return 25 * level * level + 75 * level


def ship_score(first_id: int, second_id: int) -> int:
    key = "-".join(str(part) for part in sorted((first_id, second_id)))
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 101


def format_coins(amount: int) -> str:
    return f"🪙 {amount:,}"


def format_welcome(
    template: str | None,
    member: discord.abc.User,
    guild: discord.Guild | None = None,
) -> str:
    if not template:
        template = "Welcome {user} to **{server}**! You're member #{member_count}."
    guild = guild or getattr(member, "guild", None)
    server_name = guild.name if guild is not None else "the server"
    member_count = (guild.member_count or 0) if guild is not None else 0
    display_name = getattr(member, "display_name", None) or getattr(member, "name", "there")
    return (
        template.replace("{user}", member.mention)
        .replace("{name}", display_name)
        .replace("{server}", server_name)
        .replace("{member_count}", str(member_count))
    )


async def send_modlog(bot, guild: discord.Guild, embed: discord.Embed) -> None:
    config = await bot.db.get_guild_config(guild.id)
    channel_id = config.get("modlog_channel_id")
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel is None:
        try:
            channel = await guild.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return
    if not isinstance(channel, discord.abc.Messageable):
        return
    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass
