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

class SourceError(Exception):
    pass

class Source:

    def __init__(self, ctx: commands.Context, *, data: dict, source_type: str):

        self.requester = ctx.author
        self.channel = ctx.channel
        self.bot = ctx.bot
        self.data = data
        self.type = source_type

    @classmethod
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None, source_type: str):
        loop = loop or asyncio.get_event_loop()

        if source_type == "GDrive":
            info = await gdrive.GDriveSource.create_source(search=search, loop=loop)
        elif source_type == "YouTube":
            info = await ytdl.YTDLSource.create_source(search=search, loop=loop)

        return cls(ctx, data=DataClass(**info), source_type=source_type)

    async def ready_download(self):
        if self.type == "GDrive":
            self.data = await gdrive.GDriveSource.ready_download(self.data)
        elif self.type == "YouTube":
            self.data = await ytdl.YTDLSource.ready_download(self.data)
        self.data.duration = self.parse_duration(self.data.duration)

    @classmethod
    async def get_playlist_info(cls, search: str, *, loop: asyncio.BaseEventLoop = None, source_type: str):
        loop = loop or asyncio.get_event_loop()

        if source_type == "GDrive":
            info = await gdrive.GDriveSource.get_playlist_info(search=search, loop=loop)
        elif source_type == "YouTube":
            info = await ytdl.YTDLSource.get_playlist_info(search=search, loop=loop)

        info = DataClass(**info)
        return info

    @classmethod
    async def get_playlist(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None, source_type: str):
        loop = loop or asyncio.get_event_loop()

        if source_type == "GDrive":
            sources = await gdrive.GDriveSource.get_playlist(search=search, loop=loop)
        elif source_type == "YouTube":
            sources = await ytdl.YTDLSource.get_playlist(search=search, loop=loop)

        for url in sources:
            source = await cls.create_source(ctx, url, loop=loop, source_type=source_type)
            if source:
                yield source

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
