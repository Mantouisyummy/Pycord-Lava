import json

from discord.ext.commands import Bot as OriginalBot
from discord.abc import MISSING

from lavalink import Client
from logging import Logger

from core.sources.source import SourceManager

class Bot(OriginalBot):
    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)

        self.logger = logger

        self.lavalink: Client = MISSING
    
    async def on_ready(self):
        self.logger.info("The bot is ready! Logged in as %s" % self.user)
        self.__setup_lavalink_client()

    def __setup_lavalink_client(self):
        """
        Sets up the lavalink client for the bot
        :return: Lavalink Client
        """
        self.logger.info("Setting up lavalink client...")

        self.lavalink = Client(self.user.id)

        self.logger.info("Loading lavalink nodes...")

        with open("configs/lavalink.json", "r") as f:
            config = json.load(f)

        for node in config['nodes']:
            self.logger.debug("Adding lavalink node %s", node['host'])

            self.lavalink.add_node(**node)

        self.logger.info("Done loading lavalink nodes!")

        self.lavalink.register_source(SourceManager())