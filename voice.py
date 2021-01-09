import asyncio
import itertools
import random

import discord
from async_timeout import timeout
from discord.ext import commands

import SourceDL
from main import load_file, INFO

colors = {
  'DEFAULT': 0x000000,
  'WHITE': 0xFFFFFF,
  'AQUA': 0x1ABC9C,
  'GREEN': 0x2ECC71,
  'BLUE': 0x3498DB,
  'PURPLE': 0x9B59B6,
  'LUMINOUS_VIVID_PINK': 0xE91E63,
  'GOLD': 0xF1C40F,
  'ORANGE': 0xE67E22,
  'RED': 0xE74C3C,
  'GREY': 0x95A5A6,
  'NAVY': 0x34495E,
  'DARK_AQUA': 0x11806A,
  'DARK_GREEN': 0x1F8B4C,
  'DARK_BLUE': 0x206694,
  'DARK_PURPLE': 0x71368A,
  'DARK_VIVID_PINK': 0xAD1457,
  'DARK_GOLD': 0xC27C0E,
  'DARK_ORANGE': 0xA84300,
  'DARK_RED': 0x992D22,
  'DARK_GREY': 0x979C9F,
  'DARKER_GREY': 0x7F8C8D,
  'LIGHT_GREY': 0xBCC0C0,
  'DARK_NAVY': 0x2C3E50,
  'BLURPLE': 0x7289DA,
  'GREYPLE': 0x99AAB5,
  'DARK_BUT_NOT_BLACK': 0x2C2F33,
  'NOT_QUITE_BLACK': 0x23272A
}

class VoiceError(Exception):
    pass

class Song:
    __slots__ = ('source', 'requester')

    def __init__(self, source):
        self.source = source
        self.requester = source.requester

    def create_embed(self):
        thumbnail_file = None
        color_list = [c for c in colors.values()]
        embed = (
            discord.Embed(
                title='Now playing',
                description=f'```css\n{self.source.data.title}\n```',
                color=random.choice(color_list)
            )
            .add_field(name='Duration', value=self.source.data.duration)
            .add_field(name='Requested by', value=self.requester.mention)
        )
        if self.source.data.artist != "Unknown":
            embed.add_field(name='Artist', value=self.source.data.artist)
        else:
            embed.add_field(name='Uploader', value=self.source.data.uploader)
        embed.add_field(name='URL', value=f'[Click]({self.source.data.webpage_url})')
        embed.set_author(name=self.requester.name, icon_url=self.requester.avatar_url)

        if self.source.data.thumbnail:
            embed.set_thumbnail(url=self.source.data.thumbnail)
        else:
            thumbnail_file = discord.File("image_cache\\" + str(self.source.data.title) + ".jpg", filename="image.jpg")
            embed.set_thumbnail(url="attachment://image.jpg")
        return embed, thumbnail_file

class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return iter(self._queue)

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]


class VoiceState:
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx

        self.current = None
        self.voice = None
        self.next = asyncio.Event()
        self.songs = SongQueue()
        self.song_history = []
        self.autoplaylist = []
        self.exists = True
        self.previous_message = None

        self._loop = False
        self._autoplay = True
        self._volume = 0.5
        self.skip_votes = set()

        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value

    @property
    def autoplay(self):
        return self._autoplay

    @autoplay.setter
    def autoplay(self, value: bool):
        self._autoplay = value

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    @property
    def is_playing(self):
        return self.voice and self.current

    async def audio_player_task(self):
        while True:
            self.next.clear()
            self.now = None

            if self.previous_message:
                await self.previous_message.delete()
                self.previous_message = None

            if self._loop:
                if self.current:
                    await self.songs.put(self.current)

            try:
                async with timeout(5):
                    self.current = await self.songs.get()
            except asyncio.TimeoutError:
                self.current = None
                if self._autoplay:
                    if not self.voice:
                        self.bot.loop.create_task(self.stop())
                        self.exists = False
                        return
                    INFO("Fetching autoplay List")
                    if not self.autoplaylist:
                        self.autoplaylist = list(load_file("autoplaylist.txt"))
                    while self.autoplaylist:
                        random_link = random.choice(self.autoplaylist)
                        INFO(f"Trying {random_link} from autoplaylist")
                        self.autoplaylist.remove(random_link)
                        song_url, source_type, playlist = SourceDL.get_type(random_link)
                        source_init = SourceDL.Source(self._ctx, source_type=source_type, loop=self.bot.loop)
                        if playlist:
                            playlist_info = await source_init.get_playlist_info(song_url)
                            INFO(f"Adding {playlist_info.song_num} songs from {random_link}")
                            try:
                                sources = await source_init.get_playlist(song_url)
                            except SourceDL.SourceError:
                                continue
                            else:
                                if source_type == "GDrive":
                                    for num, each_source in enumerate(sources):
                                        sources[num] = f"https://drive.google.com/file/d/{each_source}/view"
                            self.autoplaylist = sources
                            continue
                        else:
                            try:
                                source = await source_init.create_source(song_url)
                            except SourceDL.SourceError:
                                pass
                            else:
                                song = Song(source)
                                await self._ctx.voice_state.songs.put(song)
                        self.current = await self.songs.get()
                        if self.current:
                            break
                        continue
                    if not self.current:
                        self.bot.loop.create_task(self.stop())
                        self.exists = False
                        return
                else:
                    self.bot.loop.create_task(self.stop())
                    self.exists = False
                    return
            for each_song in self.song_history:
                if self.current.source.data.title == each_song.source.data.title:
                    self.song_history.remove(each_song)
            self.song_history.insert(0, self.current)
            self.current.source.volume = self._volume
            await self.current.source.ready_download()
            with open(f"audio_cache\\{self.current.source.data.expected_filename}", 'rb') as f:
                source = discord.FFmpegPCMAudio(f, pipe=True)
            self.voice.play(source, after=self.play_next_song)
            #await self.current.source.bot.change_presence(activity=discord.Game(f"{self.current.source.title}"))
            embed, thumbnail = self.current.create_embed()
            if thumbnail:
                self.previous_message = await self.current.source.channel.send(embed=embed, file=thumbnail)
            else:
                self.previous_message = await self.current.source.channel.send(embed=embed)
            await self.next.wait()

    def play_next_song(self, error=None):
        if error:
            if str(error) == "str, bytes or bytearray expected, not NoneType":
                vcs = self._ctx.guild.voice_channels
                for vc in vcs:
                    if self.bot in vc.members:
                        self.voice = vc.connect()
                        break
            if not self.voice:
                raise VoiceError(str(error))

        self.next.set()

    def skip(self):
        self.skip_votes.clear()

        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None
