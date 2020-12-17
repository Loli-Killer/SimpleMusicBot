import os
import asyncio
import functools

import youtube_dl
from pathvalidate import sanitize_filename

from main import INFO

youtube_dl.utils.bug_reports_message = lambda: ''
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

class YTDLError(Exception):
    pass

class YTDLSource:

    def __init__(self, loop: asyncio.BaseEventLoop = None):

        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
        }

        self.ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)
        self.loop = loop

    async def create_source(self, search: str):

        partial = functools.partial(self.ytdl.extract_info, search, download=False, process=False)
        try:
            data = await self.loop.run_in_executor(None, partial)
        except:
            return

        if data is None:
            raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        if 'entries' not in data:
            process_info = data
        else:
            process_info = None
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        webpage_url = process_info['webpage_url']
        partial = functools.partial(self.ytdl.extract_info, webpage_url, download=False)
        processed_info = await self.loop.run_in_executor(None, partial)

        if processed_info is None:
            raise YTDLError('Couldn\'t fetch `{}`'.format(webpage_url))

        if 'entries' not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info['entries'].pop(0)
                except IndexError:
                    raise YTDLError('Couldn\'t retrieve any matches for `{}`'.format(webpage_url))

        sorted_info = await self.sort_info(info, webpage_url)
        return sorted_info

    @staticmethod
    async def sort_info(data: dict, search: str):
        name = sanitize_filename(data['title'])
        expected_filename = name + ".mp3"

        thumbnail = data['thumbnail']
        duration = int(data['duration'])

        info = {
            "search" : search,
            "artist" : "Unknown",
            "uploader" : data['uploader'],
            "title" : name,
            "webpage_url" : data['webpage_url'],
            "duration" : duration,
            "thumbnail" : thumbnail,
            "expected_filename" : expected_filename
        }

        return info

    async def ready_download(self, data: dict):

        INFO(f"Started downloading {data.title} from {data.search}")
        if not os.path.isfile(f"audio_cache\\{data.expected_filename}"):
            download_info = YTDL_OPTIONS.copy()
            download_info['outtmpl'] = f"audio_cache\\{data.expected_filename}"
            with youtube_dl.YoutubeDL(download_info) as ydl:
                ydl.extract_info(data.search)
        INFO(f"Downloaded {data.title}")

        return data

    async def get_playlist(self, search: str):

        partial = functools.partial(self.ytdl.extract_info, search, download=False, process=False)
        data = await self.loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        sources = []
        for entry in data['entries']:
            sources.append(entry['url'])

        return sources

    async def get_playlist_info(self, search: str):

        partial = functools.partial(self.ytdl.extract_info, search, download=False, process=False)
        data = await self.loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        video_entries = list(data['entries'])
        info = {
            "title" : data['name'],
            "song_num" : len(video_entries)
        }

        return info

"""
    @classmethod
    async def search_source(cls, bot: commands.Bot, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        channel = ctx.channel
        loop = loop or asyncio.get_event_loop()

        cls.search_query = '%s%s:%s' % ('ytsearch', 10, ''.join(search))

        partial = functools.partial(cls.ytdl.extract_info, cls.search_query, download=False, process=False)
        info = await loop.run_in_executor(None, partial)

        cls.search = {}
        cls.search["title"] = f'Search results for:\n**{search}**'
        cls.search["type"] = 'rich'
        cls.search["color"] = 7506394
        cls.search["author"] = {'name': f'{ctx.author.name}', 'url': f'{ctx.author.avatar_url}', 'icon_url': f'{ctx.author.avatar_url}'}

        lst = []

        for e in info['entries']:
            #lst.append(f'`{info["entries"].index(e) + 1}.` {e.get("title")} **[{YTDLSource.parse_duration(int(e.get("duration")))}]**\n')
            VId = e.get('id')
            VUrl = 'https://www.youtube.com/watch?v=%s' % (VId)
            lst.append(f'`{info["entries"].index(e) + 1}.` [{e.get("title")}]({VUrl})\n')

        lst.append('\n**Type a number to make a choice, Type `cancel` to exit**')
        cls.search["description"] = "\n".join(lst)

        em = discord.Embed.from_dict(cls.search)
        await ctx.send(embed=em, delete_after=45.0)

        def check(msg):
            return msg.content.isdigit() == True and msg.channel == channel or msg.content == 'cancel' or msg.content == 'Cancel'

        try:
            m = await bot.wait_for('message', check=check, timeout=45.0)

        except asyncio.TimeoutError:
            rtrn = 'timeout'

        else:
            if m.content.isdigit() == True:
                sel = int(m.content)
                if 0 < sel <= 10:
                    for key, value in info.items():
                        if key == 'entries':
                            "data = value[sel - 1]"
                            VId = value[sel - 1]['id']
                            VUrl = 'https://www.youtube.com/watch?v=%s' % (VId)
                            partial = functools.partial(cls.ytdl.extract_info, VUrl, download=False)
                            data = await loop.run_in_executor(None, partial)
                    rtrn = cls(ctx, discord.FFmpegPCMAudio(data['url'], **cls.FFMPEG_OPTIONS), data=data)
                else:
                    rtrn = 'sel_invalid'
            elif m.content == 'cancel':
                rtrn = 'cancel'
            else:
                rtrn = 'sel_invalid'
        
        return rtrn

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

            value = ':'.join(duration)

        elif duration == 0:
            value = "LIVE"

        return value

"""
