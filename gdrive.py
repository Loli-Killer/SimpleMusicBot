import os
import json
import time
from io import BytesIO

from pathvalidate import sanitize_filename
from aiogoogle import Aiogoogle
from PIL import Image
from mutagen.mp3 import MP3

from main import INFO

class GDriveError(Exception):
    pass

class GDriveSource:

    def __init__(self):
        with open("credentials.json") as f:
            self.client_creds = json.load(f)

        with open("token.json") as f:
            self.user_creds = json.load(f)

        self.refreshtoken = self.user_creds['refresh_token']

        self.refreshed = False
        self.refreshed_time = None
        self.process = None

    async def create_source(self, search: str):
        await self.refresh_token()

        async with Aiogoogle(user_creds=self.user_creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover('drive', 'v3')
            data = await aiogoogle.as_user(
                drive_v3.files.get(
                    fileId=search,
                    fields='id,name,owners(displayName),createdTime,webViewLink',
                    supportsAllDrives=True
                )
            )

        sorted_info = await self.sort_info(data, search)
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

    async def ready_download(self, data: dict):

        INFO(f"Started downloading {data.title} from {data.search}")
        await self.refresh_token()
        while not os.path.isfile(f"audio_cache\\{data.expected_filename}"):
            async with Aiogoogle(user_creds=self.user_creds) as aiogoogle:
                drive_v3 = await aiogoogle.discover('drive', 'v3')
                try:
                    await aiogoogle.as_user(
                        drive_v3.files.get(fileId=data.search, download_file=f"audio_cache\\{data.expected_filename}", alt="media")
                    )
                except Exception as e:
                    if str(e) == "Line is too long":
                        pass
                    else:
                        INFO(e)
        INFO(f"Downloaded {data.title}")

        try:
            tags = MP3(f"audio_cache\\{data.expected_filename}")
        except:
            return data
        if not os.path.isfile(f"image_cache\\{data.title}.jpg"):
            try:
                pic_key = [key for key in list(tags.keys()) if "APIC" in key][0]
                pic = tags.get(pic_key)
                im = Image.open(BytesIO(pic.data))
                im.save(f"image_cache\\{data.title}.jpg")
            except:
                data.thumbnail = "https://webrandum.net/mskz/wp-content/uploads/pz-linkcard/cache/7232681e168b08a699569b8291bbeaa3c0435198368ccf2b11fa8cca02e5e115"

        try:
            data.artist = tags.get('TPE1').text[0]
        except:
            pass

        data.duration = int(tags.info.length)

        return data

    async def get_playlist(self, search: str):
        await self.refresh_token()

        async with Aiogoogle(user_creds=self.user_creds) as aiogoogle:
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

    async def get_playlist_info(self, search: str):
        await self.refresh_token()

        async with Aiogoogle(user_creds=self.user_creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover('drive', 'v3')
            folder_data = await aiogoogle.as_user(
                drive_v3.files.get(
                    fileId=search,
                    fields='id,name,owners(displayName),createdTime,webViewLink',
                    supportsAllDrives=True
                )
            )

        async with Aiogoogle(user_creds=self.user_creds) as aiogoogle:
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

    async def refresh_token(self):
        if self.refreshed:
            time_passed = int(self.refreshed_time - time.time())
            if time_passed < 2000:
                return

        async with Aiogoogle(user_creds=self.user_creds, client_creds=self.client_creds) as aiogoogle:
            creds = await aiogoogle.oauth2.refresh(self.user_creds, self.client_creds)
        creds['refresh_token'] = self.refreshtoken
        self.user_creds = creds
        self.refreshed_time = time.time()
        self.refreshed = True
        with open("token.json", 'w') as f:
            json.dump(creds, f)
