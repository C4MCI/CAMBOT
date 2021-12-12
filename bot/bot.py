from pathlib import Path

import discord
from discord.ext import commands
import os
import time
from threading import Thread
from decouple import config


class MusicBot(commands.Bot):
    def __init__(self):
        self._cogs = [p.stem for p in Path(".").glob("./bot/cogs/*.py")]
        super().__init__(
            command_prefix=self.prefix,
            case_insensitive=True,
            intents=discord.Intents.all()
        )

    def setup(self):
        print("Kurulum başlıyor...")

        for cog in self._cogs:
            self.load_extension(f"bot.cogs.{cog}")
            print(f"{cog} yüklendi.")
        print("Kurulum tamamlandı")

    def run(self):
        self.setup()
        TOKEN = config("TOKEN")

        def lavarun():
            cwd = os.getcwd()
            Lavalink_dir = cwd
            os.system(f"cd {Lavalink_dir} && java -jar Lavalink.jar")

        Thread(target=lavarun).start()
        time.sleep(60)
        print("Bot başlatılıyor...")
        super().run(TOKEN, reconnect=True)

    async def shutdown(self):
        print("Discord bağlantısı kesiliyor...")
        await super().close()

    async def close(self):
        print("Bot kapatılıyor...")
        await self.shutdown()

    async def on_connect(self):
        print(f" Discorda bağlandı (latency: {self.latency * 1000:,.0f} ms).")

    async def on_resumed(self):
        print(f"Bot çalışmaya devam ediyor.")

    async def on_disconnect(self):
        print("Botun bağlantısı kesildi")

    async def on_error(self, err, *args, **kwargs):
        raise

    async def on_command_error(self, ctx, exc):
        raise getattr(exc, "original", exc)

    async def on_ready(self):
        self.client_id = (await self.application_info()).id
        print("Bot hazır.")

    async def prefix(self, bot, message):
        return commands.when_mentioned_or(".")(bot, message)

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=commands.Context)

        if ctx.command is not None:
            await self.invoke(ctx)

    async def on_message(self, msg):
        if not msg.author.bot:
            await self.process_commands(msg)

    async def on_guild_join(self, guild):
        retStr = """
    ```md
# Bu mesaj haşmetli (C)AMCI'nın botunun bu discorda giriş yaptığının bildirisidir.```
    ```fix
# Komutlar için .help yazabilirsiniz. Çok kafanız karışırsa CAMCI'ya sorun.(Melih ve Furkan için yazdım yoksa siz anlarsınız)```
    ```diff
- BİAT EDİN```
    """
        embed = discord.Embed(title="BABANIZ GELDİ", color=discord.Color.red())
        embed.add_field(name="Bilgilendirme mesajı", value=retStr)
        await guild.text_channels[0].send(embed=embed)

    async def on_member_join(self, member):
        channels = member.guild.text_channels
        textchannels = []
        for channel in channels:
            textchannels.append(channel)
        await textchannels[0].send(f"Merhaba {member.name}, {member.guild.name} sunucusuna hoş geldin!")
        await member.create_dm()
        await member.dm_channel.send(f"Merhaba {member.name}, {member.guild.name} sunucusuna hoş geldin!")
