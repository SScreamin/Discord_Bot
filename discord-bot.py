import asyncio
from asyncio.subprocess import create_subprocess_exec
from re import S
import discord
from discord.ext import commands
from discord.ext.commands.core import command
from discord.player import FFmpegPCMAudio
import youtube_dl
import logging

from youtube_dl.YoutubeDL import YoutubeDL
from youtube_dl.utils import DownloadError

# Log Discord events
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# Instantiate the bot
bot = commands.Bot(command_prefix='$')

# YTDL options
ytdlopts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': True,
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0'  # ipv6 addresses cause issues sometimes
}

# Container for holding song info
class Song():
    def __init__(self, title, url):
        self.song_title = title
        self.song_url = url

    def get_song_title(self):
        return self.song_title

# Container for holding the Song Queue
class SongQueue():
    def __init__(self):
        self.song_queue = []

    def add_song(self, song):
        self.song_queue.append(song)

    def remove_song(self, index):
        self.song_queue.pop(index)

    def get_queue(self):
        return self.song_queue

    def get_first_song(self):
        return self.song_queue[0]

    def clear_queue(self):
        self.song_queue.clear()

# Container for playing music
class SongPlayer():
    def __init__(self):
        self.song_queue = SongQueue()
        self.volume = 0.1

    def play_song(self, ctx):
        song = self.song_queue.get_first_song().song_url
        ctx.message.guild.voice_client.play(discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(
            song, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn"), 
            volume=self.volume), after=lambda e: self.next_song(ctx))
        
    def pause_song(self, ctx):
        ctx.message.guild.voice_client.pause()

    def resume_song(self, ctx):
        ctx.message.guild.voice_client.resume()

    def next_song(self, ctx):
        self.song_queue.remove_song(0)
        if len(self.song_queue.get_queue()) != 0:
            self.play_song(ctx)

# Instantiate the song player
song_player = SongPlayer()

#############################################
#  COMMANDS and COMMAND RELATED FUNCTIONS   #
#############################################

# Prints this message when the bot is ready
@bot.event
async def on_ready():
    print('{0.user} is ready to go.'.format(bot))

# Simple command to test the bot
@bot.command()
async def test(ctx):
    """Sends a test message."""
    await ctx.send("Test these nutz.")

# Function that joins the bot to a voice channel 
#@bot.command()
async def join_voice(ctx):
    if ctx.author.voice == None:
        ctx.send("Can't join your voice channel when you're not in one doofus.")
    else:
        if ctx.message.guild.voice_client == None:
            await ctx.author.voice.channel.connect()
        else:
            ctx.author.voice.channel == ctx.message.guild.voice_client.channel
            await ctx.send("I'm already in the same channel.")

# Command that makes the bot leave its current voice channel
@bot.command()
async def leave_voice(ctx):
    """Tells bot to leave voice. Clears queue upon leaving."""
    global song_player
    if ctx.message.guild.voice_client:
        await ctx.message.guild.voice_client.disconnect()
        if len(song_player.song_queue.get_queue()) > 1:
            song_player.song_queue.clear_queue()
    else:
        await ctx.send("Can't leave a voice channel I'm not in.")

# Command that pauses music playback
@bot.command()
async def pause(ctx):
    """Pause music."""
    global song_player
    if ctx.message.guild.voice_client == None:
        await ctx.send("I'm not in voice. How can I pause?")
    else:
        if ctx.message.guild.voice_client.is_playing() == False:
            await ctx.send("I'm not playing anything. What am I pausing?")
        else:
            song_player.pause_song(ctx)
            await ctx.send("Paused: `{}`".format(song_player.song_queue.get_first_song().get_song_title()))

# Command that resumes music playback
@bot.command()
async def resume(ctx):
    """Resume playing music."""
    global song_player
    if ctx.message.guild.voice_client == None:
        await ctx.send("I'm not in voice. How can I resume?")
    else:
        if ctx.message.guild.voice_client.is_paused() == True:
            song_player.resume_song(ctx)
            await ctx.send("Resumed: `{}`".format(song_player.song_queue.get_first_song().get_song_title()))
        else:
            await ctx.send("How can I resume if I'm not paused?")

