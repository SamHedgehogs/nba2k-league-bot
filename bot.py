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

# --- REGISTRA TEAM ---
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
        await interaction.response.send_message(
            f"**{nome_squadra}** non e' una franchigia valida!

Franchigie disponibili:
{lista}",
            ephemeral=True
        )
        return

    nome_ufficiale = FRANCHIGIE_NBA[franchige_lower.index(nome_squadra.lower())]
    franchigie_prese = [t["nome"] for t in db["teams"].values()]
    
    if nome_ufficiale in franchigie_prese:
        await interaction.response.send_message(
            f"I **{nome_ufficiale}** sono gia' stati scelti da un altro utente!",
            ephemeral=True
        )
        return

    # Inizializza team
    db["teams"][user_id] = {"nome": nome_ufficiale, "cap_space": 160, "roster": []}
    
    # Importa roster dal Google Sheet se possibile
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        async with session.get(APPS_SCRIPT_URL) as response:
            if response.status == 200:
                full_data = await response.json()
                if nome_ufficiale in full_data:
                    roster = full_data[nome_ufficiale]
                    db["teams"][user_id]["roster"] = roster
                    totale_stipendi = sum(p["stipendio"] for p in roster)
                    db["teams"][user_id]["cap_space"] = round(160 - totale_stipendi, 1)
                    save_db(db)
                    await interaction.followup.send(f"Franchigia **{nome_ufficiale}** registrata con successo! Ho caricato {len(roster)} giocatori dal roster reale.")
                    return

    save_db(db)
    await interaction.followup.send(f"Franchigia **{nome_ufficiale}** registrata. (Errore caricamento roster, usa /firma_fa)")

# --- FRANCHIGIE DISPONIBILI ---
@bot.tree.command(name="franchigie", description="Mostra le franchigie NBA ancora disponibili")
async def franchigie(interaction: discord.Interaction):
    db = load_db()
    prese = [t["nome"] for t in db["teams"].values()]
    disponibili = [f for f in FRANCHIGIE_NBA if f not in prese]
    
    if not disponibili:
        await interaction.response.send_message("Tutte le 30 franchigie sono state assegnate!")
        return

    lista = "
".join([f"- {f}" for f in disponibili])
    embed = discord.Embed(
        title=f"Franchigie disponibili ({len(disponibili)}/30)",
        description=lista,
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed)

# --- INFO TEAM ---
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

# --- ROSTER ---
@bot.tree.command(name="roster", description="Mostra il roster di una squadra")
async def roster(interaction: discord.Interaction, utente: discord.Member = None):
    db = load_db()
    target_user = utente or interaction.user
    user_id = str(target_user.id)
    
    if user_id not in db["teams"]:
        await interaction.response.send_message("Questo utente non ha una squadra.", ephemeral=True)
        return
    
    team = db["teams"][user_id]
    players = team["roster"]
    
    if not players:
        await interaction.response.send_message(f"Il roster dei **{team['nome']}** e' vuoto.")
        return
    
    # Ordina per overall decrescente
    sorted_players = sorted(players, key=lambda x: x.get('overall', 0), reverse=True)
    
    desc = ""
    for p in sorted_players:
        pos = p.get('posizione', 'N/D')
        ovr = p.get('overall', '??')
        desc += f"🏀 **{p['nome']}** ({pos}) - OVR: {ovr} - ${p['stipendio']}M
"

    embed = discord.Embed(title=f"Roster: {team['nome']}", description=desc, color=discord.Color.green())
    embed.set_footer(text=f"Cap Space rimanente: ${team['cap_space']}M")
    await interaction.response.send_message(embed=embed)

# --- FIRMA FREE AGENT ---
@bot.tree.command(name="firma_fa", description="Firma un giocatore free agent")
async def firma_fa(interaction: discord.Interaction, nome: str, stipendio: float):
    db = load_db()
    user_id = str(interaction.user.id)
    if user_id not in db["teams"]:
        await interaction.response.send_message("Devi prima registrare un team!", ephemeral=True)
        return
    
    team = db["teams"][user_id]
    if team["cap_space"] < stipendio:
        await interaction.response.send_message("Non hai abbastanza spazio salariale!", ephemeral=True)
        return
    
    team["roster"].append({"nome": nome, "stipendio": stipendio, "posizione": "N/D", "overall": 0})
    team["cap_space"] = round(team["cap_space"] - stipendio, 1)
    save_db(db)
    await interaction.response.send_message(f"Hai firmato **{nome}** per **${stipendio}M**!")

