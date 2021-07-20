from redbot.core import commands, bot as RedBot

from .log import log


class LicenseInfoRemover(commands.Cog):
    """LicenseInfo command remover"""

    __author__ = ["NukDokPlex"]
    __version__ = "1.0"

    def __init__(self, bot: RedBot, *args, **kwargs):
        self.bot = bot

        super().__init__(*args, **kwargs)

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    def cog_unload(self):
        global _li
        if _li:
            self.bot.add_command(_li)


async def setup(bot: RedBot):
    lir = LicenseInfoRemover(bot)
    global _li
    _li = bot.get_command("licenseinfo")
    if _li:
        bot.remove_command(_li.name)
    bot.add_cog(lir)
    log.info("The \"licenseinfo\" command was successfully removed! You are a very bad person...")