# Command that skips the currently playing song
@bot.command()
async def skip(ctx):
    """Skip current song."""
    global song_player
    if len(song_player.song_queue.get_queue()) == 0:
        await ctx.send("Queue is currently empty.")
    elif len(song_player.song_queue.get_queue()) == 1:
        await ctx.send("Last song in queue is currently playing.")
    else:
        ctx.message.guild.voice_client.pause()
        song_player.next_song(ctx)
        await ctx.send("Skipped: `{}`".format(song_player.song_queue.get_first_song().get_song_title()))

# Command that returns the current song queue
@bot.command()
async def view_queue(ctx):
    """View current music queue."""
    global song_player
    await ctx.send("Current song queue:")
    if len(song_player.song_queue.get_queue()) == 0:
        await ctx.send("No songs in queue.")
    else:
        for song in song_player.song_queue.get_queue():
            await ctx.send("`{}`".format(song.song_title))

# Command that returns the current song title
@bot.command()
async def current_song(ctx):
    """View current song."""
    global song_player
    if len(song_player.song_queue.get_queue()) == 0:
        await ctx.send("No songs in queue.")
    else:
        await ctx.send("Currently playing: `{}`".format(song_player.song_queue.get_first_song().get_song_title()))

# Command that clears the current song queue
@bot.command()
async def clear_queue(ctx):
    """Clear music queue. Stops playback of current song."""
    global song_player
    ctx.message.guild.voice_client.stop()
    if len(song_player.song_queue.get_queue()) > 1:
        song_player.song_queue.clear_queue()
        await ctx.send("Song queue has been cleared.")
    else:
        await ctx.send("Song queue has been cleared.")

# Function for extracting the song info with YTDL
def extract_song_info(song_link):
    with YoutubeDL(ytdlopts) as ydl:
        song_info = ydl.extract_info(song_link, download=False)
    return song_info

# Function for creating a song object from the extracted song info
def create_song(song_info):
    song = Song(song_info["title"], song_info["formats"][0]["url"])
    return song

# Function to add a song to the queue
def add_song_to_queue(song):
    global song_player
    song_player.song_queue.add_song(song)

# Command to play a song
# This probably needs to be rewritten
@bot.command()
async def play(ctx, arg):
    """'$play [url]' Plays requested YouTube link."""
    global song_player
    if ctx.author.voice == None:
        await ctx.send("Need to join a voice channel to request music.")
    else:
        try:
            if ctx.message.guild.voice_client != None:
                if ctx.message.guild.voice_client.is_playing() == True:
                    if ctx.message.guild.voice_client.channel == ctx.author.voice.channel:
                        song_info = extract_song_info(arg)
                        song = create_song(song_info)
                        add_song_to_queue(song)
                        await ctx.send("Queued: `{}`".format(song.get_song_title()))
                    else:
                        await ctx.send("Bot is currently in a different voice channel. " + 
                        "Tell it to leave it's current voice channel with '$leave_voice' before having it join yours. " +
                        "This process will clear its current queue.")
                elif ctx.message.guild.voice_client.is_paused() == True:
                        song_info = extract_song_info(arg)
                        song = create_song(song_info)
                        add_song_to_queue(song)
                        await ctx.send("Queued: `{}`".format(song.get_song_title()))
                else:
                    if ctx.message.guild.voice_client.channel == ctx.author.voice.channel:
                        song_info = extract_song_info(arg)
                        song = create_song(song_info)
                        add_song_to_queue(song)
                        await ctx.send("Queued: `{}`".format(song.get_song_title()))
                        song_player.play_song(ctx)
                    else:
                        await ctx.send("Bot is currently in a different voice channel. " + 
                        "Tell it to leave it's current voice channel with '$leave_voice' before having it join yours. " +
                        "This process will clear its current queue.")
            else:
                song_info = extract_song_info(arg)
                song = create_song(song_info)
                add_song_to_queue(song)
                await ctx.send("Queued: `{}`".format(song.get_song_title()))
                await join_voice(ctx)
                song_player.play_song(ctx)
        except DownloadError:
            await ctx.send("Your play request was not valid. Make sure it's a valid YouTube link and nothing is wrong with the video.")

# Run the bot using this key
bot.run('Insert your key here.')