import asyncio
import json

from discord import Message, Embed, Guild, TextChannel
import discord
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils.chat_formatting import humanize_number
from redbot.core import commands, Config, bot as RedBot, errors, i18n
from redbot.core.commands import UserInputOptional
from redbot.core.i18n import Translator, cog_i18n


from .log import log

datadragon_version = "11.14.1"

_ = Translator("osu", __file__)

@cog_i18n(_)
class osu(commands.Cog):
    """osu! related commands."""

    def __init__(self, bot: RedBot, *args, **kwargs):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=114573088)
        default_guild = {

        }
        default_user = {
            "nickname": "",
            "id": -1
        }

        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)

        super().__init__(*args, **kwargs)

    def cog_unload(self):
        self.session.detach()
        log.info(_("osu! cog has been successfully detach!"))

    @commands.group(name="osu")
    async def _osu(self, ctx: commands.Context):
        """osu! related commands"""

        pass

    @_osu.command(name="setname")
    async def _osu_setname(self, ctx: commands.Context):
        """set's your osu! nickname in bot settings"""

        await ctx.send("Send a proper osu! ``nickname``")

        try:
            msg = await self.bot.wait_for(
                "message",
                check=MessagePredicate.same_context(ctx),
                timeout=30
            )
        except asyncio.TimeoutError:
            await ctx.send("Time is out. Cancelled.")
        else:
            await self.config.user(ctx.author).nickname.set(msg.content)

            await ctx.send(_("Your name is set as \"{name}\"").format(name=msg.content))

    @_osu.command(name="forgiveme")
    async def _osu_forgiveme(self, ctx: commands.Context):
        """clear's your osu! settings in this bot"""

        await self.config.user(ctx.author).nickname.set("")
        await self.config.user(ctx.author).id.set(-1)

        await ctx.send(_("Your settings have been reset"))


