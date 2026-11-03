
import discord
from discord.ext import commands
import os
import random
import sqlite3

intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# --------------------------------------------------
# MAGICAL DISCIPLINES
# --------------------------------------------------

MAGIC = {
    "offensive": {
        "name": "Offensive Magic",
        "emoji": "☄️"
    },
    "cunning": {
        "name": "Cunning Magic",
        "emoji": "🪶"
    },
    "defensive": {
        "name": "Defensive Magic",
        "emoji": "🛡️"
    }
}

WINS_AGAINST = {
    "offensive": "cunning",
    "cunning": "defensive",
    "defensive": "offensive"
}


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

DATABASE = "duels.db"


def initialize_database():
    with sqlite3.connect(DATABASE) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS player_stats (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                draws INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS discipline_usage (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                offensive INTEGER DEFAULT 0,
                cunning INTEGER DEFAULT 0,
                defensive INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)


def record_duel(
    guild_id,
    challenger_id,
    opponent_id,
    result,
    challenger_choice,
    opponent_choice
):
    with sqlite3.connect(DATABASE) as connection:
        for user_id in (challenger_id, opponent_id):
            connection.execute(
                "INSERT OR IGNORE INTO player_stats "
                "(guild_id, user_id) VALUES (?, ?)",
                (guild_id, user_id)
            )

        if result == "draw":
            connection.execute(
                "UPDATE player_stats SET draws = draws + 1 "
                "WHERE guild_id = ? AND user_id IN (?, ?)",
                (guild_id, challenger_id, opponent_id)
            )

        elif result == "challenger":
            connection.execute(
                "UPDATE player_stats SET wins = wins + 1 "
                "WHERE guild_id = ? AND user_id = ?",
                (guild_id, challenger_id)
            )
            connection.execute(
                "UPDATE player_stats SET losses = losses + 1 "
                "WHERE guild_id = ? AND user_id = ?",
                (guild_id, opponent_id)
            )

        else:
            connection.execute(
                "UPDATE player_stats SET wins = wins + 1 "
                "WHERE guild_id = ? AND user_id = ?",
                (guild_id, opponent_id)
            )
            connection.execute(
                "UPDATE player_stats SET losses = losses + 1 "
                "WHERE guild_id = ? AND user_id = ?",
                (guild_id, challenger_id)
            )

        # Record magical discipline usage
        for user_id, choice in (
            (challenger_id, challenger_choice),
            (opponent_id, opponent_choice)
        ):
            connection.execute(
                "INSERT OR IGNORE INTO discipline_usage "
                "(guild_id, user_id) VALUES (?, ?)",
                (guild_id, user_id)
            )

            connection.execute(
                f"UPDATE discipline_usage SET {choice} = {choice} + 1 "
                "WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
def get_player_stats(guild_id, user_id):
    with sqlite3.connect(DATABASE) as connection:
        row = connection.execute(
            "SELECT wins, losses, draws FROM player_stats "
            "WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ).fetchone()

    return row if row else (0, 0, 0)

def get_discipline_usage(guild_id, user_id):
    with sqlite3.connect(DATABASE) as connection:
        row = connection.execute(
            "SELECT offensive, cunning, defensive "
            "FROM discipline_usage "
            "WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ).fetchone()

    return row if row else (0, 0, 0)

def get_player_rank(wins):
    ranks = [
        (100, "Champion"),
        (75, "Master Duelist"),
        (50, "Expert Duelist"),
        (30, "Skilled Duelist"),
        (15, "Adept Duelist"),
        (5, "Novice Duelist"),
        (0, "First-Year Duelist")
    ]

    for required_wins, title in ranks:
        if wins >= required_wins:
            return title

    return "First-Year Duelist"
def get_leaderboard(guild_id):
    with sqlite3.connect(DATABASE) as connection:
        return connection.execute(
            "SELECT user_id, wins, losses, draws "
            "FROM player_stats WHERE guild_id = ? "
            "ORDER BY wins DESC, losses ASC, draws DESC LIMIT 10",
            (guild_id,)
        ).fetchall()


# --------------------------------------------------
# DUEL MATCH DATA
# --------------------------------------------------

class DuelMatch:
    def __init__(self, challenger, opponent):
        self.challenger = challenger
        self.opponent = opponent
        self.choices = {}
        self.message = None
        self.active_view = None
        self.finished = False

    def get_result(self):
        first = self.choices[self.challenger.id]
        second = self.choices[self.opponent.id]

        if first == second:
            return "draw"

        if WINS_AGAINST[first] == second:
            return "challenger"

        return "opponent"


# --------------------------------------------------
# SOLO DUELLING
# --------------------------------------------------

class SoloDuelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    async def on_timeout(self):
        if self.message:
            await self.message.edit(
                content="⏳ **The duel timed out!** "
                        "No choice was submitted in time.",
                view=None
            )

    async def make_choice(self, interaction, choice):
        if self.is_finished():
            await interaction.response.send_message(
                "This duel has already expired.",
                ephemeral=True
            )
            return

        computer_choice = random.choice(list(MAGIC.keys()))

        if choice == computer_choice:
            result = "The duel ends in a draw!"
        elif WINS_AGAINST[choice] == computer_choice:
            result = f"**{interaction.user.display_name} wins the duel!**"
        else:
            result = "**The computer wins the duel!**"

        await interaction.response.edit_message(
            content=(
                f"🪄 **The duel has concluded!**\n\n"
                f"**You chose:** {MAGIC[choice]['emoji']} "
                f"{MAGIC[choice]['name']}\n"
                f"**Your opponent chose:** "
                f"{MAGIC[computer_choice]['emoji']} "
                f"{MAGIC[computer_choice]['name']}\n\n"
                f"{result}"
            ),
            view=None
        )
        self.stop()

    @discord.ui.button(label="Offensive Magic", emoji="☄️",
                       style=discord.ButtonStyle.danger)
    async def offensive(self, interaction, button):
        await self.make_choice(interaction, "offensive")

    @discord.ui.button(label="Cunning Magic", emoji="🪶",
                       style=discord.ButtonStyle.primary)
    async def cunning(self, interaction, button):
        await self.make_choice(interaction, "cunning")

    @discord.ui.button(label="Defensive Magic", emoji="🛡️",
                       style=discord.ButtonStyle.success)
    async def defensive(self, interaction, button):
        await self.make_choice(interaction, "defensive")


# --------------------------------------------------
# CHALLENGE ACCEPTANCE
# --------------------------------------------------

class ChallengeView(discord.ui.View):
    def __init__(self, match):
        super().__init__(timeout=120)
        self.match = match

    async def on_timeout(self):
        if self.message and not self.match.finished:
            self.match.finished = True
            await self.message.edit(
                content=(
                    "⏳ **Challenge expired!** "
                    "No response was received in time."
                ),
                view=None
            )

    @discord.ui.button(label="Accept Duel",
                       style=discord.ButtonStyle.success)
    async def accept(self, interaction, button):
        if interaction.user.id != self.match.opponent.id:
            await interaction.response.send_message(
                "This challenge wasn't issued to you!",
                ephemeral=True
            )
            return

        self.stop()
        self.match.message = interaction.message

        active_view = ActiveDuelView(self.match)
        self.match.active_view = active_view

        await interaction.response.edit_message(
            content=(
                f"⚔️ **The duel has been accepted!**\n\n"
                f"{self.match.challenger.mention} vs "
                f"{self.match.opponent.mention}\n\n"
                f"Both duelists have **2 minutes** to select "
                f"their magical discipline. Choices remain secret "
                f"until both players have submitted."
            ),
            view=active_view
        )

    @discord.ui.button(label="Decline Duel",
                       style=discord.ButtonStyle.danger)
    async def decline(self, interaction, button):
        if interaction.user.id != self.match.opponent.id:
            await interaction.response.send_message(
                "This challenge wasn't issued to you!",
                ephemeral=True
            )
            return

        self.match.finished = True
        self.stop()

        await interaction.response.edit_message(
            content=(
                f"🚫 {self.match.opponent.mention} declined the duel "
                f"from {self.match.challenger.mention}."
            ),
            view=None
        )


# --------------------------------------------------
# ACTIVE PLAYER DUEL
# --------------------------------------------------

class ActiveDuelView(discord.ui.View):
    def __init__(self, match):
        super().__init__(timeout=120)
        self.match = match

    async def on_timeout(self):
        if self.match.finished:
            return

        self.match.finished = True

        if self.match.message:
            await self.match.message.edit(
                content=(
                    "⏳ **The duel has timed out!**\n\n"
                    "One or both duelists failed to submit "
                    "a choice within 2 minutes. "
                    "No winner has been recorded."
                ),
                view=None
            )

    @discord.ui.button(label="Choose Your Magic",
                       emoji="🪄",
                       style=discord.ButtonStyle.primary)
    async def choose(self, interaction, button):
        if self.match.finished:
            await interaction.response.send_message(
                "This duel has already ended.",
                ephemeral=True
            )
            return

        if interaction.user.id not in (
            self.match.challenger.id,
            self.match.opponent.id
        ):
            await interaction.response.send_message(
                "You aren't participating in this duel!",
                ephemeral=True
            )
            return

        if interaction.user.id in self.match.choices:
            await interaction.response.send_message(
                "You've already submitted your choice!",
                ephemeral=True
            )
            return

        choice_view = ChoiceView(self.match, interaction.user.id)

        await interaction.response.send_message(
            "Select your magical discipline. "
            "Your choice will remain hidden from your opponent.",
            view=choice_view,
            ephemeral=True
        )

        choice_view.message = await interaction.original_response()


# --------------------------------------------------
# PRIVATE PLAYER CHOICES
# --------------------------------------------------

class ChoiceView(discord.ui.View):
    def __init__(self, match, player_id):
        super().__init__(timeout=120)
        self.match = match
        self.player_id = player_id

    async def on_timeout(self):
        if self.message:
            await self.message.edit(
                content="⏳ Your selection period has expired.",
                view=None
            )

    async def make_choice(self, interaction, choice):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message(
                "These choices aren't yours!",
                ephemeral=True
            )
            return

        if self.match.finished:
            await interaction.response.edit_message(
                content="⏳ This duel has already expired.",
                view=None
            )
            return

        if self.player_id in self.match.choices:
            await interaction.response.edit_message(
                content="You've already submitted your choice!",
                view=None
            )
            return

        self.match.choices[self.player_id] = choice
        self.stop()

        await interaction.response.edit_message(
            content=(
                f"🪄 Your choice of "
                f"{MAGIC[choice]['emoji']} "
                f"**{MAGIC[choice]['name']}** "
                f"has been locked in. Waiting for your opponent..."
            ),
            view=None
        )

        if len(self.match.choices) == 2:
            await reveal_duel(self.match)

    @discord.ui.button(label="Offensive Magic", emoji="⚔️",
                       style=discord.ButtonStyle.danger)
    async def offensive(self, interaction, button):
        await self.make_choice(interaction, "offensive")

    @discord.ui.button(label="Cunning Magic", emoji="🪶",
                       style=discord.ButtonStyle.primary)
    async def cunning(self, interaction, button):
        await self.make_choice(interaction, "cunning")

    @discord.ui.button(label="Defensive Magic", emoji="🛡️",
                       style=discord.ButtonStyle.success)
    async def defensive(self, interaction, button):
        await self.make_choice(interaction, "defensive")


# --------------------------------------------------
# REVEAL THE DUEL RESULT
# --------------------------------------------------

async def reveal_duel(match):
    if match.finished:
        return

    match.finished = True

    if match.active_view:
        match.active_view.stop()

    first = match.choices[match.challenger.id]
    second = match.choices[match.opponent.id]

    result = match.get_result()

    first_magic = MAGIC[first]
    second_magic = MAGIC[second]

    if result == "draw":
        announcement = "🤝 **The duel ends in a draw!**"
    elif result == "challenger":
        announcement = (
            f"🏆 **{match.challenger.mention} wins the duel!**"
        )
    else:
        announcement = (
            f"🏆 **{match.opponent.mention} wins the duel!**"
        )

    record_duel(
        match.message.guild.id,
        match.challenger.id,
        match.opponent.id,
        result,
        first,
        second
    )
    await match.message.edit(
        content=(
            f"⚔️ **THE DUEL HAS CONCLUDED!**\n\n"
            f"**{match.challenger.display_name} chose:**\n"
            f"{first_magic['emoji']} {first_magic['name']}\n\n"
            f"**{match.opponent.display_name} chose:**\n"
            f"{second_magic['emoji']} {second_magic['name']}\n\n"
            f"{announcement}"
        ),
        view=None
    )


# --------------------------------------------------
# DUEL COMMAND
# --------------------------------------------------

@bot.tree.command(
    name="duel",
    description="Challenge another witch or wizard to a magical duel."
)
async def duel(
    interaction: discord.Interaction,
    opponent: discord.Member = None
):
    if opponent is None:
        view = SoloDuelView()

        await interaction.response.send_message(
            "🪄 **A magical duel awaits!**\n"
            "Choose your discipline. Your opponent is ready.",
            view=view
        )

        view.message = await interaction.original_response()
        return

    if opponent.id == interaction.user.id:
        await interaction.response.send_message(
            "You cannot challenge yourself to a duel!",
            ephemeral=True
        )
        return

    if opponent.bot:
        await interaction.response.send_message(
            "You cannot challenge another bot to a duel!",
            ephemeral=True
        )
        return

    match = DuelMatch(interaction.user, opponent)
    view = ChallengeView(match)

    await interaction.response.send_message(
        f"⚔️ **A magical duel has been proposed!**\n\n"
        f"{interaction.user.mention} has challenged "
        f"{opponent.mention} to a duel!\n\n"
        f"Will you accept the challenge? "
        f"You have 2 minutes to respond.",
        view=view
    )

    view.message = await interaction.original_response()


# # --------------------------------------------------
# PLAYER STATISTICS
# --------------------------------------------------

@bot.tree.command(
    name="stats",
    description="View your duelling record or another player's record."
)
async def stats(
    interaction: discord.Interaction,
    player: discord.Member = None
):
    if interaction.guild is None:
        await interaction.response.send_message(
            "Player statistics are only available inside a server.",
            ephemeral=True
        )
        return

    player = player or interaction.user

    wins, losses, draws = get_player_stats(
        interaction.guild.id,
        player.id
    )

    offensive, cunning, defensive = get_discipline_usage(
        interaction.guild.id,
        player.id
    )

    rank = get_player_rank(wins)

    usage = {
        "⚔️ Offensive Magic": offensive,
        "🪶 Cunning Magic": cunning,
        "🛡️ Defensive Magic": defensive
    }

    highest_usage = max(usage.values())

    if highest_usage == 0:
        preferred = "Undetermined"
    else:
        preferred = " / ".join(
            discipline
            for discipline, count in usage.items()
            if count == highest_usage
        )

    embed = discord.Embed(
        title=f"🪄 Duelling Record: {player.display_name}",
        color=discord.Color.from_rgb(255, 242, 118)
    )

    embed.description = f"**Rank:** {rank}"

    embed.add_field(
        name="🏆 Wins",
        value=str(wins),
        inline=True
    )
    embed.add_field(
        name="💔 Losses",
        value=str(losses),
        inline=True
    )
    embed.add_field(
        name="🤝 Draws",
        value=str(draws),
        inline=True
    )

    embed.add_field(
        name="Preferred Discipline",
        value=f"**{preferred}**",
        inline=False
    )

    embed.add_field(
        name="Discipline Usage",
        value=(
            f"⚔️ Offensive Magic: **{offensive}**\n"
            f"🪶 Cunning Magic: **{cunning}**\n"
            f"🛡️ Defensive Magic: **{defensive}**"
        ),
        inline=False
    )

    embed.set_thumbnail(url=player.display_avatar.url)

    await interaction.response.send_message(embed=embed)

# --------------------------------------------------
# LEADERBOARD
# --------------------------------------------------

@bot.tree.command(
    name="leaderboard",
    description="View the server's top magical duelists."
)
async def leaderboard(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "The leaderboard is only available inside a server.",
            ephemeral=True
        )
        return

    rankings = get_leaderboard(interaction.guild.id)

    if not rankings:
        await interaction.response.send_message(
            "No duels have been recorded yet. "
            "Be the first to enter the leaderboard!"
        )
        return

    embed = discord.Embed(
        title="🏆 Hogwarts Duelling Club Leaderboard",
        description="The server's top magical duelists, ranked by wins.",
        color=discord.Color.from_rgb(255, 242, 118)
    )

    medals = ["🥇", "🥈", "🥉"]
    lines = []

    for position, (user_id, wins, losses, draws) in enumerate(
        rankings, start=1
    ):
        member = interaction.guild.get_member(user_id)

        if member:
            name = member.display_name
        else:
            try:
                user = await bot.fetch_user(user_id)
                name = user.name
            except discord.HTTPException:
                name = f"Unknown duelist ({user_id})"

        medal = medals[position - 1] if position <= 3 else f"**{position}.**"

        lines.append(
            f"{medal} **{name}** - {wins} wins, "
            f"{losses} losses, {draws} draws"
        )

    embed.description = "\n".join(lines)

    await interaction.response.send_message(embed=embed)

# --------------------------------------------------
# BOT STARTUP
# --------------------------------------------------

@bot.event
async def on_ready():
    initialize_database()
    await bot.tree.sync()

    print(f"Logged in as {bot.user}")
    print("Hogwarts Duelling Club is online!")


TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("Bot token not found!")

bot.run(TOKEN)
