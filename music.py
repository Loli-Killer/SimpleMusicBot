import math
import random

import discord
from discord.ext import commands

import SourceDL
import voice
from main import INFO, config

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, ctx: commands.Context):
        """Returns or creates voice.VoiceState for the guild defined in the passed ctx"""
        state = self.voice_states.get(ctx.guild.id)
        if not state or not state.exists:
            state = voice.VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    def cog_unload(self):
        """Unloads the music cog"""
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    def cog_check(self, ctx: commands.Context):
        """Prevent calling commands in DM's"""
        if not ctx.guild:
            raise commands.NoPrivateMessage('This command can\'t be used in DM channels.')

        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        #Set voice state for every command
        ctx.voice_state = self.get_voice_state(ctx)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        await ctx.send('An error occurred: {}'.format(str(error)))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != self.bot.user.id and message.content.startswith(tuple(config["prefix"])):
            INFO(f"{message.guild}/{message.channel}/{message.author.name}>{message.content}")
            #if message.embeds:
            #    print(message.embeds[0].to_dict())

    @commands.command(name='join', invoke_without_subcommand=True)
    async def _join(self, ctx: commands.Context):
        """Joins a voice channel."""

        destination = ctx.author.voice.channel

        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name='summon')
    async def _summon(self, ctx: commands.Context, *, channel: discord.VoiceChannel = None):
        """Summons the bot to a voice channel.
        If no channel was specified, it joins your channel.
        """

        await ctx.message.delete(delay=5)
        if not channel and not ctx.author.voice:
            raise voice.VoiceError('You are neither connected to a voice channel nor specified a channel to join.', delete_after=5)

        destination = channel or ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name='leave', aliases=['disconnect'])
    @commands.has_permissions(manage_guild=True)
    async def _leave(self, ctx: commands.Context):
        """Clears the queue and leaves the voice channel."""

        await ctx.message.delete(delay=5)
        if not ctx.voice_state.voice:
            return await ctx.send('Not connected to any voice channel.', delete_after=5)

        await ctx.voice_state.stop()
        del self.voice_states[ctx.guild.id]

    @commands.command(name='volume')
    @commands.is_owner()
    async def _volume(self, ctx: commands.Context, *, volume: int):
        """Sets the volume of the player."""

        await ctx.message.delete(delay=5)
        if not ctx.voice_state.is_playing:
            return await ctx.send('Nothing being played at the moment.', delete_after=5)

        if 0 > volume > 100:
            return await ctx.send('Volume must be between 0 and 100', delete_after=5)

        ctx.voice_state.volume = volume / 100
        await ctx.send('Volume of the player set to {}%'.format(volume))

    @commands.command(name='now', aliases=['current', 'playing', 'np', 'nowplaying'])
    async def _now(self, ctx: commands.Context):
        """Displays the currently playing song."""
        embed, thumbnail = ctx.voice_state.current.create_embed()
        await ctx.send(embed=embed, file=thumbnail, delete_after=10)
        await ctx.message.delete(delay=5)

    @commands.command(name='pause', aliases=['pa'])
    @commands.has_permissions(manage_guild=True)
    async def _pause(self, ctx: commands.Context):
        """Pauses the currently playing song."""
        await ctx.message.delete(delay=5)
        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='resume', aliases=['re', 'res'])
    @commands.has_permissions(manage_guild=True)
    async def _resume(self, ctx: commands.Context):
        """Resumes a currently paused song."""

        await ctx.message.delete(delay=5)
        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='stop')
    @commands.has_permissions(manage_guild=True)
    async def _stop(self, ctx: commands.Context):
        """Stops playing song and clears the queue."""

        ctx.voice_state.songs.clear()
        await ctx.message.delete(delay=5)

        if ctx.voice_state.is_playing:
            ctx.voice_state.voice.stop()
            await ctx.message.add_reaction('⏹')

    @commands.command(name='skip', aliases=['s'])
    async def _skip(self, ctx: commands.Context):
        """Vote to skip a song. The requester can automatically skip.
        3 skip votes are needed for the song to be skipped.
        """

        await ctx.message.delete(delay=20)
        if not ctx.voice_state.is_playing:
            return await ctx.send('Not playing any music right now...', delete_after=5)

        await ctx.message.add_reaction('⏭')
        ctx.voice_state.skip()

    @commands.command(name='queue', aliases=['q'])
    async def _queue(self, ctx: commands.Context, *, page: int = 1):
        """Shows the player's queue.
        You can optionally specify the page to show. Each page contains 10 elements.
        """

        await ctx.message.delete(delay=5)
        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Empty queue.', delete_after=5)

        items_per_page = 10
        pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(ctx.voice_state.songs[start:end], start=start):
            queue += f'`{i+1}.` [**{song.source.data.title}**]({song.source.data.webpage_url})\n'

        embed = (
            discord.Embed(
                description='**{} tracks:**\n\n{}'.format(len(ctx.voice_state.songs), queue)
            )
            .set_footer(text='Viewing page {}/{}'.format(page, pages))
        )
        await ctx.send(embed=embed, delete_after=5)

    @commands.command(name='history')
    async def _history(self, ctx: commands.Context, *, page: int = 1):
        """Shows the player's history.
        You can optionally specify the page to show. Each page contains 10 elements.
        """

        await ctx.message.delete(delay=5)
        if len(ctx.voice_state.song_history) == 0:
            return await ctx.send('Empty history.', delete_after=5)

        items_per_page = 10
        pages = math.ceil(len(ctx.voice_state.song_history) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(ctx.voice_state.song_history[start:end], start=start):
            queue += f'`{i+1}.` [**{song.source.data.title}**]({song.source.data.webpage_url})\n'

        embed = (
            discord.Embed(
                description='**{} tracks:**\n\n{}'.format(len(ctx.voice_state.song_history), queue)
            )
            .set_footer(text='Viewing page {}/{}'.format(page, pages))
        )
        await ctx.send(embed=embed, delete_after=5)

    @commands.command(name='shuffle')
    async def _shuffle(self, ctx: commands.Context):
        """Shuffles the queue."""

        await ctx.message.delete(delay=5)
        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Empty queue.', delete_after=5)

        ctx.voice_state.songs.shuffle()

    @commands.command(name='remove')
    async def _remove(self, ctx: commands.Context, index: int):
        """Removes a song from the queue at a given index."""

        await ctx.message.delete(delay=5)
        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Empty queue.', delete_after=5)

        ctx.voice_state.songs.remove(index - 1)

    @commands.command(name='loop')
    async def _loop(self, ctx: commands.Context):
        """Loops the currently playing song.
        Invoke this command again to unloop the song.
        """

        await ctx.message.delete(delay=5)
        if not ctx.voice_state.is_playing:
            return await ctx.send('Nothing being played at the moment.', delete_after=5)

        # Inverse boolean value to loop and unloop.
        ctx.voice_state.loop = not ctx.voice_state.loop
        await ctx.send('Looping a song is now turned ' + ('on' if ctx.voice_state.loop else 'off'), delete_after=5)

    @commands.command(name='clean')
    async def _clean(self, ctx: commands.Context, *, search_range: int = 50):
        """Cleans bot commands and bot messages
        """

        await ctx.message.delete(delay=5)
        try:
            float(search_range)  # lazy check
            search_range = min(int(search_range), 1000)
        except:
            return

        def is_possible_command_invoke(entry):
            valid_call = any(
                entry.content.startswith(prefix) for prefix in config["prefix"])  # can be expanded
            return valid_call and not entry.content[1:2].isspace()

        delete_invokes = True
        delete_all = ctx.channel.permissions_for(ctx.author).manage_messages

        def check(message):
            if is_possible_command_invoke(message) and delete_invokes:
                return delete_all or message.author == ctx.author
            return message.author == self.bot.user

        if ctx.channel.permissions_for(ctx.guild.me).manage_messages:
            deleted = await ctx.channel.purge(check=check, limit=search_range, before=ctx.message)

        await ctx.send('Cleaned up {0} message{1}.'.format(len(deleted), 's' * bool(deleted)), delete_after=15)

    @commands.command(name='play', aliases=['p'])
    async def _play(self, ctx: commands.Context, *, search: str):
        """Plays a song.
        If there are songs in the queue, this will be queued until the
        other songs finished playing.
        This command automatically searches from various sites if no URL is provided.
        A list of these sites can be found here: https://rg3.github.io/youtube-dl/supportedsites.html
        """

        async with ctx.typing():
            song_url, source_type, playlist = SourceDL.get_type(search)
            source_init = SourceDL.Source(ctx, source_type=source_type, loop=self.bot.loop)

            if playlist:
                playlist_info = await source_init.get_playlist_info(song_url)
                playlist_message = await ctx.send(f'Queuing {playlist_info.title}')
                try:
                    sources = await source_init.get_playlist(song_url)
                except SourceDL.SourceError as e:
                    await ctx.send('An error occurred while processing this request: {}'.format(str(e)))
                    return
            else:
                sources = [song_url]

            for source_num, each_source in enumerate(sources):
                try:
                    source = await source_init.create_source(each_source)
                except SourceDL.SourceError as e:
                    await ctx.send('An error occurred while processing this request: {}'.format(str(e)))
                    continue
                else:
                    if not ctx.voice_state.voice:
                        await ctx.invoke(self._join)

                    song = voice.Song(source)
                    await ctx.voice_state.songs.put(song)
                    sources[source_num] = source

            color_list = [c for c in voice.colors.values()]
            if playlist:
                embed = (
                    discord.Embed(
                        description=f'Enqueued {playlist_info.song_num} songs from {playlist_info.title} by {ctx.author.name}',
                        color=random.choice(color_list)
                    )
                )
                playlist_message.delete()
            else:
                embed = (
                    discord.Embed(
                        description=f'Enqueued {sources[0].data.title} by {ctx.author.name}',
                        color=random.choice(color_list)
                    )
                )

            await ctx.send(embed=embed, delete_after=10)
            await ctx.message.delete(delay=10)

    @_join.before_invoke
    @_play.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('You are not connected to any voice channel.')

        #if ctx.voice_client:
            #if ctx.voice_client.channel != ctx.author.voice.channel:
                #raise commands.CommandError('Bot is already in a voice channel.')
