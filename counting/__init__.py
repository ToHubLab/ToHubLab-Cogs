from .core import ToHubLabCounting

async def setup(bot):
    await bot.add_cog(ToHubLabCounting(bot))
