import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
import discord
from discord.ext import commands

from tidalcord.tidalcord_exceptions import TidalLoginError
from tidalcord.tidalcord import TidalCord
from tidalcord.tidalsession import TidalSession
from tidalcord.urlhandler import UrlHandler
from tidalcord.lru_cache import LRUCache


async def main():
    # Load environment variables
    load_dotenv()

    # Retrieve and validate Discord token
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("Missing DISCORD_TOKEN in environment variables.")

    # Retrieve and validate Tidal session path
    tidal_session_path = os.getenv("TIDAL_SESSION_PATH")
    if not tidal_session_path:
        raise ValueError("Missing TIDAL_SESSION_PATH in environment variables.")

    tidal_session_path = Path(tidal_session_path)

    # Ensure the directory exists
    tidal_session_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize Tidal session
    tidal_session = TidalSession(tidal_session_path)
    if not tidal_session.logged_in:
        raise TidalLoginError("Failed to log in to Tidal.")

    # Initialize URL handler and cache
    urlhandler = UrlHandler(tidal_session)
    cache = LRUCache("music_cache", max_size=5 * 1024**3)

    # Configure bot intents
    intents = discord.Intents.default()
    intents.message_content = True

    # Create bot instance
    bot = commands.Bot(command_prefix="!", intents=intents)

    # Add TidalCord cog
    await bot.add_cog(TidalCord(bot, tidal_session, urlhandler, cache))

    # Start the bot
    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
