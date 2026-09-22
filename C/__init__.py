from .c import C


async def setup(bot):
    await bot.add_cog(C(bot))