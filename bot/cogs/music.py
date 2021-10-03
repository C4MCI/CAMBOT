import datetime as dt
import re
import typing as t
import spotipy
import os
import sys
import time

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path)

from spotipy.oauth2 import SpotifyClientCredentials
import random
from enum import Enum
import requests
from bs4 import BeautifulSoup
from lyricsgenius import Genius


from randomsong import *
from googleapiclient.discovery import build
from decouple import config
from dotenv import load_dotenv
import asyncio
import discord
import wavelink2 as wavelink
from discord.ext import commands

URL_REGEX = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
OPTIONS = {
    "1️⃣": 0,
    "2⃣": 1,
    "3⃣": 2,
    "4⃣": 3,
    "5⃣": 4,
    "❌": 5,
}
QUEUE_OPS = ["⏬", "🔽", "🔼", "⏫"]

load_dotenv()
SPOTIPY_CLIENT_ID = config('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = config('SPOTIPY_CLIENT_SECRET')
YOUTUBE_API_KEY = config("YOUTUBE_API_KEY")


class AlreadyConnectedToChannel(commands.CommandError):
    pass


class NoVoiceChannel(commands.CommandError):
    pass


class QueueIsEmpty(commands.CommandError):
    pass


class NoTracksFound(commands.CommandError):
    pass


class PlayerIsAlreadyPaused(commands.CommandError):
    pass


class PlayerIsAlreadyPlaying(commands.CommandError):
    pass


class NoMoreTracks(commands.CommandError):
    pass


class NoPreviousTracks(commands.CommandError):
    pass


class InvalidRepeatValue(commands.CommandError):
    pass


class NoBackwardsQueue(commands.CommandError):
    pass


class RepeatMode(Enum):
    NONE = 0
    ONE = 1
    ALL = 2


class Autoplay(Enum):
    OFF = 0
    ON = 1
    KARMA = 2


def getSpotifyTracks(playlistURL):
    spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials())

    results = spotify.user_playlist_tracks(user="", playlist_id=playlistURL)

    trackList = [];
    for i in results["items"]:
        trackList.append(f'ytsearch:{i["track"]["artists"][0]["name"] + " - " + i["track"]["name"]}')

    return trackList;


def getSpotifyTracks_track(trackURL):
    spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials())

    results = spotify.track(track_id=trackURL)

    trackList = [];

    trackList.append(results["artists"][0]["name"] + '' + "-" + '' + results['name'])

    return trackList;


def get_related_video_title(videoID):
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    request = youtube.search().list(
        part="snippet",
        type="video",
        relatedToVideoId=videoID,
        maxResults=10
    )
    response = request.execute()
    while True:
        try:
            title = response["items"][random.choice(range(10))]["snippet"]["title"]
            break
        except KeyError:
            continue

    return title


class Queue:
    def __init__(self):
        self._queue = []
        self.position = 0
        self.number = 1
        self.repeat_mode = RepeatMode.NONE
        self.autoplay = Autoplay.OFF

    @property
    def is_empty(self):
        return not self._queue

    @property
    def first_track(self):
        if not self._queue:
            raise QueueIsEmpty

        return self._queue[0]

    @property
    def current_track(self):
        if not self._queue:
            raise QueueIsEmpty

        if self.position <= len(self._queue) - 1:
            return self._queue[self.position]

    @property
    def upcoming(self):
        if not self._queue:
            raise QueueIsEmpty

        return self._queue[self.position + 1:]

    @property
    def history(self):
        if not self._queue:
            raise QueueIsEmpty

        return self._queue[:self.position]

    @property
    def lenght(self):
        return len(self._queue)

    def add(self, *args):
        self._queue.extend(args)

    def add_next(self, *args):
        self._queue.insert((self.position + self.number), args[0])
        self.number += 1

    def get_next_track(self):
        if not self._queue:
            raise QueueIsEmpty

        self.position += 1

        if self.position < 0:
            return None

        elif self.position > len(self._queue) - 1:
            if self.repeat_mode == RepeatMode.ALL:
                self.position = 0
            else:

                return None
        self.number = 1
        return self._queue[self.position]

    def shuffle(self):
        if not self._queue:
            raise QueueIsEmpty

        upcoming = self.upcoming
        random.shuffle(upcoming)
        self._queue = self._queue[:self.position + 1]
        self._queue.extend(upcoming)

    def set_repeat_mode(self, mode):
        if mode == "none":
            self.repeat_mode = RepeatMode.NONE
        elif mode == "1":
            self.repeat_mode = RepeatMode.ONE
        elif mode == "all":
            self.repeat_mode = RepeatMode.ALL

    def set_autoplay_mode(self, mode):
        if mode == "on":
            self.autoplay = Autoplay.ON
        elif mode == "off":
            self.autoplay = Autoplay.OFF
        elif mode == "karma":
            self.autoplay = Autoplay.KARMA

    def get_queue(self):  # Do NOT use if not needed
        return self._queue

    def clear(self):
        self._queue.clear()

    def jump(self, pst):
        if not self._queue:
            raise QueueIsEmpty
        self.position = pst - 1

    def get_number(self):
        return self.number

    def reset_position(self):
        self.position = 0


