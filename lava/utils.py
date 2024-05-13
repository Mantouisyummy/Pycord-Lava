import subprocess
from io import BytesIO
from typing import Iterable, Optional, TYPE_CHECKING, Tuple, Union

import aiohttp
import imageio
import youtube_related
import youtube_search
from discord import ApplicationContext, AutocompleteContext, Interaction
from disnake.utils import get
from lavalink import AudioTrack

from lava.classes.voice_client import LavalinkVoiceClient
from lava.errors import UserNotInVoice, BotNotInVoice, MissingVoicePermissions, UserInDifferentChannel
from lava.embeds import ErrorEmbed
from lava.playlist import Playlist



if TYPE_CHECKING:
    from lava.classes.player import LavaPlayer

def check_remote_diff():
    local_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip().decode('utf-8')

    remote_commit = subprocess.check_output(['git', 'ls-remote', 'origin', 'HEAD']).split()[0].decode('utf-8')
    
    if local_commit != remote_commit:
        subprocess.call(['git', 'pull'])

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


def split_list(input_list, chunk_size) -> Iterable[list[AudioTrack]]:
    length = len(input_list)

    num_sublists = length // chunk_size

    for i in range(num_sublists):
        yield input_list[i * chunk_size:(i + 1) * chunk_size]

    if length % chunk_size != 0:
        yield input_list[num_sublists * chunk_size:]

async def find_playlist(playlist:str, ctx: ApplicationContext | AutocompleteContext) -> Union[Tuple[str, Optional[str]], int]:
    """
    Find a playlist by uuid.

    :param playlist: The uuid of the playlist.
    :param ctx: The application context.
    :param public: Flag indicating whether to search for public playlists.
    :return: A tuple containing the title and ID of the found playlist if it exists and meets the criteria,
             or -1 if the playlist doesn't exist or doesn't meet the criteria.
             or -1 if the playlist doesn't exist or doesn't meet the criteria.
    """

    result = Playlist.from_uuid(playlist)

    if isinstance(ctx, ApplicationContext): 
        if result.public is False and result.user_id != ctx.author.id:
            await ctx.interaction.edit_original_response(embed=ErrorEmbed(
                title="此歌單是非公開的!"
            ))
        elif (result.public is False or result.public is True or result.public is None) and result.user_id == ctx.author.id:
            return result.name, result.user_id
        else:
            return result.name, result.user_id

    result = Playlist.from_uuid(playlist)

    if isinstance(ctx, ApplicationContext): 
        if result.public is False and result.user_id != ctx.author.id:
            await ctx.interaction.edit_original_response(embed=ErrorEmbed(
                title="此歌單是非公開的!"
            ))
        elif (result.public is False or result.public is True or result.public is None) and result.user_id == ctx.author.id:
            return result.name, result.user_id
        else:
            return result.name, result.user_id
    else:
        if result.public is False and result.user_id != ctx.interaction.user.id:
            await ctx.interaction.edit_original_response(embed=ErrorEmbed(
                title="此歌單是非公開的!"
            ))
        elif (result.public is False or result.public is True or result.public is None) and result.user_id == ctx.interaction.user.id:
            return result.name, result.user_id
        if result.public is False and result.user_id != ctx.interaction.user.id:
            await ctx.interaction.edit_original_response(embed=ErrorEmbed(
                title="此歌單是非公開的!"
            ))
        elif (result.public is False or result.public is True or result.public is None) and result.user_id == ctx.interaction.user.id:
            return result.name, result.user_id
        else:
            return result.name, result.user_id

async def ensure_voice(bot, should_connect: bool, interaction: Interaction = None, ctx:ApplicationContext = None) -> LavalinkVoiceClient:
    """
    This check ensures that the bot and command author are in the same voice channel.

    :param interaction: The interaction that triggered the command.
    :param should_connect: Should the bot connect to the channel if not connected.s
    """
    if interaction:
        if not interaction.user.voice or not interaction.user.voice.channel:
            raise UserNotInVoice('Please join a voice channel first')

        voice_client = get(bot.voice_clients, guild=interaction.user.guild)

        if not voice_client:
            if not should_connect:
                raise BotNotInVoice('Bot is not in a voice channel.')

            permissions = interaction.user.voice.channel.permissions_for(
                interaction.user.guild.get_member(interaction.user.id)
            )

            if not permissions.connect or not permissions.speak:  # Check user limit too?
                raise MissingVoicePermissions('Connect and Speak permissions is required in order to play music')

            # noinspection PyTypeChecker
            return await interaction.user.voice.channel.connect(cls=LavalinkVoiceClient)

        if voice_client.channel.id != interaction.user.voice.channel.id:
            raise UserInDifferentChannel(
                voice_client.channel, "User must be in the same voice channel as the bot"
            )
    if ctx:
        if not ctx.user.voice or not ctx.user.voice.channel:
            raise UserNotInVoice('Please join a voice channel first')

        voice_client = get(bot.voice_clients, guild=ctx.user.guild)

        if not voice_client:
            if not should_connect:
                raise BotNotInVoice('Bot is not in a voice channel.')

            permissions = ctx.user.voice.channel.permissions_for(
                ctx.user.guild.get_member(ctx.user.id)
            )

            if not permissions.connect or not permissions.speak:  # Check user limit too?
                raise MissingVoicePermissions('Connect and Speak permissions is required in order to play music')

            # noinspection PyTypeChecker
            return await ctx.user.voice.channel.connect(cls=LavalinkVoiceClient)

        if voice_client.channel.id != ctx.user.voice.channel.id:
            raise UserInDifferentChannel(
                voice_client.channel, "User must be in the same voice channel as the bot"
            )

async def get_recommended_tracks(player: "LavaPlayer", track: AudioTrack, max_results: int) -> list[AudioTrack]:
    """
    Get recommended track from the given track.

    :param player: The player instance.
    :param track: The seed tracks to get recommended tracks from.
    :param max_results: The max amount of tracks to get.
    """
    try:
        results_from_youtube = await youtube_related.async_fetch(track.uri)
    except ValueError:  # The track is not a YouTube track
        search_results = youtube_search.YoutubeSearch(f"{track.title} by {track.author}", 1).to_dict()

        results_from_youtube = await youtube_related.async_fetch(
            f"https://youtube.com/watch?v={search_results[0]['id']}"
        )

    results: list[AudioTrack] = []

    for result in results_from_youtube:
        if result['id'] in [song.identifier for song in player.queue]:  # Don't add duplicate songs
            continue

        if len(results) >= max_results:
            break

        track = (await player.node.get_tracks(f"https://youtube.com/watch?v={result['id']}")).tracks[0]

        results.append(track)

    return results


async def get_image_size(url: str) -> Optional[Tuple[int, int]]:
    """
    Get the size of the image from the given URL.

    :param url: The URL of the image.
    :return The width and height of the image. If the image is not found, return None.
    """
    async with aiohttp.ClientSession() as session, session.get(url) as response:
        if response.status != 200:
            return None

        data = await response.read()
        img = imageio.imread(BytesIO(data))

        return img.shape[1], img.shape[0]
