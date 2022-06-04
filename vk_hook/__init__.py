from .vk_hook import VKHook


def setup(bot):
    bot.add_cog(VKHook(bot))
