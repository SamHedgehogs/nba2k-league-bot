import os
import discord
from discord.ext import commands
from discord import app_commands
import json

# Caricamento database (semplice file JSON per ora)
def load_db():
    try:
        with open('league_db.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"teams": {}, "players": [], "trades": []}

def save_db(data):
    with open('league_db.json', 'w') as f:
        json.dump(data, f, indent=4)

class LeagueBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Comandi sincronizzati per {self.user}")

bot = LeagueBot()

@bot.event
async def on_ready():
    print(f'Lega NBA 2K Online! Loggato come {bot.user}')

# COMANDO: REGISTRA TEAM
@bot.tree.command(name="registra_team", description="Registra la tua squadra NBA 2K")
async def registra_team(interaction: discord.Interaction, nome_squadra: str):
    db = load_db()
    user_id = str(interaction.user.id)
    
    if user_id in db["teams"]:
        await interaction.response.send_message(f"Hai già registrato i {db['teams'][user_id]['nome']}!", ephemeral=True)
        return
    
    db["teams"][user_id] = {
        "nome": nome_squadra,
        "cap_space": 140, # Milioni fittizi
        "roster": []
    }
    save_db(db)
    await interaction.response.send_message(f"Squadra **{nome_squadra}** registrata con successo!")

# COMANDO: INFO TEAM
@bot.tree.command(name="team", description="Mostra info sulla tua squadra")
async def team_info(interaction: discord.Interaction):
    db = load_db()
    user_id = str(interaction.user.id)
    
    if user_id not in db["teams"]:
        await interaction.response.send_message("Non hai ancora registrato una squadra. Usa /registra_team", ephemeral=True)
        return
    
    team = db["teams"][user_id]
    embed = discord.Embed(title=f"Franchigia: {team['nome']}", color=discord.Color.blue())
    embed.add_field(name="Salary Cap Space", value=f"${team['cap_space']}M")
    embed.add_field(name="Giocatori", value=len(team['roster']))
    
    await interaction.response.send_message(embed=embed)

token = os.getenv("DISCORD_TOKEN")
bot.run(token)
