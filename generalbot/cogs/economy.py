"""A lightweight global economy, grouped under /economy."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from .. import data
from ..helpers import (
    ERROR,
    GOLD,
    SUCCESS,
    WARNING,
    base_embed,
    cooldown_end,
    format_coins,
    reply_error,
    respond,
    utcnow_iso,
)

if TYPE_CHECKING:
    from ..bot import GeneralBot

DAILY_SECONDS = 24 * 60 * 60
WORK_SECONDS = 60 * 60
HEIST_SECONDS = 15 * 60


def _parse_bet(raw: str, balance: int, minimum: int) -> int:
    cleaned = raw.strip().lower().replace(",", "").replace("_", "")
    if cleaned in {"all", "max"}:
        amount = balance
    else:
        try:
            amount = int(cleaned)
        except ValueError as exc:
            raise ValueError("Bet an amount like `100`, `1,000`, or `all`.") from exc

    if amount < minimum:
        raise ValueError(f"The minimum bet is **{minimum:,}** coins.")
    if amount > balance:
        raise ValueError(f"You only have **{format_coins(balance)}**.")
    return amount


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class Economy(commands.GroupCog, group_name="economy", group_description="Earn, gamble, and lose imaginary coins"):
    def __init__(self, bot: GeneralBot) -> None:
        self.bot = bot

    @app_commands.command(name="balance", description="Show a wallet balance")
    @app_commands.describe(user="The user to check (defaults to you)")
    async def balance(
        self,
        interaction: discord.Interaction,
        user: discord.User | None = None,
    ) -> None:
        target = user or interaction.user
        balance = await self.bot.db.get_balance(target.id)
        embed = base_embed(
            f"👛 {target.display_name}'s Wallet",
            f"**{format_coins(balance)}**\n\n"
            "*Global wallet — shared across servers and DMs.*",
            color=GOLD,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await respond(interaction, embed=embed)

    @app_commands.command(name="daily", description="Collect your daily coins")
    async def daily(self, interaction: discord.Interaction) -> None:
        row = await self.bot.db.get_economy(interaction.user.id)
        end = cooldown_end(row.get("last_daily"), DAILY_SECONDS)
        if end is not None:
            await reply_error(
                interaction,
                f"You already collected your daily. Come back {discord.utils.format_dt(end, 'R')}.",
                title="Daily not ready",
            )
            return

        reward = random.randint(150, 300)
        balance = await self.bot.db.add_balance(interaction.user.id, reward)
        await self.bot.db.set_cooldown(interaction.user.id, "last_daily", utcnow_iso())
        embed = base_embed(
            "💰 Daily Reward",
            f"You collected **{format_coins(reward)}**.\n\n"
            f"New balance: **{format_coins(balance)}**",
            color=SUCCESS,
        )
        embed.set_footer(text="Come back in 24 hours · GeneralBot")
        await respond(interaction, embed=embed)

    @app_commands.command(name="work", description="Do a job for some coins")
    async def work(self, interaction: discord.Interaction) -> None:
        row = await self.bot.db.get_economy(interaction.user.id)
        end = cooldown_end(row.get("last_work"), WORK_SECONDS)
        if end is not None:
            await reply_error(
                interaction,
                f"You're still recovering from your last shift. Try again {discord.utils.format_dt(end, 'R')}.",
                title="On cooldown",
            )
            return

        reward = random.randint(40, 120)
        job = random.choice(data.JOBS)
        balance = await self.bot.db.add_balance(interaction.user.id, reward)
        await self.bot.db.set_cooldown(interaction.user.id, "last_work", utcnow_iso())
        embed = base_embed(
            "💼 Shift Complete",
            f"You {job} and earned **{format_coins(reward)}**.\n\n"
            f"New balance: **{format_coins(balance)}**",
            color=SUCCESS,
        )
        embed.set_footer(text="Work again in 1 hour · GeneralBot")
        await respond(interaction, embed=embed)

    @app_commands.command(name="gamble", description="Bet some coins")
    @app_commands.describe(amount="How much to bet (number or 'all')")
    async def gamble(self, interaction: discord.Interaction, amount: str) -> None:
        balance = await self.bot.db.get_balance(interaction.user.id)
        try:
            bet = _parse_bet(amount, balance, 10)
        except ValueError as exc:
            await reply_error(interaction, str(exc), title="Invalid bet")
            return

        roll = random.randint(1, 100)
        if roll <= 45:
            payout, outcome, color, title = bet * 2, "win", SUCCESS, "🎉 You Won!"
        elif roll <= 95:
            payout, outcome, color, title = 0, "loss", ERROR, "💸 You Lost"
        else:
            payout, outcome, color, title = bet * 4, "jackpot", GOLD, "💎 Jackpot!"

        new_balance = await self.bot.db.settle_bet(interaction.user.id, bet, payout)
        if new_balance is None:
            await reply_error(interaction, "Your balance changed before the bet settled. Try again.", title="Bet failed")
            return

        if outcome == "win":
            description = f"The dice landed on **{roll}**. You doubled your bet."
        elif outcome == "jackpot":
            description = f"The dice landed on **{roll}**. Four times your bet!"
        else:
            description = f"The dice landed on **{roll}**. Better luck next time."

        embed = base_embed(title, description, color=color)
        embed.add_field(name="Bet", value=format_coins(bet), inline=True)
        embed.add_field(name="Payout", value=format_coins(payout), inline=True)
        embed.add_field(name="Balance", value=format_coins(new_balance), inline=True)
        embed.set_footer(text="Gambling is bad. Imaginary gambling is fine · GeneralBot")
        await respond(interaction, embed=embed)

    @app_commands.command(name="heist", description="Attempt a high-risk heist")
    @app_commands.describe(amount="How much to risk (minimum 100, or 'all')")
    async def heist(self, interaction: discord.Interaction, amount: str) -> None:
        row = await self.bot.db.get_economy(interaction.user.id)
        end = cooldown_end(row.get("last_heist"), HEIST_SECONDS)
        if end is not None:
            await reply_error(
                interaction,
                f"The crew is still laying low. Plan another heist {discord.utils.format_dt(end, 'R')}.",
                title="Heist on cooldown",
            )
            return

        balance = int(row["balance"])
        try:
            bet = _parse_bet(amount, balance, 100)
        except ValueError as exc:
            await reply_error(interaction, str(exc), title="Invalid bet")
            return

        success = random.random() < 0.55
        payout = (bet * 5) // 2 if success else 0
        new_balance = await self.bot.db.settle_bet(interaction.user.id, bet, payout)
        if new_balance is None:
            await reply_error(interaction, "Your balance changed before the heist started. Try again.", title="Heist failed")
            return
        await self.bot.db.set_cooldown(interaction.user.id, "last_heist", utcnow_iso())

        if success:
            description = random.choice(data.HEIST_SUCCESS)
            title, color = "🦹 Heist Successful", SUCCESS
        else:
            description = random.choice(data.HEIST_FAILURE)
            title, color = "🚨 Heist Failed", ERROR

        embed = base_embed(title, description, color=color)
        embed.add_field(name="Risked", value=format_coins(bet), inline=True)
        embed.add_field(name="Payout", value=format_coins(payout), inline=True)
        embed.add_field(name="Balance", value=format_coins(new_balance), inline=True)
        embed.set_footer(text="Heists are on a 15 minute cooldown · GeneralBot")
        await respond(interaction, embed=embed)

    @app_commands.command(name="pay", description="Send coins to another user")
    @app_commands.describe(user="The user to pay", amount="How many coins to send")
    async def pay(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        amount: app_commands.Range[int, 1, 1_000_000],
    ) -> None:
        if user.id == interaction.user.id:
            await reply_error(interaction, "You can't pay yourself.", title="Nice try")
            return
        if user.bot:
            await reply_error(interaction, "Bots don't need your coins.", title="Invalid recipient")
            return

        balance = await self.bot.db.get_balance(interaction.user.id)
        if balance < amount:
            await reply_error(
                interaction,
                f"You only have **{format_coins(balance)}**.",
                title="Not enough coins",
            )
            return

        moved = await self.bot.db.transfer(interaction.user.id, user.id, amount)
        if not moved:
            await reply_error(interaction, "The transfer failed. Try again.", title="Payment failed")
            return
        new_balance = await self.bot.db.get_balance(interaction.user.id)
        embed = base_embed(
            "💸 Payment Sent",
            f"{interaction.user.mention} sent **{format_coins(amount)}** to {user.mention}.\n\n"
            f"Your balance: **{format_coins(new_balance)}**",
            color=SUCCESS,
        )
        await respond(interaction, embed=embed)

    @app_commands.command(name="leaderboard", description="Show the richest users")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        rows = await self.bot.db.economy_top(10)
        if not rows:
            await respond(
                interaction,
                embed=base_embed(
                    "🏦 Economy Leaderboard",
                    "Nobody has any coins yet. Try `/economy daily` to get started.",
                    color=WARNING,
                ),
            )
            return

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = []
        for position, row in enumerate(rows, start=1):
            prefix = medals.get(position, f"`#{position}`")
            lines.append(f"{prefix} <@{row['user_id']}> — **{format_coins(row['balance'])}**")
        embed = base_embed(
            "🏦 Economy Leaderboard",
            "\n".join(lines),
            color=GOLD,
        )
        embed.set_footer(text="Global wallet leaderboard · GeneralBot")
        await respond(interaction, embed=embed)


async def setup(bot: GeneralBot) -> None:
    await bot.add_cog(Economy(bot))
