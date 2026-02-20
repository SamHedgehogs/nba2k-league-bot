import os
import discord
from discord.ext import commands
from discord import app_commands
import json
import urllib.request
import asyncio

# URL Apps Script (web app, accesso: Chiunque)
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxU7vLSn0dZuVVfZTO9M6Ynl5MuXQPwcMJNFnHX2HbhZM_VzBQGHtVSZ4nVw1kVZ5eE/exec"

# Mapping nickname -> parola chiave nel nome squadra del Sheet (MAIUSCOLO)
TEAM_ALIASES = {
    "hawks": "HAWKS", "celtics": "CELTICS", "nets": "NETS",
    "hornets": "HORNETS", "bulls": "BULLS", "cavaliers": "CAVALIERS",
    "cavs": "CAVALIERS", "pistons": "PISTONS", "pacers": "PACERS",
    "heat": "HEAT", "bucks": "BUCKS", "knicks": "KNICKS",
    "magic": "MAGIC", "sixers": "76ERS", "76ers": "76ERS",
    "philadelphia": "76ERS", "raptors": "RAPTORS", "wizards": "WIZARDS",
    "washington": "WIZARDS", "mavericks": "MAVERICKS", "mavs": "MAVERICKS",
    "nuggets": "NUGGETS", "warriors": "WARRIORS", "rockets": "ROCKETS",
    "clippers": "CLIPPERS", "lakers": "LAKERS", "grizzlies": "GRIZZLIES",
    "timberwolves": "TIMBERWOLVES", "wolves": "TIMBERWOLVES",
    "pelicans": "PELICANS", "thunder": "THUNDER", "okc": "THUNDER",
    "suns": "SUNS", "trail blazers": "BLAZERS", "blazers": "BLAZERS",
    "kings": "KINGS", "spurs": "SPURS", "jazz": "JAZZ",
    "milwaukee": "BUCKS", "boston": "CELTICS", "brooklyn": "NETS",
    "charlotte": "HORNETS", "chicago": "BULLS", "cleveland": "CAVALIERS",
    "detroit": "PISTONS", "indiana": "PACERS", "miami": "HEAT",
    "new york": "KNICKS", "orlando": "MAGIC", "toronto": "RAPTORS",
    "dallas": "MAVERICKS", "denver": "NUGGETS", "golden state": "WARRIORS",
    "houston": "ROCKETS", "memphis": "GRIZZLIES", "minnesota": "TIMBERWOLVES",
    "new orleans": "PELICANS", "oklahoma": "THUNDER", "phoenix": "SUNS",
    "portland": "BLAZERS", "sacramento": "KINGS", "san antonio": "SPURS",
    "utah": "JAZZ", "atlanta": "HAWKS",
}

def find_team_in_data(query: str, data: dict):
    q = query.strip().lower()
    for key in data:
        if key.lower() == q:
            return key, data[key]
    keyword = TEAM_ALIASES.get(q)
    if keyword:
        for key in data:
            if keyword in key.upper():
                return key, data[key]
    for key in data:
        if q in key.lower():
            return key, data[key]
    return None, None

def _fetch_sync(url):
    """Fetch sincrono con urllib (gestisce redirect automaticamente)."""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; NBA2KBot/1.0)'
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode('utf-8')
        return json.loads(raw)

