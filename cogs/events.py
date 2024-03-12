from logging import getLogger
from typing import Union

from discord import TextChannel, Thread, InteractionResponded, ApplicationContext, \
    Interaction
from discord.abc import GuildChannel
from discord.ext import commands
from discord.ext.commands import Cog, CommandInvokeError
from lavalink import TrackLoadFailedEvent, DefaultPlayer, PlayerUpdateEvent, TrackEndEvent, QueueEndEvent

from lava.bot import Bot
from lava.embeds import ErrorEmbed
from lava.errors import MissingVoicePermissions, BotNotInVoice, UserNotInVoice, UserInDifferentChannel
from lava.utils import update_display, ensure_voice, toggle_autoplay, get_recommended_tracks
from lava.variables import Variables


class Events(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = getLogger("discord.events")

    async def cog_load(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener(name="on_ready")
    async def on_ready(self):
        self.bot.lavalink.add_event_hook(self.track_hook)

    async def track_hook(self, event):
        if isinstance(event, PlayerUpdateEvent):
            player: DefaultPlayer = event.player

            self.logger.debug("Received player update event for guild %s", self.bot.get_guild(player.guild_id))

            if event.player.fetch("autoplay") and len(event.player.queue) <= 5:
                self.logger.info(
                    "Queue is empty, adding recommended track for guild %s...", self.bot.get_guild(player.guild_id)
                )

                recommendations = await get_recommended_tracks(player, player.current, 5 - len(player.queue))

                for track in recommendations:
                    event.player.add(requester=0, track=track)

            try:
                await update_display(self.bot, player)
            except ValueError:
                pass

        elif isinstance(event, TrackEndEvent):
            player: DefaultPlayer = event.player

            self.logger.info("Received track end event for guild %s", self.bot.get_guild(player.guild_id))

            try:
                await update_display(self.bot, player)
            except ValueError:
                pass

        elif isinstance(event, QueueEndEvent):
            player: DefaultPlayer = event.player

            self.logger.info("Received queue end event for guild %s", self.bot.get_guild(player.guild_id))

            try:
                await update_display(self.bot, player)
            except ValueError:
                pass

        elif isinstance(event, TrackLoadFailedEvent):
            player: DefaultPlayer = event.player

            self.logger.info("Received track load failed event for guild %s", self.bot.get_guild(player.guild_id))

            # noinspection PyTypeChecker
            channel: Union[GuildChannel, TextChannel, Thread] = self.bot.get_channel(int(player.fetch("channel")))

            message = await channel.send(
                embed=ErrorEmbed(
                    f"{'無法播放歌曲'}: {event.track['title']}",
                    f"{'原因'}: `{event.original or 'Unknown'}`"
                )
            )

            await player.skip()

            await update_display(self.bot, player, message, delay=5)

    @commands.Cog.listener(name="on_slash_command_error")
    async def on_slash_command_error(self, ctx: ApplicationContext, error: CommandInvokeError):

        if isinstance(error.original, MissingVoicePermissions):
            embed = ErrorEmbed(
                '指令錯誤',
                "我需要 `連接` 和 `說話` 權限才能夠播放音樂"
            )

        elif isinstance(error.original, BotNotInVoice):
            embed = ErrorEmbed(
                '指令錯誤',
                "我沒有連接到一個語音頻道"
            )

        elif isinstance(error.original, UserNotInVoice):
            embed = ErrorEmbed(
                '指令錯誤',
                "你沒有連接到一個語音頻道"
            )

        elif isinstance(error.original, UserInDifferentChannel):
            embed = ErrorEmbed(
                '指令錯誤',
                f"你必須與我在同一個語音頻道 <#{error.original.voice.id}>"
            )

        else:
            raise error.original

        try:
            await ctx.interaction.response.send_message(embed=embed)
        except InteractionResponded:
            await ctx.interaction.edit_original_response(embed=embed)

    @commands.Cog.listener(name="on_voice_state_update")
    async def on_voice_state_update(self, member, before, after):
        if (
                before.channel is not None
                and after.channel is None
                and member.id == self.bot.user.id
        ):
            player: DefaultPlayer = self.bot.lavalink.player_manager.get(member.guild.id)

            await player.stop()
            player.queue.clear()

            try:
                await update_display(self.bot, player)
            except ValueError:  # There's no message to update
                pass

    @commands.Cog.listener(name="on_interaction")
    async def on_interaction(self, interaction: Interaction):
        try:
            if interaction.custom_id.startswith("control"):
                if interaction.custom_id.startswith("control.empty"):
                    await interaction.response.edit_message()
                    return

                try:
                    await ensure_voice(self.bot, should_connect=False, interaction=interaction)
                except (UserNotInVoice, BotNotInVoice, MissingVoicePermissions, UserInDifferentChannel):
                    return

                player: DefaultPlayer = self.bot.lavalink.player_manager.get(interaction.guild_id)

                match interaction.custom_id:
                    case "control.resume":
                        await player.set_pause(False)

                    case "control.pause":
                        await player.set_pause(True)

                    case "control.stop":
                        await player.stop()
                        player.queue.clear()

                    case "control.previous":
                        await player.seek(0)

                    case "control.next":
                        await player.skip()

                    case "control.shuffle":
                        player.set_shuffle(not player.shuffle)

                    case "control.repeat":
                        player.set_loop(player.loop + 1 if player.loop < 2 else 0)

                    case "control.rewind":
                        await player.seek(round(player.position) - 10000)

                    case "control.forward":
                        await player.seek(round(player.position) + 10000)

                    case "control.autoplay":
                        toggle_autoplay(player)

                await update_display(self.bot, player, interaction=interaction)
        except AttributeError:
            pass


def setup(bot):
    bot.add_cog(Events(bot))
