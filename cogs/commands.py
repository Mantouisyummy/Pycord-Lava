import re
import json
import discord
from os import getpid

from discord import Option, OptionChoice, ButtonStyle, Embed, ApplicationContext, AutocompleteContext
from discord.ext import commands, tasks
from discord.commands import option
from discord.utils import basic_autocomplete
from discord.ext.commands import Cog
from discord.ui import Button
from paginator import Paginator
from lavalink import DefaultPlayer, LoadResult, LoadType, Timescale, Tremolo, Vibrato, LowPass, Rotation, Equalizer
from psutil import cpu_percent, virtual_memory, Process

from core.bot import Bot
from core.embeds import ErrorEmbed, SuccessEmbed, InfoEmbed, WarningEmbed
from core.errors import UserInDifferentChannel
from core.utils import ensure_voice, update_display, split_list, bytes_to_gb, get_commit_hash, get_upstream_url, \
    get_current_branch

allowed_filters = {
    "timescale": Timescale,
    "tremolo": Tremolo,
    "vibrato": Vibrato,
    "lowpass": LowPass,
    "rotation": Rotation,
    "equalizer": Equalizer
}

async def music_term(author_id):
    try:
        with open("./JSDB/music-term.json", "r") as file:
            data = json.load(file)
        
        enabled = data[str(author_id)]["enabled"]
        if enabled == "false":
            return "false"
    except:
        return "false"

##### 音樂系統 儲存資料 #####
class MusicTerm(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="同意條款", emoji="<a:check:1064490541116563476>", style=discord.ButtonStyle.success, custom_id="music:1") 
    async def accept(self, button, interaction):
        try:
            with open("JSDB/custom_embed.json", "r") as file:
                data = json.load(file)
        
            data = data[str(interaction.guild.id)]
            color = data["color"]
            color_set = int(color, 16)
        except:
            color_set = 0x2e2e2e
        
        with open("./JSDB/music-term.json", "r") as file:
            data = json.load(file)
                
            data[str(interaction.user.id)] = {
                "enabled": "true"}
        with open("./JSDB/music-term.json", "w") as file:
            json.dump(data, file, indent=4)
        
        embed=discord.Embed(title="", color=color_set)
        embed.set_author(name=f"您已同意 Youtube 服務條款!", icon_url=(interaction.user.display_avatar.url))
        embed.add_field(name="<:file:1115287404174135346> ` 系統提示: `", value=f"**請重新使用 /music 指令......**")
        await interaction.message.edit(embed=embed, view=MusicTermTemp())
        await interaction.response.send_message(f"**<:youtube:1070326502903779378> | 恭喜! 您現在可以使用 /music 服務!**" , ephemeral=True)
        
    @discord.ui.button(label="拒絕條款", emoji="<a:deny:1064490544992108586>", style=discord.ButtonStyle.danger, custom_id="music:2")
    async def deny(self, button, interaction):
        try:
            with open("JSDB/custom_embed.json", "r") as file:
                data = json.load(file)
        
            data = data[str(interaction.guild.id)]
            color = data["color"]
            color_set = int(color, 16)
        except:
            color_set = 0x2e2e2e
        
        with open("./JSDB/music-term.json", "r") as file:
            data = json.load(file)
                
            data[str(interaction.user.id)] = {
                "enabled": "false"}
        with open("./JSDB/music-term.json", "w") as file:
            json.dump(data, file, indent=4)
        
        embed=discord.Embed(title="", color=color_set)
        embed.set_author(name=f"您已拒絕 Youtube 服務條款!", icon_url=(interaction.user.display_avatar.url))
        embed.add_field(name="<:file:1115287404174135346> ` 系統提示: `", value=f"**指令系統已撤回您的音樂指令請求!**")
        await interaction.message.edit(embed=embed, view=MusicTermTemp())
        await interaction.response.send_message(f"**<a:deny:1064490544992108586> | 系統已撤回您的 /music 使用權!**" , ephemeral=True)
