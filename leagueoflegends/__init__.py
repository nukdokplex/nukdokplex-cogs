from .leagueoflegends import LeagueOfLegends


def setup(bot):
    bot.add_cog(LeagueOfLegends(bot))
