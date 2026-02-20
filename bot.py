import os
import discord
from discord.ext import commands
from discord import app_commands
import json
import urllib.request
import asyncio

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwuJkvPsNo_QLRrPTwo-H6Lm79xm0n56ukoVpAsUjHzZlQq62GoSLqZh5LVkJCkT0KS/exec"

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

CAP = 225
LUX_TAX = 275

def find_team_in_data(query, data):
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
    req = urllib.request.Request(APPS_SCRIPT_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)

async def fetch_sheet_data():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_sync)

def sal_bar(total):
    pct = min(total / CAP, 1.3)
    filled = int(pct * 10)
    bar = chr(9608) * min(filled, 10) + chr(9617) * (10 - min(filled, 10))
    if total > LUX_TAX:
        status = "\U0001f534"
    elif total > CAP:
        status = "\U0001f7e1"
    else:
        status = "\U0001f7e2"
    return f"{status} `{bar}` ${round(total, 1)}M / ${CAP}M"

def create_roster_embed(team_key, team_info):
    players = team_info.get("roster", [])
    discord_user = team_info.get("discord_user", "")
    nome_squadra = team_info.get("squadra", team_key)
    sorted_players = sorted(players, key=lambda x: x.get("overall", 0), reverse=True)

    def safe_sum(key):
        return sum((p.get(key) or 0) for p in players if p.get(key) not in ("RFA", None, 0, ""))

    sal26 = safe_sum("stipendio_2k26")
    sal27 = safe_sum("stipendio_2k27")
    sal28 = safe_sum("stipendio_2k28")

    def cell(v):
        if v == "RFA": return "RFA"
        if not v or v == 0: return "-"
        return f"${v}M"

    lines = [f"{'#':<3} {'GIOCATORE':<22} {'OVR':<5} {'2K26':>7} {'2K27':>7} {'2K28':>7}", "-" * 54]
    for i, p in enumerate(sorted_players, 1):
        p_nome = p.get("nome", "???")
        if len(p_nome) > 21: p_nome = p_nome[:19] + ".."
        lines.append(f"{i:<3} {p_nome:<22} {p.get('overall',0):<5} {cell(p.get('stipendio_2k26')):>7} {cell(p.get('stipendio_2k27')):>7} {cell(p.get('stipendio_2k28')):>7}")

    table = "```\n" + "\n".join(lines) + "\n```"
    color = 0xFF0000 if sal26 > LUX_TAX else (0xFF8C00 if sal26 > CAP else 0x00C851)
    
    embed = discord.Embed(title=f"\U0001f3c0 {nome_squadra}", description=table, color=color)
    if discord_user: embed.add_field(name="\U0001f464 GM", value=f"`{discord_user}`", inline=True)
    
    top8 = sorted_players[:8]
    if top8:
        avg_ovr = round(sum(p.get("overall", 0) for p in top8) / len(top8), 1)
        embed.add_field(name="\u2b50 OVR medio Top 8", value=f"`{avg_ovr}`", inline=True)

    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(name="\U0001f4b0 Salary 2K26", value=sal_bar(sal26), inline=False)
    if sal27 > 0: embed.add_field(name="\U0001f4b0 Salary 2K27", value=sal_bar(sal27), inline=False)
    if sal28 > 0: embed.add_field(name="\U0001f4b0 Salary 2K28", value=sal_bar(sal28), inline=False)
    embed.set_footer(text=f"Cap: ${CAP}M | Luxury Tax: ${LUX_TAX}M")
    return embed

class LeagueBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        await self.tree.sync()

bot = LeagueBot()

@bot.tree.command(name="roster", description="Mostra il roster di una squadra")
async def roster(interaction: discord.Interaction, squadra: str):
    await interaction.response.defer()
    try:
        all_data = await fetch_sheet_data()
        team_key, team_info = find_team_in_data(squadra, all_data)
        if not team_info:
            await interaction.followup.send(f"Squadra **{squadra}** non trovata.")
            return
        await interaction.followup.send(embed=create_roster_embed(team_key, team_info))
    except Exception as e:
        await interaction.followup.send(f"Errore: {e}")

@bot.tree.command(name="crea_canali_team", description="Crea i canali per ogni franchigia e posta il roster")
async def crea_canali_team(interaction: discord.Interaction):
    await interaction.response.defer()
    guild = interaction.guild
    try:
        all_data = await fetch_sheet_data()
    except Exception as e:
        await interaction.followup.send(f"Errore caricamento dati: {e}")
        return

    category = discord.utils.get(guild.categories, name="FRANCHIGIE")
    if not category:
        try: category = await guild.create_category("FRANCHIGIE")
        except:
            await interaction.followup.send("Errore permessi categoria.")
            return

    existing_channels = {c.name: c for c in category.text_channels}
    
    async def process_team(team_key, team_info):
        c_name = team_key.lower().replace(" ", "-")
        try:
            channel = existing_channels.get(c_name)
            if not channel:
                channel = await guild.create_text_channel(c_name, category=category)
                status = "NEW"
            else:
                status = "UPD"
            
            # Pulisce vecchi messaggi del bot e posta il roster aggiornato
            async for message in channel.history(limit=50):
                if message.author == bot.user: await message.delete()
            
            await channel.send(embed=create_roster_embed(team_key, team_info))
            return status
        except: return "KO"

    results = await asyncio.gather(*(process_team(k, v) for k, v in all_data.items()))
    await interaction.followup.send(f"**Operazione Completata!**\nNuovi: {results.count('NEW')}\nAggiornati: {results.count('UPD')}\nFalliti: {results.count('KO')}")

bot.run(os.getenv("DISCORD_TOKEN"))
