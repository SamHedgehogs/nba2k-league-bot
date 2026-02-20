import os
import discord
from discord.ext import commands
from discord import app_commands
import json
import urllib.request
import asyncio

# URL Apps Script (web app, accesso: Chiunque)
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwuJkvPsNo_QLRrPTwo-H6Lm79xm0n56ukoVpAsUjHzZlQq62GoSLqZh5LVkJCkT0KS/exec"

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
    "houston": "ROCKETS", "los angeles clippers": "CLIPPERS",
    "los angeles lakers": "LAKERS", "memphis": "GRIZZLIES",
    "minnesota": "TIMBERWOLVES", "new orleans": "PELICANS",
    "oklahoma": "THUNDER", "phoenix": "SUNS", "portland": "BLAZERS",
    "sacramento": "KINGS", "san antonio": "SPURS", "utah": "JAZZ",
    "atlanta": "HAWKS",
}

CAP = 225  # Salary cap
LUX_TAX = 275  # Luxury tax threshold

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

def _fetch_sync():
    req = urllib.request.Request(
        APPS_SCRIPT_URL,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)

async def fetch_sheet_data():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_sync)

def load_db():
    try:
        with open('league_db.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"teams": {}, "players": [], "trades": [], "reali": {}}

def save_db(data):
    with open('league_db.json', 'w') as f:
        json.dump(data, f, indent=4)

def fmt_sal(s):
    """Formatta stipendio per la tabella monospace."""
    if s == 'RFA':
        return 'RFA  '
    if not s or s == 0:
        return 'FA   '
    return f"{s}M  "

def sal_bar(total, cap=CAP):
    """Barra visiva del salary cap."""
    pct = min(total / cap, 1.2)
    filled = int(pct * 10)
    bar = '█' * filled + '░' * (10 - min(filled, 10))
    if total > LUX_TAX:
        status = '🔴'
    elif total > CAP:
        status = '🟡'
    else:
        status = '🟢'
    return f"{status} `{bar}` ${round(total, 1)}M / ${cap}M"

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
            f"Squadra **'{squadra}'** non trovata.\nProva con: `Bucks`, `Sixers`, `Lakers`, `Celtics`..."
        )
        return

    players = team_info.get("roster", [])
    discord_user = team_info.get("discord_user", "")
    nome_squadra = team_info.get("squadra", team_key)

    sorted_players = sorted(players, key=lambda x: x.get('overall', 0), reverse=True)

    # Calcolo totali salary
    def safe_sum(year_key):
        return sum(
            (p.get(year_key) or 0)
            for p in players
            if p.get(year_key) not in ('RFA', None, 0, '')
        )

    sal26 = safe_sum('stipendio_2k26')
    sal27 = safe_sum('stipendio_2k27')
    sal28 = safe_sum('stipendio_2k28')

    # --- Costruisce tabella monospace ---
    # Header
    lines = []
    lines.append(f"{'#':<3} {'GIOCATORE':<22} {'OVR':<5} {'2K26':>7} {'2K27':>7} {'2K28':>7}")
    lines.append("-" * 54)

    for i, p in enumerate(sorted_players, 1):
        nome = p.get('nome', '???')
        # Tronca nomi lunghi
        if len(nome) > 21:
            nome = nome[:19] + '..''
        ovr = p.get('overall', 0)
        s26 = p.get('stipendio_2k26', 0)
        s27 = p.get('stipendio_2k27', 0)
        s28 = p.get('stipendio_2k28', 0)

        def cell(v):
            if v == 'RFA':
                return 'RFA'
            if not v or v == 0:
                return '-'
            return f"${v}M"

        lines.append(
            f"{i:<3} {nome:<22} {ovr:<5} {cell(s26):>7} {cell(s27):>7} {cell(s28):>7}"
        )

    table = "```\n" + "\n".join(lines) + "\n```"

    # --- Embed ---
    # Colore: verde se sotto cap, arancio se sopra, rosso se luxury tax
    if sal26 > LUX_TAX:
        color = 0xFF0000
    elif sal26 > CAP:
        color = 0xFF8C00
    else:
        color = 0x00C851

    embed = discord.Embed(
        title=f"🏀 {nome_squadra}",
        description=table,
        color=color
    )

    # GM
    if discord_user:
        embed.add_field(name="👤 GM", value=f"`{discord_user}`", inline=True)

    # OVR medio top 8
    top8 = sorted_players[:8]
    if top8:
        avg_ovr = round(sum(p.get('overall', 0) for p in top8) / len(top8), 1)
        embed.add_field(name="⭐ OVR medio Top 8", value=f"`{avg_ovr}`", inline=True)

    embed.add_field(name="\u200b", value="\u200b", inline=False)

    # Salary bars
    embed.add_field(
        name="💰 Salary 2K26",
        value=sal_bar(sal26),
        inline=False
    )
    if sal27 > 0:
        embed.add_field(
            name="💰 Salary 2K27",
            value=sal_bar(sal27),
            inline=False
        )
    if sal28 > 0:
        embed.add_field(
            name="💰 Salary 2K28",
            value=sal_bar(sal28),
            inline=False
        )

    embed.set_footer(text=f"Cap: ${CAP}M  |  Luxury Tax: ${LUX_TAX}M  |  🟢 Sotto cap  🟡 Over cap  🔴 Luxury tax")

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="init_league", description="Ricarica i dati dal Google Sheet e mostra le squadre trovate")
async def init_league(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        all_data = await fetch_sheet_data()
        db = load_db()
        db["reali"] = all_data
        save_db(db)
        team_list = ", ".join(all_data.keys())
        await interaction.followup.send(
            f"Dati lega caricati! **{len(all_data)} squadre**: {team_list}"
        )
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

    msg = f"Canali pronti nella categoria **FRANCHIGIE**.\n"
    if created:
        msg += f"✅ Creati: {', '.join(created)}\n"
    if skipped:
        msg += f"⏭️ Gia' esistenti: {', '.join(skipped)}"
    await interaction.followup.send(msg)

bot.run(os.getenv("DISCORD_TOKEN"))
