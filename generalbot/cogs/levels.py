"""Global XP and levels, grouped under /level."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..helpers import (
    BRAND,
    GOLD,
    SUCCESS,
    base_embed,
    level_progress,
    progress_bar,
    respond,
    utcnow_iso,
)

if TYPE_CHECKING:
    from ..bot import GeneralBot


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class Levels(commands.GroupCog, group_name="level", group_description="Earn XP and climb the global leaderboard"):
    def __init__(self, bot: GeneralBot) -> None:
        self.bot = bot

    @app_commands.command(name="rank", description="Show a user's level and XP")
    @app_commands.describe(user="The user to check (defaults to you)")
    async def rank(
        self,
        interaction: discord.Interaction,
        user: discord.User | None = None,
    ) -> None:
        target = user or interaction.user
        row = await self.bot.db.get_level(target.id)
        xp = int(row["xp"])
        level, current, needed = level_progress(xp)
        position = await self.bot.db.level_rank(target.id)
        total = await self.bot.db.level_user_count()

        embed = base_embed(
            f"📈 {target.display_name}'s Rank",
            f"**Level {level}** · {xp:,} XP total",
            color=GOLD if level >= 10 else BRAND,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(
            name="Progress",
            value=(
                f"`{progress_bar(current, needed)}`\n"
                f"{current:,} / {needed:,} XP\n"
                f"**{needed - current:,} XP** to level {level + 1}"
            ),
            inline=False,
        )
        embed.add_field(name="Leaderboard rank", value=f"#{position} of {total}", inline=True)
        embed.set_footer(text="XP is global and earns 15–25 XP per message · GeneralBot")
        await respond(interaction, embed=embed)

    @app_commands.command(name="leaderboard", description="Show the top XP earners")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        rows = await self.bot.db.level_top(10)
        if not rows:
            await respond(
                interaction,
                embed=base_embed(
                    "🏆 Level Leaderboard",
                    "Nobody has earned XP yet. Start chatting!",
                    color=BRAND,
                ),
            )
            return

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = []
        for position, row in enumerate(rows, start=1):
            level, _, _ = level_progress(int(row["xp"]))
            prefix = medals.get(position, f"`#{position}`")
            lines.append(
                f"{prefix} <@{row['user_id']}> — **Level {level}** · {int(row['xp']):,} XP"
            )
        embed = base_embed("🏆 Level Leaderboard", "\n".join(lines), color=GOLD)
        embed.set_footer(text="Global leaderboard · GeneralBot")
        await respond(interaction, embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.type != discord.MessageType.default:
            return

        result = await self.bot.db.award_xp(
            message.author.id,
            random.randint(15, 25),
            utcnow_iso(),
            cooldown_seconds=60,
        )
        if result is None:
            return

        old_xp, new_xp = result
        old_level = level_progress(old_xp)[0]
        new_level = level_progress(new_xp)[0]
        if new_level <= old_level:
            return

        embed = base_embed(
            "🎉 Level Up!",
            f"{message.author.mention} reached **level {new_level}**!",
            color=SUCCESS,
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text="Keep chatting to earn more XP · GeneralBot")
        try:
            await message.channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot: GeneralBot) -> None:
    await bot.add_cog(Levels(bot))
