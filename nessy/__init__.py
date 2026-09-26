from .nessy import Nessy


async def setup(bot):
    """Load all cogs in this package."""
    await bot.add_cog(Nessy(bot))