# --- TAGLIA GIOCATORE ---
@bot.tree.command(name="taglia", description="Taglia un giocatore dal tuo roster")
async def taglia(interaction: discord.Interaction, nome_giocatore: str):
    db = load_db()
    user_id = str(interaction.user.id)
    if user_id not in db["teams"]:
        await interaction.response.send_message("Non hai una squadra!", ephemeral=True)
        return
    
    team = db["teams"][user_id]
    player = next((p for p in team["roster"] if p["nome"].lower() == nome_giocatore.lower()), None)
    
    if not player:
        await interaction.response.send_message(f"Giocatore **{nome_giocatore}** non trovato nel roster.", ephemeral=True)
        return
    
    team["roster"].remove(player)
    team["cap_space"] = round(team["cap_space"] + player["stipendio"], 1)
    save_db(db)
    await interaction.response.send_message(f"Hai tagliato **{player['nome']}**. Recuperati ${player['stipendio']}M.")

# --- PROPONI TRADE ---
@bot.tree.command(name="proponi_trade", description="Proponi uno scambio a un altro utente")
async def proponi_trade(interaction: discord.Interaction, utente_avversario: discord.Member, mio_giocatore: str, giocatore_avversario: str):
    db = load_db()
    user_id = str(interaction.user.id)
    target_id = str(utente_avversario.id)
    
    if user_id not in db["teams"] or target_id not in db["teams"]:
        await interaction.response.send_message("Entrambi i team devono essere registrati!", ephemeral=True)
        return
    
    team_a = db["teams"][user_id]
    team_b = db["teams"][target_id]
    
    p_a = next((p for p in team_a["roster"] if p["nome"].lower() == mio_giocatore.lower()), None)
    p_b = next((p for p in team_b["roster"] if p["nome"].lower() == giocatore_avversario.lower()), None)
    
    if not p_a:
        await interaction.response.send_message(f"**{mio_giocatore}** non e' nel tuo roster!", ephemeral=True)
        return
    if not p_b:
        await interaction.response.send_message(f"**{giocatore_avversario}** non e' nel roster di {team_b['nome']}!", ephemeral=True)
        return
    
    db["trades"].append({"da": user_id, "a": target_id, "giocatore_da": p_a["nome"], "giocatore_a": p_b["nome"], "stato": "in attesa"})
    save_db(db)
    
    embed = discord.Embed(title="Proposta di Trade!", color=discord.Color.orange())
    embed.add_field(name=f"{team_a['nome']} offre", value=p_a['nome'])
    embed.add_field(name=f"{team_b['nome']} cede", value=p_b['nome'])
    embed.set_footer(text=f"{utente_avversario.display_name} usa /accetta_trade")
    await interaction.response.send_message(embed=embed)

# --- ACCETTA TRADE ---
@bot.tree.command(name="accetta_trade", description="Accetta l'ultima trade proposta al tuo team")
async def accetta_trade(interaction: discord.Interaction):
    db = load_db()
    user_id = str(interaction.user.id)
    
    trade = next((t for t in reversed(db["trades"]) if t["a"] == user_id and t["stato"] == "in attesa"), None)
    
    if not trade:
        await interaction.response.send_message("Non hai trade in attesa.", ephemeral=True)
        return
    
    team_a = db["teams"][trade["da"]]
    team_b = db["teams"][user_id]
    
    p_a = next((p for p in team_a["roster"] if p["nome"] == trade["giocatore_da"]), None)
    p_b = next((p for p in team_b["roster"] if p["nome"] == trade["giocatore_a"]), None)
    
    if not p_a or not p_b:
        await interaction.response.send_message("Errore: uno dei giocatori non e' piu' disponibile.", ephemeral=True)
        return

    # Scambio
    team_a["roster"].remove(p_a)
    team_b["roster"].remove(p_b)
    team_a["roster"].append(p_b)
    team_b["roster"].append(p_a)
    
    # Ricalcolo Cap Space
    team_a["cap_space"] = round(team_a["cap_space"] + p_a["stipendio"] - p_b["stipendio"], 1)
    team_b["cap_space"] = round(team_b["cap_space"] + p_b["stipendio"] - p_a["stipendio"], 1)
    
    trade["stato"] = "completata"
    save_db(db)
    
    await interaction.response.send_message(f"Trade completata! **{p_a['nome']}** va a {team_b['nome']}, **{p_b['nome']}** va a {team_a['nome']}!")

token = os.getenv("DISCORD_TOKEN")
bot.run(token)
