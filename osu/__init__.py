from .osu import osu


def setup(bot):
    bot.add_cog(osu(bot))