class Player(wavelink.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = Queue()
        self.q_msg_list = []

    async def connect(self, ctx, channel=None):
        self.ctx_glob2 = ctx
        if self.is_connected:
            raise AlreadyConnectedToChannel

        if (channel := getattr(ctx.author.voice, "channel", channel)) is None:
            raise NoVoiceChannel

        await super().connect(channel.id)
        return channel

    async def teardown(self):
        try:
            await self.sent_message.delete()
            for i in self.q_msg_list:
                await i.delete()
            self.q_msg_list.clear()
        except (discord.errors.NotFound, AttributeError):
            pass
        try:
            await self.destroy()
            await self.ctx_glob2.send(":raised_hand:", delete_after=5)
        except (KeyError, AttributeError):
            pass

    async def add_spot_tracks_track(self, ctx, tracks):
        self.ctx_glob2 = ctx
        if not tracks:
            return NoTracksFound
        else:
            self.queue.add(tracks[0])
        await self.start_playback()
        if self.is_playing and self.queue.lenght > 1:
            embed = discord.Embed(color=ctx.author.color)
            embed.description = f"Sıraya eklenen şarkı: [{tracks[0].title}]({tracks[0].uri}) [{ctx.author.mention}]"
            q_msg = await ctx.send(embed=embed)
            self.q_msg_list.append(q_msg)


    async def add_spot_tracks(self, ctx, tracks):
        self.ctx_glob2 = ctx
        if not tracks:
            return NoTracksFound
        else:
            self.queue.add(tracks[0])
        if self.queue.autoplay == Autoplay.OFF:
            await self.start_playback()

    async def add_spot_tracks_track_next(self, ctx, tracks):
        sayı = 0
        if sayı > 10:
            self.ctx_glob2 = ctx
        if not tracks:
            return NoTracksFound
        else:
            self.queue.add_next(tracks[0])
        if self.is_playing and self.queue.lenght >= 1:
            embed = discord.Embed(color=ctx.author.color)
            embed.description = f"Sıraya eklenen şarkı: [{tracks[0].title}]({tracks[0].uri}) [{ctx.author.mention}]"
            q_msg = await ctx.send(embed=embed)
            self.q_msg_list.append(q_msg)
        sayı += 1

    async def add_spot_tracks_next(self, ctx, tracks):
        sayı = 0
        if sayı > 10:
            self.ctx_glob2 = ctx
        if not tracks:
            return NoTracksFound
        else:
            self.queue.add_next(tracks[0])
        await self.start_playback()
        sayı += 1

    async def add_tracks(self, ctx, tracks):
        self.ctx_glob2 = ctx
        if not tracks:
            return NoTracksFound

        if isinstance(tracks, wavelink.TrackPlaylist):
            self.queue.add(*tracks.tracks)
            sayı = 0
            for i in tracks.tracks:
                sayı += 1
            if sayı > 1:
                embed = discord.Embed(colour=ctx.author.color)
                embed.description = f"**{sayı}** şarkı sıraya eklendi."
                await ctx.send(embed=embed)
        elif len(tracks) == 1:
            self.queue.add(tracks[0])
            if self.queue.lenght > 1 and self.is_playing:
                embed = discord.Embed(color=ctx.author.color)
                embed.description = f"Sıraya eklenen şarkı: [{tracks[0].title}]({tracks[0].uri}) [{ctx.author.mention}]"
                q_msg = await ctx.send(embed=embed)
                self.q_msg_list.append(q_msg)
        else:
            if (track := await self.choose_track(ctx, tracks)) is not None:
                self.queue.add(track)
                if self.queue.lenght > 1 and self.is_playing:
                    embed = discord.Embed(color=ctx.author.color)
                    embed.description = f"Sıraya eklenen şarkı: [{track.title}]({track.uri}) [{ctx.author.mention}]"
                    q_msg = await ctx.send(embed=embed)
                    self.q_msg_list.append(q_msg)

        if not self.is_playing and not self.queue.is_empty:
            await self.start_playback()

    async def add_tracks_next(self, ctx, tracks):
        sayı = 0
        self.ctx_glob2 = ctx
        if not tracks:
            return NoTracksFound

        if isinstance(tracks, wavelink.TrackPlaylist):
            sayı = 0
            for i in tracks.tracks:
                self.queue.add_next(i)
                sayı += 1
            if sayı > 1:
                embed = discord.Embed(colour=ctx.author.color)
                embed.description = f"**{sayı}** şarkı sıraya eklendi."
                await ctx.send(embed=embed)
                if sayı > 10:
                    self.ctx_glob2 = ctx
        elif len(tracks) == 1:
            self.queue.add_next(tracks[0])
            embed = discord.Embed(color=ctx.author.color)
            embed.description = f"Sıraya eklenen şarkı: [{tracks[0].title}]({tracks[0].uri}) [{ctx.author.mention}]"
            q_msg = await ctx.send(embed=embed)
            self.q_msg_list.append(q_msg)
        else:
            if (track := await self.choose_track(ctx, tracks)) is not None:
                self.queue.add_next(track)
                if self.queue.lenght > 1:
                    embed = discord.Embed(color=ctx.author.color)
                    embed.description = f"Sıraya eklenen şarkı: [{track.title}]({track.uri}) [{ctx.author.mention}]"
                    q_msg = await ctx.send(embed=embed)
                    self.q_msg_list.append(q_msg)

        if not self.is_playing and not self.queue.is_empty:
            await self.start_playback()
        sayı += 1

    async def choose_track(self, ctx, tracks):

        def _check(r, u):
            return (
                    r.emoji in OPTIONS.keys()
                    and u == ctx.author
                    and r.message.id == msg.id
            )

        embed = discord.Embed(
            title="Bir şarkı seçin",
            description=(
                "\n".join(
                    f"**{i + 1}.** [{t.title}]({t.uri}) ({t.length // 60000}:{str(t.length % 60).zfill(2)})"
                    for i, t in enumerate(tracks[:5])
                )
            ),
            colour=ctx.author.color,
            timestamp=dt.datetime.utcnow()
        )
        embed.set_author(name="Arama Sonuçları")
        embed.set_footer(text=f"{ctx.author.name}", icon_url=ctx.author.avatar_url)

        msg = await ctx.send(embed=embed)
        for emoji in list(OPTIONS.keys())[:min(len(tracks), len(OPTIONS))]:
            await msg.add_reaction(emoji)

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=60.0, check=_check)
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.message.delete()
        else:
            await msg.delete()
            if reaction.emoji == "❌":
                await ctx.message.delete()
                await msg.delete()
            else:
                return tracks[OPTIONS[reaction.emoji]]

    async def start_playback(self):
        if not self.is_playing and self.is_connected:
            await self.play(self.queue.current_track)
            self.playing_embed = discord.Embed(
                title="Şu an çalan şarkı",
                colour=self.ctx_glob2.author.color,
                timestamp=dt.datetime.utcnow()
            )
            self.playing_embed.add_field(name="İsim",
                                         value=f"[{self.queue.current_track.title}]({self.queue.current_track.uri})",
                                         inline=True)
            self.playing_embed.add_field(name="Süre",
                                         value=f"[{self.queue.current_track.length // 60000}:{str(self.queue.current_track.length % 60).zfill(2)}]")
            self.playing_embed.add_field(name="Durum", value="Çalıyor")
            self.playing_embed.set_footer(text=f"{self.ctx_glob2.author.display_name}",
                                          icon_url=self.ctx_glob2.author.avatar_url)
            self.playing_embed.set_thumbnail(url=f"{self.queue.current_track.thumb}")
            self.sent_message = await self.ctx_glob2.send(embed=self.playing_embed)

    async def change_playing_status_off(self):
        self.playing_embed = discord.Embed(
            title="Şu an çalan şarkı",
            colour=self.ctx_glob2.author.color,
            timestamp=dt.datetime.utcnow()
        )
        self.playing_embed.add_field(name="İsim",
                                     value=f"[{self.queue.current_track.title}]({self.queue.current_track.uri})",
                                     inline=True)
        self.playing_embed.add_field(name="Süre",
                                     value=f"[{self.queue.current_track.length // 60000}:{str(self.queue.current_track.length % 60).zfill(2)}]")
        self.playing_embed.add_field(name="Durum", value="Duraklatıldı")
        self.playing_embed.set_footer(text=f"{self.ctx_glob2.author.display_name}",
                                      icon_url=self.ctx_glob2.author.avatar_url)
        self.playing_embed.set_thumbnail(url=f"{self.queue.current_track.thumb}")
        await self.sent_message.edit(embed=self.playing_embed)

    async def change_playing_status_on(self):
        self.playing_embed = discord.Embed(
            title="Şu an çalan şarkı",
            colour=self.ctx_glob2.author.color,
            timestamp=dt.datetime.utcnow()
        )
        self.playing_embed.add_field(name="İsim",
                                     value=f"[{self.queue.current_track.title}]({self.queue.current_track.uri})",
                                     inline=True)
        self.playing_embed.add_field(name="Süre",
                                     value=f"[{self.queue.current_track.length // 60000}:{str(self.queue.current_track.length % 60).zfill(2)}]")
        self.playing_embed.add_field(name="Durum", value="Çalıyor")
        self.playing_embed.set_footer(text=f"{self.ctx_glob2.author.display_name}",
                                      icon_url=self.ctx_glob2.author.avatar_url)
        self.playing_embed.set_thumbnail(url=f"{self.queue.current_track.thumb}")
        await self.sent_message.edit(embed=self.playing_embed)

    async def advance(self):
        self.queue.number = 1
        try:
            await self.sent_message.delete()
            await self.q_msg_list[0].delete()
            self.q_msg_list.pop(0)
        except (discord.errors.NotFound, AttributeError, IndexError):
            pass
        try:
            if (track := self.queue.get_next_track()) is not None:
                await self.start_playback()
        except QueueIsEmpty:
            self.ctx_glob2 = None
            pass

    async def repeat_track(self):
        await self.play(self.queue.current_track)


