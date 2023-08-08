import asyncio
import subprocess
from typing import Union, Iterable, Optional

from discord import ApplicationContext, Message, Thread, TextChannel, Embed, NotFound, Colour, ButtonStyle, Interaction
from discord.abc import GuildChannel
from discord.ui import Button
from discord.utils import get
from lavalink import DefaultPlayer, parse_time, DeferredAudioTrack, LoadResult
from spotipy import Spotify

from core.bot import Bot
from core.errors import UserNotInVoice, MissingVoicePermissions, BotNotInVoice, UserInDifferentChannel
from core.sources.track import SpotifyAudioTrack
from core.variables import Variables
from core.voice_client import LavalinkVoiceClient
from core.view import View


def get_current_branch() -> str:
    """
    Get the current branch of the git repository
    :return: The current branch
    """
    output = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
    return output.strip().decode()


def get_upstream_url(branch: str) -> Optional[str]:
    """
    Get the upstream url of the branch
    :param branch: The branch to get the upstream url of
    :return: The upstream url, or None if it doesn't exist
    """
    try:
        output = subprocess.check_output(['git', 'config', '--get', f'branch.{branch}.remote'])
    except subprocess.CalledProcessError:
        return None

    remote_name = output.strip().decode()

    output = subprocess.check_output(['git', 'config', '--get', f'remote.{remote_name}.url'])
    return output.strip().decode()


def get_commit_hash() -> str:
    """
    Get the commit hash of the current commit.
    :return: The commit hash
    """
    return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('utf-8').strip()


def bytes_to_gb(bytes_: int) -> float:
    """
    Convert bytes to gigabytes.

    :param bytes_: The number of bytes.
    """
    return bytes_ / 1024 ** 3


def split_list(input_list, chunk_size) -> Iterable[list]:
    length = len(input_list)

    num_sublists = length // chunk_size

    for i in range(num_sublists):
        yield input_list[i * chunk_size:(i + 1) * chunk_size]

    if length % chunk_size != 0:
        yield input_list[num_sublists * chunk_size:]


async def ensure_voice(bot:Bot, should_connect: bool, interaction: Interaction = None, ctx:ApplicationContext = None) -> LavalinkVoiceClient:
    """
    This check ensures that the bot and command author are in the same voice channel.

    :param ctx: The ctx that triggered the command.
    :param should_connect: Whether the bot should connect to the voice channel if it isn't already connected.
    """

    if ctx:
        player = bot.lavalink.player_manager.create(ctx.author.guild.id)
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise UserNotInVoice('Please join a voice channel first')

        v_client = get(ctx.bot.voice_clients, guild=ctx.author.guild)

        if not v_client:
            if not should_connect:
                raise BotNotInVoice('Bot is not in a voice channel.')

            permissions = ctx.author.voice.channel.permissions_for(
                ctx.author.guild.get_member(ctx.bot.user.id)
            )

            if not permissions.connect or not permissions.speak:  # Check user limit too?
                raise MissingVoicePermissions('Connect and Speak permissions is required in order to play music')

            player.store('channel', ctx.channel.id)

            # noinspection PyTypeChecker
            return await ctx.author.voice.channel.connect(cls=LavalinkVoiceClient)

        if v_client.channel.id != ctx.author.voice.channel.id:
            raise UserInDifferentChannel(
                v_client.channel, "User must be in the same voice channel as the bot"
            )
    else:
        player = bot.lavalink.player_manager.create(interaction.user.guild.id)

        if not interaction.user.voice or not interaction.user.voice.channel:
            raise UserNotInVoice('Please join a voice channel first')

        v_client = get(bot.voice_clients, guild=interaction.user.guild)

        if not v_client:
            if not should_connect:
                raise BotNotInVoice('Bot is not in a voice channel.')

            permissions = interaction.user.voice.channel.permissions_for(
                interaction.user.guild.get_member(ctx.bot.user.id)
            )

            if not permissions.connect or not permissions.speak:  # Check user limit too?
                raise MissingVoicePermissions('Connect and Speak permissions is required in order to play music')

            player.store('channel', interaction.channel.id)

            # noinspection PyTypeChecker
            return await interaction.user.voice.channel.connect(cls=LavalinkVoiceClient)

        if v_client.channel.id != interaction.user.voice.channel.id:
            raise UserInDifferentChannel(
                v_client.channel, "User must be in the same voice channel as the bot"
            )


def toggle_autoplay(player: DefaultPlayer) -> None:
    """
    Toggle autoplay for the player.

    :param player: The player instance.
    """
    if player.fetch("autoplay"):
        player.delete("autoplay")

        for item in player.queue:  # Remove songs added by autoplay
            if not item.requester:
                player.queue.remove(item)

    else:
        player.store("autoplay", "1")


