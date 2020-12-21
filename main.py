import json

import discord
from discord.ext import commands
from loguru import logger

import music

with open('config.json') as f:
    config = json.load(f)

INFO = logger.info
DEBUG = logger.debug
bot = commands.Bot(command_prefix=config["prefix"], description="Music Bot")

@bot.event
async def on_ready():
    activity = discord.Game(name='with Nep')
    await bot.change_presence(activity=activity)
    print(f'Logged in as {bot.user.name}')
    bot.add_cog(music.Music(bot))

def main():
    bot.run(config['token'])

def load_file(filename, skip_commented_lines=True, comment_char='#'):
    try:
        with open(filename, encoding='utf8') as f:
            results = []
            for line in f:
                line = line.strip()

                if line and not (skip_commented_lines and line.startswith(comment_char)):
                    results.append(line)

            return results

    except IOError as e:
        print("Error loading", filename, e)
        return []

if __name__ == "__main__":
    main()
