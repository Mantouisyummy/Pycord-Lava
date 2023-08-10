import re
import discord
from os import getpid

from discord import Option, OptionChoice, ButtonStyle, Embed, ApplicationContext, AutocompleteContext
from discord.ext import commands
from discord.commands import option
from discord.utils import basic_autocomplete
from discord.ext.commands import Cog
from discord.ui import Button , View
from lavalink import DefaultPlayer, LoadResult, LoadType, Timescale, Tremolo, Vibrato, LowPass, Rotation, Equalizer
from psutil import cpu_percent, virtual_memory, Process

from core.bot import Bot
from core.embeds import ErrorEmbed, SuccessEmbed, InfoEmbed, WarningEmbed
from core.errors import UserInDifferentChannel
from core.utils import ensure_voice, update_display, split_list, bytes_to_gb, get_commit_hash, get_upstream_url, \
    get_current_branch

from core.view import View

allowed_filters = {
    "timescale": Timescale,
    "tremolo": Tremolo,
    "vibrato": Vibrato,
    "lowpass": LowPass,
    "rotation": Rotation,
    "equalizer": Equalizer
}



class Commands(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    announcement = discord.SlashCommandGroup("music", "機器人 | 音樂指令")

    async def search(self, ctx: AutocompleteContext):
        query = ctx.options['query']
        if re.match(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", query):
            return []

        if not query:
            return []

        choices = []

        result = await self.bot.lavalink.get_tracks(f"ytsearch:{query}")

        for track in result.tracks:
            choices.append(
                OptionChoice(
                    name=f"{track.title[:80]} by {track.author[:16]}", value=track.uri
                )
            )

        return choices

    @announcement.command(
        name="info",
        description="顯示機器人資訊"
    )
    async def info(self, ctx: ApplicationContext):

        embed = Embed(
            title='機器人資訊',
            color=0x2b2d31
        )

        embed.add_field(
            name='啟動時間',
            value=f"<t:{round(Process(getpid()).create_time())}:F>",
            inline=True
        )

        branch = get_current_branch()
        upstream_url = get_upstream_url(branch)

        embed.add_field(
            name='版本資訊',
            value=f"{get_commit_hash()} on {branch} from {upstream_url}",
        )

        embed.add_field(name="​", value="​", inline=True)

        embed.add_field(
            name='CPU',
            value=f"{cpu_percent()}%",
            inline=True
        )

        embed.add_field(
            name='RAM',
            value=f"{round(bytes_to_gb(virtual_memory()[3]), 1)} GB / "
                  f"{round(bytes_to_gb(virtual_memory()[0]), 1)} GB "
                  f"({virtual_memory()[2]}%)",
            inline=True
        )

        embed.add_field(name="​", value="​", inline=True)

        embed.add_field(
            name='伺服器數量',
            value=len(self.bot.guilds),
            inline=True
        )

        embed.add_field(
            name='播放器數量',
            value=len(self.bot.lavalink.player_manager.players),
            inline=True
        )

        embed.add_field(name="​", value="​", inline=True)

        await ctx.send(
            embed=embed
        )

    @announcement.command(
        name='nowplaying',
        description="顯示目前正在播放的歌曲"
    )
    async def nowplaying(self, ctx: ApplicationContext):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        await update_display(self.bot, player, new_message=(await ctx.interaction.original_response()))

    @announcement.command(
        name="play",
        description="播放音樂",
    )
    async def play(self, ctx: ApplicationContext, query:Option(str, "歌曲名稱或網址，支援 YouTube, YouTube Music, SoundCloud,Spotify", autocomplete=search, name="query"), index:Option(int, "要將歌曲放置於當前播放序列的位置", name="index", required=False)):
        await ctx.response.defer()

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

        if not results or not results.tracks:  # If nothing was found
            return await ctx.interaction.edit_original_response(
                embed=ErrorEmbed(
                    "command.play.error.no_results.title",
                    "如果你想要使用關鍵字搜尋，請在輸入關鍵字後等待幾秒，搜尋結果將會自動顯示在上方",
                )
            )

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
                await ctx.interaction.edit_original_response(
                    embeds=[
                               SuccessEmbed(
                                   "已加入播放序列",
                                   {results.tracks[0].title}
                               )
                           ] + filter_warnings
                )

            case LoadType.PLAYLIST:
                # TODO: Ask user if they want to add the whole playlist or just some tracks

                for iter_index, track in enumerate(results.tracks):
                    player.add(
                        requester=ctx.author.id, track=track,
                        index=index + iter_index
                    )

                # noinspection PyTypeChecker
                await ctx.interaction.edit_original_response(
                    embeds=[
                               SuccessEmbed(
                                   title=f"'已加入播放序列' {len(results.tracks)} / {results.playlist_info.name}",
                                   description='\n'.join(
                                       [
                                           f"**[{index + 1}]** {track.title}"
                                           for index, track in enumerate(results.tracks[:10])
                                       ]
                                   ) + "..." if len(results.tracks) > 10 else ""
                               )
                           ] + filter_warnings
                )

        # If the player isn't already playing, start it.
        if not player.is_playing:
            await player.play()

        await update_display(
            self.bot, player, await ctx.interaction.original_response(), delay=5
        )

    @announcement.command(
        name="skip",
        description="跳過當前播放的歌曲")
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

    @announcement.command(
        name="remove",
        description="移除歌曲")
    async def remove(self, ctx: ApplicationContext, target: Option(
                int,
                "要移除的歌曲編號",
                name="target",
                required=True)):
        await ctx.response.defer()

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

    @announcement.command(
        name="clean",
        description="清除播放序列"
    )
    async def clean(self, ctx: ApplicationContext):
        await ctx.response.defer()

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

    @announcement.command(
        name="pause",
        description="暫停當前播放的歌曲"
    )
    async def pause(self, ctx: ApplicationContext):
        await ctx.response.defer()

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

    @announcement.command(
        name="resume",
        description="恢復當前播放的歌曲"
    )
    async def resume(self, ctx: ApplicationContext):
        await ctx.response.defer()

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

    @announcement.command(
        name="stop",
        description="停止播放並清空播放序列"
    )
    async def stop(self, ctx: ApplicationContext):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        await player.stop()
        player.queue.clear()

        await update_display(self.bot, player, await ctx.interaction.original_response())

    @announcement.command(
        name="connect",
        description="連接至你當前的語音頻道"
    )
    async def connect(self, ctx: ApplicationContext):
        await ctx.response.defer()

        try:
            await ensure_voice(self.bot, ctx=ctx, should_connect=True)

            await ctx.interaction.edit_original_response(
                embed=SuccessEmbed("已連接至語音頻道")
            )

        except UserInDifferentChannel:
            player: DefaultPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)


            view = View()
            view.add_item(item=Button(
                    label=str(
                        "繼續"
                    ),
                    style=ButtonStyle.green, custom_id="continue"
                ))

            await ctx.interaction.edit_original_response(
                embed=WarningEmbed(
                    "警告",
                    "機器人已經在一個頻道中了，繼續移動將會中斷對方的音樂播放，是否要繼續?"
                ),
                view=view
            )

            try:
                await self.bot.wait_for(
                    "interaction",
                    check=lambda i: i.data["custom_id"] == "continue" and i.user.id == ctx.user.id,
                    timeout=10
                )

            except TimeoutError:
                await ctx.interaction.edit_original_response(
                    embed=ErrorEmbed(
                        "已取消"
                    ),
                    view=None
                )
                return

            await player.stop()
            player.queue.clear()

            await ctx.guild.voice_client.disconnect(force=False)

            await ensure_voice(self.bot, ctx=ctx, should_connect=True)

            await ctx.interaction.edit_original_response(
                embed=SuccessEmbed("已連接至語音頻道"),
                view=None
            )

        finally:
            await update_display(
                bot=self.bot,
                player=player or self.bot.lavalink.player_manager.get(ctx.guild.id),
                new_message=await ctx.interaction.original_response(),
                delay=5,
            )

    @announcement.command(
        name="disconnect",
        description=
            "斷開與語音頻道的連接"
    )
    async def disconnect(self, ctx: ApplicationContext):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        await player.stop()
        player.queue.clear()

        await ctx.guild.voice_client.disconnect(force=False)

        await update_display(self.bot, player, await ctx.interaction.original_response())

    @announcement.command(
        name='queue',
        description="顯示播放序列"
    )
    async def queue(self, ctx: commands.Context):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )

        if not player.queue:
            return await ctx.interaction.edit_original_response(
                embed=InfoEmbed("播放序列", "播放序列中沒有歌曲")
            )


        songs_need_page = 1
        pages = []
        page_index = 0

        for iteration, songs_in_page in enumerate(split_list(player.queue, songs_need_page)):
            page_content = '\n'.join(
                [
                    f"**[{index + 1 + (iteration * songs_need_page)}]** {track.title}"
                    for index, track in enumerate(songs_in_page)
                ]
            )
            pages.append(page_content)

        total_pages = len(pages)

        async def send_page():
            embed = discord.Embed(title="<:3541854:1031106127238279168> | 播放序列", description=pages[page_index],color=discord.Colour.random())
            embed.set_footer(text=f"頁數：{page_index+1} / {total_pages}")
            embed.set_author(name='音樂系統')# , icon_url="https://your_icon_link" #可添加icon鏈結
            await ctx.interaction.edit_original_response(embed=embed, view=queue_button())

        class queue_button(View):
            def __init__(self):
                super().__init__()

            @discord.ui.button(label="上一頁", custom_id="previous_queue",emoji="<:rewinds:1138683401851908196>")
            async def previous_page(self, button: discord.ui.Button, interaction: discord.Interaction):
                nonlocal page_index
                if page_index == 0:
                    self.previous_page.disabled = True
                    await interaction.response.edit_message(view=self)

                    embed = discord.Embed(title="<:idea:1139066934797807690> | 提示", description="沒有上一頁了",color=discord.Colour.random())
                    embed.set_author(name='音樂系統')# , icon_url="https://your_icon_link" #可添加icon鏈結
                    await interaction.followup.send(embed=embed , ephemeral=True)

                elif page_index > 0:
                    page_index -= 1
                    await send_page()
                    self.previous_page.disabled = False
                    await interaction.response.edit_message(view=self)

            @discord.ui.button(label="下一頁", custom_id="next_queue",emoji="<:fastforward:1138682837722202162>")
            async def next_page(self, button: discord.ui.Button, interaction: discord.Interaction):
                nonlocal page_index
                if page_index < total_pages - 1:
                    page_index += 1
                    await send_page()
                    self.next_page.disabled = False
                    await interaction.response.edit_message(view=self)
                else:
                    self.next_page.disabled = True
                    await interaction.response.edit_message(view=self)

                    embed = discord.Embed(title="<:idea:1139066934797807690> | 提示", description="沒有下一頁了",color=discord.Colour.random())
                    embed.set_author(name='音樂系統')# , icon_url="https://your_icon_link" #可添加icon鏈結
                    await interaction.followup.send(embed=embed , ephemeral=True)
        await send_page()

    @announcement.command(
        name="repeat",
        description="更改重複播放模式",)
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

    @announcement.command(
        name="shuffle",
        description="切換隨機播放模式"
    )
    async def shuffle(self, ctx: ApplicationContext):
        await ctx.response.defer()

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
