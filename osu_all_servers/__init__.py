from .osu_all_servers import osuAllServers


def setup(bot):
    bot.add_cog(VKHook(bot))