##### 音樂系統 儲存資料 #####
class MusicTermTemp(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="同意條款", emoji="<a:check:1064490541116563476>", style=discord.ButtonStyle.success, disabled=True, custom_id="music:1") 
    async def accept(self, button, interaction):
        try:
            with open("JSDB/custom_embed.json", "r") as file:
                data = json.load(file)
        
            data = data[str(interaction.guild.id)]
            color = data["color"]
            color_set = int(color, 16)
        except:
            color_set = 0x2e2e2e
        
        with open("./JSDB/music-term.json", "r") as file:
            data = json.load(file)
                
            data[str(interaction.user.id)] = {
                "enabled": "true"}
        with open("./JSDB/music-term.json", "w") as file:
            json.dump(data, file, indent=4)
        
        embed=discord.Embed(title="", color=color_set)
        embed.set_author(name=f"您已同意 Youtube 服務條款!", icon_url=(interaction.user.display_avatar.url))
        embed.add_field(name="<:file:1115287404174135346> ` 系統提示: `", value=f"**請重新使用 /music 指令......**")
        await interaction.message.edit(embed=embed, view=MusicTermTemp())
        await interaction.response.send_message(f"**<:youtube:1070326502903779378> | 恭喜! 您現在可以使用 /music 服務!**" , ephemeral=True)
        
    @discord.ui.button(label="拒絕條款", emoji="<a:deny:1064490544992108586>", style=discord.ButtonStyle.danger, disabled=True, custom_id="music:2")
    async def deny(self, button, interaction):
        try:
            with open("JSDB/custom_embed.json", "r") as file:
                data = json.load(file)
        
            data = data[str(interaction.guild.id)]
            color = data["color"]
            color_set = int(color, 16)
        except:
            color_set = 0x2e2e2e
        
        with open("./JSDB/music-term.json", "r") as file:
            data = json.load(file)
                
            data[str(interaction.user.id)] = {
                "enabled": "false"}
        with open("./JSDB/music-term.json", "w") as file:
            json.dump(data, file, indent=4)
        
        embed=discord.Embed(title="", color=color_set)
        embed.set_author(name=f"您已拒絕 Youtube 服務條款!", icon_url=(interaction.user.display_avatar.url))
        embed.add_field(name="<:file:1115287404174135346> ` 系統提示: `", value=f"**指令系統已撤回您的音樂指令請求!**")
        await interaction.message.edit(embed=embed, view=MusicTermTemp())
        await interaction.response.send_message(f"**<a:deny:1064490544992108586> | 系統已撤回您的 /music 使用權!**" , ephemeral=True)