async def get_recommended_tracks(spotify: Spotify,
                                 player: DefaultPlayer,
                                 tracks: list[DeferredAudioTrack],
                                 amount: int = 10) -> list[SpotifyAudioTrack]:
    """
    Get recommended tracks from the given track.

    :param spotify: The spotify instance.
    :param player: The player instance.
    :param tracks: The seed tracks to get recommended tracks from.
    :param amount: The amount of recommended tracks to get.
    """
    seed_tracks = []

    for track in tracks:
        if not isinstance(track, SpotifyAudioTrack):
            try:
                result = spotify.search(f"{track.title} by {track.author}", type="track", limit=1)

                seed_tracks.append(result["tracks"]["items"][0]["id"])

            except IndexError:
                continue

            continue

        seed_tracks.append(track.identifier)

    recommendations = spotify.recommendations(seed_tracks=seed_tracks, limit=amount)

    output = []

    for track in recommendations["tracks"]:
        load_result: LoadResult = await player.node.get_tracks(track['external_urls']['spotify'], check_local=True)

        output.append(load_result.tracks[0])

    return output


async def update_display(bot: Bot, player: DefaultPlayer, new_message: Message = None, delay: int = 0,
                         interaction: Interaction = None) -> None:
    """
    Update the display of the current song.

    Note: If new message is provided, Old message will be deleted after 5 seconds

    :param bot: The bot instance.
    :param player: The player instance.
    :param new_message: The new message to update the display with, None to use the old message.
    :param delay: The delay in seconds before updating the display.
    :param ctx: The ctx to be responded to.
    :param locale: The locale to use.
    """

    bot.logger.info(
        "Updating display for player in guild %s in a %s seconds delay", bot.get_guild(player.guild_id), delay
    )

    await asyncio.sleep(delay)

    # noinspection PyTypeChecker
    channel: Union[GuildChannel, TextChannel, Thread] = bot.get_channel(int(player.fetch('channel')))

    try:
        message: Message = await channel.fetch_message(int(player.fetch('message')))
    except (TypeError, NotFound):  # Message not found
        if not new_message:
            raise ValueError("No message found or provided to update the display with")

    if new_message:
        try:
            bot.logger.debug(
                "Deleting old existing display message for player in guild %s", bot.get_guild(player.guild_id)
            )

            bot.loop.create_task(message.delete())
        except (AttributeError, UnboundLocalError):
            pass

        message = new_message

    if not player.is_connected or not player.current:
        components = []

    else:
        components = [
                Button(
                    style=ButtonStyle.green if player.shuffle else ButtonStyle.grey,
                    emoji="<:world:1076721234152276038>",
                    custom_id="control.shuffle",
                    row=0
                ),
                Button(
                    style=ButtonStyle.grey,
                    emoji="<:_left:1130794030771470407>",
                    custom_id="control.previous",
                    row=0
                ),
                Button(
                    style=ButtonStyle.green,
                    emoji="<:pause:1130474848364273684>",
                    custom_id="control.pause"
                ) if not player.paused else Button(
                    style=ButtonStyle.red,
                    emoji="<:dots:1086991737395875920>",
                    custom_id="control.resume",
                    row=0
                ),
                Button(
                    style=ButtonStyle.grey,
                    emoji="<:_right:1130793817575006218>",
                    custom_id="control.next",
                    row=0
                ),
                Button(
                    style=[ButtonStyle.grey, ButtonStyle.green, ButtonStyle.blurple][player.loop],
                    emoji="<:sync:1130482503497551992>",
                    custom_id="control.repeat",
                    row=0
                ),
                Button(
                    style=ButtonStyle.green if player.fetch("autoplay") else ButtonStyle.grey,
                    emoji="<:file:1115287404174135346>",
                    custom_id="control.autoplay",
                    disabled=not bool(Variables.SPOTIFY_CLIENT),
                    row=1
                ),
                Button(
                    style=ButtonStyle.grey,
                    emoji="<:left:1130794140502863943>",
                    custom_id="control.rewind",
                    row=1
                ),
                Button(
                    style=ButtonStyle.red,
                    emoji="<:delete:1076130754146357310>",
                    custom_id="control.stop",
                    row=1
                ),
                Button(
                    style=ButtonStyle.grey,
                    emoji="<:right:1130794177827962931>",
                    custom_id="control.forward",
                    row=1
                ),
                Button(
                    style=ButtonStyle.grey,
                    emoji="<:crossmark:1127265792640163840>",
                    custom_id="control.empty",
                    row=1
                )
            ]
    
    view = View()
    if view.children == []:
        for item in components:
            view.add_item(item)

    if interaction:
        await interaction.response.edit_message(embed=generate_display_embed(bot, player), view=view)
    else:
        await message.edit(embed=generate_display_embed(bot, player), view=view)

    bot.logger.debug("Updating player in guild %s display message to %s", bot.get_guild(player.guild_id), message.id)

    player.store('message', message.id)


