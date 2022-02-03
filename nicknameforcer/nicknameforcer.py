import discord
from redbot.core import commands, Config, bot as RedBot, errors, i18n
from redbot.core.i18n import Translator, cog_i18n
from .log import log

_ = Translator("NicknameForcer", __file__)


@cog_i18n(_)
class NicknameForcer(commands.Cog):
    """Nickname Forcer related commands."""

    bot: RedBot

    def __init__(self, bot: RedBot, *args, **kwargs):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=13371448228)
        default_user = {
            "nickname": ""
        }
        default_guild = {
            "users_to_force": []
        }
        self.config.register_user(**default_user)
        self.config.register_guild(**default_guild)

        super().__init__(*args, **kwargs)

    @commands.group(alias=["nf"])
    async def nickforcer(self, ctx:commands.Context):
        """Nickname Forcer related commands"""

        pass

    @nickforcer.command()
    @commands.admin()
    async def set(self, ctx: commands.Context, user: discord.Member, nick: commands.UserInputOptional[str]):
        """Sets the user to Nickname Forcer"""
        await self.config.user(user).nickname.set(nick)
        current_users = await self.config.guild(ctx.guild).users_to_force()
        if user.id not in current_users:
            current_users.append(user.id)
            await self.config.guild(ctx.guild).users_to_force.set(current_users)
        await ctx.send(_("This user now will be forced with this nickname: **{nickname}**").format(nickname=nick))
        try:
            await user.edit(nick=nick)
        except discord.errors.Forbidden:
            await ctx.send(_("So I've tried to do this, but i have no permission to change nicknames of other users, "
                             "add it to me, please."))

    @nickforcer.command()
    @commands.admin()
    async def unset(self, ctx: commands.context, user: discord.Member):
        """Unsets the user to Nickname Forcer"""
        current_users = await self.config.guild(ctx.guild).users_to_force()
        if user.id not in current_users:
            await ctx.send(_("Nothing to unset..."))
        else:
            current_users.remove(user.id)
            await ctx.send(_("User {mention} has been removed from forcing!").format(mention=user.mention))

    @commands.Cog.listener()
    async def on_member_update(self, beforeMem: discord.Member, afterMem: discord.Member):
        """Updates a member nickname"""
        if beforeMem.nick == afterMem.nick:
            return
        if await self.bot.cog_disabled_in_guild(self, afterMem.guild):
            return
        users_to_force = await self.config.guild(afterMem.guild).users_to_force()
        if afterMem.id not in users_to_force:
            return
        nick = await self.config.user(afterMem).nickname()
        try:
            await afterMem.edit(nick=nick)
        except discord.errors.Forbidden:
            log.exception("Encountered an expected discord.errors.Forbidden setting nickname (maybe no permission) "
                          f" to {afterMem} in {afterMem.guild} ({afterMem.guild.id})")

    def cog_unload(self):
        self.session.detach()
