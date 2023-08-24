import asyncio
import logging
import json
import os

from discord import Intents
from colorlog import ColoredFormatter
from dotenv import load_dotenv

from core.bot import Bot
from os import getenv

def main():
    load_dotenv()

    setup_logging()

    main_logger = logging.getLogger("discord")

    loop = asyncio.new_event_loop()

    bot = Bot(
        logger=main_logger,
        command_prefix=getenv("PREFIX", "l!"), intents=Intents.all(), loop=loop,
    )

    load_extensions(bot=bot)

    bot.run(getenv("TOKEN"))

def setup_logging():
    """
    Set up the loggings for the bot
    :return: None
    """
    formatter = ColoredFormatter(
        '%(asctime)s %(log_color)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'white',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        handlers=[stream_handler, file_handler], level=logging.INFO
    )


def load_extensions(bot: Bot) -> Bot:
    """
    Load extensions in extensions.json file
    :param bot: The bot to load the extensions to
    :return: The bot
    """
    for filename in os.listdir("./cogs"):
        if filename.endswith('.py'):
            bot.load_extension(f"cogs.{filename[:-3]}")

    return bot


if __name__ == "__main__":
    main()
