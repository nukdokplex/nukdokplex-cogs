import asyncio
import datetime
import json

from discord import Message, Embed, Guild, TextChannel
import discord
from discord.ext import tasks
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils.chat_formatting import humanize_number
from redbot.core import commands, Config, bot as RedBot, errors, i18n
from discord.errors import NotFound as DiscordNotFoundError

from redbot.core.i18n import Translator, cog_i18n

from .log import log

_ = Translator("osuAllServers", __file__)

@cog_i18n(_)
class osuAllServers(commands.Cog):
    """osu! related commands"""

    def __init__(self, bot: RedBot, *args, **kwargs):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=13371448228)

        super().__init__(*args, **kwargs)

    def cog_unload(self):
        self.session.detach()

    @commands.command()
    async def osu(self, ctx: commands.Context):
        """osu! related commands"""

        pass

    @osu.command()
    async def bancho(self, ctx: commands.Context):
        """osu!bancho related commands"""

        pass

    # ---- osu! bancho ----








