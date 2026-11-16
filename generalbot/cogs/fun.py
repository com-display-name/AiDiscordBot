"""Entertainment commands, grouped under /fun."""

from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING, Literal

import discord
from discord import app_commands
from discord.ext import commands

from .. import data
from ..helpers import (
    BRAND,
    ERROR,
    GOLD,
    SUCCESS,
    WARNING,
    base_embed,
    parse_dice,
    progress_bar,
    reply_error,
    respond,
    ship_score,
)
from ..views import PollView, TriviaView

if TYPE_CHECKING:
    from ..bot import GeneralBot


def _split_options(raw: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"[,;\n]", raw)]
    return [part for part in parts if part]


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class Fun(commands.GroupCog, group_name="fun", group_description="Games, jokes, and random nonsense"):
    def __init__(self, bot: GeneralBot) -> None:
        self.bot = bot

    @app_commands.command(name="8ball", description="Ask the magic 8-ball a yes/no question")
    @app_commands.describe(question="The question on your mind")
    async def eightball(self, interaction: discord.Interaction, question: str) -> None:
        question = question.strip()
        if not question:
            await reply_error(interaction, "Ask me an actual question.", title="Question required")
            return
        if len(question) > 300:
            await reply_error(interaction, "Keep the question under 300 characters.")
            return

        category = random.choices(
            ("positive", "neutral", "negative"), weights=(45, 20, 35), k=1
        )[0]
        answer = random.choice(data.EIGHT_BALL[category])
        color = {"positive": SUCCESS, "neutral": BRAND, "negative": ERROR}[category]
        embed = base_embed(
            "🎱 Magic 8-Ball",
            f"**You asked:** {discord.utils.escape_markdown(question)}\n\n**Answer:** {answer}",
            color=color,
        )
        await respond(interaction, embed=embed)

    @app_commands.command(name="coinflip", description="Flip a coin")
    async def coinflip(self, interaction: discord.Interaction) -> None:
        result = random.choice(("Heads", "Tails"))
        embed = base_embed(
            "🪙 Coin Flip",
            f"The coin landed on **{result}**.\n\n`{random.choice(('🪙', '🪙', '✨'))}`",
            color=GOLD if result == "Heads" else BRAND,
        )
        await respond(interaction, embed=embed)

    @app_commands.command(name="roll", description="Roll dice using NdS notation")
    @app_commands.describe(dice="Dice expression, e.g. 1d6, 2d20, or 3d8+2")
    async def roll(self, interaction: discord.Interaction, dice: str = "1d6") -> None:
        try:
            count, sides, modifier = parse_dice(dice)
        except ValueError as exc:
            await reply_error(interaction, str(exc), title="Invalid dice")
            return

        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls) + modifier
        expression = f"{count}d{sides}" + (f"{modifier:+d}" if modifier else "")
        embed = base_embed("🎲 Dice Roll", f"`{expression}` → **{total}**", color=BRAND)
        if count <= 20:
            embed.add_field(
                name="Rolls",
                value=", ".join(f"`{value}`" for value in rolls),
                inline=False,
            )
        if modifier:
            embed.add_field(name="Modifier", value=f"{modifier:+d}", inline=True)
        await respond(interaction, embed=embed)

    @app_commands.command(name="choose", description="Let the bot pick from your options")
    @app_commands.describe(options="Options separated by commas or new lines")
    async def choose(self, interaction: discord.Interaction, options: str) -> None:
        choices = _split_options(options)
        if len(choices) < 2:
            await reply_error(
                interaction,
                "Give me at least two options, separated by commas. Example: `red, green, blue`.",
                title="Not enough options",
            )
            return
        if len(choices) > 20:
            await reply_error(interaction, "Please keep it to 20 options or fewer.")
            return

        choice = random.choice(choices)
        embed = base_embed(
            "🤔 Decision Time",
            f"I choose... **{discord.utils.escape_markdown(choice)}**!\n\n"
            f"*Out of {len(choices)} options.*",
            color=SUCCESS,
        )
        await respond(interaction, embed=embed)

    @app_commands.command(name="rps", description="Play rock, paper, scissors against the bot")
    @app_commands.describe(choice="Your move")
    async def rps(
        self,
        interaction: discord.Interaction,
        choice: Literal["rock", "paper", "scissors"],
    ) -> None:
        bot_choice = random.choice(("rock", "paper", "scissors"))
        wins = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
        if choice == bot_choice:
            outcome, color, title = "It's a tie!", WARNING, "🤝 Tie"
        elif wins[choice] == bot_choice:
            outcome, color, title = "You win!", SUCCESS, "🎉 You Win"
        else:
            outcome, color, title = "I win!", ERROR, "🤖 I Win"

        emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
        embed = base_embed(
            title,
            f"You chose {emojis[choice]} **{choice.title()}**.\n"
            f"I chose {emojis[bot_choice]} **{bot_choice.title()}**.\n\n**{outcome}**",
            color=color,
        )
        await respond(interaction, embed=embed)

    @app_commands.command(name="ship", description="Calculate the compatibility between two people")
    @app_commands.describe(first="The first person", second="The second person (defaults to you)")
    async def ship(
        self,
        interaction: discord.Interaction,
        first: discord.User,
        second: discord.User | None = None,
    ) -> None:
        second = second or interaction.user
        if first.id == second.id:
            await reply_error(interaction, "Pick two different people.", title="Can't ship that")
            return

        score = ship_score(first.id, second.id)
        if score >= 90:
            verdict = "Soulmates. It's honestly a little disgusting."
        elif score >= 75:
            verdict = "Great match. Something is definitely there."
        elif score >= 50:
            verdict = "There's potential. Proceed with caution."
        elif score >= 25:
            verdict = "Awkward. But hey, opposites attract?"
        else:
            verdict = "Run. Run far away."

        embed = base_embed(
            "💘 Ship Meter",
            f"{first.mention} + {second.mention}",
            color=BRAND,
        )
        embed.add_field(
            name="Compatibility",
            value=f"`{progress_bar(score, 100)}`\n**{score}%**",
            inline=False,
        )
        embed.add_field(name="Verdict", value=verdict, inline=False)
        embed.set_thumbnail(url=first.display_avatar.url)
        await respond(interaction, embed=embed)

    @app_commands.command(name="iq", description="Measure someone's totally real IQ")
    @app_commands.describe(user="The person to test (defaults to you)")
    async def iq(
        self,
        interaction: discord.Interaction,
        user: discord.User | None = None,
    ) -> None:
        target = user or interaction.user
        score = max(1, min(200, round(random.gauss(100, 15))))
        if score >= 140:
            verdict = "Galaxy brain. Please explain the meaning of life."
        elif score >= 120:
            verdict = "Very smart. Suspiciously smart, even."
        elif score >= 100:
            verdict = "Above average. Nice."
        elif score >= 85:
            verdict = "Perfectly average. The test was probably rigged."
        elif score >= 70:
            verdict = "Room temperature IQ. Cozy."
        else:
            verdict = "Oof. But at least you're memorable."

        embed = base_embed(
            f"🧠 {target.display_name}'s IQ",
            f"**{score}**\n\n{verdict}",
            color=GOLD if score >= 120 else BRAND,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="Peer-reviewed by absolutely nobody · GeneralBot")
        await respond(interaction, embed=embed)

    @app_commands.command(name="joke", description="Tell a joke")
    async def joke(self, interaction: discord.Interaction) -> None:
        embed = base_embed("😂 Joke", random.choice(data.JOKES), color=WARNING)
        await respond(interaction, embed=embed)

    @app_commands.command(name="truth", description="Get a truth question")
    async def truth(self, interaction: discord.Interaction) -> None:
        embed = base_embed("🫣 Truth", random.choice(data.TRUTHS), color=BRAND)
        await respond(interaction, embed=embed)

    @app_commands.command(name="dare", description="Get a dare")
    async def dare(self, interaction: discord.Interaction) -> None:
        embed = base_embed("😈 Dare", random.choice(data.DARES), color=ERROR)
        await respond(interaction, embed=embed)

    @app_commands.command(name="trivia", description="Answer a trivia question")
    async def trivia(self, interaction: discord.Interaction) -> None:
        question = random.choice(data.TRIVIA)
        view = TriviaView(question, interaction.user.id)
        await interaction.response.send_message(embed=view.embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="poll", description="Create a button poll")
    @app_commands.describe(
        question="The poll question",
        option1="First option",
        option2="Second option",
        option3="Optional third option",
        option4="Optional fourth option",
        option5="Optional fifth option",
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: str | None = None,
        option4: str | None = None,
        option5: str | None = None,
    ) -> None:
        question = question.strip()
        options = [
            option.strip()
            for option in (option1, option2, option3, option4, option5)
            if option is not None and option.strip()
        ]
        if not question:
            await reply_error(interaction, "Your poll needs a question.")
            return
        if len(question) > 256:
            await reply_error(interaction, "Keep the poll question under 256 characters.")
            return
        if len(options) < 2:
            await reply_error(interaction, "A poll needs at least two options.")
            return
        if any(len(option) > 80 for option in options):
            await reply_error(interaction, "Each option must be 80 characters or fewer.")
            return
        if len({option.casefold() for option in options}) != len(options):
            await reply_error(interaction, "Poll options must be unique.")
            return

        view = PollView(question, options)
        await interaction.response.send_message(embed=view.render_embed(), view=view)
        view.message = await interaction.original_response()


async def setup(bot: GeneralBot) -> None:
    await bot.add_cog(Fun(bot))
