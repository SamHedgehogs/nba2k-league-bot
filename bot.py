import os
import discord
from discord.ext import commands
from discord import app_commands
import json
import urllib.request
import asyncio

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzVqbuwreLosa2ppL3sK8bUGAxAHFBdqZxbGq5Qru-mgV6_ducAFDWK25JoVN4DB_NT/exec"

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

# NUOVE SOGLIE SALARY
MIN_CAP = 130
SAL_CAP = 160
HARD_CAP = 200

ADMIN_CHANNEL_NAME = "admin-league"
MERCATO_CHANNEL_NAME = "mercato"

def find_team_in_data(query, data):
    q = query.strip().lower()
    for key in data:
        if key.lower() == q: return key, data[key]
    keyword = TEAM_ALIASES.get(q)
    if keyword:
        for key in data:
            if keyword in key.upper(): return key, data[key]
    for key in data:
        if q in key.lower(): return key, data[key]
    return None, None

def _fetch_sync():
    req = urllib.request.Request(APPS_SCRIPT_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

async def fetch_sheet_data():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_sync)

def sal_bar(total):
    pct = min(total / SAL_CAP, 1.3)
    filled = int(pct * 10)
    bar = chr(9608) * min(filled, 10) + chr(9617) * (10 - min(filled, 10))
    if total > HARD_CAP: 
        status = "\U0001f534" # Rosso (🔴)
    elif total > SAL_CAP: 
        status = "\U0001f7e1" # Giallo (🟡)
    elif total >= MIN_CAP: 
        status = "\U0001f7e2" # Verde (🟢)
    else: 
        status = "\U0001f535" # Blu (🔵)
    return f"{status} `{bar}` ${round(total, 1)}M / ${SAL_CAP}M"

def create_roster_embed(team_key, team_info):
    players = team_info.get("roster", [])
    nome_squadra = team_info.get("squadra", team_key)
    sorted_players = sorted(players, key=lambda x: x.get("overall", 0), reverse=True)

    def safe_sum(key):
        return sum((p.get(key) or 0) for p in players if p.get(key) not in ("RFA", "UFA", "-"))

    sal26 = safe_sum("stipendio_2k26")

    def cell(v):
        if v in ("RFA", "UFA"): return v
        return f"{v}" if v and v != 0 else "-"

    header = f"{'#':<2} {'GIOCATORE':<18} {'OVR':<3} {'26':>4} {'27':>4} {'28':>4} {'29':>4} {'30':>4}"
    lines = [header, "-" * 55]
    for i, p in enumerate(sorted_players, 1):
        n = p.get("nome", "???")
        if len(n) > 18: n = n[:16] + ".."
        row = f"{i:<2} {n:<18} {p.get('overall',0):<3} {cell(p.get('stipendio_2k26')):>4} {cell(p.get('stipendio_2k27')):>4} {cell(p.get('stipendio_2k28')):>4} {cell(p.get('stipendio_2k29')):>4} {cell(p.get('stipendio_2k30')):>4}"
        lines.append(row)

    table = "```
