"""Marriage and relationship commands, grouped under /social."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..helpers import (
    GOLD,
    SUCCESS,
    WARNING,
    base_embed,
    parse_iso,
    reply_error,
    respond,
    try_dm,
)
from ..views import ProposalView

if TYPE_CHECKING:
    from ..bot import GeneralBot


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class Social(commands.GroupCog, group_name="social", group_description="Marriage, divorce, and relationship status"):
    def __init__(self, bot: GeneralBot) -> None:
        self.bot = bot

    @app_commands.command(name="marry", description="Propose to another user")
    @app_commands.describe(user="The user you want to marry")
    async def marry(self, interaction: discord.Interaction, user: discord.User) -> None:
        if user.id == interaction.user.id:
            await reply_error(interaction, "You can't marry yourself.", title="Nice try")
            return
        if user.bot:
            await reply_error(interaction, "Bots are not eligible for marriage.", title="Invalid partner")
            return

        mine = await self.bot.db.get_marriage(interaction.user.id)
        if mine is not None:
            await reply_error(
                interaction,
                f"You're already married to <@{mine['partner_id']}>. Use `/social divorce` first.",
                title="Already married",
            )
            return
        theirs = await self.bot.db.get_marriage(user.id)
        if theirs is not None:
            await reply_error(
                interaction,
                f"{user.mention} is already married to <@{theirs['partner_id']}>.",
                title="Already married",
            )
            return

        view = ProposalView(self.bot.db, interaction.user, user)
        await interaction.response.send_message(
            content=f"{user.mention}, you have a marriage proposal!",
            embed=view.embed,
            view=view,
        )
        view.message = await interaction.original_response()

    @app_commands.command(name="divorce", description="End your current marriage")
    async def divorce(self, interaction: discord.Interaction) -> None:
        marriage = await self.bot.db.get_marriage(interaction.user.id)
        if marriage is None:
            await reply_error(interaction, "You're not married.", title="Nothing to end")
            return

        partner_id = await self.bot.db.divorce(interaction.user.id)
        if partner_id is None:
            await reply_error(interaction, "The divorce could not be completed.", title="Divorce failed")
            return

        embed = base_embed(
            "💔 Divorced",
            f"You and <@{partner_id}> are no longer married.",
            color=WARNING,
        )
        await respond(interaction, embed=embed)

        partner = self.bot.get_user(partner_id)
        if partner is not None:
            await try_dm(
                partner,
                base_embed(
                    "💔 Divorce",
                    f"{interaction.user.mention} ended your marriage.",
                    color=WARNING,
                ),
            )

    @app_commands.command(name="status", description="Show a user's marriage status")
    @app_commands.describe(user="The user to check (defaults to you)")
    async def status(
        self,
        interaction: discord.Interaction,
        user: discord.User | None = None,
    ) -> None:
        target = user or interaction.user
        marriage = await self.bot.db.get_marriage(target.id)
        if marriage is None:
            embed = base_embed(
                f"💍 {target.display_name}'s Status",
                "Single and ready to mingle.\n\nUse `/social marry` to propose to someone.",
                color=SUCCESS,
            )
        else:
            married_at = parse_iso(marriage.get("married_at"))
            since = discord.utils.format_dt(married_at, "F") if married_at else "Unknown"
            embed = base_embed(
                f"💍 {target.display_name}'s Status",
                f"Married to <@{marriage['partner_id']}>.\n\n**Since:** {since}",
                color=GOLD,
            )
        embed.set_thumbnail(url=target.display_avatar.url)
        await respond(interaction, embed=embed)


async def setup(bot: GeneralBot) -> None:
    await bot.add_cog(Social(bot))