class Commands(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    music_command = discord.SlashCommandGroup("music", "機器人 | 音樂指令")

    async def search(self, ctx: AutocompleteContext):
        query = ctx.options['query']

        if query.startswith("https://www.youtube.com") is True:
            print("?")
            return []

        if re.match(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", query):
            return []
        
        if not query:
            return []

        choices = []

        result = await self.bot.lavalink.get_tracks(f"ytsearch:{query}")

        for track in result.tracks:
            choices.append(
                OptionChoice(
                    name=f"{track.title[:80]} by {track.author[:16]}", value=(track.uri + "auto")
                )
            )

        return choices

    @music_command.command(
        name='dashboard',
        description="使用者 | 音樂系統 | 顯示目前正在播放的歌曲"
    )
    async def nowplaying(self, ctx: ApplicationContext):
        await ctx.response.defer()
        term = await music_term(ctx.author.id)
        if term == "false":
            embed=discord.Embed(title="", color=0x2e2e2e)
            embed.set_author(name=f"Youtube - 服務條款須知", icon_url=(ctx.author.display_avatar.url))
            embed.add_field(name="<:file:1115287404174135346> ` 快速簡介: `", value=f"**因於部分原因 您必須先行同意及查看服務條款!**", inline=False)
            embed.add_field(name="<:youtube:1070326502903779378> ` 服務條款: `", value=f"**[Youtube 服務條款](https://www.youtube.com/t/terms?hl=zh-tw)**", inline=False)
            await ctx.respond(embed=embed, view=MusicTerm())
            return
        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        await update_display(self.bot, player, new_message=(await ctx.interaction.original_response()))

    @music_command.command(
        name="play",
        description="使用者 | 音樂系統 | 播放音樂",
    )
    async def play(self, ctx: ApplicationContext, query:Option(str, "歌曲名稱或網址，支援 YouTube, YouTube Music, SoundCloud, Spotify", autocomplete=search, name="query"), index:Option(int, "要將歌曲放置於當前播放序列的位置", name="index", required=False)):
        await ctx.response.defer()
        term = await music_term(ctx.author.id)
        if term == "false":
            embed=discord.Embed(title="", color=0x2e2e2e)
            embed.set_author(name=f"Youtube - 服務條款須知", icon_url=(ctx.author.display_avatar.url))
            embed.add_field(name="<:file:1115287404174135346> ` 快速簡介: `", value=f"**因於部分原因 您必須先行同意及查看服務條款!**", inline=False)
            embed.add_field(name="<:youtube:1070326502903779378> ` 服務條款: `", value=f"**[Youtube 服務條款](https://www.youtube.com/t/terms?hl=zh-tw)**", inline=False)
            await ctx.respond(embed=embed, view=MusicTerm())
            return
                          
        if ctx.author.voice is None:
            embed=discord.Embed(title=f" ", color=0x2e2e2e)
            embed.set_author(name=f"警告! 機器人不會通靈!", icon_url=(ctx.author.display_avatar.url))
            embed.add_field(name="<:file:1115287404174135346> ` 音樂系統: `", value=f"**幫我加入一個語音頻道啦!**", inline=False)
            await ctx.interaction.edit_original_response(embed=embed)
            return
            
        if "auto" not in query:
            if "spotify" in query:
                pass
            else:
                embed=discord.Embed(title=f" ", color=0x2e2e2e)
                embed.set_author(name=f"警告! 外在輸入連結不可用!", icon_url=(ctx.author.display_avatar.url))
                embed.add_field(name="<:file:1115287404174135346> ` 音樂系統: `", value=f"**||沒辦法... 我怕被 Tos 搞 QAQ||**", inline=False)
                await ctx.interaction.edit_original_response(embed=embed)
                return
        else:
            query.replace('auto', '')

        await ensure_voice(self.bot, ctx=ctx, should_connect=True)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        player.store("channel", ctx.channel.id)

        results: LoadResult = await player.node.get_tracks(query)

        # Check locals
        if not results or not results.tracks:
            self.bot.logger.info("No results found with lavalink for query %s, checking local sources", query)
            results: LoadResult = await player.node.get_tracks(query, check_local=True)

        # Find the index song should be (In front of any autoplay songs)
        if not index:
            index = sum(1 for t in player.queue if t.requester)

        filter_warnings = [
            InfoEmbed(
                title="提醒",
                description=str(
                        '偵測到 效果器正在運作中，\n'
                        '這可能會造成音樂聲音有變形(加速、升高等)的情形產生，\n'
                        '如果這不是你期望的，可以透過效果器的指令來關閉它們\n'
                        '指令名稱通常等於效果器名稱，例如 `/timescale` 就是控制 Timescale 效果器\n\n'
                        '以下是正在運行的效果器：'
                    )
                ) + ' ' + ', '.join([key.capitalize() for key in player.filters])
        ] if player.filters else []

        match results.load_type:
            case LoadType.TRACK:
                player.add(
                    requester=ctx.author.id,
                    track=results.tracks[0], index=index
                )

                # noinspection PyTypeChecker
                embed=discord.Embed(title=f" ", color=0x2e2e2e)
                embed.set_author(name=f"{results.tracks[0].title}", icon_url=(ctx.author.display_avatar.url))
                embed.add_field(name="<:file:1115287404174135346> ` 音樂系統: `", value=f"**正在播放 {results.tracks[0].title[0:50]}**", inline=False)
                await ctx.interaction.edit_original_response(embed=embed)

            case LoadType.PLAYLIST:
                # TODO: Ask user if they want to add the whole playlist or just some tracks

                for iter_index, track in enumerate(results.tracks):
                    player.add(
                        requester=ctx.author.id, track=track,
                        index=index + iter_index
                    )

                # noinspection PyTypeChecker
                embed=discord.Embed(title=f" ", color=0x2e2e2e)
                embed.set_author(name=f"{results.tracks[0].title}", icon_url=(ctx.author.display_avatar.url))
                embed.add_field(name="<:file:1115287404174135346> ` 音樂系統: `", value=f'**已加入播放序列:{len(results.tracks)} / {results.playlist_info.name}\n'.join([f"**[{index + 1}]** {track.title}"for index, track in enumerate(results.tracks[:10])]) + "..." if len(results.tracks) > 10 else "", inline=False)
                await ctx.interaction.edit_original_response(embed=embed)

        # If the player isn't already playing, start it.
        if not player.is_playing:
            await player.play()

        await update_display(
            self.bot, player, await ctx.interaction.original_response(), delay=5
        )

    @music_command.command(
        name="skip",
        description="使用者 | 音樂系統 | 跳過當前播放的歌曲")
    async def skip(self, ctx: ApplicationContext, target:Option(
                int,
                "要跳到的歌曲編號",
                name="target",
                required=False
            ), 
            move: Option(
                int,
                "是否移除目標以前的所有歌曲，如果沒有提供 target，這個參數會被忽略",
                name="move",
                required=False
            )):
        term = await music_term(ctx.author.id)
        if term == "false":
            embed=discord.Embed(title="", color=0x2e2e2e)
            embed.set_author(name=f"Youtube - 服務條款須知", icon_url=(ctx.author.display_avatar.url))
            embed.add_field(name="<:file:1115287404174135346> ` 快速簡介: `", value=f"**因於部分原因 您必須先行同意及查看服務條款!**", inline=False)
            embed.add_field(name="<:youtube:1070326502903779378> ` 服務條款: `", value=f"**[Youtube 服務條款](https://www.youtube.com/t/terms?hl=zh-tw)**", inline=False)
            await ctx.respond(embed=embed, view=MusicTerm())
            return
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        if not player.is_playing:
            return await ctx.interaction.edit_original_response(
                embed=ErrorEmbed("沒有正在播放的歌曲")
            )

        if target:
            if len(player.queue) < target or target < 1:
                return await ctx.interaction.edit_original_response(
                    embed=ErrorEmbed("無效的歌曲編號")
                )
            if move:
                player.queue.insert(0, player.queue.pop(target - 1))

            else:
                player.queue = player.queue[target - 1:]

        await player.skip()

        await ctx.interaction.edit_original_response(
            embed=SuccessEmbed("已跳過歌曲")
        )

        await update_display(
            self.bot, player, await ctx.interaction.original_response(), delay=5
        )

    @music_command.command(
        name="track_remove",
        description="使用者 | 音樂系統 | 移除指定歌曲")
    async def remove(self, ctx: ApplicationContext, target: Option(
                int,
                "要移除的歌曲編號",
                name="target",
                required=True)):
        await ctx.response.defer()
        term = await music_term(ctx.author.id)
        if term == "false":
            embed=discord.Embed(title="", color=0x2e2e2e)
            embed.set_author(name=f"Youtube - 服務條款須知", icon_url=(ctx.author.display_avatar.url))
            embed.add_field(name="<:file:1115287404174135346> ` 快速簡介: `", value=f"**因於部分原因 您必須先行同意及查看服務條款!**", inline=False)
            embed.add_field(name="<:youtube:1070326502903779378> ` 服務條款: `", value=f"**[Youtube 服務條款](https://www.youtube.com/t/terms?hl=zh-tw)**", inline=False)
            await ctx.respond(embed=embed, view=MusicTerm())
            return
        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        if len(player.queue) < target or target < 1:
            return await ctx.interaction.edit_original_response(
                embed=ErrorEmbed("無效的歌曲編號")
            )

        player.queue.pop(target - 1)

        await ctx.interaction.edit_original_response(
            embed=SuccessEmbed("已移除歌曲")
        )

        await update_display(
            self.bot, player, await ctx.interaction.original_response(), delay=5
        )

    @music_command.command(
        name="track_clean",
        description="使用者 | 音樂系統 | 清除播放序列"
    )
    async def clean(self, ctx: ApplicationContext):
        await ctx.response.defer()
        term = await music_term(ctx.author.id)
        if term == "false":
            embed=discord.Embed(title="", color=0x2e2e2e)
            embed.set_author(name=f"Youtube - 服務條款須知", icon_url=(ctx.author.display_avatar.url))
            embed.add_field(name="<:file:1115287404174135346> ` 快速簡介: `", value=f"**因於部分原因 您必須先行同意及查看服務條款!**", inline=False)
            embed.add_field(name="<:youtube:1070326502903779378> ` 服務條款: `", value=f"**[Youtube 服務條款](https://www.youtube.com/t/terms?hl=zh-tw)**", inline=False)
            await ctx.respond(embed=embed, view=MusicTerm())
            return
        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        player.queue.clear()

        await ctx.interaction.edit_original_response(
            embed=SuccessEmbed("已清除播放序列")
        )

        await update_display(
            self.bot, player, await ctx.interaction.original_response(), delay=5
        )

    @music_command.command(
        name="pause",
        description="使用者 | 音樂系統 | 暫停當前播放的歌曲"
    )
    async def pause(self, ctx: ApplicationContext):
        await ctx.response.defer()
        term = await music_term(ctx.author.id)
        if term == "false":
            embed=discord.Embed(title="", color=0x2e2e2e)
            embed.set_author(name=f"Youtube - 服務條款須知", icon_url=(ctx.author.display_avatar.url))
            embed.add_field(name="<:file:1115287404174135346> ` 快速簡介: `", value=f"**因於部分原因 您必須先行同意及查看服務條款!**", inline=False)
            embed.add_field(name="<:youtube:1070326502903779378> ` 服務條款: `", value=f"**[Youtube 服務條款](https://www.youtube.com/t/terms?hl=zh-tw)**", inline=False)
            await ctx.respond(embed=embed, view=MusicTerm())
            return
        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        if not player.is_playing:
            return await ctx.interaction.edit_original_response(
                embed=ErrorEmbed("沒有正在播放的歌曲")
            )

        await player.set_pause(True)

        await ctx.interaction.edit_original_response(
            embed=SuccessEmbed("已暫停歌曲")
        )

    @music_command.command(
        name="resume",
        description="使用者 | 音樂系統 | 恢復當前播放的歌曲"
    )
    async def resume(self, ctx: ApplicationContext):
        await ctx.response.defer()
        term = await music_term(ctx.author.id)
        if term == "false":
            embed=discord.Embed(title="", color=0x2e2e2e)
            embed.set_author(name=f"Youtube - 服務條款須知", icon_url=(ctx.author.display_avatar.url))
            embed.add_field(name="<:file:1115287404174135346> ` 快速簡介: `", value=f"**因於部分原因 您必須先行同意及查看服務條款!**", inline=False)
            embed.add_field(name="<:youtube:1070326502903779378> ` 服務條款: `", value=f"**[Youtube 服務條款](https://www.youtube.com/t/terms?hl=zh-tw)**", inline=False)
            await ctx.respond(embed=embed, view=MusicTerm())
            return
        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        if not player.paused:
            return await ctx.interaction.edit_original_response(
                embed=ErrorEmbed("沒有暫停的歌曲")
            )

        await player.set_pause(False)

        await ctx.interaction.edit_original_response(
            embed=SuccessEmbed("已繼續歌曲")
        )

        await update_display(
            self.bot, player, await ctx.interaction.original_response(), delay=5
        )

    @music_command.command(
        name="stop",
        description="使用者 | 音樂系統 | 停止播放並清空播放序列"
    )
    async def stop(self, ctx: ApplicationContext):
        await ctx.response.defer()
        term = await music_term(ctx.author.id)
        if term == "false":
            embed=discord.Embed(title="", color=0x2e2e2e)
            embed.set_author(name=f"Youtube - 服務條款須知", icon_url=(ctx.author.display_avatar.url))
            embed.add_field(name="<:file:1115287404174135346> ` 快速簡介: `", value=f"**因於部分原因 您必須先行同意及查看服務條款!**", inline=False)
            embed.add_field(name="<:youtube:1070326502903779378> ` 服務條款: `", value=f"**[Youtube 服務條款](https://www.youtube.com/t/terms?hl=zh-tw)**", inline=False)
            await ctx.respond(embed=embed, view=MusicTerm())
            return
        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        await player.stop()
        player.queue.clear()

        await update_display(self.bot, player, await ctx.interaction.original_response())

    @music_command.command(
        name="connect",
        description="使用者 | 音樂系統 | 連接至你當前的語音頻道"
    )
    async def connect(self, ctx: ApplicationContext):
        await ctx.response.defer()
        term = await music_term(ctx.author.id)
        if term == "false":
            embed=discord.Embed(title="", color=0x2e2e2e)
            embed.set_author(name=f"Youtube - 服務條款須知", icon_url=(ctx.author.display_avatar.url))
            embed.add_field(name="<:file:1115287404174135346> ` 快速簡介: `", value=f"**因於部分原因 您必須先行同意及查看服務條款!**", inline=False)
            embed.add_field(name="<:youtube:1070326502903779378> ` 服務條款: `", value=f"**[Youtube 服務條款](https://www.youtube.com/t/terms?hl=zh-tw)**", inline=False)
            await ctx.respond(embed=embed, view=MusicTerm())
            return
        try:
            await ensure_voice(bot=self.bot, ctx=ctx, should_connect=True)

            await ctx.interaction.edit_original_response(
                embed=SuccessEmbed("已連接至語音頻道")
            )

        except UserInDifferentChannel:
            player: DefaultPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

            await ctx.interaction.edit_original_response(
                embed=WarningEmbed(
                    "警告",
                    "機器人已經在一個頻道中了，繼續移動將會中斷對方的音樂播放，是否要繼續?"
                ),
                components=[
                    Button(
                        label=str(
                            "繼續"
                        ),
                        style=ButtonStyle.green, custom_id="continue"
                    )
                ]
            )

            try:
                await self.bot.wait_for(
                    "button_click",
                    check=lambda i: i.data.custom_id in ["continue"] and i.user.id == ctx.user.id,
                    timeout=10
                )

            except TimeoutError:
                await ctx.interaction.edit_original_response(
                    embed=ErrorEmbed(
                        "已取消"
                    ),
                    components=[]
                )

                return

            await player.stop()
            player.queue.clear()

            await ctx.guild.voice_client.disconnect(force=False)

            await ensure_voice(ctx, should_connect=True)

            await ctx.interaction.edit_original_response(
                embed=SuccessEmbed("已連接至語音頻道"),
                components=[]
            )

        finally:
            player: DefaultPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)
            await update_display(
                bot=self.bot,
                player=player or self.bot.lavalink.player_manager.get(ctx.guild.id),
                new_message=await ctx.interaction.original_response(),
                delay=5,
            )

    @music_command.command(
        name="disconnect",
        description=
            "使用者 | 音樂系統 | 斷開與語音頻道的連接"
    )
    async def disconnect(self, ctx: ApplicationContext):
        await ctx.response.defer()
        term = await music_term(ctx.author.id)
        if term == "false":
            embed=discord.Embed(title="", color=0x2e2e2e)
            embed.set_author(name=f"Youtube - 服務條款須知", icon_url=(ctx.author.display_avatar.url))
            embed.add_field(name="<:file:1115287404174135346> ` 快速簡介: `", value=f"**因於部分原因 您必須先行同意及查看服務條款!**", inline=False)
            embed.add_field(name="<:youtube:1070326502903779378> ` 服務條款: `", value=f"**[Youtube 服務條款](https://www.youtube.com/t/terms?hl=zh-tw)**", inline=False)
            await ctx.respond(embed=embed, view=MusicTerm())
            return
        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        await player.stop()
        player.queue.clear()

        await ctx.guild.voice_client.disconnect(force=False)

        await update_display(self.bot, player, await ctx.interaction.original_response())

    @music_command.command(
        name="queue",
        description="使用者 | 音樂系統 | 顯示播放序列"
    )
    async def queue(self, ctx: ApplicationContext):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        term = await music_term(ctx.author.id)
        if term == "false":
            embed=discord.Embed(title="", color=0x2e2e2e)
            embed.set_author(name=f"Youtube - 服務條款須知", icon_url=(ctx.author.display_avatar.url))
            embed.add_field(name="<:file:1115287404174135346> ` 快速簡介: `", value=f"**因於部分原因 您必須先行同意及查看服務條款!**", inline=False)
            embed.add_field(name="<:youtube:1070326502903779378> ` 服務條款: `", value=f"**[Youtube 服務條款](https://www.youtube.com/t/terms?hl=zh-tw)**", inline=False)
            await ctx.respond(embed=embed, view=MusicTerm())
            return 

        if not player or not player.queue:
            return await ctx.response.send_message(
                embed=ErrorEmbed("播放序列為空")
            )

        pages: list[InfoEmbed] = []

        for iteration, songs_in_page in enumerate(split_list(player.queue, 10)):
            pages.append(
                InfoEmbed(
                    title="播放序列",
                    description='\n'.join(
                        [
                            f"**[{index + 1 + (iteration * 10)}]** {track.title}"
                            f" {'🔥' if not track.requester else ''}"
                            for index, track in enumerate(songs_in_page)
                        ]
                    )
                )
            )

        paginator = Paginator(
            timeout=60,
            previous_button=Button(
                style=ButtonStyle.blurple, emoji='⏪'
            ),
            next_button=Button(
                style=ButtonStyle.blurple,
                emoji='⏩'
            ),
            trash_button=Button(
                style=ButtonStyle.red,
                emoji='⏹️'
            ),
            page_counter_style=ButtonStyle.green,
            interaction_check_message=ErrorEmbed(
                "沒事戳這顆幹嘛？"
            )
        )

        await paginator.start(ctx, pages)

    @music_command.command(
        name="repeat",
        description="使用者 | 音樂系統 | 更改重複播放模式"
    )
    async def repeat(self, ctx: ApplicationContext, mode: Option(
        name="mode",
        description="重複播放模式",
        choices=[
            OptionChoice(
                name='關閉',
                value=f"{'關閉'}/0"
            ),
            OptionChoice(
                name='單曲',
                value=f"{'單曲'} 單曲/1"
            ),
            OptionChoice(
                name='整個序列',
                value=f"{'整個序列'} 整個序列/2"
                )
            ],
            required=True)):
        
        term = await music_term(ctx.author.id)
        if term == "false":
            embed=discord.Embed(title="", color=0x2e2e2e)
            embed.set_author(name=f"Youtube - 服務條款須知", icon_url=(ctx.author.display_avatar.url))
            embed.add_field(name="<:file:1115287404174135346> ` 快速簡介: `", value=f"**因於部分原因 您必須先行同意及查看服務條款!**", inline=False)
            embed.add_field(name="<:youtube:1070326502903779378> ` 服務條款: `", value=f"**[Youtube 服務條款](https://www.youtube.com/t/terms?hl=zh-tw)**", inline=False)
            await ctx.respond(embed=embed, view=MusicTerm())
            return
        
        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        

        player.set_loop(int(mode.split("/")[1]))

        await ctx.response.send_message(
            embed=SuccessEmbed(
                f"{'成功將重複播放模式更改為'}: {mode.split('/')[0]}"
            )
        )

        await update_display(
            self.bot, player, await ctx.interaction.original_response(), delay=5
        )

    @music_command.command(
        name="shuffle",
        description="使用者 | 音樂系統 | 切換隨機播放模式"
    )
    async def shuffle(self, ctx: ApplicationContext):
        await ctx.response.defer()
        
        term = await music_term(ctx.author.id)
        if term == "false":
            embed=discord.Embed(title="", color=0x2e2e2e)
            embed.set_author(name=f"Youtube - 服務條款須知", icon_url=(ctx.author.display_avatar.url))
            embed.add_field(name="<:file:1115287404174135346> ` 快速簡介: `", value=f"**因於部分原因 您必須先行同意及查看服務條款!**", inline=False)
            embed.add_field(name="<:youtube:1070326502903779378> ` 服務條款: `", value=f"**[Youtube 服務條款](https://www.youtube.com/t/terms?hl=zh-tw)**", inline=False)
            await ctx.respond(embed=embed, view=MusicTerm())
            return
        
        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        player.set_shuffle(not player.shuffle)

        await ctx.interaction.edit_original_response(
            embed=SuccessEmbed(
                f"{'隨機播放模式'}：{'開啟' if player.shuffle else '關閉'}"
            )
        )

        await update_display(
            self.bot, player, await ctx.interaction.original_response(), delay=5
        )

def setup(bot):
    bot.add_cog(Commands(bot))
