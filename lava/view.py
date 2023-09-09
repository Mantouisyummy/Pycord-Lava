from discord.ui import View
from discord.ui.item import Item

class View(View):
    def __init__(self):
        super().__init__(timeout=None)
