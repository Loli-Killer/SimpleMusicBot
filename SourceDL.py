import asyncio
import re

from discord.ext import commands

import ytdl
import gdrive

def get_type(search: str):

    if re.match(r"https:\/\/drive\.google\.com\/(drive\/folders\/|open\?id=|drive\/u\/\d\/folders\/)([\da-zA-Z-_]+)", search):
        search = re.match(r"https:\/\/drive\.google\.com\/(drive\/folders\/|open\?id=|drive\/u\/\d\/folders\/)([\da-zA-Z-_]+)", search).group(2)
        playlist = True
        source_type = "GDrive"
    elif re.match(r"https:\/\/drive\.google\.com\/(file\/d\/)([\da-zA-Z-_]+)", search):
        search = re.match(r"https:\/\/drive\.google\.com\/(file\/d\/)([\da-zA-Z-_]+)", search).group(2)
        playlist = False
        source_type = "GDrive"
    else:
        source_type = "YouTube"
        playlistRegex = r'watch\?v=.+&(list=[^&]+)'
        matches = re.search(playlistRegex, search)
        groups = matches.groups() if matches is not None else []
        search = "https://www.youtube.com/playlist?" + groups[0] if len(groups) > 0 else search
        if "www.youtube.com/playlist" in search:
            playlist = True
        else:
            playlist = False

    return search, source_type, playlist

class DataClass:

    def __init__(self, **info):
        self.__dict__.update(info)

class MusicInfo:
    def __init__(
        self,
        ctx: commands.Context,
        source_type: str,
        data: dict,
        gdrive: gdrive.GDriveSource,
        youtube: ytdl.YTDLSource
    ):

        self.requester = ctx.author
        self.channel = ctx.channel
        self.bot = ctx.bot
        self.source_type = source_type
        self.data = data
        self.gdrive = gdrive
        self.youtube = youtube

    async def ready_download(self):

        if self.source_type == "GDrive":
            self.data = await self.gdrive.ready_download(self.data)
        elif self.source_type == "YouTube":
            self.data = await self.youtube.ready_download(self.data)

        self.data.duration = self.parse_duration(self.data.duration)

    @staticmethod
    def parse_duration(duration: int):
        if duration > 0:
            minutes, seconds = divmod(duration, 60)
            hours, minutes = divmod(minutes, 60)
            days, hours = divmod(hours, 24)

            duration = []
            if days > 0:
                duration.append('{}'.format(days).zfill(2))
            if hours > 0:
                duration.append('{}'.format(hours).zfill(2))
            if minutes > 0:
                duration.append('{}'.format(minutes).zfill(2))
            if seconds > 0:
                duration.append('{}'.format(seconds).zfill(2))

            if len(duration) == 1:
                duration.append("00")
            value = ':'.join(duration)

        elif duration == 0:
            value = "LIVE"

        return value

class SourceError(Exception):
    pass

class Source:

    def __init__(self, ctx: commands.Context, source_type: str, loop: asyncio.BaseEventLoop = None):

        self.ctx = ctx
        self.loop = loop or asyncio.get_event_loop()
        self.source_type = source_type
        self.gdrive = gdrive.GDriveSource()
        self.youtube = ytdl.YTDLSource(self.loop)

    async def create_source(self, search: str):

        if self.source_type == "GDrive":
            info = await self.gdrive.create_source(search=search)
        elif self.source_type == "YouTube":
            info = await self.youtube.create_source(search=search)

        data = DataClass(**info)

        return MusicInfo(self.ctx, self.source_type, data, self.gdrive, self.youtube)

    async def get_playlist_info(self, search: str):

        if self.source_type == "GDrive":
            info = await self.gdrive.get_playlist_info(search=search)
        elif self.source_type == "YouTube":
            info = await self.youtube.get_playlist_info(search=search)

        info = DataClass(**info)
        return info

    async def get_playlist(self, search: str):

        if self.source_type == "GDrive":
            sources = await self.gdrive.get_playlist(search=search)
        elif self.source_type == "YouTube":
            sources = await self.youtube.get_playlist(search=search)

        return sources
