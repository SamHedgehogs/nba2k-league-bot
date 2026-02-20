import os
import discord
from discord.ext import commands
from discord import app_commands
import json
import aiohttp

# Lista delle 30 franchigie NBA (solo soprannome)
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
        lista = "
".join(FRANCHIGIE_NBA)
        await interaction.response.send_message(f"**{nome_squadra}** non e' una franchigia valida!
Franchigie disponibili:
{lista}", ephemeral=True)
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
                    data = await resp.json()
                    if nome_ufficiale in data:
                        db["teams"][user_id]["roster"] = data[nome_ufficiale]
                        costo = sum(p["stipendio"] for p in data[nome_ufficiale])
                        db["teams"][user_id]["cap_space"] = round(160 - costo, 1)
                        save_db(db)
                        await interaction.followup.send(f"Franchigia **{nome_ufficiale}** registrata! Caricati {len(data[nome_ufficiale])} giocatori.")
                        return
        except: pass
    
    save_db(db)
    await interaction.followup.send(f"Franchigia **{nome_ufficiale}** registrata senza roster reale (errore script).")

@bot.tree.command(name="franchigie", description="Mostra le franchigie disponibili")
async def franchigie(interaction: discord.Interaction):
    db = load_db()
    prese = [t["nome"] for t in db["teams"].values()]
    disponibili = [f for f in FRANCHIGIE_NBA if f not in prese]
    if not disponibili:
        await interaction.response.send_message("Tutte le franchigie sono assegnate!")
        return
    lista = "
".join([f"- {f}" for f in disponibili])
    await interaction.response.send_message(embed=discord.Embed(title="Disponibili", description=lista, color=0xFFD700))

@bot.tree.command(name="roster", description="Mostra il roster")
async def roster(interaction: discord.Interaction, utente: discord.Member = None):
    db = load_db()
    uid = str(utente.id if utente else interaction.user.id)
    if uid not in db["teams"]:
        await interaction.response.send_message("Nessuna squadra trovata.", ephemeral=True)
        return
    team = db["teams"][uid]
    players = sorted(team["roster"], key=lambda x: x.get('overall', 0), reverse=True)
    desc = "
".join([f"🏀 **{p['nome']}** ({p.get('posizione','?')}) OVR:{p.get('overall','?')} - ${p['stipendio']}M" for p in players])
    embed = discord.Embed(title=f"Roster: {team['nome']}", description=desc or "Vuoto", color=0x00FF00)
    embed.set_footer(text=f"Cap Space: ${team['cap_space']}M")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="firma_fa", description="Firma un free agent")
async def firma_fa(interaction: discord.Interaction, nome: str, stipendio: float):
    db = load_db()
    uid = str(interaction.user.id)
    if uid not in db["teams"]:
        await interaction.response.send_message("Registra prima un team!", ephemeral=True)
        return
    team = db["teams"][uid]
    if team["cap_space"] < stipendio:
        await interaction.response.send_message("Budget insufficiente!", ephemeral=True)
        return
    team["roster"].append({"nome": nome, "stipendio": stipendio, "posizione": "N/D", "overall": 0})
    team["cap_space"] = round(team["cap_space"] - stipendio, 1)
    save_db(db)
    await interaction.response.send_message(f"Firmato {nome} per ${stipendio}M!")

@bot.tree.command(name="taglia", description="Taglia un giocatore")
async def taglia(interaction: discord.Interaction, nome_giocatore: str):
    db = load_db()
    uid = str(interaction.user.id)
    if uid not in db["teams"]: return
    team = db["teams"][uid]
    p = next((x for x in team["roster"] if x["nome"].lower() == nome_giocatore.lower()), None)
    if not p:
        await interaction.response.send_message("Giocatore non trovato.", ephemeral=True)
        return
    team["roster"].remove(p)
    team["cap_space"] = round(team["cap_space"] + p["stipendio"], 1)
    save_db(db)
    await interaction.response.send_message(f"Tagliato {p['nome']}. Recuperati ${p['stipendio']}M.")

@bot.tree.command(name="proponi_trade", description="Proponi scambio")
async def proponi_trade(interaction: discord.Interaction, utente: discord.Member, mio_p: str, suo_p: str):
    db = load_db()
    u1, u2 = str(interaction.user.id), str(utente.id)
    if u1 not in db["teams"] or u2 not in db["teams"]:
        await interaction.response.send_message("Team non registrati.", ephemeral=True)
        return
    db["trades"].append({"da":u1, "a":u2, "p1":mio_p, "p2":suo_p, "stato":"attesa"})
    save_db(db)
    await interaction.response.send_message(f"Trade proposta a {utente.mention}!")

@bot.tree.command(name="accetta_trade", description="Accetta trade")
async def accetta_trade(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    t = next((x for x in reversed(db["trades"]) if x["a"] == uid and x["stato"] == "attesa"), None)
    if not t:
        await interaction.response.send_message("Nessuna trade.", ephemeral=True)
        return
    t1, t2 = db["teams"][t["da"]], db["teams"][uid]
    p1 = next((x for x in t1["roster"] if x["nome"].lower() == t["p1"].lower()), None)
    p2 = next((x for x in t2["roster"] if x["nome"].lower() == t["p2"].lower()), None)
    if not p1 or not p2:
        await interaction.response.send_message("Giocatori non piu' disponibili.", ephemeral=True)
        return
    t1["roster"].remove(p1); t2["roster"].remove(p2)
    t1["roster"].append(p2); t2["roster"].append(p1)
    t1["cap_space"] = round(t1["cap_space"] + p1["stipendio"] - p2["stipendio"], 1)
    t2["cap_space"] = round(t2["cap_space"] + p2["stipendio"] - p1["stipendio"], 1)
    t["stato"] = "fatto"
    save_db(db)
    await interaction.response.send_message("Trade completata!")

bot.run(os.getenv("DISCORD_TOKEN"))