async def fetch_sheet_data():
    """Scarica i dati dal Google Sheet in modo asincrono."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_sync, APPS_SCRIPT_URL)

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
        await self.tree.sync()
        print(f"Comandi sincronizzati per {self.user}")

bot = LeagueBot()

@bot.event
async def on_ready():
    print(f'Lega NBA 2K Online! Loggato come {bot.user}')

@bot.tree.command(name="roster", description="Mostra il roster di una squadra")
@app_commands.describe(squadra="Nome della franchigia (es: Bucks, Sixers, Lakers)")
async def roster(interaction: discord.Interaction, squadra: str):
    await interaction.response.defer()
    try:
        all_data = await fetch_sheet_data()
    except Exception as e:
        await interaction.followup.send(f"Errore connessione Apps Script: {e}")
        return

    team_key, team_info = find_team_in_data(squadra, all_data)
    if not team_info:
        await interaction.followup.send(
            f"Squadra '{squadra}' non trovata. Prova con: Bucks, Sixers, Lakers, Celtics..."
        )
        return

    players = team_info.get("roster", [])
    discord_user = team_info.get("discord_user", "")
    nome_squadra = team_info.get("squadra", team_key)

    sal26_tot = sum(p.get("stipendio_2k26", 0) or 0 for p in players if p.get("stipendio_2k26") != "RFA")
    sal27_tot = sum(p.get("stipendio_2k27", 0) or 0 for p in players if p.get("stipendio_2k27") not in ("RFA", 0, None))
    sal28_tot = sum(p.get("stipendio_2k28", 0) or 0 for p in players if p.get("stipendio_2k28") not in ("RFA", 0, None))
    CAP = 225

    sorted_players = sorted(players, key=lambda x: x.get('overall', 0), reverse=True)

    def fmt_sal(s):
        if s == 'RFA': return 'RFA'
        if not s: return '-'
        return f"${s}M"

    desc_lines = []
    for p in sorted_players:
        nome = p.get('nome', 'Sconosciuto')
        ovr = p.get('overall', '?')
        s26 = p.get('stipendio_2k26', 0)
        s27 = p.get('stipendio_2k27', 0)
        s28 = p.get('stipendio_2k28', 0)
        desc_lines.append(f"**{nome}** (OVR {ovr}) | 2K26:{fmt_sal(s26)} 2K27:{fmt_sal(s27)} 2K28:{fmt_sal(s28)}")

    desc = "\n".join(desc_lines) if desc_lines else "Roster vuoto"
    if len(desc) > 4000:
        desc = desc[:4000] + "\n..."

    embed = discord.Embed(title=nome_squadra, description=desc, color=0x1E90FF)
    if discord_user:
        embed.add_field(name="GM", value=discord_user, inline=True)
    embed.add_field(name="Salary 2K26", value=f"${round(sal26_tot,2)}M / ${CAP}M", inline=True)
    if sal27_tot:
        embed.add_field(name="Salary 2K27", value=f"${round(sal27_tot,2)}M / ${CAP}M", inline=True)
    if sal28_tot:
        embed.add_field(name="Salary 2K28", value=f"${round(sal28_tot,2)}M / ${CAP}M", inline=True)

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="init_league", description="Ricarica i dati dal Google Sheet")
async def init_league(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        all_data = await fetch_sheet_data()
        db = load_db()
        db["reali"] = all_data
        save_db(db)
        team_list = ", ".join(all_data.keys())
        await interaction.followup.send(f"Dati lega caricati! {len(all_data)} squadre: {team_list}")
    except Exception as e:
        await interaction.followup.send(f"Errore Apps Script: {e}")

@bot.tree.command(name="crea_canali_team", description="Crea i canali per ogni franchigia nella categoria FRANCHIGIE")
async def crea_canali_team(interaction: discord.Interaction):
    await interaction.response.defer()
    guild = interaction.guild
    try:
        all_data = await fetch_sheet_data()
        team_names = list(all_data.keys())
    except Exception:
        team_names = []

    category = discord.utils.get(guild.categories, name="FRANCHIGIE")
    if not category:
        category = await guild.create_category("FRANCHIGIE")

    created, skipped = [], []
    for nome in team_names:
        c_name = nome.lower().replace(" ", "-")
        existing = discord.utils.get(category.text_channels, name=c_name)
        if not existing:
            await guild.create_text_channel(c_name, category=category)
            created.append(c_name)
        else:
            skipped.append(c_name)

    msg = "Canali pronti nella categoria 'FRANCHIGIE'.\n"
    if created: msg += f"Creati: {', '.join(created)}\n"
    if skipped: msg += f"Gia' esistenti: {', '.join(skipped)}"
    await interaction.followup.send(msg)

bot.run(os.getenv("DISCORD_TOKEN"))
