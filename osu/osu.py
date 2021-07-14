import asyncio
import json

import discord

from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils.chat_formatting import humanize_number
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from redbot.core import commands, Config, bot as RedBot, errors, i18n
from redbot.core.commands import UserInputOptional
from redbot.core.i18n import Translator, cog_i18n

from ossapi import Ossapi, OssapiV2, GameMode


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
        log.info("osu! cog has been successfully detach!")

    async def get_client_credentials(self, ctx: commands.Context = None):
        credentials = await self.bot.get_shared_api_tokens("osu")

        if credentials is None and ctx is not None:
            await ctx.send(_("Error! osu! ``client id`` and ``client secret`` have not been set. to set them use the "
                             "command ``{prefix}set api osu client_id,[YOUR CLIENT ID] client_secret,[YOUR CLIENT "
                             "SECRET]``.").format(prefix=ctx.prefix))

        if credentials is None:
            return None

        client_id = credentials.get("client_id")
        client_secret = credentials.get("client_secret")

        if ctx is not None and (client_id is None or not str.isnumeric(client_id) or int(client_id) == -1):
            await ctx.send(_("Error! osu! ``client id`` and ``client secret`` have not been set. to set them use the "
                             "command ``{prefix}set api osu client_id,[YOUR CLIENT ID] client_secret,[YOUR CLIENT "
                             "SECRET]``.").format(prefix=ctx.prefix))
        if client_id is None or not str.isnumeric(client_id) or int(client_id) == -1:
            return None

        if client_secret is None or client_secret == "":
            await ctx.send(_("Error! osu! ``client id`` and ``client secret`` have not been set. to set them use the "
                             "command ``{prefix}set api osu client_id,[YOUR CLIENT ID] client_secret,[YOUR CLIENT "
                             "SECRET]``.").format(prefix=ctx.prefix))
        if client_secret is None or client_secret == "":
            return None

        return {
            'client_id': int(client_id),
            'client_secret': client_secret
        }

    @commands.group(name="osu")
    async def _osu(self, ctx: commands.Context):
        """osu! related commands"""

        pass

    async def select_user(self, ctx: commands.Context, users: list):
        message = None
        count = len(users)
        index = 0
        previous = discord.emoji.Emoji()
        menu()
        while True:
            user = users[index]
            embed = discord.Embed(title=_("osu! user search"))
            embed.set_author(name=user.username, url=f"https://osu.ppy.sh/users/{user.id}")
            embed.set_footer(text=_("\"Red Discord Bot\" cog developed by NukDokPlex using \"ossapi\" wrapper"))
            embed.set_thumbnail(url=user.avatar_url)
            embed.add_field(
                name=_("Country"),
                value=user.country_code,
                inline=True
            )
            embed.add_field(
                name=_("Identifier"),
                value=str(user.id),
                inline=True
            )

            if message is None:
                message = await ctx.send(embed=embed)

            else:




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
            credentials = await self.get_client_credentials(ctx)

            if credentials is None:
                return

            api = OssapiV2(client_id=credentials['client_id'], client_secret=credentials['client_secret'])

            try:
                users = api.search(query=msg.content).user.data
            except ValueError:
                await ctx.send(
                    _("An error occurred when trying to search for a user with this nickname. Please try again later...")
                )
                return

            if users is None or len(users) < 1:
                await ctx.send(
                    _("No luck finding you... Try a neater nickname or use this command: ``{prefix}osu setid [YOUR "
                      "OSU ID]``").format(prefix=ctx.prefix)
                )
                return

            if len(users) > 0:
                await self.select_user(ctx, users)

            await self.config.user(ctx.author).nickname.set(msg.content)
            await self.config.user(ctx.author).id.set(-1)

            await ctx.send(_("Your name is set as \"{name}\"").format(name=msg.content))

    @_osu.command(name="setid")
    async def _osu_setid(self, ctx: commands.Context, user_id: int):
        """set's the osu! user by id"""

        if user_id < 0:
            user_id = -user_id

        await ctx.send(str(id))

    @_osu.command(name="forgiveme")
    async def _osu_forgiveme(self, ctx: commands.Context):
        """clear's your osu! settings in this bot"""

        await self.config.user(ctx.author).nickname.set("")
        await self.config.user(ctx.author).id.set(-1)

        await ctx.send(_("Your settings have been reset"))


