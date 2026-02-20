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

# Nuova URL Apps Script aggiornata
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxU7vLSn0dZuVVfZTO9M6Ynl5MuXQPwcMJNFnHX2HbhZM_VzBQGHtVSZ4nVw1kVZ5eE/exec"

def load_db():
    try:
        with open('league_db.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"teams": {}, "players": [], "trades": [], "reali": {}}

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
        # Sincronizza i comandi slash globalmente
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
                        costo = sum(p.get("stipendio", 0) for p in data[nome_ufficiale])
                        db["teams"][user_id]["cap_space"] = round(160 - costo, 1)
                        save_db(db)
                        await interaction.followup.send(f"Franchigia **{nome_ufficiale}** registrata! Caricati {len(data[nome_ufficiale])} giocatori.")
                        return
        except Exception as e:
            print(f"Errore Apps Script: {e}")
    
    save_db(db)
    await interaction.followup.send(f"Franchigia **{nome_ufficiale}** registrata senza roster reale (errore script).")

@bot.tree.command(name="roster", description="Mostra il roster di una squadra")
@app_commands.describe(squadra="Nome della franchigia (es: Hawks)")
async def roster(interaction: discord.Interaction, squadra: str = None):
    db = load_db()
    
    target_team = None
    nome_visualizzato = ""

    if squadra:
        s_low = squadra.lower()
        # 1. Cerca tra i team REGISTRATI dagli utenti
        for uid, t in db["teams"].items():
            if t["nome"].lower() == s_low:
                target_team = t
                nome_visualizzato = t["nome"]
                break
        
        # 2. Se non trovato tra i registrati, cerca nei dati REALI (se caricati con /init_league)
        if not target_team and "reali" in db:
            for f_nome, players in db["reali"].items():
                if f_nome.lower() == s_low:
                    target_team = {"nome": f_nome, "roster": players, "cap_space": "N/A"}
                    nome_visualizzato = f_nome
                    break
        
        if not target_team:
            await interaction.response.send_message(f"Squadra '{squadra}' non trovata o non ancora registrata.", ephemeral=True)
            return
    else:
        # Se non specifica nulla, mostra il team di chi scrive
        uid = str(interaction.user.id)
        if uid not in db["teams"]:
            await interaction.response.send_message("Non hai un team registrato. Specifica una squadra: `/roster squadra:Hawks`", ephemeral=True)
            return
        target_team = db["teams"][uid]
        nome_visualizzato = target_team["nome"]

    players = sorted(target_team["roster"], key=lambda x: x.get('overall', 0), reverse=True)
    
    # Costruisco la lista stringhe per l'embed
    desc_list = []
    for p in players:
        n = p.get('nome', 'Sconosciuto')
        pos = p.get('posizione', '?')
        ovr = p.get('overall', '?')
        # Gestisco sia 'stipendio' che '2025-26 Salary' (nomi colonne diverse possibili)
        sal = p.get('stipendio') or p.get('2025-26 Salary') or 0
        desc_list.append(f"🏀 **{n}** ({pos}) OVR:{ovr} - ${sal}M")
    
        desc = "\n".join(desc_list)
    embed = discord.Embed(title=f"Roster: {nome_visualizzato}", description=desc or "Roster vuoto", color=0x00FF00)
    
    cap = target_team.get("cap_space", "N/A")
    embed.set_footer(text=f"Cap Space rimanente: ${cap}M (Soglia: $160M)")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="init_league", description="Carica i dati dei roster dal Google Sheet")
async def init_league(interaction: discord.Interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(APPS_SCRIPT_URL) as resp:
                if resp.status == 200:
                    all_data = await resp.json(content_type=None)
                    db = load_db()
                    db["reali"] = all_data
                    save_db(db)
                    await interaction.followup.send(f"✅ Dati lega caricati! {len(all_data)} squadre pronte.")
                else:
                    await interaction.followup.send("❌ Errore Apps Script: Status " + str(resp.status))
        except Exception as e:
            await interaction.followup.send(f"❌ Errore connessione: {e}")

@bot.tree.command(name="crea_canali_team", description="Crea i canali per ogni franchigia")
async def crea_canali_team(interaction: discord.Interaction):
    await interaction.response.defer()
    guild = interaction.guild
    category = discord.utils.get(guild.categories, name="FRANCHIGIE")
    if not category:
        category = await guild.create_category("FRANCHIGIE")
    
    for f in FRANCHIGIE_NBA:
        c_name = f.lower().replace(" ", "-")
        existing = discord.utils.get(category.text_channels, name=c_name)
        if not existing:
            await guild.create_text_channel(c_name, category=category)
    
    await interaction.followup.send("✅ Canali franchigie pronti nella categoria 'FRANCHIGIE'.")

bot.run(os.getenv("DISCORD_TOKEN"))
