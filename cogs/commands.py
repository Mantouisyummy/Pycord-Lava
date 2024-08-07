import re
import discord
import json


from os import getpid, path
from discord import (
    Option,
    ButtonStyle,
    Embed,
    ApplicationContext,
    AutocompleteContext,
    OptionChoice,
    Interaction
)
from discord.ext.commands import Cog
from discord.ui import Button
from lavalink import (
    LoadResult,
    LoadType,
    Timescale,
    Tremolo,
    Vibrato,
    LowPass,
    Rotation,
    Equalizer,
)
from psutil import cpu_percent, virtual_memory, Process

from lava.bot import Bot
from lava.embeds import ErrorEmbed, SuccessEmbed, InfoEmbed, WarningEmbed, LoadingEmbed
from lava.errors import UserInDifferentChannel
from lava.utils import (
    ensure_voice,
    split_list,
    bytes_to_gb,
    get_commit_hash,
    get_upstream_url,
    get_current_branch,
)
from lava.view import View
from lava.modal import PlaylistModal
from lava.paginator import Paginator
from lava.classes.player import LavaPlayer
from lava.playlist import Playlist, Mode

allowed_filters = {
    "timescale": Timescale,
    "tremolo": Tremolo,
    "vibrato": Vibrato,
    "lowpass": LowPass,
    "rotation": Rotation,
    "equalizer": Equalizer,
}