class Music(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot):
        self.bot = bot
        self.wavelink = wavelink.Client(bot=bot)
        self.bot.loop.create_task(self.start_nodes())

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        for i in range(1):
            if not member.bot and after.channel is None:
                await asyncio.sleep(5)
                if not [m for m in before.channel.members if not m.bot]:
                    if self.get_player(member.guild).is_connected:
                        embed = discord.Embed(
                            description="**Sesli sohbette kimse olmadığı için ÇIKIŞ YAPIYORUM.**",
                            colour=discord.Color.red()
                        )
                        await self.ctx_msc.send(embed=embed, delete_after=5)
                        await self.get_player(member.guild).teardown()
                        break

    @wavelink.WavelinkMixin.listener()
    async def on_node_ready(self, node):
        print(f"Wawelink Node'u {node.identifier} hazır.")

    @wavelink.WavelinkMixin.listener("on_track_end")
    async def on_player_stop(self, node, payload):
        if payload.player.queue.repeat_mode == RepeatMode.ONE:
            await payload.player.repeat_track()
        elif payload.player.queue.position == payload.player.queue.lenght - 1:
            if payload.player.queue.autoplay == Autoplay.ON or payload.player.queue.autoplay == Autoplay.KARMA:
                if self.genre:
                    query = f"ytsearch: {main(genre=self.genre)}"
                    print(main(genre=self.genre))
                    await payload.player.add_spot_tracks(self.ctx_msc, await  self.wavelink.get_tracks(query))
                    await payload.player.advance()
                elif self.genre is None and payload.player.queue.autoplay == Autoplay.ON:
                    query = f"ytsearch: {get_related_video_title(payload.player.queue.current_track.ytid)}"
                    await payload.player.add_spot_tracks(self.ctx_msc, await self.wavelink.get_tracks(query))
                    await payload.player.advance()
                elif payload.player.queue.autoplay == Autoplay.KARMA:
                    query = f"ytsearch: {main()}"
                    await payload.player.add_spot_tracks(self.ctx_msc, await  self.wavelink.get_tracks(query))
                    await payload.player.advance()
            else:
                await payload.player.advance()
        else:
            await payload.player.advance()

    @wavelink.WavelinkMixin.listener("on_track_stuck")
    @wavelink.WavelinkMixin.listener("on_track_exception")
    async def on_player_stuck(self, node, payload):
        embed = discord.Embed(
            description="**Bu video yaş kısıtlamalı olduğu için oynatılamıyor.**",
            colour=discord.Colour.red()
        )
        await self.ctx_msc.send(embed=embed)

    async def cog_check(self, ctx):
        self.ctx_msc = ctx
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send(f"Özel mesaj yoluyla müzik komutu gönderemezsin. [{ctx.author.mention}]")
            return False

        return True

    async def start_nodes(self):
        await self.bot.wait_until_ready()

        nodes = {
            "GENEL": {
                "host": "127.0.0.1",
                "port": 2333,
                "rest_uri": "http://127.0.0.1:2333",
                "password": "youshallnotpass",
                "identifier": "GENEL",
                "region": "europe",
            }
        }

        for node in nodes.values():
            await self.wavelink.initiate_node(**node)

    def get_player(self, obj):
        if isinstance(obj, commands.Context):
            return self.wavelink.get_player(obj.guild.id, cls=Player, context=obj)
        elif isinstance(obj, discord.Guild):
            return self.wavelink.get_player(obj.id, cls=Player)

    @commands.command(name="connect", aliases=["join"])
    async def connect_command(self, ctx, *, channel: t.Optional[discord.VoiceChannel]):
        self.ctx_msc = ctx
        player = self.get_player(ctx)
        channel = await player.connect(ctx, channel)
        await ctx.send(f"'{channel.name}' kanalına bağlandı.")

    @connect_command.error
    async def connect_command_error(self, ctx, exc):
        if isinstance(exc, AlreadyConnectedToChannel):
            embed = discord.Embed(
                description=f"**Mal CAMCI beceremediği için ikinci bir ses kanalına bağlanamıyorum.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(exc, NoVoiceChannel):
            embed = discord.Embed(
                description="**Bu komutu kullanmak için önce bir ses kanalına bağlanmanız gerekiyor.**",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name="disconnect", aliases=["dc", "leave", "l"])
    async def disconnect_command(self, ctx):
        player = self.get_player(ctx)
        await player.teardown()

    @commands.command(name="play", aliases=["p"])
    async def play_command(self, ctx, *, query: t.Optional[str]):
        self.ctx_msc = ctx
        player = self.get_player(ctx)

        if not player.is_connected:
            await player.connect(ctx)

        if query is None:
            if player.is_playing and not player.is_paused:
                raise PlayerIsAlreadyPlaying

            if player.queue.is_empty:
                raise QueueIsEmpty

            await player.set_pause(False)
            await ctx.message.add_reaction("▶")
            await player.change_playing_status_on()

        else:
            query = query.strip("<>")
            if not re.match(URL_REGEX, query):
                query = f"ytsearch:{query}"
                await player.add_tracks(ctx, await self.wavelink.get_tracks(query))
            elif re.match(URL_REGEX, query) and "open.spotify.com/playlist/" in query:
                tracklist = getSpotifyTracks(query)

                embed = discord.Embed(colour=ctx.author.color)
                embed.description = f"**{len(tracklist)}** şarkı sıraya eklendi."
                await ctx.send(embed=embed)

                for i in tracklist:
                    await player.add_spot_tracks(ctx, await self.wavelink.get_tracks_playlist(i))
            elif re.match(URL_REGEX, query) and "open.spotify.com/track/" in query:
                tracklist = getSpotifyTracks_track(query)
                query_list = []
                for i in tracklist:
                    query_list.append(f"ytsearch:{i}")
                for i in query_list:
                    await player.add_spot_tracks_track(ctx, await self.wavelink.get_tracks(i))


            else:
                await player.add_tracks(ctx, await self.wavelink.get_tracks(query))

    @play_command.error
    async def play_command_error(self, ctx, exc):
        if isinstance(exc, AlreadyConnectedToChannel):
            embed = discord.Embed(
                description=f"**Mal CAMCI beceremediği için ikinci bir ses kanalına bağlanamıyorum.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(exc, NoVoiceChannel):
            embed = discord.Embed(
                description="**Bu komutu kullanmak için önce bir ses kanalına bağlanmanız gerekiyor.**",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(exc, QueueIsEmpty):
            embed = discord.Embed(
                description=f"**Oynatma sırasında şarkı olmadığı için oynatmaya başlayamıyorum.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(exc, PlayerIsAlreadyPlaying):
            pass

    @commands.command(name="pause", aliases=["wait"])
    async def pause_command(self, ctx):
        player = self.get_player(ctx)

        if player.is_paused:
            raise PlayerIsAlreadyPaused
        if player.is_playing:
            await player.set_pause(True)
            await ctx.message.add_reaction("⏸️")
            await player.change_playing_status_off()

    @pause_command.error
    async def pause_command_error(self, ctx, exc):
        if isinstance(exc, PlayerIsAlreadyPaused):
            embed = discord.Embed(
                description=f"**Ben bekliyorum sen devam et.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name="resume")
    async def resume_command(self, ctx):
        player = self.get_player(ctx)

        if not player.is_paused and not player.queue.is_empty:
            raise PlayerIsAlreadyPlaying

        if player.queue.is_empty:
            raise QueueIsEmpty

        await player.set_pause(False)
        await ctx.message.add_reaction("▶")
        await player.change_playing_status_on()

    @resume_command.error
    async def resume_command_error(self, ctx, exc):
        if isinstance(exc, PlayerIsAlreadyPlaying):
            pass
        elif isinstance(exc, QueueIsEmpty):
            embed = discord.Embed(
                description=f"**Oynatma sırasında şarkı olmadığı için oynatmaya başlayamıyorum.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name="stop")
    async def stop_command(self, ctx):
        player = self.get_player(ctx)
        player.queue.clear()
        for i in player.q_msg_list:
            await i.delete()
        player.q_msg_list.clear()
        await player.stop()
        await ctx.message.add_reaction("⏹")
        player.queue.reset_position()
        player.queue.set_autoplay_mode("off")

    @commands.command(name="next", aliases=["skip"])
    async def next_command(self, ctx):
        player = self.get_player(ctx)

        if not player.queue.upcoming and player.queue.autoplay == Autoplay.OFF and player.queue.repeat_mode == RepeatMode.NONE:
            raise NoMoreTracks

        await player.stop()
        await ctx.message.add_reaction("⏭️")

    @next_command.error
    async def next_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            embed = discord.Embed(
                description=f"**Sırada şarkı olmadığı için ilerleyemiyorum.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)

        elif isinstance(exc, NoMoreTracks):
            embed = discord.Embed(
                description=f"**Sırada şarkı olmadığı için ilerleyemiyorum.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name="previous", aliases=["back"])
    async def previous_command(self, ctx):
        player = self.get_player(ctx)

        if not player.queue.history:
            raise NoPreviousTracks
        else:
            if player.is_playing:
                player.queue.position -= 2
                await player.stop()
                await ctx.message.add_reaction("⏮️")
            else:
                player.queue.position -= 1
                await player.start_playback()
                await ctx.message.add_reaction("⏮️")

    @previous_command.error
    async def previous_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            embed = discord.Embed(
                description=f"**Oynatma sırasında şarkı olmadığı için oynatmaya başlayamıyorum.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)

        elif isinstance(exc, NoPreviousTracks):
            embed = discord.Embed(
                description=f"**Sırasın daha gerisinde şarkı olmadığı için oynatmaya başlayamıyorum.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name="shuffle")
    async def shuffle_command(self, ctx):
        player = self.get_player(ctx)
        player.queue.shuffle()
        await ctx.message.add_reaction("🔀")

    @shuffle_command.error
    async def shuffle_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            embed = discord.Embed(
                description=f"**Oynatma sırasında şarkı olmadığı için oynatmaya başlayamıyorum.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name="repeat", aliases=["loop"])
    async def repeat_command(self, ctx, mode: t.Optional[str]):

        if mode is None:
            mode = "1"
        elif mode == "off":
            mode = "none"

        if mode not in ("none", "1", "all"):
            raise InvalidRepeatValue

        player = self.get_player(ctx)
        player.queue.set_repeat_mode(mode)
        embed = discord.Embed(
            description=f"**Yeniden oynatma modu {mode}'e ayarlandı**",
            color=ctx.author.color
        )
        await ctx.send(embed=embed)

    @commands.command(name="autoplay", aliases=["ap", "auto"])
    async def autoplay_command(self, ctx, *, genre: t.Optional[str]):
        player = self.get_player(ctx)
        self.genre = genre
        if not player.is_connected:
            await player.connect(ctx)
        if player.is_connected and player.queue.autoplay == Autoplay.OFF and not player.is_playing and genre is not None:
            try:
                query = f"ytsearch: {main(self.genre)}"
            except TimeoutError:
                embed = discord.Embed(
                    description="**Lütfen geçerli bir şarkı türü giriniz. Eğer istediğiniz bir tür yok ise komutu direkt .autoplay olarak kullanabilirsiniz**",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
            await player.add_spot_tracks(ctx, await self.wavelink.get_tracks(query))

        if player.queue.autoplay == Autoplay.ON and genre is not None:
            embed = discord.Embed(
                description=f"**Şarkı türü bir sonraki şarkıda '{genre}' olarak güncellenecek.**",
                color=ctx.author.color
            )
            await ctx.send(embed=embed)

        if player.queue.autoplay == Autoplay.OFF:
            player.queue.set_autoplay_mode("on")
            if not genre:
                embed = discord.Embed(
                    description="**Otomatik oynatma açık.**",
                    color=ctx.author.color
                )
            else:
                embed = discord.Embed(
                    description=f"**Otomatik oynatma açık. Şarkı türü '{genre}' olarak ayarlandı.**",
                    color=ctx.author.color
                )
            await ctx.send(embed=embed)
        elif player.queue.autoplay == Autoplay.ON and not genre:
            player.queue.set_autoplay_mode("off")
            embed = discord.Embed(
                description="**Otomatik oynatma kapalı.**",
                color=ctx.author.color
            )
            await ctx.send(embed=embed)
        elif player.queue.autoplay == Autoplay.KARMA:
            player.queue.set_autoplay_mode("off")
            embed = discord.Embed(
                description="**Otomatik oynatma kapalı.**",
                color=ctx.author.color
            )
            await ctx.send(embed=embed)

        if player.is_connected and player.queue.autoplay == Autoplay.ON and not player.is_playing and genre is None:
            player.queue.set_autoplay_mode("karma")
            query = f"ytsearch: {main()}"
            await player.add_spot_tracks(ctx, await self.wavelink.get_tracks(query))
            await player.start_playback()

    @commands.command(name="queue", aliases=["q"])
    async def queue_command(self, ctx, show: t.Optional[int] = 5):
        player = self.get_player(ctx)

        if player.queue.is_empty:
            raise QueueIsEmpty

        embed = discord.Embed(
            title="Çalma sırası",
            description=f"Sıradaki ilk {show} şarkı gösteriliyor.",
            colour=ctx.author.color,
            timestamp=dt.datetime.utcnow()
        )
        embed.set_footer(text=f"{ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        try:
            embed.add_field(name="Şu an çalan şarkı",
                            value=f"[{player.queue.current_track.title}]({player.queue.current_track.uri}) [{player.queue.current_track.length // 60000}:{str(player.queue.current_track.length % 60).zfill(2)}]",
                            inline=False)
        except AttributeError:
            embed.add_field(name="Şu an çalan şarkı", value="Şu an çalan şarkı yok.", inline=False)
        if upcoming := player.queue.upcoming:
            embed.add_field(
                name="Sıradakiler",
                value="\n".join(
                    f"**{i + 1}.** [{t.title}]({t.uri}) [{t.length // 60000}:{str(t.length % 60).zfill(2)}]" for i, t in
                    enumerate(player.queue.upcoming[:show])),
                inline=False
            )

        msg = await ctx.send(embed=embed)

        def _check(r, u):
            return (
                    r.emoji in QUEUE_OPS
                    and u == ctx.author
                    and r.message.id == msg.id
            )

        for i in QUEUE_OPS:
            await msg.add_reaction(i)
        while True:
            try:
                pending_tasks = [
                    self.bot.wait_for('reaction_add', check=_check),
                    self.bot.wait_for('reaction_remove', check=_check)
                ]
            except asyncio.TimeoutError:
                await msg.delete()
                await ctx.message.delete()
                break

            done_tasks, pending_tasks = await asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done_tasks:
                reaction, user = await task
            else:

                if reaction.emoji == QUEUE_OPS[0]:
                    oldshow = len(player.queue.upcoming) - 5
                    show = len(player.queue.upcoming)
                    newembed = discord.Embed(
                        title="Çalma sırası",
                        description=f"Sıradaki ilk {show} şarkı gösteriliyor.",
                        colour=ctx.author.color,
                        timestamp=dt.datetime.utcnow()
                    )
                    newembed.set_footer(text=f"{ctx.author.display_name}", icon_url=ctx.author.avatar_url)
                    try:
                        newembed.add_field(name="Şu an çalan şarkı",
                                           value=f"[{player.queue.current_track.title}]({player.queue.current_track.uri}) [{player.queue.current_track.length // 60000}:{str(player.queue.current_track.length % 60).zfill(2)}]",
                                           inline=False)
                    except AttributeError:
                        newembed.add_field(name="Şu an çalan şarkı", value="Şu an çalan şarkı yok.", inline=False)
                    if upcoming := player.queue.upcoming:
                        a = list(enumerate(player.queue.upcoming))
                        newembed.add_field(
                            name="Sıradakiler",
                            value="\n".join(
                                f"**{i + 1}.** [{t.title}]({t.uri}) [{t.length // 60000}:{str(t.length % 60).zfill(2)}]"
                                for
                                i, t in a[oldshow:show]
                            ),
                            inline=False
                        )
                    await msg.edit(embed=newembed)

                if reaction.emoji == QUEUE_OPS[1]:
                    if (show + 5) < len(player.queue.get_queue()):
                        oldshow = show
                        show = oldshow + 5
                    else:
                        pass

                    newembed = discord.Embed(
                        title="Çalma sırası",
                        description=f"Sıradaki ilk {show} şarkı gösteriliyor.",
                        colour=ctx.author.color,
                        timestamp=dt.datetime.utcnow()
                    )
                    newembed.set_footer(text=f"{ctx.author.display_name}", icon_url=ctx.author.avatar_url)
                    try:
                        newembed.add_field(name="Şu an çalan şarkı",
                                           value=f"[{player.queue.current_track.title}]({player.queue.current_track.uri}) [{player.queue.current_track.length // 60000}:{str(player.queue.current_track.length % 60).zfill(2)}]",
                                           inline=False)
                    except AttributeError:
                        newembed.add_field(name="Şu an çalan şarkı", value="Şu an çalan şarkı yok.", inline=False)
                    if upcoming := player.queue.upcoming:
                        a = list(enumerate(player.queue.upcoming))
                        newembed.add_field(
                            name="Sıradakiler",
                            value="\n".join(
                                f"**{i + 1}.** [{t.title}]({t.uri}) [{t.length // 60000}:{str(t.length % 60).zfill(2)}]"
                                for
                                i, t in a[oldshow:show]
                            ),
                            inline=False
                        )
                    await msg.edit(embed=newembed)

                if reaction.emoji == QUEUE_OPS[2]:
                    try:
                        if (oldshow - 5) >= 0:
                            oldshow -= 5
                            show -= 5
                        else:
                            pass
                        newembed = discord.Embed(
                            title="Çalma sırası",
                            description=f"Sıradaki ilk {show} şarkı gösteriliyor.",
                            colour=ctx.author.color,
                            timestamp=dt.datetime.utcnow()
                        )
                        newembed.set_footer(text=f"{ctx.author.display_name}", icon_url=ctx.author.avatar_url)
                        try:
                            newembed.add_field(name="Şu an çalan şarkı",
                                               value=f"[{player.queue.current_track.title}]({player.queue.current_track.uri}) [{player.queue.current_track.length // 60000}:{str(player.queue.current_track.length % 60).zfill(2)}]",
                                               inline=False)
                        except AttributeError:
                            newembed.add_field(name="Şu an çalan şarkı", value="Şu an çalan şarkı yok.", inline=False)
                        if upcoming := player.queue.upcoming:
                            a = list(enumerate(player.queue.upcoming))
                            newembed.add_field(
                                name="Sıradakiler",
                                value="\n".join(
                                    f"**{i + 1}.** [{t.title}]({t.uri}) [{t.length // 60000}:{str(t.length % 60).zfill(2)}]"
                                    for
                                    i, t in a[oldshow:show]
                                ),
                                inline=False
                            )
                        await msg.edit(embed=newembed)
                    except:
                        if show < 0:
                            raise NoBackwardsQueue

                if reaction.emoji == QUEUE_OPS[3]:
                    oldshow = 0
                    show = 5
                    newembed = discord.Embed(
                        title="Çalma sırası",
                        description=f"Sıradaki ilk {show} şarkı gösteriliyor.",
                        colour=ctx.author.color,
                        timestamp=dt.datetime.utcnow()
                    )
                    newembed.set_footer(text=f"{ctx.author.display_name}", icon_url=ctx.author.avatar_url)
                    try:
                        newembed.add_field(name="Şu an çalan şarkı",
                                           value=f"[{player.queue.current_track.title}]({player.queue.current_track.uri}) [{player.queue.current_track.length // 60000}:{str(player.queue.current_track.length % 60).zfill(2)}]",
                                           inline=False)
                    except AttributeError:
                        newembed.add_field(name="Şu an çalan şarkı", value="Şu an çalan şarkı yok.", inline=False)
                    if upcoming := player.queue.upcoming:
                        a = list(enumerate(player.queue.upcoming))
                        newembed.add_field(
                            name="Sıradakiler",
                            value="\n".join(
                                f"**{i + 1}.** [{t.title}]({t.uri}) [{t.length // 60000}:{str(t.length % 60).zfill(2)}]"
                                for
                                i, t in a[oldshow:show]
                            ),
                            inline=False
                        )
                    await msg.edit(embed=newembed)

    @queue_command.error
    async def queue_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            embed = discord.Embed(
                description=f"**Şu anda sırada bir şarkı yok.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)
        if isinstance(exc, NoMoreTracks):
            pass

    @commands.command(name="jump", aliases=["skipto"])
    async def jump_command(self, ctx, q_num: int):
        player = self.get_player(ctx)

        if not player.queue.upcoming:
            raise NoMoreTracks

        if (q_num - 1) < len(player.queue.upcoming):
            position = player.queue.get_queue().index(player.queue.upcoming[q_num - 1])
            player.queue.jump(position)
            await player.stop()
        else:
            raise NoMoreTracks

    @jump_command.error
    async def jump_command_error(self, ctx, exc):
        if isinstance(exc, NoMoreTracks):
            embed = discord.Embed(
                description=f"**Lütfen geçerli bir değer giriniz.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name="playnext", aliases=["pn"])
    async def playnext_command(self, ctx, *, query: t.Optional[str]):
        player = self.get_player(ctx)

        if not player.is_connected:
            await player.connect(ctx)

        if query is None:
            if player.is_playing and not player.is_paused:
                raise PlayerIsAlreadyPlaying

            if player.queue.is_empty:
                raise QueueIsEmpty

            await player.set_pause(False)
            await ctx.message.add_reaction("▶")

        else:
            query = query.strip("<>")
            if not re.match(URL_REGEX, query):
                query = f"ytsearch:{query}"
                await player.add_tracks_next(ctx, await self.wavelink.get_tracks(query))
            elif re.match(URL_REGEX, query) and "open.spotify.com/playlist/" in query:
                tracklist = getSpotifyTracks(query)

                embed = discord.Embed(colour=ctx.author.color)
                embed.description = f"**{len(tracklist)}** şarkı sıraya eklendi."
                await ctx.send(embed=embed)

                for i in tracklist:
                    await player.add_spot_tracks_next(ctx, await self.wavelink.get_tracks_playlist(i))
            elif re.match(URL_REGEX, query) and "open.spotify.com/track/" in query:
                tracklist = getSpotifyTracks_track(query)
                query_list = []
                for i in tracklist:
                    query_list.append(f"ytsearch:{i}")
                for i in query_list:
                    await player.add_spot_tracks_track_next(ctx, await self.wavelink.get_tracks(i))

            else:
                await player.add_tracks_next(ctx, await self.wavelink.get_tracks(query))

    @playnext_command.error
    async def playnext_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            embed = discord.Embed(
                description=f"**Oynatma sırasında şarkı olmadığı için oynatmaya başlayamıyorum.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name="lyrics", help="Çalan şarkının sözlerini gösterir.")
    async def lyrics(self, ctx, *, query: t.Optional[str]):
        player = self.get_player(ctx)
        if query is None:
            try:
                genius = Genius()
                title = player.queue.current_track.title
                excluded_terms = ["( Official Video )", "(Official Video)", " (Remix)", "(Live)", "[Official Video]",
                                  "#"]
                for i in excluded_terms:
                    title = title.replace(i, "")
                title = re.sub("[\(\[].*?[\)\]]", "", title)
                title = title.strip()
                song = genius.search_song(title, get_full_info=False)
                if len(song.lyrics) <= 2048:
                    embed = discord.Embed(
                        title=f"{song.full_title.replace('by', '-')}",
                        color=ctx.author.color,
                        timestamp=dt.datetime.utcnow()
                    )
                    embed.description = song.lyrics
                    embed.set_footer(text=f"{ctx.author.display_name}", icon_url=ctx.author.avatar_url)
                    await ctx.send(embed=embed)
                else:
                    lyrics = song.lyrics.split("\n")
                    half = (len(lyrics) / 2)
                    first_half = ""
                    second_half = ""
                    for i in lyrics[:int(half)]:
                        first_half += f"{i}\n"
                    for j in lyrics[int(half):]:
                        second_half += f"{j}\n"

                    def _check(r, u):
                        return (
                                r.emoji in QUEUE_OPS
                                and u == ctx.author
                                and r.message.id == msg.id
                        )

                    if len(first_half) <= 2048:
                        embed = discord.Embed(
                            title=f"{song.full_title.replace('by', '-')}",
                            colour=ctx.author.color,
                            timestamp=dt.datetime.utcnow(),
                            description=first_half
                        )
                        msg = await ctx.send(embed=embed)

                        for i in QUEUE_OPS[1:3]:
                            await msg.add_reaction(i)
                        while True:
                            try:
                                pending_tasks = [
                                    self.bot.wait_for('reaction_add', check=_check),
                                    self.bot.wait_for('reaction_remove', check=_check)
                                ]
                            except asyncio.TimeoutError:
                                await msg.delete()
                                await ctx.message.delete()
                                break

                            done_tasks, pending_tasks = await asyncio.wait(pending_tasks,
                                                                           return_when=asyncio.FIRST_COMPLETED)
                            for task in done_tasks:
                                reaction, user = await task
                            else:
                                if reaction.emoji == QUEUE_OPS[1]:
                                    newembed = discord.Embed(
                                        title=f"{song.full_title.replace('by', '-')}",
                                        colour=ctx.author.color,
                                        timestamp=dt.datetime.utcnow(),
                                        description=second_half
                                    )
                                    await msg.edit(embed=newembed)
                                if reaction.emoji == QUEUE_OPS[2]:
                                    newembed = discord.Embed(
                                        title=f"{song.full_title.replace('by', '-')}",
                                        colour=ctx.author.color,
                                        timestamp=dt.datetime.utcnow(),
                                        description=first_half
                                    )
                                    await msg.edit(embed=newembed)
                    else:
                        quarter = (len(lyrics) / 4)
                        quarter1 = ""
                        quarter2 = ""
                        quarter3 = ""
                        quarter4 = ""
                        for i in lyrics[:int(quarter)]:
                            quarter1 += f"{i}\n"
                        for i in lyrics[int(quarter):int(half)]:
                            quarter2 += f"{i}\n"
                        for i in lyrics[int(half):int((half + quarter))]:
                            quarter3 += f"{i}\n"
                        for i in lyrics[int((half + quarter)):]:
                            quarter4 += f"{i}\n"

                        order_list = [quarter1, quarter2, quarter3, quarter4]

                        embed = discord.Embed(
                            title=f"{song.full_title.replace('by', '-')}",
                            colour=ctx.author.color,
                            timestamp=dt.datetime.utcnow(),
                            description=quarter1
                        )
                        msg = await ctx.send(embed=embed)

                        for i in QUEUE_OPS[1:3]:
                            await msg.add_reaction(i)
                        order_num = 0
                        while True:
                            try:
                                pending_tasks = [
                                    self.bot.wait_for('reaction_add', check=_check),
                                    self.bot.wait_for('reaction_remove', check=_check)
                                ]
                            except asyncio.TimeoutError:
                                await msg.delete()
                                await ctx.message.delete()
                                break

                            done_tasks, pending_tasks = await asyncio.wait(pending_tasks,
                                                                           return_when=asyncio.FIRST_COMPLETED)
                            for task in done_tasks:
                                reaction, user = await task

                            else:
                                if reaction.emoji == QUEUE_OPS[1]:
                                    if (order_num + 1) <= (len(order_list) - 1):
                                        order_num += 1
                                    newembed = discord.Embed(
                                        title=f"{song.full_title.replace('by', '-')}",
                                        colour=ctx.author.color,
                                        timestamp=dt.datetime.utcnow(),
                                        description=order_list[order_num]
                                    )
                                    await msg.edit(embed=newembed)
                                if reaction.emoji == QUEUE_OPS[2]:
                                    if (order_num - 1) >= 0:
                                        order_num -= 1
                                    newembed = discord.Embed(
                                        title=f"{song.full_title.replace('by', '-')}",
                                        colour=ctx.author.color,
                                        timestamp=dt.datetime.utcnow(),
                                        description=order_list[order_num]
                                    )
                                    await msg.edit(embed=newembed)

            except AttributeError:
                embed = discord.Embed(
                    description="Bu şarkının sözlerini bulamadım. Daha tutarlı bir arama yapmak\n için **'.lyrics şarkı ismi, sanatçı'** şeklinde bu komutu kullanabilirsiniz.",
                    colour=discord.Color.red()
                )
                await ctx.send(embed=embed)
            except QueueIsEmpty:
                embed = discord.Embed(
                    description="Komutu bu şekilde kullanmak için bir şarkı açmalısınız. Eğer şarkı açmadan arama yapmak istiyorsanız komutu \n**'.lyrics şarkı ismi, sanatçı'** şeklinde kullanabilirsiniz",
                    colour=discord.Color.red()
                )
                await ctx.send(embed=embed)

        else:
            try:
                query_list = query.split(",")
                title = query_list[0].strip()
                artist = query_list[1].strip()
                genius = Genius()
                song = genius.search_song(title=title, artist=artist, get_full_info=False)

                if len(song.lyrics) <= 2048:
                    embed = discord.Embed(title=f"{song.full_title.replace('by', '-')}", colour=ctx.author.color,
                                          timestamp=dt.datetime.utcnow())
                    embed.description = song.lyrics
                    embed.set_footer(text=f"{ctx.author.display_name}", icon_url=ctx.author.avatar_url)
                    await ctx.send(embed=embed)

                else:
                    lyrics = song.lyrics.split("\n")
                    half = (len(lyrics) / 2)
                    first_half = ""
                    second_half = ""
                    for i in lyrics[:int(half)]:
                        first_half += f"{i}\n"
                    for j in lyrics[int(half):]:
                        second_half += f"{j}\n"

                    def _check(r, u):
                        return (
                                r.emoji in QUEUE_OPS
                                and u == ctx.author
                                and r.message.id == msg.id
                        )

                    if len(first_half) <= 2048:
                        embed = discord.Embed(
                            title=f"{song.full_title.replace('by', '-')}",
                            colour=ctx.author.color,
                            timestamp=dt.datetime.utcnow(),
                            description=first_half
                        )
                        msg = await ctx.send(embed=embed)

                        for i in QUEUE_OPS[1:3]:
                            await msg.add_reaction(i)
                        while True:
                            try:
                                pending_tasks = [
                                    self.bot.wait_for('reaction_add', check=_check),
                                    self.bot.wait_for('reaction_remove', check=_check)
                                ]
                            except asyncio.TimeoutError:
                                await msg.delete()
                                await ctx.message.delete()
                                break

                            done_tasks, pending_tasks = await asyncio.wait(pending_tasks,
                                                                           return_when=asyncio.FIRST_COMPLETED)
                            for task in done_tasks:
                                reaction, user = await task
                            else:
                                if reaction.emoji == QUEUE_OPS[1]:
                                    newembed = discord.Embed(
                                        title=f"{song.full_title.replace('by', '-')}",
                                        colour=ctx.author.color,
                                        timestamp=dt.datetime.utcnow(),
                                        description=second_half
                                    )
                                    await msg.edit(embed=newembed)
                                if reaction.emoji == QUEUE_OPS[2]:
                                    newembed = discord.Embed(
                                        title=f"{song.full_title.replace('by', '-')}",
                                        colour=ctx.author.color,
                                        timestamp=dt.datetime.utcnow(),
                                        description=first_half
                                    )
                                    await msg.edit(embed=newembed)
                    else:
                        quarter = (len(lyrics) / 4)
                        quarter1 = ""
                        quarter2 = ""
                        quarter3 = ""
                        quarter4 = ""
                        for i in lyrics[:int(quarter)]:
                            quarter1 += f"{i}\n"
                        for i in lyrics[int(quarter):int(half)]:
                            quarter2 += f"{i}\n"
                        for i in lyrics[int(half):int((half + quarter))]:
                            quarter3 += f"{i}\n"
                        for i in lyrics[int((half + quarter)):]:
                            quarter4 += f"{i}\n"

                        order_list = [quarter1, quarter2, quarter3, quarter4]

                        embed = discord.Embed(
                            title=f"{song.full_title.replace('by', '-')}",
                            colour=ctx.author.color,
                            timestamp=dt.datetime.utcnow(),
                            description=quarter1
                        )
                        msg = await ctx.send(embed=embed)

                        for i in QUEUE_OPS[1:3]:
                            await msg.add_reaction(i)
                        order_num = 0
                        while True:
                            try:
                                pending_tasks = [
                                    self.bot.wait_for('reaction_add', check=_check),
                                    self.bot.wait_for('reaction_remove', check=_check)
                                ]
                            except asyncio.TimeoutError:
                                await msg.delete()
                                await ctx.message.delete()
                                break

                            done_tasks, pending_tasks = await asyncio.wait(pending_tasks,
                                                                           return_when=asyncio.FIRST_COMPLETED)
                            for task in done_tasks:
                                reaction, user = await task

                            else:
                                if reaction.emoji == QUEUE_OPS[1]:
                                    if (order_num + 1) <= (len(order_list) - 1):
                                        order_num += 1
                                    newembed = discord.Embed(
                                        title=f"{song.full_title.replace('by', '-')}",
                                        colour=ctx.author.color,
                                        timestamp=dt.datetime.utcnow(),
                                        description=order_list[order_num]
                                    )
                                    await msg.edit(embed=newembed)
                                if reaction.emoji == QUEUE_OPS[2]:
                                    if (order_num - 1) >= 0:
                                        order_num -= 1
                                    newembed = discord.Embed(
                                        title=f"{song.full_title.replace('by', '-')}",
                                        colour=ctx.author.color,
                                        timestamp=dt.datetime.utcnow(),
                                        description=order_list[order_num]
                                    )
                                    await msg.edit(embed=newembed)

            except AttributeError:
                embed = discord.Embed(
                    description="Bu şarkının sözlerini bulamadım. Lütfen **şarkı ismi ve sanatçı** değerlerini doğru girdiğinizden emin olun ve tekrar deneyin.\nÖrnek Kullanım: **.lyrics Blank Space, Taylor Swift**",
                    colour=discord.Color.red()
                )
                await ctx.send(embed=embed)
            except IndexError:
                embed = discord.Embed(
                    description="Lütfen komutu **'.lyrics şarkı ismi, sanatçı'** şeklinde kullanın.",
                    colour=discord.Color.red()
                )
                await ctx.send(embed=embed)

    @commands.command(name="melihtürkçe", aliases=["melihturkce", "mt"])
    async def melihtürkçe(self, ctx):
        await self.play_command(ctx,
                                query="https://open.spotify.com/playlist/7Gtcw9CldGujNtJSgEmgrc?si=23qrqpu6TsCHt39g16MU-w")

    @melihtürkçe.error
    async def mt_error(self, ctx, exc):
        if isinstance(exc, AlreadyConnectedToChannel):
            embed = discord.Embed(
                description=f"**Mal CAMCI beceremediği için ikinci bir ses kanalına bağlanamıyorum.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(exc, NoVoiceChannel):
            embed = discord.Embed(
                description="**Bu komutu kullanmak için önce bir ses kanalına bağlanmanız gerekiyor.**",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(exc, QueueIsEmpty):
            embed = discord.Embed(
                description=f"**Oynatma sırasında şarkı olmadığı için oynatmaya başlayamıyorum.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(exc, PlayerIsAlreadyPlaying):
            pass

    @commands.command(name="semihtürkçe", aliases=["semihturkce", "st"])
    async def semihtürkçe(self, ctx):
        await self.play_command(ctx,
                                query="https://open.spotify.com/playlist/4spClhnBMnfdPLcdjaKsdn?si=P-Qskgd9QB2as_U1gHT6bA")

    @semihtürkçe.error
    async def st_error(self, ctx, exc):
        if isinstance(exc, AlreadyConnectedToChannel):
            embed = discord.Embed(
                description=f"**Mal CAMCI beceremediği için ikinci bir ses kanalına bağlanamıyorum.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(exc, NoVoiceChannel):
            embed = discord.Embed(
                description="**Bu komutu kullanmak için önce bir ses kanalına bağlanmanız gerekiyor.**",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(exc, QueueIsEmpty):
            embed = discord.Embed(
                description=f"**Oynatma sırasında şarkı olmadığı için oynatmaya başlayamıyorum.** [{ctx.author.mention}]",
                colour=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(exc, PlayerIsAlreadyPlaying):
            pass


class Diğer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="furkansavar",
                      help="Bu komut sadece Furkan TOPRAK (Toprak Elektrik) online iken çalışır. Furkanı kışkırtıp ortamdan uzaklaştırmak için bu komutu kullanın.")
    async def furkansavar_command(self, ctx):
        furkan = ctx.guild.get_member(340579053163773954)
        if furkan.status == discord.Status.online:
            await ctx.send("https://youtu.be/OsGentI_NHo?t=58")
        elif furkan is None:
            await ctx.send("Furkan Toprak bu sunucuda bulunmuyor. Bu mesaj kendini 3 saniye içerisinde imha edecek.", delete_after=3)
        else:
            await ctx.send("Furkan Toprak online değil. Bu mesaj kendini 3 saniye içerisinde imha edecek.",
                           delete_after=3)

    @commands.command(name="tft", help="Milleti TFT'ye çağırmak için kullan.")
    async def tft_cagrisi(self, ctx):
        await ctx.send(
            "<@246781799152222208> <@269754892531400714> <@254254267685142529> <@261847126818947073> <@464746264215683072> TFT gelin amcıklar")

    @commands.command(name="kedi", help="Rastgele bir kedi resmi yollar.")
    async def cats(self, ctx):
        url = "http://aws.random.cat//meow"
        response = requests.get(url)
        jresponse = response.json()
        resim = jresponse["file"]
        await ctx.send(resim)

    @commands.command(name="dolar", help="Dolar kurunu gösterir.")
    async def dolar(self, ctx):
        url = "https://kur.doviz.com/serbest-piyasa/amerikan-dolari"

        response = requests.get(url)
        content = response.content
        soup = BeautifulSoup(content, "html.parser")

        for i in soup.find_all("span", {"class": "change up", "data-socket-key": "USD"}):
            degisim = "+"
            günlük_yüzde = (((i.text).rsplit())[0])
        for i in soup.find_all("span", {"class": "change down", "data-socket-key": "USD"}):
            degisim = ""
            günlük_yüzde = (((i.text).rsplit())[0])
        for i in soup.find("span", {"data-socket-attr": "a", "data-socket-key": "USD"}):
            günlük_değişim = (i.rsplit()[0])
        for i in soup.find("span", {"data-socket-attr": "s", "data-socket-key": "USD"}):
            kur = i
        for i in soup.find("div", {"class": "text-xs text-blue-gray-2"}):
            son_güncelleme = (i[5:10])
        embed = discord.Embed(
            title="Amerikan Doları",
            colour=ctx.author.color,
        )
        embed.add_field(name="Kur", value=kur, inline=True)
        embed.add_field(name="Günlük Değişim", value=f"{degisim}{günlük_yüzde} ({günlük_değişim})", inline=True)
        embed.add_field(name="Son Güncelleme", value=son_güncelleme)
        embed.set_thumbnail(
            url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/Flag_of_the_United_States.svg/1920px-Flag_of_the_United_States.svg.png")
        await ctx.send(embed=embed)

    @commands.command(name="euro", help="Euro kurunu gösterir.")
    async def euro(self, ctx):
        url = "https://kur.doviz.com/serbest-piyasa/euro"

        response = requests.get(url)
        content = response.content
        soup = BeautifulSoup(content, "html.parser")
        for i in soup.find_all("span", {"class": "change up", "data-socket-key": "EUR"}):
            degisim = "+"
            günlük_yüzde = (((i.text).rsplit())[0])
        for i in soup.find_all("span", {"class": "change down", "data-socket-key": "EUR"}):
            degisim = ""
            günlük_yüzde = (((i.text).rsplit())[0])
        for i in soup.find("span", {"data-socket-attr": "a", "data-socket-key": "EUR"}):
            günlük_değişim = (i.rsplit()[0])
        for i in soup.find("span", {"data-socket-attr": "s", "data-socket-key": "EUR"}):
            kur = i
        for i in soup.find("div", {"class": "text-xs text-blue-gray-2"}):
            son_güncelleme = (i[5:10])
        embed = discord.Embed(
            title="Euro",
            colour=ctx.author.color,
        )
        embed.add_field(name="Kur", value=kur, inline=True)
        embed.add_field(name="Günlük Değişim", value=f"{degisim}{günlük_yüzde} ({günlük_değişim})", inline=True)
        embed.add_field(name="Son Güncelleme", value=son_güncelleme)
        embed.set_thumbnail(
            url="https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/Flag_of_Europe.svg/1280px-Flag_of_Europe.svg.png")
        await ctx.send(embed=embed)

    @commands.command(name="altın", help="Gram altın fiyatını gösterir.")
    async def altın(self, ctx):
        url = "https://altin.doviz.com/gram-altin"

        response = requests.get(url)
        content = response.content
        soup = BeautifulSoup(content, "html.parser")
        for i in soup.find_all("div",
                               {"data-socket-attr": "c", "data-socket-key": "gram-altin", "class": "change status up"}):
            print(i)
            degisim = "+"
            günlük_yüzde = (((i.text).rsplit())[0])
        for i in soup.find_all("div", {"data-socket-attr": "c", "data-socket-key": "gram-altin",
                                       "class": "change status down"}):
            degisim = ""
            günlük_yüzde = (((i.text).rsplit())[0])
        for i in soup.find("span", {"data-socket-attr": "a", "data-socket-key": "gram-altin"}):
            günlük_değişim = (i.rsplit()[0])
        for i in soup.find("div", {"data-socket-attr": "s", "data-socket-key": "gram-altin"}):
            kur = i
        for i in soup.find("div", {"class": "text-xs text-blue-gray-2"}):
            son_güncelleme = (i[5:10])
        embed = discord.Embed(
            title="Gram Altın",
            colour=ctx.author.color,
        )
        embed.add_field(name="Fiyat", value=kur, inline=True)
        embed.add_field(name="Günlük Değişim", value=f"{degisim}{günlük_yüzde} ({günlük_değişim})", inline=True)
        embed.add_field(name="Son Güncelleme", value=son_güncelleme)
        embed.set_thumbnail(
            url="https://iasbh.tmgrup.com.tr/96b53f/752/395/0/57/652/400?u=https://isbh.tmgrup.com.tr/sbh/2020/04/08/altin-fiyatlari-yukselis-egiliminde-1586335652329.jpg")
        await ctx.send(embed=embed)

    @commands.command(name="akp", help="AKP'nin son 20 yılda ülkeye kattığı değerleri gösterir.")
    async def akp(self, ctx):
        url = "https://www.doviz.com/"

        response = requests.get(url)
        content = response.content
        soup = BeautifulSoup(content, "html.parser")

        fiyatlar = soup.find_all("span", {"class": "value"})
        altin = fiyatlar[0].text
        dolar = fiyatlar[1].text
        euro = fiyatlar[2].text
        sterlin = fiyatlar[3].text

        embed = discord.Embed(
            title="xD",
            colour=ctx.author.color
        )
        embed.add_field(name="Dolar", value=dolar, inline=True)
        embed.add_field(name="Euro", value=euro, inline=True)
        embed.add_field(name="Sterlin", value=sterlin, inline=True)
        embed.set_thumbnail(url="https://i.pinimg.com/originals/55/3b/c5/553bc5162e5f51298cff2db5d2c34f23.png")
        await ctx.send(embed=embed)

    @commands.command(name="2023")
    async def ikibinyirmiüç(self, ctx):
        embed = discord.Embed(
            title="SÜPER GÜÇ",
            color=ctx.author.color
        )
        embed.add_field(name="DOLAR", value="0,5507", inline=True)
        embed.add_field(name="Günlük değişim", value="-%3131,31", inline=True)
        embed.add_field(name="Son Güncelleme", value="01.01.2023", inline=True)
        embed.set_thumbnail(url="http://c12.incisozluk.com.tr/res/incisozluk//11503/7/2827457_o586a.jpg")
        await ctx.send(embed=embed)

    @commands.command(name="about")
    async def about(self, ctx):
        embed = discord.Embed(
            title="CAMBOT v1.0",
            color=ctx.author.color
        )
        embed.add_field(name="TR", value="CAMCI tarafından yazılmış ve lisanslanmıştır. Detaylı bilgi için [CAMBOT resmi Github sayfasını](https://github.com/C4MCI/CAMBOT) ziyaret edebilirsiniz.")
        embed.add_field(name="EN", value="Written by CAMCI. This project is MIT licensed. You can check [official Github repository of CAMBOT](https://github.com/C4MCI/CAMBOT) for further information.")
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Music(bot))
    bot.add_cog(Diğer(bot))
