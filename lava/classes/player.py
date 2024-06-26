import asyncio
from time import time
from typing import TYPE_CHECKING, Optional, Union, List, Dict
from random import randrange

from discord import Message, ButtonStyle, Embed, Colour, Guild, Interaction
from discord.ui import Button
from lavalink import DefaultPlayer, Node, parse_time, TrackEndEvent, RequestError, PlayerErrorEvent, TrackStuckEvent, \
    QueueEndEvent, TrackLoadFailedEvent, AudioTrack, DeferredAudioTrack

from lavalink.common import MISSING

from lava.embeds import ErrorEmbed
from lava.utils import get_recommended_tracks, get_image_size
from lava.view import View

if TYPE_CHECKING:
    from lava.bot import Bot


class LavaPlayer(DefaultPlayer):
    def __init__(self, bot: "Bot", guild_id: int, node: Node):
        super().__init__(guild_id, node)

        self.bot: Bot = bot
        self.message: Optional[Message] = None

        self._guild: Optional[Guild] = None

        self.autoplay: bool = False

        self._last_update: int = 0
        self._last_position = 0
        self.position_timestamp = 0

        self.__display_image_as_wide: Optional[bool] = None
        self.__last_image_url: str = ""

        self.queue: List[AudioTrack] = []

    @property
    def guild(self) -> Optional[Guild]:
        if not self._guild:
            self._guild = self.bot.get_guild(self.guild_id)

        return self._guild
    
    async def play(self,
                   track: Optional[Union[AudioTrack, 'DeferredAudioTrack', Dict[str, Union[Optional[str], bool, int]]]] = None,
                   start_time: int = 0,
                   end_time: int = MISSING,
                   no_replace: bool = MISSING,
                   volume: int = MISSING,
                   pause: bool = False,
                   **kwargs):
        """|coro|

        Plays the given track.

        This method is basically same as the original DefaultPlayer.play(),
        but changed the way the songs are played.

        Parameters
        ----------
        track: Optional[Union[:class:`DeferredAudioTrack`, :class:`AudioTrack`, Dict[str, Union[Optional[str], bool, int]]]]
            The track to play. If left unspecified, this will default to the first track in the queue. Defaults to ``None``
            which plays the next song in queue. Accepts either an AudioTrack or a dict representing a track
            returned from Lavalink.
        start_time: :class:`int`
            The number of milliseconds to offset the track by.
            If left unspecified, the track will start from the beginning.
        end_time: :class:`int`
            The position at which the track should stop playing.
            This is an absolute position, so if you want the track to stop at 1 minute, you would pass 60000.
            If left unspecified, the track will play through to the end.
        no_replace: :class:`bool`
            If set to true, operation will be ignored if the player already has a current track.
            If left unspecified, the currently playing track will always be replaced.
        volume: :class:`int`
            The initial volume to set. This is useful for changing the volume between tracks etc.
            If left unspecified, the volume will remain at its current setting.
        pause: :class:`bool`
            Whether to immediately pause the track after loading it. Defaults to ``False``.
        **kwargs: Any
            The kwargs to use when playing. You can specify any extra parameters that may be
            used by plugins, which offer extra features not supported out-of-the-box by Lavalink.py.

        Raises
        ------
        :class:`ValueError`
            If invalid values were provided for ``start_time`` or ``end_time``.
        :class:`TypeError`
            If wrong types were provided for ``no_replace``, ``volume`` or ``pause``.
        """
        if isinstance(no_replace, bool) and no_replace and self.is_playing:
            return

        if track is not None and isinstance(track, dict):
            track = AudioTrack(track, 0)

        if self.loop > 0 and self.current:
            if self.loop == 1:
                if track is not None:
                    self.queue.insert(0, self.current)
                else:
                    track = self.current
            elif self.loop == 2:
                self.queue.append(self.current)

        self._last_position = 0
        self.position_timestamp = 0
        self.paused = pause

        if not track:
            if not self.queue:
                await self.stop()  # Also sets current to None.
                await self.client._dispatch_event(QueueEndEvent(self))
                return
            elif self.is_playing and self.current == self.queue[-1]:
                await self.stop()  # Also sets current to None.
                await self.client._dispatch_event(QueueEndEvent(self))
                return 

            if not self.current or len(self.queue) <= 1:
                track_at = randrange(len(self.queue)) if self.shuffle else 0
            else:
                track_at = randrange(len(self.queue)) if self.shuffle else (self.queue.index(self.current) + 1)

            track = self.queue[track_at]

        if start_time is not MISSING:
            if not isinstance(start_time, int) or not 0 <= start_time < track.duration:
                raise ValueError('start_time must be an int with a value equal to, or greater than 0, and less than the track duration')

        if end_time is not MISSING:
            if not isinstance(end_time, int) or not 1 <= end_time <= track.duration:
                raise ValueError('end_time must be an int with a value equal to, or greater than 1, and less than, or equal to the track duration')

        await self.play_track(track, start_time, end_time, no_replace, volume, pause, **kwargs)

    async def previous(self):
        """
        Plays the previous track in the queue.
        """
        if len(self.queue) > 1 and (self.queue.index(self.current) - 1) != -1:
            await self.play(self.queue[self.queue.index(self.current) - 1])
            return

    async def check_autoplay(self) -> bool:
        """
        Check the autoplay status and add recommended tracks if enabled.

        :return: True if tracks were added, False otherwise.
        """
        if not self.autoplay or len(self.queue) >= 5:
            return False
        self.bot.logger.info(
            "Queue is empty, adding recommended track for guild %s...", self.guild
        )

        recommendations = await get_recommended_tracks(self, self.current, 5 - len(self.queue))

        for recommendation in recommendations:
            self.add(requester=0, track=recommendation)

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
                    style=ButtonStyle.grey,
                    emoji="⬛",
                    custom_id="control.empty",
                    row=1
                )
            ]
    
        view = View()
        if view.children == []:
            for item in components:
                view.add_item(item)

        if interaction:
            await interaction.response.edit_message(
                embed=(await self.__generate_display_embed()), view=view
            )

        else:
            await self.message.edit(embed=(await self.__generate_display_embed()), view=view)

        self.bot.logger.debug(
            "Updating player in guild %s display message to %s", self.bot.get_guild(self.guild_id), self.message.id
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