def generate_display_embed(bot: Bot, player: DefaultPlayer) -> Embed:
    embed = Embed()

    if player.is_playing:
        embed.set_author(
            name="播放中",
            icon_url="https://cdn.discordapp.com/emojis/987643956403781692.webp"
        )

        embed.colour = 0x2e2e2e

    elif player.paused:
        embed.set_author(
            name="已暫停",
            icon_url="https://cdn.discordapp.com/emojis/987661771609358366.webp"
        )

        embed.colour = Colour.orange()

    elif not player.is_connected:
        embed.set_author(
            name="已斷線",
            icon_url="https://cdn.discordapp.com/emojis/987646268094439488.webp"
        )

        embed.colour = 0x2e2e2e

    elif not player.current:
        embed.set_author(
            name="已結束",
            icon_url="https://cdn.discordapp.com/emojis/987645074450034718.webp"
        )

        embed.colour = 0x2e2e2e

    loop_mode_text = {
        0: '關閉',
        1: '單曲',
        2: '整個序列'
    }

    if player.current:
        embed.title = " "
        embed.set_author(name=f"{player.current.title}", icon_url=(bot.user.display_avatar.url))
        embed.description = f"`{format_time(player.position)}`" \
                            f" {generate_progress_bar(bot, player.current.duration, player.position)} " \
                            f"`{format_time(player.current.duration)}`"

        embed.add_field(name="<:user:1089127891423477800> ` 歌曲作者 `", value=f"**{player.current.author}**", inline=True)
        embed.add_field(
            name="<:slash_command:1115945935806156810> ` 點播者 `",
            value="**自動播放**" if not player.current.requester else f"**<@{player.current.requester}>**",
            inline=True
        )  # Requester will be 0 if the song is added by autoplay
        embed.add_field(
            name="<:sync:1130482503497551992> ` 重複播放 `", value=f"**{loop_mode_text[player.loop]}**",
            inline=True
        )

        embed.add_field(
            name="<:file:1115287404174135346> ` 播放清單 `",
            value=('\n'.join(
                [
                    f"**[{index + 1}]** {track.title}"
                    for index, track in enumerate(player.queue[:5])
                ]
            ) + (f"**\n還有更多...**" if len(player.queue) > 5 else "")) or
                  "**空**",
            inline=True
        )
        embed.add_field(
            name="<:setting:1068454475871817799> ` 效果器狀態 `",
            value=', '.join([key.capitalize() for key in player.filters]) or "**無**",
            inline=True
        )
        embed.add_field(
            name="<:world:1076721234152276038> ` 隨機播放 `",
            value="**開啟**"
            if player.shuffle else "**關閉**",
            inline=True
        )

    else:
        embed.title = "沒有正在播放的音樂"

    return embed


def format_time(time: Union[float, int]) -> str:
    """
    Formats the time into DD:HH:MM:SS
    :param time: Time in milliseconds
    :return: Formatted time
    """
    days, hours, minutes, seconds = parse_time(round(time))

    days, hours, minutes, seconds = map(round, (days, hours, minutes, seconds))

    return f"{str(minutes).zfill(2)}:{str(seconds).zfill(2)}"


def generate_progress_bar(bot: Bot, duration: Union[float, int], position: Union[float, int]):
    """
    Generate a progress bar.

    :param bot: The bot instance.
    :param duration: The duration of the song.
    :param position: The current position of the song.
    :return: The progress bar.
    """
    duration = round(duration / 1000)
    position = round(position / 1000)

    if duration == 0:
        duration += 1

    percentage = position / duration

    return f"<:1:1134114363725316138>" \
           f"{'<:2__:1134114356938952704>' * round(percentage * 10)}" \
           f"{'<:2__:1134114356938952704>' if percentage != 1 else '<:2__:1134114356938952704>'}" \
           f"{'<:2:1134114366636183612>' * round((1 - percentage) * 10)}" \
           f"{'<:2:1134114366636183612>' if percentage != 1 else '<:2:1134114366636183612>'}" \
           f"<:3:1134114358813794384>"