class Commands(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    music = discord.SlashCommandGroup("music", "音樂")
    playlist = discord.SlashCommandGroup("playlist", "歌單")

    async def search(self, ctx: AutocompleteContext):
        query = ctx.options["query"]
        if re.match(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            query,
        ):
            return []

        if not query:
            return []

        choices = []

        result = await self.bot.lavalink.get_tracks(f"ytmsearch:{query}")

        for track in result.tracks:
            choices.append(
                OptionChoice(
                    name=f"{track.title[:80]} by {track.author[:16]}", value=track.uri
                )
            )

        return choices

    async def playlist_search(self, ctx: AutocompleteContext):
        uid = ctx.options["playlist"]

        choices = []

        if not uid:
            playlist = Playlist.find_playlist(user_id=ctx.interaction.user.id)
            choices.append(
                OptionChoice(
                    name=playlist.name + f" ({len(playlist.to_dict()[playlist.name]['data']['tracks'])}首)", value=playlist.uid
                )
            )
            return choices
        return choices

    async def global_playlist_search(self, ctx: AutocompleteContext):
        uid = ctx.options["playlist"]

        choices = []

        if not uid:
            playlist = Playlist.find_playlist(user_id=ctx.interaction.user.id)
            choices.append(
                OptionChoice(
                    name=playlist.name + f" ({len(playlist.to_dict()[playlist.name]['data']['tracks'])}首)", value=playlist.uid
                )
            )
        else:
            playlist = Playlist.find_playlist(uid=uid, mode=Mode.GLOBAL, user_id=ctx.interaction.user.id)
            if playlist: 
                choices.append(
                    OptionChoice(
                        name=playlist.name + f" 歌單擁有者 by ({self.bot.get_user(playlist.owner_id)})", value=playlist.uid
                    )
                )
        return choices
    async def songs_search(self, ctx: AutocompleteContext):
        playlist = ctx.options["playlist"]
        song = ctx.options["song"]

        choices = []

        if not playlist:
            return []
        
        playlist = Playlist.find_playlist(uid=playlist, user_id=ctx.interaction.user.id)
        
        if playlist:
            result = LoadResult.from_dict(playlist.to_dict())

            for track in result.tracks:
                choices.append(OptionChoice(name=track.title, value=track.position))

            if not song:
                return choices

            return choices

    @music.command(name="info", description="顯示機器人資訊")
    async def info(self, ctx: ApplicationContext):
        embed = Embed(title="機器人資訊", color=0x2B2D31)

        embed.add_field(
            name="啟動時間",
            value=f"<t:{round(Process(getpid()).create_time())}:F>",
            inline=True,
        )

        branch = get_current_branch()
        upstream_url = get_upstream_url(branch)

        embed.add_field(
            name="版本資訊",
            value=f"{get_commit_hash()} on {branch} from {upstream_url}",
        )

        embed.add_field(name="​", value="​", inline=True)

        embed.add_field(name="CPU", value=f"{cpu_percent()}%", inline=True)

        embed.add_field(
            name="RAM",
            value=f"{round(bytes_to_gb(virtual_memory()[3]), 1)} GB / "
            f"{round(bytes_to_gb(virtual_memory()[0]), 1)} GB "
            f"({virtual_memory()[2]}%)",
            inline=True,
        )

        embed.add_field(name="​", value="​", inline=True)

        embed.add_field(name="伺服器數量", value=len(self.bot.guilds), inline=True)

        embed.add_field(
            name="播放器數量",
            value=len(self.bot.lavalink.player_manager.players),
            inline=True,
        )

        embed.add_field(name="​", value="​", inline=True)

        await ctx.send(embed=embed)

    @music.command(name="nowplaying", description="顯示目前正在播放的歌曲")
    async def nowplaying(self, ctx: ApplicationContext):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: LavaPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        await player.update_display(
            player, new_message=(await ctx.interaction.original_response())
        )

    @music.command(
        name="play",
        description="播放音樂",
    )
    async def play(
        self,
        ctx: ApplicationContext,
        query: Option(
            str,
            "歌曲名稱或網址，支援 YouTube, YouTube Music, SoundCloud,Spotify",
            autocomplete=search,
            name="query",
        ),
        index: Option(int, "要將歌曲放置於當前播放序列的位置", name="index", required=False),
    ):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=True)

        player: LavaPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        player.store("channel", ctx.channel.id)

        results: LoadResult = await player.node.get_tracks(query)

        # Check locals
        if not results or not results.tracks:
            self.bot.logger.info(
                "No results found with lavalink for query %s, checking local sources",
                query,
            )
            results: LoadResult = await self.bot.lavalink.get_local_tracks(query)

        if not results or not results.tracks:  # If nothing was found
            return await ctx.interaction.edit_original_response(
                embed=ErrorEmbed(
                    "沒有任何結果",
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
                ) + ' ' + ', '.join([key.capitalize() for key in player.filters])
            )
        ] if player.filters else []

        match results.load_type:
            case LoadType.TRACK:
                player.add(
                    requester=ctx.author.id, track=results.tracks[0], index=index
                )

                # noinspection PyTypeChecker
                await ctx.interaction.edit_original_response(
                    embeds=[SuccessEmbed("已加入播放序列", {results.tracks[0].title})]
                    + filter_warnings
                )

            case LoadType.PLAYLIST:
                # TODO: Ask user if they want to add the whole playlist or just some tracks

                for iter_index, track in enumerate(results.tracks):
                    player.add(
                        requester=ctx.author.id, track=track, index=index + iter_index
                    )

                # noinspection PyTypeChecker
                await ctx.interaction.edit_original_response(
                    embeds=[
                        SuccessEmbed(
                            title=f"'已加入播放序列' {len(results.tracks)} / {results.playlist_info.name}",
                            description=(
                                "\n".join(
                                    [
                                        f"**[{index + 1}]** {track.title}"
                                        for index, track in enumerate(
                                            results.tracks[:10]
                                        )
                                    ]
                                )
                                + "..."
                                if len(results.tracks) > 10
                                else ""
                            ),
                        )
                    ]
                    + filter_warnings
                )

        # If the player isn't already playing, start it.
        if not player.is_playing:
            await player.play()

        await player.update_display(await ctx.interaction.original_response())

    @music.command(name="skip", description="跳過當前播放的歌曲")
    async def skip(
        self,
        ctx: ApplicationContext,
        target: Option(int, "要跳到的歌曲編號", name="target", required=False),
        move: Option(
            int,
            "是否移除目標以前的所有歌曲，如果沒有提供 target，這個參數會被忽略",
            name="move",
            required=False,
        ),
    ):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: LavaPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

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
                player.queue = player.queue[target - 1 :]

        await player.skip()

        await ctx.interaction.edit_original_response(embed=SuccessEmbed("已跳過歌曲"))

        await player.update_display(await ctx.interaction.original_response(), delay=5)

    @music.command(name="remove", description="移除歌曲")
    async def remove(
        self,
        ctx: ApplicationContext,
        target: Option(int, "要移除的歌曲編號", name="target", required=True),
    ):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: LavaPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if len(player.queue) < target or target < 1:
            return await ctx.interaction.edit_original_response(
                embed=ErrorEmbed("無效的歌曲編號")
            )

        player.queue.pop(target - 1)

        await ctx.interaction.edit_original_response(embed=SuccessEmbed("已移除歌曲"))

        await player.update_display(await ctx.interaction.original_response(), delay=5)

    @music.command(name="clean", description="清除播放序列")
    async def clean(self, ctx: ApplicationContext):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: LavaPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        player.queue.clear()

        await ctx.interaction.edit_original_response(embed=SuccessEmbed("已清除播放序列"))

        await player.update_display(await ctx.interaction.original_response(), delay=5)

    @music.command(name="pause", description="暫停當前播放的歌曲")
    async def pause(self, ctx: ApplicationContext):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: LavaPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.interaction.edit_original_response(
                embed=ErrorEmbed("沒有正在播放的歌曲")
            )

        await player.set_pause(True)

        await ctx.interaction.edit_original_response(embed=SuccessEmbed("已暫停歌曲"))

    @music.command(name="resume", description="恢復當前播放的歌曲")
    async def resume(self, ctx: ApplicationContext):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: LavaPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.paused:
            return await ctx.interaction.edit_original_response(
                embed=ErrorEmbed("沒有暫停的歌曲")
            )

        await player.set_pause(False)

        await ctx.interaction.edit_original_response(embed=SuccessEmbed("已繼續歌曲"))

        await player.update_display(await ctx.interaction.original_response(), delay=5)

    @music.command(name="stop", description="停止播放並清空播放序列")
    async def stop(self, ctx: ApplicationContext):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: LavaPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        await player.stop()
        player.queue.clear()

        await player.update_display(await ctx.interaction.original_response())

    @music.command(name="connect", description="連接至你當前的語音頻道")
    async def connect(self, ctx: ApplicationContext):
        await ctx.response.defer()

        try:
            await ensure_voice(self.bot, ctx=ctx, should_connect=True)

            await ctx.interaction.edit_original_response(embed=SuccessEmbed("已連接至語音頻道"))

        except UserInDifferentChannel:
            player: LavaPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

            view = View()
            view.add_item(
                item=Button(
                    label=str("繼續"), style=ButtonStyle.green, custom_id="continue"
                )
            )

            await ctx.interaction.edit_original_response(
                embed=WarningEmbed(
                    "警告",
                    "機器人已經在一個頻道中了，繼續移動將會中斷對方的音樂播放，是否要繼續?",
                ),
                view=view,
            )

            try:
                await self.bot.wait_for(
                    "interaction",
                    check=lambda i: i.data["custom_id"] == "continue"
                    and i.user.id == ctx.user.id,
                    timeout=10,
                )

            except TimeoutError:
                await ctx.interaction.edit_original_response(
                    embed=ErrorEmbed("已取消"), view=None
                )
                return

            await player.stop()
            player.queue.clear()

            await ctx.guild.voice_client.disconnect(force=False)

            await ensure_voice(self.bot, ctx=ctx, should_connect=True)

            await ctx.interaction.edit_original_response(
                embed=SuccessEmbed("已連接至語音頻道"), view=None
            )

        finally:
            await player.update_display(
                new_message=await ctx.interaction.original_response(),
                delay=5,
            )

    @music.command(name="disconnect", description="斷開與語音頻道的連接")
    async def disconnect(self, ctx: ApplicationContext):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: LavaPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        await player.stop()
        player.queue.clear()

        await ctx.guild.voice_client.disconnect(force=False)

        await player.update_display(await ctx.interaction.original_response())

    @music.command(name="queue", description="顯示播放序列")
    async def queue(self, ctx: ApplicationContext):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: LavaPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.queue:
            return await ctx.interaction.edit_original_response(
                embed=InfoEmbed("播放序列", "播放序列中沒有歌曲")
            )

        pages: list[InfoEmbed] = []

        for iteration, songs_in_page in enumerate(split_list(player.queue, 10)):
            pages.append(
                InfoEmbed(
                    title="播放序列",
                    description="\n".join(
                        [
                            f"**[{index + 1 + (iteration * 10)}]** {track.title}"
                            f" {'🔥' if not track.requester else ''}"
                            for index, track in enumerate(songs_in_page)
                        ]
                    ),
                )
            )

        await ctx.interaction.edit_original_response(
            embed=pages[0], view=Paginator(pages, ctx.author.id, None)
        )

    @music.command(name="repeat", description="更改重複播放模式")
    async def repeat(
        self,
        ctx: ApplicationContext,
        mode: Option(
            name="mode",
            description="重複播放模式",
            choices=[
                OptionChoice(name="關閉", value=f"{'關閉'}/0"),
                OptionChoice(name="單曲", value=f"{'單曲'} 單曲/1"),
                OptionChoice(name="整個序列", value=f"{'整個序列'} 整個序列/2"),
            ],
            required=True,
        ),
    ):
        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: LavaPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        player.set_loop(int(mode.split("/")[1]))

        await ctx.response.send_message(
            embed=SuccessEmbed(f"{'成功將重複播放模式更改為'}: {mode.split('/')[0]}")
        )

        await player.update_display(await ctx.interaction.original_response(), delay=5)

    @music.command(name="shuffle", description="切換隨機播放模式")
    async def shuffle(self, ctx: ApplicationContext):
        await ctx.response.defer()

        await ensure_voice(self.bot, ctx=ctx, should_connect=False)

        player: LavaPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        player.set_shuffle(not player.shuffle)

        await ctx.interaction.edit_original_response(
            embed=SuccessEmbed(f"{'隨機播放模式'}：{'開啟' if player.shuffle else '關閉'}")
        )

        await player.update_display(await ctx.interaction.original_response(), delay=5)

    @music.command(
        name="timescale",
        description="修改歌曲的速度、音調",
    )
    async def timescale(
        self,
        ctx: ApplicationContext,
        speed: Option(float, name="speed", description="速度 (≥ 0.1)", required=True),
        pitch: Option(float, name="pitch", description="音調 (≥ 0.1)", required=True),
        rate: Option(float, name="rate", description="速率 (≥ 0.1)", required=True),
    ):
        interaction = ctx.interaction
        kwargs = {"speed": speed, "pitch": pitch, "rate": rate}
        await self.update_filter(interaction, "timescale", **kwargs)

    @music.command(name="tremolo", description="為歌曲增加一個「顫抖」的效果")
    async def tremolo(
        self,
        ctx: ApplicationContext,
        frequency: Option(
            float, name="frequency", description="頻率 (0 < n)", required=True
        ),
        depth: Option(
            float, name="depth", description="強度 (0 < n ≤ 1)", required=True
        ),
    ):
        interaction = ctx.interaction
        kwargs = {"frequency": frequency, "depth": depth}
        await self.update_filter(interaction, "tremolo", **kwargs)

    @music.command(name="vibrato", description="為歌曲增加一個「震動」的效果")
    async def vibrato(
        self,
        ctx: ApplicationContext,
        frequency: Option(
            float, name="frequency", description="頻率 (0 < n)", required=True
        ),
        depth: Option(
            float, name="depth", description="強度 (0 < n ≤ 1)", required=True
        ),
    ):
        interaction = ctx.interaction
        kwargs = {"frequency": frequency, "depth": depth}
        await self.update_filter(interaction, "vibrato", **kwargs)

    @music.command(
        name="rotation",
        description="8D 環繞效果",
    )
    async def rotation(
        self,
        ctx: ApplicationContext,
        rotation_hz: Option(
            float, name="rotation_hz", description="頻率 (0 ≤ n)", required=True
        ),
    ):
        interaction = ctx.interaction
        kwargs = {"rotation_hz": rotation_hz}
        await self.update_filter(interaction, "rotation", **kwargs)

    @music.command(name="lowpass", description="低音增強 (削弱高音)")
    async def lowpass(
        self,
        ctx: ApplicationContext,
        smoothing: Option(
            int, name="smoothing", description="強度 (1 < n)", required=True
        ),
    ):
        interaction = ctx.interaction
        kwargs = {"smoothing": smoothing}
        await self.update_filter(interaction, "lowpass", **kwargs)

    @music.command(
        name="bassboost",
        description="低音增強 (等化器)",
    )
    async def bassboost(self, ctx: ApplicationContext):
        interaction = ctx.interaction

        player: LavaPlayer = self.bot.lavalink.player_manager.get(interaction.guild.id)

        audio_filter = player.get_filter("equalizer")

        if not audio_filter:
            await self.update_filter(
                interaction,
                "equalizer",
                player=player,
                bands=[(0, 0.3), (1, 0.2), (2, 0.1)],
            )
            return

        await self.update_filter(interaction, "equalizer", player=player)

    async def update_filter(
        self,
        interaction: Interaction,
        filter_name: str,
        player: LavaPlayer = None,
        **kwargs,
    ):
        await interaction.response.defer()

        await ensure_voice(interaction, should_connect=False)

        if not player:
            player: LavaPlayer = self.bot.lavalink.player_manager.get(
                interaction.guild.id
            )
        if not kwargs:
            await player.remove_filter(filter_name)

            await interaction.edit_original_response(
                embed=SuccessEmbed(f"'已移除效果器'：{allowed_filters[filter_name].__name__}")
            )

            await player.update_display(await interaction.original_response(), delay=5)

            return

        audio_filter = player.get_filter(filter_name) or allowed_filters[filter_name]()

        try:
            audio_filter.update(**kwargs)

        except ValueError:
            await interaction.edit_original_response(embed=ErrorEmbed("請輸入有效的參數"))
            return

        await player.set_filter(audio_filter)

        await interaction.edit_original_response(
            embed=SuccessEmbed(f"'已設置效果器'：{allowed_filters[filter_name].__name__}")
        )

        await player.update_display(await interaction.original_response(), delay=5)

    @playlist.command(name="create", description="建立一個歌單")
    async def create(
        self,
        ctx: ApplicationContext,
        name: Option(str, "清單名稱", name="name", required=True),
        public: Option(
            bool,
            "是否公開",
            name="public",
            choices=[
                OptionChoice(name="True", value=True),
                OptionChoice(name="False", value=False),
            ],
            required=True,
        ),
    ):
        await ctx.response.defer()

        if path.isfile(f"./playlist/{ctx.author.id}.json"):
            with open(f"./playlist/{ctx.author.id}.json", "r", encoding="utf-8") as f:
                data = json.load(f)

            if name not in data.keys():
                data = {
                        name: {
                            "public": public,
                            "loadType": "playlist",
                            "data": {
                                "info": {"name": name, "selectedTrack": -1},
                                "pluginInfo": {},
                                "tracks": [],
                            },
                        },
                    }

                with open(
                    f"./playlist/{ctx.author.id}.json", "w", encoding="utf-8"
                ) as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
            else:
                return await ctx.interaction.edit_original_response(
                    embed=ErrorEmbed(f"你已經有同名的歌單了!")
                )
        else:
            with open(f"./playlist/{ctx.author.id}.json", "w", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            name: {
                                "public": public,
                                "loadType": "playlist",
                                "data": {
                                    "info": {"name": name, "selectedTrack": -1},
                                    "pluginInfo": {},
                                    "tracks": [],
                                },
                            },
                        },
                        indent=4,
                        ensure_ascii=False,
                    )
                )

        await ctx.interaction.edit_original_response(
            embed=SuccessEmbed(f"建立成功! 名稱為: `{name}`")
        )

    @playlist.command(name="public", description="切換歌單的公開狀態")
    async def public(
        self,
        ctx: ApplicationContext,
        playlist: Option(
            str,
            "清單名稱",
            name="playlist",
            required=True,
            autocomplete=playlist_search,
        ),
        public: Option(
            bool,
            "是否公開",
            name="public",
            choices=[
                OptionChoice(name="是", value=True),
                OptionChoice(name="否", value=False),
            ],
            required=True,
        ),
    ):
        await ctx.response.defer()

        if path.isfile(f"./playlist/{ctx.author.id}.json"):
            with open(f"./playlist/{ctx.author.id}.json", "r", encoding="utf-8") as f:
                data = json.load(f)

            playlist_info = Playlist.find_playlist(uid=playlist, user_id=ctx.author.id)

            if playlist is None:
                return await ctx.interaction.edit_original_response(embed=ErrorEmbed(f"你沒有播放清單!"))

            data[playlist_info.name]["public"] = public

            with open(f"./playlist/{ctx.author.id}.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        else:
            await ctx.interaction.edit_original_response(embed=ErrorEmbed(f"你沒有播放清單!"))

        await ctx.interaction.edit_original_response(
            embed=SuccessEmbed(f"已切換公開狀態為 `{'公開' if public is True else '非公開'}`")
        )

    @playlist.command(name="rename", description="重命名一個歌單")
    async def rename(
        self,
        ctx: ApplicationContext,
        playlist: Option(
            str,
            "清單名稱",
            name="playlist",
            autocomplete=playlist_search,
            required=True,
        ),
        newname: Option(str, "新名稱", name="name", required=True),
    ):
        await ctx.response.defer()

        await ctx.interaction.edit_original_response(
            embed=LoadingEmbed(title="正在讀取中...")
        )

        with open(f"./playlist/{ctx.author.id}.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        playlist_info = Playlist.find_playlist(uid=playlist, user_id=ctx.author.id)
        
        if Playlist.comparison(playlist_info, user_id=ctx.author.id):
            data[newname] = data.pop(playlist_info.name)

            with open(f"./playlist/{ctx.author.id}.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            await ctx.interaction.edit_original_response(
                embed=SuccessEmbed(f"更名成功! 新的名字為 `{newname}`")
            )
        else:
            return await ctx.interaction.edit_original_response(
                embed=ErrorEmbed(f"這不是你的播放清單!")
            )

    @playlist.command(name="join", description="加入歌曲至指定的歌單")
    async def join(
        self,
        ctx: ApplicationContext,
        playlist: Option(
            str, "歌單", name="playlist", required=True, autocomplete=playlist_search
        ),
        query: Option(
            str,
            "歌曲名稱，支援 YouTube, YouTube Music, SoundCloud,Spotify (如不填入將切至輸入網址畫面)",
            autocomplete=search,
            name="query",
            default=False,
        ),
    ):
        playlist_info = Playlist.find_playlist(uid=playlist, user_id=ctx.author.id)

        if query is False:
            with open(f"./playlist/{ctx.author.id}.json", "r", encoding="utf-8") as f:
                data = json.load(f)

            modal = PlaylistModal(title="加入歌曲", name=playlist_info.name, bot=self.bot)
            await ctx.send_modal(modal)

        else:
            await ctx.defer()

            await ctx.interaction.edit_original_response(
                embed=LoadingEmbed(title="正在讀取中...")
            )

            with open(f"./playlist/{ctx.user.id}.json", "r", encoding="utf-8") as f:
                data = json.load(f)

            if Playlist.comparison(playlist_info, user_id=ctx.author.id):
                result: LoadResult = await self.bot.lavalink.get_tracks(
                    query, check_local=True
                )

                for track in result.tracks:
                    data[playlist_info.name]["data"]["tracks"].append(
                        {
                            "encoded": track.track,
                            "info": {
                                "identifier": track.identifier,
                                "isSeekable": track.is_seekable,
                                "author": track.author,
                                "length": track.duration,
                                "isStream": track.stream,
                                "position": track.position,
                                "title": track.title,
                                "uri": track.uri,
                                "sourceName": track.source_name,
                                "artworkUrl": track.artwork_url,
                                "isrc": track.isrc,
                            },
                            "pluginInfo": track.plugin_info,
                            "userData": track.user_data,
                        },
                    )

                data[playlist_info.name]["data"]["tracks"] = data[playlist_info.name]["data"]["tracks"]
                
                with open(f"./playlist/{ctx.user.id}.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)

                await ctx.interaction.edit_original_response(
                    embed=SuccessEmbed(title=f"添加成功!")
                )

    @playlist.command(name="remove", description="移除歌曲至指定的歌單")
    async def remove(
        self,
        ctx: ApplicationContext,
        playlist: Option(
            str, "歌單", name="playlist", required=True, autocomplete=playlist_search
        ),
        song: Option(int, "歌曲", name="song", required=True, autocomplete=songs_search),
    ):
        await ctx.defer()

        await ctx.interaction.edit_original_response(
            embed=LoadingEmbed(title="正在讀取中...")
        )

        with open(
            f"./playlist/{ctx.interaction.user.id}.json", "r", encoding="utf-8"
        ) as f:
            data = json.load(f)

        playlist_info = Playlist.find_playlist(uid=playlist, user_id=ctx.author.id)

        del data[playlist_info.name]["data"]["tracks"][song]

        with open(
            f"./playlist/{ctx.interaction.user.id}.json", "w", encoding="utf-8"
        ) as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        await ctx.interaction.edit_original_response(
            embed=SuccessEmbed(title="成功從歌單移除歌曲")
        )

    @playlist.command(name="delete", description="移除指定的歌單")
    async def delete(
        self,
        ctx: ApplicationContext,
        playlist: Option(
            str, "歌單", name="playlist", required=True, autocomplete=playlist_search
        ),
    ):
        await ctx.defer()

        await ctx.interaction.edit_original_response(
            embed=LoadingEmbed(title="正在讀取中...")
        )

        with open(
            f"./playlist/{ctx.interaction.user.id}.json", "r", encoding="utf-8"
        ) as f:
            data = json.load(f)

        playlist_info = Playlist.find_playlist(uid=playlist, user_id=ctx.author.id)

        del data[playlist_info.name]

        with open(
            f"./playlist/{ctx.interaction.user.id}.json", "w", encoding="utf-8"
        ) as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        await ctx.interaction.edit_original_response(embed=SuccessEmbed(title="成功移除歌單"))

    @playlist.command(name="play", description="播放歌單中的歌曲")
    async def playlist_play(
        self,
        ctx: ApplicationContext,
        playlist: Option(
            str,
            "歌單",
            name="playlist",
            required=True,
            autocomplete=global_playlist_search,
        ),
    ):
        await ctx.response.defer()

        try:
            await ctx.interaction.edit_original_response(
                embed=LoadingEmbed(title="正在讀取中...")
            )

            playlist_info = Playlist.find_playlist(uid=playlist, user_id=ctx.author.id, mode=Mode.GLOBAL)

            if playlist_info is (None or False):
                return await ctx.interaction.edit_original_response(embed=ErrorEmbed(title="此歌單為非公開!"))

            with open(f"./playlist/{playlist_info.owner_id}.json", "r", encoding="utf-8") as f:
                data = json.load(f)

            if not data[playlist_info.name]["data"]["tracks"]:
                return await ctx.interaction.edit_original_response(
                    embed=InfoEmbed("歌單", "歌單中沒有歌曲")
                )

            await ensure_voice(self.bot, ctx=ctx, should_connect=True)

            player: LavaPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

            filter_warnings = (
                [
                    InfoEmbed(
                        title="提醒",
                        description=str(
                            "偵測到 效果器正在運作中，\n"
                            "這可能會造成音樂聲音有變形(加速、升高等)的情形產生，\n"
                            "如果這不是你期望的，可以透過效果器的指令來關閉它們\n"
                            "指令名稱通常等於效果器名稱，例如 `/timescale` 就是控制 Timescale 效果器\n\n"
                            "以下是正在運行的效果器："
                        ),
                    )
                    + " "
                    + ", ".join([key.capitalize() for key in player.filters])
                ]
                if player.filters
                else []
            )

            player.store("channel", ctx.channel.id)

            index = sum(1 for t in player.queue if t.requester)

            results = LoadResult.from_dict(data[playlist_info.name])

            for iter_index, track in enumerate(results.tracks):
                player.add(
                    requester=ctx.author.id, track=track, index=index + iter_index
                )

            await ctx.interaction.edit_original_response(
                embeds=[
                    SuccessEmbed(
                        title=f"已加入播放序列 {len(results.tracks)}首 / {results.playlist_info.name}",
                        description=(
                            "\n".join(
                                [
                                    f"**[{index + 1}]** {track.title}"
                                    for index, track in enumerate(results.tracks[:10])
                                ]
                            )
                            + "..."
                            if len(results.tracks) > 10
                            else ""
                        ),
                    )
                ]
                + filter_warnings
            )

            # If the player isn't already playing, start it.
            if not player.is_playing:
                await player.play()

            await player.update_display(
                await ctx.interaction.original_response(), delay=5
            )

        except TypeError as e:
            pass

    @playlist.command(name="info", description="查看指定歌單的資訊")
    async def info(
        self,
        ctx: ApplicationContext,
        playlist: Option(
            str,
            "歌單",
            name="playlist",
            required=True,
            autocomplete=global_playlist_search,
        ),
    ):
        await ctx.defer()

        playlist_info = Playlist.find_playlist(uid=playlist, user_id=ctx.author.id, mode=Mode.GLOBAL)

        if playlist_info is (None or False):
            return await ctx.interaction.edit_original_response(embed=ErrorEmbed(title="此歌單為非公開!"))
        else:
            if ctx.author.id == playlist_info.owner_id:
                try:
                    with open(
                        f"./playlist/{ctx.author.id}.json", "r", encoding="utf-8"
                    ) as f:
                        data = json.load(f)

                    if not data[playlist_info.name]["data"]["tracks"]:
                        return await ctx.interaction.edit_original_response(
                            embed=InfoEmbed("歌單", "歌單中沒有歌曲")
                        )

                    results = LoadResult.from_dict(data[playlist_info.name])

                    pages: list[InfoEmbed] = []

                    for iteration, songs_in_page in enumerate(
                        split_list(results.tracks, 10)
                    ):
                        pages.append(
                            InfoEmbed(
                                title=f"{playlist_info.name} - 歌單資訊",
                                description="\n".join(
                                    [
                                        f"**[{index + 1 + (iteration * 10)}]** [{track.title}]({track.uri}) ({LavaPlayer._format_time((track.duration))}) by {track.author}"
                                        for index, track in enumerate(songs_in_page)
                                    ]
                                ),
                            ).set_footer(text=f"ID: {playlist}")
                        )
                    await ctx.interaction.edit_original_response(
                        embed=pages[0], view=Paginator(pages, ctx.author.id, None)
                    )
                except TypeError:
                    pass
            else:

                with open(f"./playlist/{playlist_info.owner_id}.json", "r", encoding="utf-8") as f:
                    data = json.load(f)

                if not data[playlist_info.name]["data"]["tracks"]:
                    return await ctx.interaction.edit_original_response(
                        embed=InfoEmbed("歌單", "歌單中沒有歌曲")
                    )

                results = LoadResult.from_dict(data[playlist_info.name])

                pages: list[InfoEmbed] = []

                for iteration, songs_in_page in enumerate(
                    split_list(results.tracks, 10)
                ):
                    pages.append(
                        InfoEmbed(
                            title=f"{playlist_info.name} - 歌單資訊 by {self.bot.get_user(int(playlist_info.owner_id)).name}",
                            description="\n".join(
                                [
                                    f"**[{index + 1 + (iteration * 10)}]** {track.title}"
                                    for index, track in enumerate(songs_in_page)
                                ]
                            ),
                        ).set_footer(text=f"ID: {playlist}")
                    )
                await ctx.interaction.edit_original_response(
                    embed=pages[0], view=Paginator(pages, ctx.author.id, None)
                )


def setup(bot):
    bot.add_cog(Commands(bot))