" + "
".join(lines) + "
```"
    color = 0xFF0000 if sal26 > HARD_CAP else (0xFF8C00 if sal26 > SAL_CAP else 0x00FF00)
    embed = discord.Embed(title=f"\U0001f3c0 {nome_squadra}", description=table, color=color)
    
    if team_info.get("discord_user"):
        embed.add_field(name="\U0001f464 GM", value=f"<@{team_info['discord_user']}>", inline=True)
    
    top8 = sorted_players[:8]
    if top8:
        avg = round(sum(p.get("overall", 0) for p in top8) / len(top8), 1)
        embed.add_field(name="\u2b50 OVR Top 8", value=f"`{avg}`", inline=True)
    
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(name="\U0001f4b0 Salary 2K26", value=sal_bar(sal26), inline=False)
    return embed

class LeagueBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = LeagueBot()

@bot.tree.command(name="roster", description="Mostra il roster di una squadra")
async def roster(interaction: discord.Interaction, squadra: str):
    await interaction.response.defer()
    data = await fetch_sheet_data()
    key, info = find_team_in_data(squadra, data)
    if not info:
        await interaction.followup.send("Squadra non trovata.")
        return
    await interaction.followup.send(embed=create_roster_embed(key, info))

@bot.tree.command(name="crea_canali_team", description="Inizializza canali e roster")
async def crea_canali_team(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await fetch_sheet_data()
    cat = discord.utils.get(interaction.guild.categories, name="FRANCHIGIE") or await interaction.guild.create_category("FRANCHIGIE")
    
    async def proc(k, v):
        name = k.lower().replace(" ", "-")
        ch = discord.utils.get(cat.text_channels, name=name) or await interaction.guild.create_text_channel(name, category=cat)
        async for m in ch.history(limit=50):
            if m.author == bot.user: await m.delete()
        await ch.send(embed=create_roster_embed(k, v))
        
    await asyncio.gather(*(proc(k, v) for k, v in data.items()))
    await interaction.followup.send("Canali aggiornati con roster!")

@bot.tree.command(name="cut", description="Taglia un giocatore dal roster")
async def cut(interaction: discord.Interaction, giocatore: str, motivazione: str = "Nessuna"):
    admin_ch = discord.utils.get(interaction.guild.text_channels, name=ADMIN_CHANNEL_NAME)
    if not admin_ch:
        await interaction.response.send_message("Canale admin non trovato.", ephemeral=True)
        return
    embed = discord.Embed(title="\u2702\ufe0f Richiesta CUT", color=0xFF4444)
    embed.add_field(name="GM", value=interaction.user.mention)
    embed.add_field(name="Giocatore", value=giocatore)
    embed.add_field(name="Motivazione", value=motivazione)
    await admin_ch.send(embed=embed)
    await interaction.response.send_message(f"Richiesta di taglio per **{giocatore}** inviata agli admin!", ephemeral=True)

@bot.tree.command(name="firma_free_agent", description="Invia un'offerta a un Free Agent")
async def firma_fa(interaction: discord.Interaction, giocatore: str, offerta: str, anni: int, motivazione: str = "Nessuna"):
    admin_ch = discord.utils.get(interaction.guild.text_channels, name=ADMIN_CHANNEL_NAME)
    if not admin_ch:
        await interaction.response.send_message("Canale admin non trovato.", ephemeral=True)
        return
    embed = discord.Embed(title="\U0001f50b Offerta Free Agent", color=0x4444FF)
    embed.add_field(name="GM", value=interaction.user.mention)
    embed.add_field(name="Giocatore", value=giocatore)
    embed.add_field(name="Offerta", value=offerta)
    embed.add_field(name="Durata", value=f"{anni} anni")
    embed.add_field(name="Motivazione", value=motivazione)
    await admin_ch.send(embed=embed)
    await interaction.response.send_message(f"Offerta per **{giocatore}** registrata. Attendi la valutazione degli admin.", ephemeral=True)

@bot.tree.command(name="trade", description="Proponi una trade")
async def trade(interaction: discord.Interaction, squadra_ricevente: str, giocatori_dati: str, giocatori_ricevuti: str, stipendio_ceduto: float, stipendio_ricevuto: float):
    await interaction.response.defer(ephemeral=True)
    data = await fetch_sheet_data()
    k1, info1 = find_team_in_data(interaction.channel.name.replace("-", " "), data)
    k2, info2 = find_team_in_data(squadra_ricevente, data)
    if not info2:
        await interaction.followup.send("Squadra ricevente non trovata.")
        return
    
    sal1 = sum((p.get("stipendio_2k26") or 0) for p in info1.get("roster", []) if p.get("stipendio_2k26") not in ("RFA", "UFA", "-"))
    error = None
    if sal1 > HARD_CAP:
        if stipendio_ricevuto > stipendio_ceduto:
            error = f"Sei sopra l'Hard Cap (${sal1}M). Non puoi aumentare il monte ingaggi."
    elif sal1 > SAL_CAP:
        if stipendio_ricevuto > (stipendio_ceduto * 1.3):
            error = f"Sei sopra il Salary Cap (${sal1}M). Il ricevuto (${stipendio_ricevuto}M) supera il 130% del ceduto (${round(stipendio_ceduto*1.3,1)}M)."
    
    if error:
        await interaction.followup.send(f"\u26a0\ufe0f **Violazione Salary Cap:** {error}")
        return

    admin_ch = discord.utils.get(interaction.guild.text_channels, name=ADMIN_CHANNEL_NAME)
    if not admin_ch:
        await interaction.followup.send("Canale admin non trovato.")
        return

    embed = discord.Embed(title="\U0001f91d Proposta di Trade", color=0xFFFF00)
    embed.add_field(name="GM Proponente", value=interaction.user.mention)
    embed.add_field(name="Squadra Ricevente", value=k2)
    embed.add_field(name="Cede", value=f"{giocatori_dati} (${stipendio_ceduto}M)")
    embed.add_field(name="Riceve", value=f"{giocatori_ricevuti} (${stipendio_ricevuto}M)")

    class TradeView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
        @discord.ui.button(label="Accetta", style=discord.ButtonStyle.green)
        async def accept(self, b_int, button):
            mercato_ch = discord.utils.get(b_int.guild.text_channels, name=MERCATO_CHANNEL_NAME)
            if mercato_ch:
                res_embed = discord.Embed(title="\u2705 TRADE UFFICIALE", color=0x00FF00, description=f"Lo scambio tra **{k1 or 'Sconosciuta'}** e **{k2}** è stato approvato!")
                res_embed.add_field(name="Dettagli", value=f"Dati: {giocatori_dati}
Ricevuti: {giocatori_ricevuti}")
                await mercato_ch.send(embed=res_embed)
            await b_int.response.send_message("Trade approvata e postata in mercato.")
            self.stop()
        @discord.ui.button(label="Rifiuta", style=discord.ButtonStyle.red)
        async def deny(self, b_int, button):
            await b_int.response.send_message("Trade rifiutata.")
            self.stop()

    await admin_ch.send(embed=embed, view=TradeView())
    await interaction.followup.send("Proposta di trade inviata agli admin!")

bot.run(os.getenv("DISCORD_TOKEN"))
