"""Rating commands, grouped under /rate."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..helpers import BRAND, base_embed, progress_bar, respond

if TYPE_CHECKING:
    from ..bot import GeneralBot


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class Rate(commands.GroupCog, group_name="rate", group_description="Rate users on random nonsense"):
    def __init__(self, bot: GeneralBot) -> None:
        self.bot = bot

    async def _send_rating(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        *,
        title: str,
        emoji: str,
        noun: str,
        color: int = BRAND,
    ) -> None:
        percent = random.randint(0, 100)
        bar = progress_bar(percent, 100, length=10)
        embed = base_embed(
            f"{emoji} {title}",
            f"**{user.mention}** has **{percent}%** {noun}.\n\n`{bar}` {percent}%",
            color=color,
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await respond(interaction, embed=embed)

    @app_commands.command(name="rizz", description="Rate a user's rizz")
    @app_commands.describe(user="The user to rate")
    async def rizz(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self._send_rating(
            interaction,
            user,
            title="Rizz Rating",
            emoji="😏",
            noun="rizz",
            color=0xE91E63,
        )

    @app_commands.command(name="aura", description="Rate a user's aura")
    @app_commands.describe(user="The user to rate")
    async def aura(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self._send_rating(
            interaction,
            user,
            title="Aura Rating",
            emoji="✨",
            noun="aura",
            color=0x9B59B6,
        )

    @app_commands.command(name="skill", description="Rate a user's skill")
    @app_commands.describe(user="The user to rate")
    async def skill(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self._send_rating(
            interaction,
            user,
            title="Skill Rating",
            emoji="🎯",
            noun="skill",
            color=0x3498DB,
        )

    @app_commands.command(name="ragequit", description="Rate a user's ragequit level")
    @app_commands.describe(user="The user to rate")
    async def ragequit(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self._send_rating(
            interaction,
            user,
            title="Ragequit Rating",
            emoji="💢",
            noun="ragequit energy",
            color=0xE74C3C,
        )


async def setup(bot: GeneralBot) -> None:
    await bot.add_cog(Rate(bot))
