"""Playful reaction commands, grouped under /reaction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..helpers import (
    BRAND,
    ERROR,
    GOLD,
    SUCCESS,
    WARNING,
    base_embed,
    reply_error,
    respond,
)

if TYPE_CHECKING:
    from ..bot import GeneralBot


@dataclass(frozen=True)
class ActionInfo:
    name: str
    title: str
    emoji: str
    verb: str
    color: int
    responses: tuple[str, ...]


ACTIONS: dict[str, ActionInfo] = {
    "kiss": ActionInfo("kiss", "Kiss", "💋", "kisses", GOLD, ("kiss", "slap")),
    "cuddle": ActionInfo("cuddle", "Cuddle", "🤗", "cuddles", SUCCESS, ("cuddle", "hug")),
    "punch": ActionInfo("punch", "Punch", "👊", "punches", ERROR, ("punch", "slap")),
    "shoot": ActionInfo("shoot", "Finger Gun", "🔫", "shoots a finger gun at", ERROR, ("shoot", "punch")),
    "hug": ActionInfo("hug", "Hug", "🫂", "hugs", SUCCESS, ("hug", "cuddle")),
    "slap": ActionInfo("slap", "Slap", "✋", "slaps", WARNING, ("slap", "punch")),
    "pat": ActionInfo("pat", "Head Pat", "🫳", "pats", SUCCESS, ("pat", "hug")),
    "highfive": ActionInfo("highfive", "High Five", "🙌", "high-fives", GOLD, ("highfive", "hug")),
    "bite": ActionInfo("bite", "Bite", "🦷", "bites", WARNING, ("bite", "slap")),
    "boop": ActionInfo("boop", "Boop", "👉", "boops", BRAND, ("boop", "pat")),
}


def _count_text(count: int) -> str:
    return f"That's **{count}** time{'s' if count != 1 else ''} now."


def build_reaction_embed(
    action: ActionInfo,
    actor: discord.abc.User,
    target: discord.abc.User,
    count: int,
    *,
    back: bool = False,
) -> discord.Embed:
    verb = f"{action.verb} back" if back else action.verb
    embed = base_embed(
        f"{action.emoji} {action.title}",
        f"{actor.mention} {verb} {target.mention}!\n\n{_count_text(count)}",
        color=action.color,
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    return embed


class ReactionView(discord.ui.View):
    def __init__(
        self,
        bot: GeneralBot,
        action_name: str,
        actor_id: int,
        target_id: int,
    ) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.action_name = action_name
        self.actor_id = actor_id
        self.target_id = target_id
        self.message: discord.Message | None = None
        self._add_buttons()

    def _add_buttons(self) -> None:
        action = ACTIONS.get(self.action_name)
        if action is None:
            return
        for response_name in action.responses:
            response = ACTIONS.get(response_name)
            if response is None:
                continue
            label = response.name if response_name != self.action_name else f"{response.name} back"
            style = (
                discord.ButtonStyle.primary
                if response_name == self.action_name
                else discord.ButtonStyle.secondary
            )
            button = discord.ui.Button(
                label=label,
                style=style,
                emoji=response.emoji,
                custom_id=f"reaction:{self.action_name}:{response_name}:{self.actor_id}:{self.target_id}",
            )

            async def callback(interaction: discord.Interaction, rn: str = response_name) -> None:
                await self._handle_response(interaction, rn)

            button.callback = callback
            self.add_item(button)

    async def _handle_response(self, interaction: discord.Interaction, response_name: str) -> None:
        if interaction.user.id != self.target_id:
            await interaction.response.send_message(
                "Only the person who received this reaction can respond.",
                ephemeral=True,
            )
            return

        response_action = ACTIONS.get(response_name)
        if response_action is None:
            await interaction.response.send_message("That reaction isn't available.", ephemeral=True)
            return

        actor = interaction.user
        try:
            target = interaction.client.get_user(self.actor_id) or await interaction.client.fetch_user(self.actor_id)
        except discord.HTTPException:
            await interaction.response.send_message("Couldn't find the user to respond to.", ephemeral=True)
            return

        if actor.id == target.id:
            await interaction.response.send_message(
                "You can't react to yourself.",
                ephemeral=True,
            )
            return

        count = await self.bot.db.increment_reaction_count(response_action.name, actor.id, target.id)
        is_back = response_name == self.action_name
        embed = build_reaction_embed(response_action, actor, target, count, back=is_back)
        view = ReactionView(self.bot, response_action.name, actor.id, target.id)

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        await interaction.response.edit_message(view=self)
        try:
            view.message = await interaction.followup.send(embed=embed, view=view, wait=True)
        except TypeError:
            view.message = await interaction.followup.send(embed=embed, view=view)
        self.stop()

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class Reaction(commands.GroupCog, group_name="reaction", group_description="Playful reactions for you and your friends"):
    def __init__(self, bot: GeneralBot) -> None:
        self.bot = bot

    async def _send_action(
        self,
        interaction: discord.Interaction,
        action_name: str,
        user: discord.User,
    ) -> None:
        action = ACTIONS[action_name]
        if user.id == interaction.user.id:
            await reply_error(
                interaction,
                "Pick someone else for that reaction.",
                title="Can't target yourself",
            )
            return

        count = await self.bot.db.increment_reaction_count(action_name, interaction.user.id, user.id)
        embed = build_reaction_embed(action, interaction.user, user, count)
        view = ReactionView(self.bot, action_name, interaction.user.id, user.id)
        await respond(interaction, embed=embed, view=view)
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            view.message = None

    @app_commands.command(name="kiss", description="Kiss someone")
    @app_commands.describe(user="Who to kiss")
    async def kiss(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self._send_action(interaction, "kiss", user)

    @app_commands.command(name="cuddle", description="Cuddle someone")
    @app_commands.describe(user="Who to cuddle")
    async def cuddle(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self._send_action(interaction, "cuddle", user)

    @app_commands.command(name="punch", description="Punch someone")
    @app_commands.describe(user="Who to punch")
    async def punch(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self._send_action(interaction, "punch", user)

    @app_commands.command(name="shoot", description="Shoot someone with a finger gun")
    @app_commands.describe(user="Who to shoot")
    async def shoot(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self._send_action(interaction, "shoot", user)

    @app_commands.command(name="hug", description="Hug someone")
    @app_commands.describe(user="Who to hug")
    async def hug(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self._send_action(interaction, "hug", user)

    @app_commands.command(name="slap", description="Slap someone")
    @app_commands.describe(user="Who to slap")
    async def slap(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self._send_action(interaction, "slap", user)

    @app_commands.command(name="pat", description="Pat someone on the head")
    @app_commands.describe(user="Who to pat")
    async def pat(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self._send_action(interaction, "pat", user)

    @app_commands.command(name="highfive", description="High-five someone")
    @app_commands.describe(user="Who to high-five")
    async def highfive(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self._send_action(interaction, "highfive", user)

    @app_commands.command(name="bite", description="Playfully bite someone")
    @app_commands.describe(user="Who to bite")
    async def bite(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self._send_action(interaction, "bite", user)

    @app_commands.command(name="boop", description="Boop someone's nose")
    @app_commands.describe(user="Who to boop")
    async def boop(self, interaction: discord.Interaction, user: discord.User) -> None:
        await self._send_action(interaction, "boop", user)


async def setup(bot: GeneralBot) -> None:
    await bot.add_cog(Reaction(bot))
