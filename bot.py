import os
import discord
from discord.ext import commands
from discord import app_commands
import json
import aiohttp

# Config
FRANCHIGIE_NBA = [
    "Hawks", "Celtics", "Nets", "Hornets",
    "Bulls", "Cavaliers", "Pistons", "Pacers",
    "Heat", "Bucks", "Knicks", "Magic",
    "Sixers", "Raptors", "Wizards",
    "Mavericks", "Nuggets", "Warriors", "Rockets",
    "Clippers", "Lakers", "Grizzlies", "Timberwolves",
    "Pelicans", "Thunder", "Suns",
    "Trail Blazers", "Kings", "Spurs", "Jazz"
]

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxU7vLSn0dZuVVfZTO9M6Ynl5MuXQPwcMJNFnHX2HbhZM_VzBQGHtVSZ4nVw1kVZ5eE/exec"

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
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Comandi sincronizzati per {self.user}")

bot = LeagueBot()

@bot.event
async def on_ready():
    print(f'Lega NBA 2K Online! Loggato come {bot.user}')

@bot.tree.command(name="registra_team", description="Registra la tua franchigia NBA 2K")
async def registra_team(interaction: discord.Interaction, nome_squadra: str):
    db = load_db()
    user_id = str(interaction.user.id)
    if user_id in db["teams"]:
        await interaction.response.send_message(f"Hai gia' registrato i **{db['teams'][user_id]['nome']}**!", ephemeral=True)
        return
    
    franchige_lower = [f.lower() for f in FRANCHIGIE_NBA]
    if nome_squadra.lower() not in franchige_lower:
        await interaction.response.send_message(f"Franchigia non valida. Scegli tra: {', '.join(FRANCHIGIE_NBA)}", ephemeral=True)
        return
    
    nome_ufficiale = FRANCHIGIE_NBA[franchige_lower.index(nome_squadra.lower())]
    if any(t["nome"] == nome_ufficiale for t in db["teams"].values()):
        await interaction.response.send_message(f"I **{nome_ufficiale}** sono gia' stati scelti!", ephemeral=True)
        return

    await interaction.response.defer()
    db["teams"][user_id] = {"nome": nome_ufficiale, "cap_space": 160, "roster": []}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(APPS_SCRIPT_URL) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    if nome_ufficiale in data:
                        db["teams"][user_id]["roster"] = data[nome_ufficiale]
                        costo = sum(p["stipendio"] for p in data[nome_ufficiale])
                        db["teams"][user_id]["cap_space"] = round(160 - costo, 1)
                        save_db(db)
                        await interaction.followup.send(f"Franchigia **{nome_ufficiale}** registrata! Caricati {len(data[nome_ufficiale])} giocatori.")
                        return
        except Exception as e:
            print(f"Errore Apps Script: {e}")
    
    save_db(db)
    await interaction.followup.send(f"Franchigia **{nome_ufficiale}** registrata senza roster reale (errore script).")

@bot.tree.command(name="roster", description="Mostra il roster di una squadra")
@app_commands.describe(squadra="Nome della franchigia (opzionale se sei registrato)")
async def roster(interaction: discord.Interaction, squadra: str = None):
    db = load_db()
    
    target_team = None
    if squadra:
        squadra_lower = squadra.lower()
        # Cerca tra i nomi ufficiali
        for f in FRANCHIGIE_NBA:
            if f.lower() == squadra_lower:
                # Cerca se qualcuno l'ha presa
                for t in db["teams"].values():
                    if t["nome"] == f:
                        target_team = t
                        break
                # Se nessuno l'ha presa, mostra il roster base (se possibile) o errore
                if not target_team:
                    await interaction.response.send_message(f"La squadra **{f}** non è ancora stata registrata da nessun utente.", ephemeral=True)
                    return
                break
        if not target_team:
            await interaction.response.send_message("Franchigia non trovata.", ephemeral=True)
            return
    else:
        uid = str(interaction.user.id)
        if uid not in db["teams"]:
            await interaction.response.send_message("Non hai un team registrato. Specifica una squadra: `/roster squadra:Hawks`", ephemeral=True)
            return
        target_team = db["teams"][uid]

    players = sorted(target_team["roster"], key=lambda x: x.get('overall', 0), reverse=True)
    desc = "
".join([f"🏀 **{p['nome']}** ({p.get('posizione','?')}) OVR:{p.get('overall','?')} - ${p['stipendio']}M" for p in players])
    embed = discord.Embed(title=f"Roster: {target_team['nome']}", description=desc or "Vuoto", color=0x00FF00)
    embed.set_footer(text=f"Cap Space: ${target_team['cap_space']}M")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="init_league", description="Inizializza la lega dal file Google Sheets (Admin only)")
async def init_league(interaction: discord.Interaction):
    # Solo tu puoi farlo per ora (SamHedgehogs)
    if str(interaction.user.id) != "111111111111111111": # Sostituire col tuo ID se vuoi restrizione
        pass 

    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(APPS_SCRIPT_URL) as resp:
                if resp.status == 200:
                    all_data = await resp.json(content_type=None)
                    db = {"teams": {}, "players": [], "trades": []}
                    # Assegniamo i team a ID fittizi o lasciamo liberi per la registrazione?
                    # Per ora carichiamo i dati in una struttura di "roster reali" nel DB
                    db["reali"] = all_data
                    save_db(db)
                    await interaction.followup.send("Dati della lega caricati correttamente!")
                else:
                    await interaction.followup.send("Errore nel recupero dati dallo script.")
        except Exception as e:
            await interaction.followup.send(f"Errore: {e}")

@bot.tree.command(name="crea_canali_team", description="Crea i canali per ogni squadra (Admin only)")
async def crea_canali_team(interaction: discord.Interaction):
    await interaction.response.defer()
    guild = interaction.guild
    category = await guild.create_category("FRANCHIGIE")
    
    for f in FRANCHIGIE_NBA:
        channel_name = f.lower().replace(" ", "-")
        await guild.create_text_channel(channel_name, category=category)
    
    await interaction.followup.send("Canali creati!")

bot.run(os.getenv("DISCORD_TOKEN"))
