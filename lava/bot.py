import json
from logging import Logger
from typing import Optional

from discord.ext.commands import Bot as OriginalBot

from lava.classes.lavalink_client import LavalinkClient
from lava.source import SourceManager


class Bot(OriginalBot):
    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)

        self.logger = logger

        self._lavalink: Optional[LavalinkClient] = None

    async def on_ready(self):
        self.logger.info("The bot is ready! Logged in as %s" % self.user)

        self.__setup_lavalink_client()

    @property
    def lavalink(self) -> LavalinkClient:
        if not self.is_ready():
            raise RuntimeError("The bot is not ready yet!")

        if self._lavalink is None:
            self.__setup_lavalink_client()

        return self._lavalink

    def __setup_lavalink_client(self):
        """
        Sets up the lavalink client for the bot
        :return: Lavalink Client
        """
        self.logger.info("Setting up lavalink client...")

        self._lavalink = LavalinkClient(self, user_id=self.user.id)

        self.logger.info("Loading lavalink nodes...")

        with open("configs/lavalink.json", "r") as f:
            config = json.load(f)

        for node in config['nodes']:
            self.logger.debug("Adding lavalink node %s", node['host'])

            self.lavalink.add_node(**node)

        self.logger.info("Done loading lavalink nodes!")

        self.lavalink.register_source(SourceManager())
