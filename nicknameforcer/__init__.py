from .nicknameforcer import NicknameForcer


def setup(bot):
    bot.add_cog(NicknameForcer(bot))
