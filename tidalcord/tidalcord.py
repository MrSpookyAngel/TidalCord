import asyncio
import random
import requests
import signal
import logging

from discord.ext import commands, tasks
import discord

from tidalcord.lru_cache import LRUCache
from tidalcord.tidalsession import TidalSession
from tidalcord.urlhandler import UrlHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TidalCord")


class TidalCord(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        session: TidalSession,
        urlhandler: UrlHandler,
        cache: LRUCache,
    ):
        self.bot = bot
        self.session = session
        self.urlhandler = urlhandler
        self.cache = cache

        self.current_track = None
        self.is_paused = False
        self.lock = asyncio.Lock()
        self.music_queue = []
        self.voice_client = None
        self.current_volume = 0.5

        signal.signal(signal.SIGINT, self.signal_handler)
        self.pre_download_tracks_task.start()

        logger.info("TidalCord initialized")

    def signal_handler(self, sig, frame):
        logger.info("Received SIGINT. Shutting down...")
        asyncio.create_task(self.bot.close())

    async def join_voice_channel(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("You must be in a voice channel.")
            return False
        channel = ctx.author.voice.channel
        if not self.voice_client or not self.voice_client.is_connected():
            self.voice_client = await channel.connect()
            self.auto_disconnect_empty_channel_task.start()
        elif self.voice_client.channel != channel:
            await self.voice_client.move_to(channel)
        return True

    async def play_next(self):
        if not self.music_queue:
            self.current_track = None
            asyncio.create_task(self.start_auto_disconnect_no_track_task())
            return
        self.auto_disconnect_no_track_task.cancel()
        track = self.music_queue.pop(0)
        await self.play_track(track)

    async def play_track(self, track: dict):
        file_path = self.download_track(track)
        if not file_path:
            logger.error("Failed to download track.")
            self.current_track = None
            return
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(str(file_path)), volume=self.current_volume
        )
        self.voice_client.play(
            source,
            after=lambda e: asyncio.run_coroutine_threadsafe(
                self.play_next(), self.bot.loop
            ),
        )
        self.current_track = track

    def download_track(self, track: dict):
        cache_key = track["id"]
        file_path = self.cache.get(cache_key)

        if not file_path:
            logger.info(f"Downloading track: {self.get_formatted_track(track)}")
            try:
                url = track["url"]
                response = requests.get(url, stream=True)
                if response.status_code == 200:
                    file_path = self.cache.cache_dir / cache_key
                    self.cache.add(cache_key, response.iter_content(chunk_size=8192))
                else:
                    logger.error(f"Failed to download track: {response.status_code}")
                    return
            except requests.RequestException as e:
                logger.error(f"Error while downloading track: {e}")
                return

        return file_path

    @tasks.loop(seconds=2)
    async def pre_download_tracks_task(self):
        if not self.music_queue or self.current_track is None:
            return
        async with self.lock:
            for track in self.music_queue:
                if not self.download_track(track):
                    logger.error(f"Pre-downloading track: {track['title']}")

    @tasks.loop(seconds=10)
    async def auto_disconnect_empty_channel_task(self):
        if self.voice_client and len(self.voice_client.channel.members) <= 1:
            await self.voice_client.disconnect()
            self.voice_client = None
            logger.info("Disconnected due to an empty channel.")
            self.auto_disconnect_empty_channel_task.stop()
            self.auto_disconnect_no_track_task.cancel()

    @tasks.loop(seconds=300)
    async def auto_disconnect_no_track_task(self):
        if self.voice_client and self.current_track is None:
            await self.voice_client.disconnect()
            self.voice_client = None
            logger.info("Disconnected due to no track being played.")
            self.auto_disconnect_empty_channel_task.stop()
            self.auto_disconnect_no_track_task.stop()

    async def start_auto_disconnect_no_track_task(self):
        await asyncio.sleep(300)
        self.auto_disconnect_no_track_task.start()

    @staticmethod
    def get_formatted_track(track: dict) -> str:
        hours, remainder = divmod(track["duration"], 3600)
        minutes, seconds = divmod(remainder, 60)
        duration = (
            f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            if hours
            else f"{minutes:02d}:{seconds:02d}"
        )
        featured = (
            ""
            if not track["featured_artists"]
            else " ft. " + ", ".join(track["featured_artists"])
        )
        need_featured = (
            featured
            and "feat. " not in track["title"].lower()
            and "ft. " not in track["title"].lower()
        )
        return f"{track['artist']} - {track['title']}{featured if need_featured else ''} ({duration})"

    # Commands
    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str = None):
        if not await self.join_voice_channel(ctx):
            return

        if query is None:
            await self.resume(ctx)
            return

        try:
            track = self.urlhandler(query)
            if track is None:
                raise ValueError("No track was found.")
        except ValueError:
            tracks = self.session.search_tracks(query.lower(), limit=1)
            if not tracks:
                await ctx.send("No tracks found.")
                return
            track = tracks[0]

        self.music_queue.append(track)
        await ctx.send(
            f"{ctx.author.name} added **{self.get_formatted_track(track)}** to the queue."
        )

        if self.current_track is None:
            await self.play_next()

    @commands.command(name="search")
    async def search(self, ctx: commands.Context, *, query: str):
        if not await self.join_voice_channel(ctx):
            return

        num_emojis = [f"{i}\N{COMBINING ENCLOSING KEYCAP}" for i in range(10)]
        cancel_emoji = "\N{CROSS MARK}"

        tracks = self.session.search_tracks(query.lower(), limit=10)
        if not tracks:
            await ctx.send("No tracks found")
            return

        message = f"{ctx.author.name}'s search results for '{query}':\n" + "\n".join(
            f"{i}\. **{self.get_formatted_track(track)}**"
            for i, track in enumerate(tracks)
        )
        results_message = await ctx.send(message)

        emoji_map = {num_emojis[i]: track for i, track in enumerate(tracks)}
        for emoji in emoji_map:
            await results_message.add_reaction(emoji)
        await results_message.add_reaction(cancel_emoji)

        def check(reaction, user):
            return (
                user == ctx.author
                and reaction.message.id == results_message.id
                and (reaction.emoji in emoji_map or reaction.emoji == cancel_emoji)
            )

        try:
            reaction, _ = await self.bot.wait_for(
                "reaction_add", timeout=30.0, check=check
            )
            if reaction.emoji == cancel_emoji:
                await ctx.send("Search canceled. No track was added.")
                return

            selected_track = emoji_map[reaction.emoji]
            self.music_queue.append(selected_track)
            await ctx.send(
                f"{ctx.author.name} added **{self.get_formatted_track(selected_track)}** to the queue."
            )

            if self.current_track is None:
                await self.play_next()
        except asyncio.TimeoutError:
            await ctx.send("Search canceled. You took too long to choose a track!")

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            await ctx.send(f"{ctx.author.name} paused the track.")

    @commands.command(name="current", aliases=["now", "nowplaying", "playing"])
    async def current(self, ctx: commands.Context):
        message = (
            f"Current track: {self.get_formatted_track(self.current_track)}"
            if self.current_track
            else "No track currently playing."
        )
        await ctx.send(message)

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context):
        message = (
            "Queue:\n"
            + "\n".join(
                f"{i}\. **{self.get_formatted_track(track)}**"
                for i, track in enumerate(self.music_queue[:10], start=1)
            )
            if self.music_queue
            else "No tracks in the queue."
        )
        await ctx.send(message)

    @commands.command(name="resume")
    async def resume(self, ctx: commands.Context):
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            await ctx.send(f"{ctx.author.name} resumed the current track.")

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx: commands.Context):
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
            await ctx.send(f"{ctx.author.name} skipped the current track.")

    @commands.command(name="remove", aliases=["r", "delete", "d"])
    async def remove(self, ctx: commands.Context, *, index: int = 1):
        if not self.music_queue:
            await ctx.send("No tracks in the queue.")
            return
        index -= 1
        if index < 0 and index > len(self.music_queue):
            await ctx.send(
                f"Index number must be 1 ≤ [number] ≤ {len(self.music_queue)+1}."
            )
            return
        track = self.music_queue.pop(index)
        await ctx.send(
            f"{ctx.author.name} removed {self.get_formatted_track(track)} from the queue."
        )

    @commands.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context):
        if len(self.music_queue) < 2:
            await ctx.send("At least 2 tracks required in the queue to shuffle.")
            return
        random.shuffle(self.music_queue)
        await ctx.send(f"{ctx.author.name} shuffled the queue.")

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        await ctx.send(f"Pong! Latency: {self.bot.latency * 1000:.2f}ms.")

    @commands.command(name="volume")
    @commands.has_guild_permissions(manage_guild=True)
    async def volume(self, ctx: commands.Context, *, level: int = None):
        if level is None:
            await ctx.send(f"Current volume is {int(self.current_volume*100)}%.")
            return
        if level < 1 or level > 100:
            await ctx.send("Volume number must be 1 ≤ [number] ≤ 100.")
            return
        self.current_volume = level / 100.0
        if self.voice_client and self.voice_client.source:
            self.voice_client.source.volume = self.current_volume
        await ctx.send(f"Volume set to {level}%.")

    @commands.command(name="disconnect", aliases=["leave"])
    @commands.has_guild_permissions(manage_guild=True)
    async def disconnect(self, ctx: commands.Context):
        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None
            await ctx.send("Disconnected from voice channel.")

    @commands.command(name="shutdown")
    @commands.has_guild_permissions(manage_guild=True)
    async def shutdown(self, ctx: commands.Context):
        await ctx.send("Shutting down...")
        await self.bot.close()
