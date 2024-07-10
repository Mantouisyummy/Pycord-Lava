import asyncio
from time import time
from typing import TYPE_CHECKING, Optional, Union, List

import pylrc
import syncedlyrics
from discord import Message, ButtonStyle, Embed, Colour, Guild, Interaction
from discord.ui import Button
from lavalink import DefaultPlayer, Node, parse_time, TrackEndEvent, RequestError, PlayerErrorEvent, TrackStuckEvent, \
    QueueEndEvent, TrackLoadFailedEvent, AudioTrack

from pylrc.classes import Lyrics, LyricLine
from lavalink.common import MISSING

from lava.embeds import ErrorEmbed
from lava.utils import get_recommended_tracks, get_image_size, find_lyrics_within_range
from lava.view import View

if TYPE_CHECKING:
    from lava.bot import Bot


class LavaPlayer(DefaultPlayer):
    def __init__(self, bot: "Bot", guild_id: int, node: Node):
        super().__init__(guild_id, node)

        self.history = []
        self.bot: Bot = bot
        self.message: Optional[Message] = None

        self._guild: Optional[Guild] = None

        self.autoplay: bool = False
        self.is_adding_song: bool = False
        self.show_lyrics: bool = True

        self._last_update: int = 0
        self._last_position = 0
        self.position_timestamp = 0

        self.__display_image_as_wide: Optional[bool] = None
        self.__last_image_url: str = ""

        self.queue: List[AudioTrack] = []
        self._lyrics: Union[Lyrics[LyricLine], None] = None

    @property
    def lyrics(self) -> Union[Lyrics[LyricLine], None]:
        if self._lyrics == MISSING:
            return MISSING

        if self._lyrics is not None:
            return self._lyrics

        try:
            lrc = syncedlyrics.search(f"{self.current.title} {self.current.author}")
        except Exception:
            return MISSING

        if not lrc:
            self._lyrics = MISSING
            return self._lyrics

        self._lyrics = pylrc.parse(lrc)

        return self._lyrics

    @property
    def guild(self) -> Optional[Guild]:
        if not self._guild:
            self._guild = self.bot.get_guild(self.guild_id)

        return self._guild

    async def check_autoplay(self) -> bool:
        """
        Check the autoplay status and add recommended tracks if enabled.

        :return: True if tracks were added, False otherwise.
        """
        if not self.autoplay or self.is_adding_song or len(self.queue) >= 30:
            return False

        self.is_adding_song = True

        self.bot.logger.info(
            "Queue is empty, adding recommended track for guild %s...", self.guild
        )

        recommendations = await get_recommended_tracks(self, self.current, 5 - len(self.queue))

        if not recommendations:
            self.is_adding_song = False
            self.autoplay = False

            if self.message:
                message = await self.message.channel.send(
                    embed=ErrorEmbed(
                        self.bot.get_text(
                            'error.autoplay_failed', self.locale, '我找不到任何推薦的歌曲，所以我停止了自動播放'
                        ),
                    )
                )

                await self.update_display(message, delay=5)

            return False

        for recommendation in recommendations:
            self.add(requester=0, track=recommendation)

        self.is_adding_song = False

    async def toggle_autoplay(self):
        """
        Toggle autoplay for the player.
        """
        if not self.autoplay:
            self.autoplay = True
            return

        self.autoplay = False

        for item in self.queue:  # Remove songs added by autoplay
            if item.requester == 0:
                self.queue.remove(item)

    async def update_display(self,
                             new_message: Optional[Message] = None,
                             delay: int = 0,
                             interaction: Optional[Interaction] = None) -> None:
        """
        Update the display of the current song.

        Note: If new message is provided, Old message will be deleted after 5 seconds

        :param new_message: The new message to update the display with, None to use the old message.
        :param delay: The delay in seconds before updating the display.
        :param interaction: The interaction to be responded to.
        :param locale: The locale to use for the display
        """

        self.bot.logger.info(
            "Updating display for player in guild %s in a %s seconds delay", self.bot.get_guild(self.guild_id), delay
        )

        await asyncio.sleep(delay)

        if not self.message and not new_message:
            self.bot.logger.warning(
                "No message to update display for player in guild %s", self.bot.get_guild(self.guild_id)
            )
            return

        if new_message:
            try:
                self.bot.logger.debug(
                    "Deleting old existing display message for player in guild %s", self.bot.get_guild(self.guild_id)
                )

                _ = self.bot.loop.create_task(self.message.delete())
            except (AttributeError, UnboundLocalError):
                pass

            self.message = new_message

        if not self.is_connected or not self.current:
            components = []

        else:
            components = [
                Button(
                    style=ButtonStyle.green if self.shuffle else ButtonStyle.grey,
                    emoji="🔀",
                    custom_id="control.shuffle",
                    row=0
                ),
                Button(
                    style=ButtonStyle.blurple,
                    emoji="⏮️",
                    custom_id="control.previous",
                    row=0
                ),
                Button(
                    style=ButtonStyle.green,
                    emoji="⏸️",
                    custom_id="control.pause"
                ) if not self.paused else Button(
                    style=ButtonStyle.red,
                    emoji="▶️",
                    custom_id="control.resume",
                    row=0
                ),
                Button(
                    style=ButtonStyle.blurple,
                    emoji="⏭️",
                    custom_id="control.next",
                    row=0
                ),
                Button(
                    style=[ButtonStyle.grey, ButtonStyle.green, ButtonStyle.blurple][self.loop],
                    emoji="🔁",
                    custom_id="control.repeat",
                    row=0
                ),
                Button(
                    style=ButtonStyle.green if self.fetch("autoplay") else ButtonStyle.grey,
                    emoji="🔥",
                    custom_id="control.autoplay",
                    row=1
                ),
                Button(
                    style=ButtonStyle.blurple,
                    emoji="⏪",
                    custom_id="control.rewind",
                    row=1
                ),
                Button(
                    style=ButtonStyle.red,
                    emoji="⏹️",
                    custom_id="control.stop",
                    row=1
                ),
                Button(
                    style=ButtonStyle.blurple,
                    emoji="⏩",
                    custom_id="control.forward",
                    row=1
                ),
                Button(
                    style=ButtonStyle.green if self.show_lyrics else ButtonStyle.grey,
                    emoji="🎤",
                    custom_id="control.lyrics",
                    row=1
                )
            ]

        embeds = [await self.__generate_display_embed()]

        if self.is_playing and self.show_lyrics:
            embeds.append(await self.__generate_lyrics_embed())

        view = View()
        if not view.children:
            for item in components:
                view.add_item(item)

        if interaction:
            await interaction.response.edit_message(
                embeds=embeds, view=view
            )

        else:
            await self.message.edit(embeds=embeds, view=view)

        self.bot.logger.debug(
            "Updating player in guild %s display message to %s", self.bot.get_guild(self.guild_id), self.message.id
        )

    async def __generate_lyrics_embed(self) -> Embed:
        """Generate the lyrics embed for the player."""
        if self.lyrics is MISSING:
            return Embed(
                title='🎤 | 歌詞',
                description='*你得自己唱出這首歌的歌詞*',
                color=Colour.red()
            )

        lyrics_in_range = find_lyrics_within_range(self.lyrics, (self.position / 1000), 5.0)

        lyrics_text = '\n'.join(
            [
                f"## {lyric.text}"
                for lyric in lyrics_in_range
            ]
        ) or "## ..."

        return Embed(
            title='🎤 | 歌詞', description=lyrics_text,
            color=Colour.blurple()
        )

    async def __generate_display_embed(self) -> Embed:
        """
        Generate the display embed for the player.

        :return: The generated embed
        """
        embed = Embed()

        if self.is_playing:
            embed.set_author(
                name="播放中",
                icon_url="https://cdn.discordapp.com/emojis/987643956403781692.webp"
            )

            embed.colour = Colour.green()

        elif self.paused:
            embed.set_author(
                name="已暫停",
                icon_url="https://cdn.discordapp.com/emojis/987661771609358366.webp"
            )

            embed.colour = Colour.orange()

        elif not self.is_connected:
            embed.set_author(
                name="已斷線",
                icon_url="https://cdn.discordapp.com/emojis/987646268094439488.webp"
            )

            embed.colour = Colour.red()

        elif not self.current:
            embed.set_author(
                name="已結束",
                icon_url="https://cdn.discordapp.com/emojis/987645074450034718.webp"
            )

            embed.colour = Colour.red()

        loop_mode_text = {
            0: '關閉',
            1: '單曲',
            2: '整個序列'
        }

        if self.current:
            embed.title = self.current.title
            embed.description = f"`{self._format_time(self.position)}`" \
                                f" {self.__generate_progress_bar(self.current.duration, self.position)} " \
                                f"`{self._format_time(self.current.duration)}`"

            embed.add_field(name="👤 作者", value=self.current.author, inline=True)
            embed.add_field(
                name="👥 點播者",
                value="自動播放" if not self.current.requester else f"<@{self.current.requester}>",
                inline=True
            )  # Requester will be 0 if the song is added by autoplay
            embed.add_field(
                name="🔁 重複播放模式", value=loop_mode_text[self.loop],
                inline=True
            )

            embed.add_field(
                name="📃 播放序列",
                value=('\n'.join(
                    [
                        f"**[{index + 1}]** {track.title}"
                        for index, track in enumerate(self.queue[:5])
                    ]
                ) + (f"\n還有更多..." if len(self.queue) > 5 else "")) or
                      "空",
                inline=True
            )
            embed.add_field(
                name="⚙️ 已啟用效果器",
                value=', '.join([key.capitalize() for key in self.filters]) or "無",
                inline=True
            )
            embed.add_field(
                name="🔀 隨機播放",
                value="開啟"
                if self.shuffle else "關閉",
                inline=True
            )

            if self.current.artwork_url:
                if await self.is_current_artwork_wide():
                    embed.set_image(url=self.current.artwork_url)
                else:
                    embed.set_thumbnail(url=self.current.artwork_url)

        else:
            embed.title = "沒有正在播放的音樂"

        return embed

    @staticmethod
    def _format_time(time_ms: Union[float, int]) -> str:
        """
        Formats the time into DD:HH:MM:SS

        :param time_ms: Time in milliseconds
        :return: Formatted time
        """
        days, hours, minutes, seconds = parse_time(round(time_ms))

        days, hours, minutes, seconds = map(round, (days, hours, minutes, seconds))

        return ((f"{str(hours).zfill(2)}:" if hours else "")
                + f"{str(minutes).zfill(2)}:{str(seconds).zfill(2)}")

    def __generate_progress_bar(self, duration: Union[float, int], position: Union[float, int]):
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

        return f"⬜" \
               f"{'⬜' * round(percentage * 10)}" \
               f"{'⬜' if percentage != 1 else '⬜'}" \
               f"{'⬛' * round((1 - percentage) * 10)}" \
               f"{'⬛' if percentage != 1 else '⬛'}"

    async def is_current_artwork_wide(self) -> bool:
        """
        Check if the current playing track's artwork is wide.
        """
        if not self.current:
            return False

        if not self.current.artwork_url:
            return False

        if self.__last_image_url == self.current.artwork_url:
            return self.__display_image_as_wide

        self.__last_image_url = self.current.artwork_url

        width, height = await get_image_size(self.current.artwork_url)

        self.__display_image_as_wide = width > height

        return self.__display_image_as_wide

    async def _update_state(self, state: dict):
        """
        Updates the position of the player.

        Parameters
        ----------
        state: :class:`dict`
            The state that is given to update.
        """
        self._last_update = int(time() * 1000)
        self._last_position = state.get('position', 0)
        self.position_timestamp = state.get('time', 0)

        _ = self.bot.loop.create_task(self.check_autoplay())
        _ = self.bot.loop.create_task(self.update_display())

    async def _handle_event(self, event):
        if isinstance(event, TrackStuckEvent) or isinstance(event, TrackEndEvent) and event.reason.may_start_next():
            await self._handle_track_event()
        elif isinstance(event, TrackEndEvent):
            await self._handle_track_end_event()
        elif isinstance(event, QueueEndEvent):
            await self._handle_queue_end_event()
        elif isinstance(event, TrackLoadFailedEvent):
            await self._handle_track_load_failed_event(event)

    async def _handle_track_event(self):
        try:
            await self.play()
        except RequestError as error:
            await self.client._dispatch_event(PlayerErrorEvent(self, error))  # skipcq: PYL-W0212
            self.bot.logger.exception(
                '[DefaultPlayer:%d] Encountered a request error whilst starting a new track.', self.guild_id
            )

    async def _handle_track_end_event(self):
        self.bot.logger.info("Received track end event for guild %s", self.bot.get_guild(self.guild_id))
        try:
            await self.update_display()
        except ValueError:
            pass

    async def _handle_queue_end_event(self):
        self.bot.logger.info("Received queue end event for guild %s", self.bot.get_guild(self.guild_id))
        try:
            await self.update_display()
        except ValueError:
            pass

    async def _handle_track_load_failed_event(self, event):
        self.bot.logger.info("Received track load failed event for guild %s", self.bot.get_guild(self.guild_id))
        message = await self.message.channel.send(
            embed=ErrorEmbed(
                title=f"無法播放歌曲: {event.track['title']}",
                reason=f"{event.original or 'Unknown'}"
            )
        )
        await self.skip()
        await self.update_display(message, delay=5)

    def reset_lyrics(self):
        """
        Reset the lyrics cache.
        """
        self._lyrics = None

    async def toggle_lyrics(self):
        """
        Toggle lyrics display for the player.
        """
        self.show_lyrics = not self.show_lyrics
