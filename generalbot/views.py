"""Interactive views used by the entertainment commands."""

from __future__ import annotations

import discord

from .database import Database
from .helpers import (
    BRAND,
    ERROR,
    GOLD,
    SUCCESS,
    WARNING,
    base_embed,
    progress_bar,
    truncate,
    utcnow_iso,
)


class TriviaView(discord.ui.View):
    def __init__(self, question: dict, author_id: int) -> None:
        super().__init__(timeout=30)
        self.question = question
        self.author_id = author_id
        self.correct_index = int(question["answer"])
        self.answered = False
        self.message: discord.Message | None = None
        self.buttons: list[discord.ui.Button] = []

        for index, choice in enumerate(question["choices"]):
            letter = "ABCD"[index]
            button = discord.ui.Button(
                label=truncate(f"{letter}. {choice}", 80),
                style=discord.ButtonStyle.secondary,
            )
            button.callback = self._make_callback(index)
            self.add_item(button)
            self.buttons.append(button)

        self.embed = self._build_embed()

    def _build_embed(self) -> discord.Embed:
        embed = base_embed(
            "🧠 Trivia",
            f"**{self.question['question']}**\n\nPick the correct answer below. You have 30 seconds.",
            color=BRAND,
            footer="GeneralBot Trivia",
        )
        return embed

    def _make_callback(self, index: int):
        async def callback(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await interaction.response.send_message(
                    "This isn't your trivia question. Start your own with `/fun trivia`.",
                    ephemeral=True,
                )
                return
            if self.answered:
                await interaction.response.send_message(
                    "You already answered this one.", ephemeral=True
                )
                return

            self.answered = True
            correct = index == self.correct_index
            for child_index, button in enumerate(self.buttons):
                button.disabled = True
                if child_index == self.correct_index:
                    button.style = discord.ButtonStyle.success
                elif child_index == index:
                    button.style = discord.ButtonStyle.danger

            embed = self.embed.copy()
            embed.color = SUCCESS if correct else ERROR
            answer = self.question["choices"][self.correct_index]
            letter = "ABCD"[self.correct_index]
            if correct:
                result = "✅ Correct!"
            else:
                result = f"❌ Not quite. The answer was **{letter}. {answer}**."
            embed.add_field(name="Result", value=result, inline=False)
            embed.set_footer(
                text=f"Answered by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url,
            )
            await interaction.response.edit_message(embed=embed, view=self)

        return callback

    async def on_timeout(self) -> None:
        if self.answered:
            return
        for button in self.buttons:
            button.disabled = True
        if self.message is not None:
            embed = self.embed.copy()
            embed.color = WARNING
            answer = self.question["choices"][self.correct_index]
            letter = "ABCD"[self.correct_index]
            embed.add_field(
                name="Time's up",
                value=f"The answer was **{letter}. {answer}**.",
                inline=False,
            )
            embed.set_footer(text="GeneralBot Trivia · timed out")
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass


class ProposalView(discord.ui.View):
    def __init__(
        self,
        db: Database,
        author: discord.abc.User,
        target: discord.abc.User,
    ) -> None:
        super().__init__(timeout=60)
        self.db = db
        self.author = author
        self.target = target
        self.message: discord.Message | None = None
        self.resolved = False
        self.embed = base_embed(
            "💍 Marriage Proposal",
            f"{author.mention} is proposing to {target.mention}!\n\n"
            f"{target.mention}, do you accept?",
            color=GOLD,
            footer="This proposal expires in 60 seconds · GeneralBot",
        )
        self.embed.set_thumbnail(url=target.display_avatar.url)

    def _disable_buttons(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="💍")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.target.id:
            await interaction.response.send_message(
                "This proposal isn't for you.", ephemeral=True
            )
            return
        if self.resolved:
            await interaction.response.send_message(
                "This proposal has already been answered.", ephemeral=True
            )
            return

        self.resolved = True
        self._disable_buttons()
        married = await self.db.marry(
            self.author.id,
            self.target.id,
            utcnow_iso(),
        )
        if married:
            embed = base_embed(
                "💍 Just Married!",
                f"{self.author.mention} and {self.target.mention} are now married!",
                color=SUCCESS,
                footer="Use /social divorce if things go south · GeneralBot",
            )
        else:
            embed = base_embed(
                "💔 Proposal Failed",
                "One of you is already married.",
                color=ERROR,
            )
        embed.set_thumbnail(url=self.target.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.secondary, emoji="💔")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.target.id:
            await interaction.response.send_message(
                "This proposal isn't for you.", ephemeral=True
            )
            return
        if self.resolved:
            await interaction.response.send_message(
                "This proposal has already been answered.", ephemeral=True
            )
            return

        self.resolved = True
        self._disable_buttons()
        embed = base_embed(
            "💔 Proposal Declined",
            f"{self.target.mention} declined {self.author.mention}'s proposal.",
            color=ERROR,
        )
        embed.set_thumbnail(url=self.target.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self) -> None:
        if self.resolved:
            return
        self.resolved = True
        self._disable_buttons()
        if self.message is None:
            return
        embed = base_embed(
            "⌛ Proposal Expired",
            f"{self.target.mention} didn't answer {self.author.mention}'s proposal.",
            color=WARNING,
        )
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass


class PollView(discord.ui.View):
    def __init__(self, question: str, options: list[str]) -> None:
        super().__init__(timeout=300)
        self.question = question
        self.options = options
        self.votes: dict[int, set[int]] = {index: set() for index in range(len(options))}
        self.message: discord.Message | None = None
        self.buttons: list[discord.ui.Button] = []

        for index, option in enumerate(options):
            button = discord.ui.Button(
                label=truncate(option, 80), style=discord.ButtonStyle.primary
            )
            button.callback = self._make_callback(index)
            self.add_item(button)
            self.buttons.append(button)

    def _make_callback(self, index: int):
        async def callback(interaction: discord.Interaction) -> None:
            if self.message is None:
                self.message = interaction.message
            user_id = interaction.user.id
            if user_id in self.votes[index]:
                self.votes[index].remove(user_id)
            else:
                for voters in self.votes.values():
                    voters.discard(user_id)
                self.votes[index].add(user_id)
            await interaction.response.edit_message(embed=self.render_embed(), view=self)

        return callback

    def render_embed(self, *, closed: bool = False) -> discord.Embed:
        total = sum(len(voters) for voters in self.votes.values())
        lines = [f"**{discord.utils.escape_markdown(self.question)}**", ""]
        for index, option in enumerate(self.options):
            count = len(self.votes[index])
            percentage = (count / total * 100) if total else 0
            bar = progress_bar(count, max(total, 1), length=10)
            lines.append(
                f"`{bar}` **{discord.utils.escape_markdown(option)}** — "
                f"{count} vote{'s' if count != 1 else ''} ({percentage:.0f}%)"
            )
        lines.append("")
        if closed:
            lines.append("🔒 **Poll closed.**")
        else:
            lines.append(
                f"Total votes: **{total}** · Click a button to vote, click again to remove."
            )
        embed = base_embed("📊 Poll", "\n".join(lines), color=BRAND, footer="GeneralBot Poll")
        return embed

    async def on_timeout(self) -> None:
        for button in self.buttons:
            button.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(embed=self.render_embed(closed=True), view=self)
            except discord.HTTPException:
                pass
