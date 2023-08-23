from discord.ui import View, button, Button
from discord import ButtonStyle, Interaction

class Paginator(View):
    """
    Paginator for Embeds.
    Parameters:
    ----------
    embeds: List[Embed]
        List of embeds which are in the Paginator. Paginator starts from first embed.
    author: int
        The ID of the author who can interact with the buttons. Anyone can interact with the Paginator Buttons if not specified.
    timeout: float
        How long the Paginator should timeout in, after the last interaction.

    """
    def __init__(self, embeds: list, author: int = None, timeout: float = None):
        if not timeout:
            super().__init__(timeout=None)
        else:
            super().__init__(timeout=timeout)

        self.embeds = embeds
        self.author = author
        self.CurrentEmbed = 0
        CountButton = [x for x in self.children if x.custom_id == "count"][0]
        CountButton.label = f"{self.CurrentEmbed + 1} / {len(self.embeds)}"
        previousButton = [x for x in self.children if x.custom_id == "previous"][0]
        previousButton.disabled = True
        nextButton = [x for x in self.children if x.custom_id == "next"][0]
        nextButton.disabled = (False if len(self.embeds) > 1 else True)

    @button(emoji="⬅️", style=ButtonStyle.blurple, custom_id="previous")
    async def previous(self, button: Button, interaction: Interaction):
        if interaction.user.id != self.author and self.author != None:
                return await interaction.response.send_message("你無法點選這個按鈕!", ephemeral=True)
        if self.CurrentEmbed:
            nextButton = [x for x in self.children if x.custom_id == "next"][0]

            if nextButton.disabled == True:
                nextButton.disabled = False

            self.CurrentEmbed -= 1
            CountButton = [x for x in self.children if x.custom_id == "count"][0]
            CountButton.label = f"{self.CurrentEmbed + 1} / {len(self.embeds)}"

            if self.CurrentEmbed == 0:
                button.disabled = True
            await interaction.response.edit_message(embed=self.embeds[self.CurrentEmbed], view=self)
   

    @button(label="/", style=ButtonStyle.green, disabled=True, custom_id="count")
    async def count(self, button: Button, interaction: Interaction):
        pass
    
    @button(emoji="➡️", style=ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        if interaction.user.id != self.author and self.author != 123:
            return await interaction.response.send_message("你無法點選這個按鈕!", ephemeral=True)
            
        previousButton = [x for x in self.children if x.custom_id == "previous"][0]
        if previousButton.disabled == True:
            previousButton.disabled = False

        self.CurrentEmbed += 1
        CountButton = [x for x in self.children if x.custom_id == "count"][0]
        CountButton.label = f"{self.CurrentEmbed + 1} / {len(self.embeds)}" 
        if self.CurrentEmbed == len(self.embeds) - 1:
            button.disabled = True

        await interaction.response.edit_message(embed=self.embeds[self.CurrentEmbed], view=self)