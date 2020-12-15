import asyncio
import os
import json
import time
from io import BytesIO

from discord.ext import commands
from pathvalidate import sanitize_filename
from aiogoogle import Aiogoogle
from PIL import Image
from mutagen.mp3 import MP3

from main import logger

class GDriveError(Exception):
    pass

class GDriveSource:

    with open("credentials.json") as f:
        client_creds = json.load(f)

    with open("token.json") as f:
        user_creds = json.load(f)

    refreshtoken = user_creds['refresh_token']

    refreshed = False
    refreshed_time = None
    process = None

    @classmethod
    async def create_source(cls, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()
        await cls.refresh_token()

        async with Aiogoogle(user_creds=cls.user_creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover('drive', 'v3')
            data = await aiogoogle.as_user(
                drive_v3.files.get(
                    fileId=search,
                    fields='id,name,owners(displayName),createdTime,webViewLink',
                    supportsAllDrives=True
                )
            )

        sorted_info = await cls.sort_info(data, search)
        return sorted_info

    @staticmethod
    async def sort_info(data: dict, search: str):

        expected_filename = sanitize_filename(data['name'])
        name = expected_filename.rsplit(".", 1)[0]

        info = {
            "search" : search,
            "artist" : "Unknown",
            "uploader" : "Unknown",
            "title" : name,
            "webpage_url" : data['webViewLink'],
            "duration" : 0,
            "thumbnail" : None,
            "expected_filename" : expected_filename
        }

        return info

    @classmethod
    async def ready_download(cls, data: dict):

        logger.info(f"Started downloading {data.search}")
        await cls.refresh_token()
        logger.info(data.expected_filename)
        if not os.path.isfile(f"audio_cache\\{data.expected_filename}"):
            async with Aiogoogle(user_creds=cls.user_creds) as aiogoogle:
                drive_v3 = await aiogoogle.discover('drive', 'v3')
                try:
                    await aiogoogle.as_user(
                        drive_v3.files.get(fileId=data.search, download_file=f"audio_cache\\{data.expected_filename}", alt="media")
                    )
                except Exception as e:
                    if str(e) == "Line is too long":
                        pass
                    else:
                        logger.info(e)
                        pass
        logger.info(f"Downloaded {data.search}")

        tags = MP3(f"audio_cache\\{data.expected_filename}")
        if not os.path.isfile(f"image_cache\\{data.title}.jpg"):
            try:
                pic = tags.get("APIC:") or tags.get('APIC:"Album cover"')
                im = Image.open(BytesIO(pic.data))
                im.save(f"image_cache\\{data.title}.jpg")
            except:
                pass

        try:
            data.artist = tags.get('TPE1').text[0]
        except:
            pass

        data.duration = int(tags.info.length)

        return data

    @classmethod
    async def get_playlist(cls, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()
        await cls.refresh_token()

        async with Aiogoogle(user_creds=cls.user_creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover('drive', 'v3')
            data = await aiogoogle.as_user(
                drive_v3.files.list(
                    q=f"mimeType contains 'audio' and '{search}' in parents",
                    fields='files(name,id),nextPageToken',
                    orderBy='folder,name,createdTime',
                    pageSize=1000,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                )
            )

        if data is None:
            raise GDriveError('Couldn\'t find anything that matches `{}`'.format(search))

        sources = []
        for entry in data['files']:
            sources.append(entry['id'])

        return sources

    @classmethod
    async def get_playlist_info(cls, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()
        await cls.refresh_token()

        async with Aiogoogle(user_creds=cls.user_creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover('drive', 'v3')
            folder_data = await aiogoogle.as_user(
                drive_v3.files.get(
                    fileId=search,
                    fields='id,name,owners(displayName),createdTime,webViewLink',
                    supportsAllDrives=True
                )
            )

        async with Aiogoogle(user_creds=cls.user_creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover('drive', 'v3')
            file_data = await aiogoogle.as_user(
                drive_v3.files.list(
                    q=f"mimeType contains 'audio' and '{search}' in parents",
                    fields='files(name,id),nextPageToken',
                    orderBy='folder,name,createdTime',
                    pageSize=1000,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                )
            )

        if file_data is None:
            raise GDriveError('Couldn\'t find anything that matches `{}`'.format(search))

        data = {
            "title" : folder_data['name'],
            "song_num" : len(file_data['files'])
        }

        return data

    @classmethod
    async def refresh_token(cls):
        if cls.refreshed:
            time_passed = int(cls.refreshed_time - time.time())
            if time_passed < 3000:
                return

        async with Aiogoogle(user_creds=cls.user_creds, client_creds=cls.client_creds) as aiogoogle:
            creds = await aiogoogle.oauth2.refresh(cls.user_creds, cls.client_creds)
        creds['refresh_token'] = cls.refreshtoken
        cls.user_creds = creds
        cls.refreshed_time = time.time()
        cls.refreshed = True
        with open("token.json", 'w') as f:
            json.dump(creds, f)
