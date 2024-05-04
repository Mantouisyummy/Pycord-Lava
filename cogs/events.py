from logging import getLogger
from typing import Union

import lavalink
from discord import TextChannel, Thread, InteractionResponded, ApplicationContext, \
    Interaction
from discord.abc import GuildChannel
from discord.ext import commands
from discord.ext.commands import Cog, CommandInvokeError
from lavalink import TrackLoadFailedEvent, DefaultPlayer, PlayerUpdateEvent, TrackEndEvent, QueueEndEvent

from lava.bot import Bot
from lava.embeds import ErrorEmbed
from lava.errors import MissingVoicePermissions, BotNotInVoice, UserNotInVoice, UserInDifferentChannel
from lava.utils import ensure_voice, get_recommended_tracks
from lava.classes.player import LavaPlayer


class Events(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = getLogger("discord.events")
        
    async def cog_load(self):
        await self.bot.wait_until_ready()

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
            player: LavaPlayer = self.bot.lavalink.player_manager.get(member.guild.id)

            await player.stop()
            player.queue.clear()

            try:
                await player.update_display(self.bot, player)
            except ValueError:  # There's no message to update
                pass

    @commands.Cog.listener(name="on_interaction")
    async def on_interaction(self, interaction: Interaction):
        custom_id = interaction.data.get("custom_id", None)
        try:
            if custom_id is not None:
                if custom_id.startswith("control"):
                    if custom_id.startswith("control.empty"):
                        await interaction.response.edit_message()
                        return

                    try:
                        await ensure_voice(self.bot, should_connect=False, interaction=interaction)
                    except (UserNotInVoice, BotNotInVoice, MissingVoicePermissions, UserInDifferentChannel):
                        return

                    player: LavaPlayer = self.bot.lavalink.player_manager.get(interaction.guild_id)

                    match custom_id:
                        case "control.resume":
                            await player.set_pause(False)

                        case "control.pause":
                            await player.set_pause(True)

                        case "control.stop":
                            await player.stop()
                            player.queue.clear()

                        case "control.previous":
                            await player.previous()

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
                            await player.toggle_autoplay()

                    await player.update_display(interaction=interaction)
        except AttributeError as e:
            print(e)
            pass


def setup(bot):
    bot.add_cog(Events(bot))
