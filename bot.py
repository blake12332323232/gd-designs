# ===================== IMPORTS =====================
import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import pandas as pd
from enum import Enum
from datetime import datetime
import asyncio

# ===================== CONFIG =====================
GUILD_ID = 1462264007439417551
DATA_FILE = "data.json"
PROMOTION_FILE = "promotions.json"
INFRACTIONS_FILE = "infractions.csv"

CATEGORY_MAP = {
    "Order Livery": 1462264008936787993,
    "Order ELS": 1462264008936787993,
    "Order Clothing": 1462264008936787993,
    "Order Graphics": 1462264008936787993,
    "Order Discord Server": 1462264008936787993,
    "Order Bots": 1462264008936787993,
}

ROLE_MAP = {
    "Order Livery": 1462264007464321046,
    "Order ELS": 1469158583110471794,
    "Order Clothing": 1462264007451873535,
    "Order Graphics": 1462264007451873534,
    "Order Discord Server": 1462264007451873533,
    "Order Bots": 1462264007451873532,
}

ROLE_IDS = [
    1469157176248369355,  # Junior Designer
    1469156917191639253,  # Designer
    1469156779949821984,  # Senior Designer
    1462264007464321047,  # Lead Designer
    1469156457206517810,  # Trial Admin
    1462264007493812248,  # Junior Admin
    1462264007493812249,  # Admin
    1462264007493812250,  # Senior Admin
    1469155995443007499,  # Head Admin
    1462264007506399434,  # Junior Manager
    1462264007506399435,  # Manager
    1469155809509511271,  # Senior Manager
    1462264007493812254,  # Community Manager
    1462264007506399439,  # Executive
    1462264007506399440,  # Owner / Highest
]

infraction_channel_id = 1469160415639376073
infraction_permissions_role = 1469159700959465610
TICKET_PANEL_CHANNEL_ID = 1462264008349585465
REVIEW_CHANNEL_ID = 1462264008349585463
ORDER_LOG_CHANNEL_ID = 1469159536651800756

# ===================== DATA =====================
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"ticket_counter": 0, "claims": {}}, f, indent=4)
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def next_ticket():
    data = load_data()
    data["ticket_counter"] += 1
    save_data(data)
    return f"{data['ticket_counter']:04d}"

def load_promotions():
    if not os.path.exists(PROMOTION_FILE):
        return {}
    with open(PROMOTION_FILE, "r") as f:
        return json.load(f)

def save_promotions(data):
    with open(PROMOTION_FILE, "w") as f:
        json.dump(data, f, indent=4)

if os.path.exists(INFRACTIONS_FILE):
    infraction_df = pd.read_csv(INFRACTIONS_FILE, dtype={'MessageID': str})
    if not infraction_df.empty:
        icount = infraction_df['InfractionID'].max()
    else:
        icount = 0
else:
    infraction_df = pd.DataFrame(columns=[
        'InfractionID','staffID','staffMention','InfractionType',
        'Reason','IssuedBy','IssuedByID','MessageID','staff Notes','User Notes'
    ])
    icount = 0

def save_infractions():
    infraction_df.to_csv(INFRACTIONS_FILE, index=False)

class infraction_type(Enum):
    verbal_warning = 'Verbal Warning'
    written_warning = 'Written Warning'
    warning = 'Warning'
    fire_warning = 'Fire Warning'
    activity_notice = 'Activity Notice'
    suspension = 'Suspension'
    strike = 'Strike'
    demotion = 'Demotion'
    termination_notice = 'Termination Notice'
    termination = 'Termination'
    blacklist = 'Blacklist'

# ===================== BOT =====================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===================== CONTRACT =====================
contracts = {}

class ContractView(View):
    def __init__(self, contract_id: int):
        super().__init__(timeout=None)
        self.contract_id = contract_id

    @discord.ui.button(label="Accept Contract", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: Button):
        contract = contracts[self.contract_id]
        if interaction.user.id != contract["customer_id"]:
            return await interaction.response.send_message("❌ Only the customer can accept this contract.", ephemeral=True)
        embed = contract["embed"]
        embed.add_field(name="Status", value=f"🟢 **Accepted by {interaction.user.mention}**", inline=False)
        embed.color = discord.Color.green()
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message("✅ Contract accepted.", ephemeral=True)

    @discord.ui.button(label="Reject Contract", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: Button):
        contract = contracts[self.contract_id]
        if interaction.user.id != contract["customer_id"]:
            return await interaction.response.send_message("❌ Only the customer can reject this contract.", ephemeral=True)
        embed = contract["embed"]
        embed.add_field(name="Status", value=f"🔴 **Rejected by {interaction.user.mention}**", inline=False)
        embed.color = discord.Color.red()
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message("❌ Contract rejected.", ephemeral=True)

@bot.tree.command(name="contract", description="Send an order confirmation contract", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(customer="Customer", designer="Designer", designs="Number of designs", days="Estimated time (days)", subtotal="Sub-total price", final_price="Final price")
async def contract(interaction: discord.Interaction, customer: discord.Member, designer: discord.Member, designs: int, days: int, subtotal: int, final_price: int):
    embed = discord.Embed(title="Evil Creations Order Confirmation", description=f"Hey {customer.mention}! Review the details and accept/reject the contract.", color=0xf5a623)
    embed.add_field(name="👤 Customer", value=customer.mention, inline=True)
    embed.add_field(name="🎨 Designer", value=designer.mention, inline=True)
    embed.add_field(name="⭐ Designs", value=str(designs), inline=True)
    embed.add_field(name="⏱ Estimated Time", value=f"{days}d", inline=True)
    embed.add_field(name="💰 Sub-Total", value=str(subtotal), inline=True)
    embed.add_field(name="💵 Final Price", value=str(final_price), inline=True)
    embed.set_footer(text="Please review and click Accept or Reject below.")
    contract_id = len(contracts) + 1
    contracts[contract_id] = {"customer_id": customer.id, "embed": embed}
    await interaction.response.send_message(embed=embed, view=ContractView(contract_id))

# ===================== TICKETS =====================
class TicketSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="Choose a service", options=[discord.SelectOption(label=k, value=k) for k in CATEGORY_MAP], custom_id="ticket-select")

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        guild = interaction.guild
        category = guild.get_channel(CATEGORY_MAP[choice])
        role = guild.get_role(ROLE_MAP[choice])
        channel = await guild.create_text_channel(
            name=f"🔴-{interaction.user.name}-{next_ticket()}",
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True),
                guild.me: discord.PermissionOverwrite(view_channel=True),
                role: discord.PermissionOverwrite(view_channel=True)
            }
        )
        embed = discord.Embed(title="Order Ticket", description="Thank you! Fill out the format accurately.\n```Order Description:\nBudget:\nDeadline:\nReferences:```", color=discord.Color.green())
        await channel.send(content=f"{role.mention} {interaction.user.mention}", embed=embed)
        await interaction.response.send_message(f"🎟 Ticket created: {channel.mention}", ephemeral=True)

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# ===================== CLAIM / UNCLAIM =====================
@bot.tree.command(name="claimticket", description="Claim or unclaim the current ticket", guild=discord.Object(id=GUILD_ID))
async def claimticket(interaction: discord.Interaction):
    data = load_data()
    cid = str(interaction.channel.id)
    if cid in data["claims"]:
        del data["claims"][cid]
        save_data(data)
        await interaction.channel.edit(name=interaction.channel.name.replace("🟢", "🔴"))
        embed = discord.Embed(title="🔓 Ticket Unclaimed", description=f"Ticket unclaimed by {interaction.user.mention}", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        data["claims"][cid] = interaction.user.id
        save_data(data)
        await interaction.channel.edit(name=interaction.channel.name.replace("🔴", "🟢"))
        embed = discord.Embed(title="✅ Ticket Claimed", description=f"Ticket claimed by {interaction.user.mention}", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ===================== CLOSE TICKET =====================
class CloseRequestView(View):
    def __init__(self, ticket_channel):
        super().__init__(timeout=None)
        self.ticket_channel = ticket_channel

    @discord.ui.button(label='✅ Confirm Closure', style=discord.ButtonStyle.green)
    async def confirm(self, button: Button, interaction: discord.Interaction):
        await self.ticket_channel.send('The ticket has been closed.')
        await self.ticket_channel.delete()

    @discord.ui.button(label='❌ Cancel Closure', style=discord.ButtonStyle.red)
    async def cancel(self, button: Button, interaction: discord.Interaction):
        await interaction.response.send_message('Ticket closure canceled.', ephemeral=True)

@bot.tree.command(name="closerequest", description="Request to close the ticket", guild=discord.Object(id=GUILD_ID))
async def closerequest(interaction: discord.Interaction):
    await interaction.response.send_message("Closure requested. Staff will confirm.", view=CloseRequestView(interaction.channel), ephemeral=True)

@bot.tree.command(name="closeticket", description="Immediately close the ticket", guild=discord.Object(id=GUILD_ID))
async def closeticket(interaction: discord.Interaction):
    await interaction.channel.delete()

# ===================== PAYMENT =====================
@bot.tree.command(name="payment", description="Send a payment link embed", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(payment_link="Link for payment")
async def payment(interaction: discord.Interaction, payment_link: str):
    embed = discord.Embed(title="💰 Payment Required", description=f"Please complete the payment here: [Click to Pay]({payment_link})", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

# ===================== INFRACTIONS =====================
@bot.tree.command(name='infraction', description='Issue an infraction', guild=discord.Object(id=GUILD_ID))
@app_commands.describe(staff='Staff to infract', infraction='Infraction type', reason='Reason')
async def infraction_cmd(interaction: discord.Interaction, staff: discord.Member, infraction: infraction_type, reason: str):
    global icount, infraction_df
    needed_role = interaction.guild.get_role(infraction_permissions_role)
    if needed_role not in interaction.user.roles:
        return await interaction.response.send_message("❌ Missing permissions.", ephemeral=True)
    icount += 1
    embed = discord.Embed(title=f"Infraction #{icount}", description=f"Staff: {staff.mention}\nInfraction: {infraction.value}\nReason: {reason}\nIssued by: {interaction.user.mention}", color=discord.Color.red())
    infraction_channel = interaction.guild.get_channel(infraction_channel_id)
    msg = await infraction_channel.send(embed=embed)
    new_entry = {'InfractionID': icount, 'staffID': staff.id, 'staffMention': staff.mention, 'InfractionType': infraction.value, 'Reason': reason, 'IssuedBy': interaction.user.mention, 'IssuedByID': interaction.user.id, 'MessageID': str(msg.id)}
    infraction_df = pd.concat([infraction_df, pd.DataFrame([new_entry])], ignore_index=True)
    save_infractions()
    await interaction.response.send_message("Infraction issued.", ephemeral=True)

# ===================== PROMOTIONS =====================
promotion_group = app_commands.Group(name="promotion", description="Promotion commands")

@promotion_group.command(name="issue", description="Promote a member")
@app_commands.describe(member="Member", reason="Reason")
async def promotion_issue(interaction: discord.Interaction, member: discord.Member, reason: str):
    promotions = load_promotions()
    # Example: give next role in ROLE_IDS
    current_idx = next((i for i, r in enumerate(ROLE_IDS) if r in [role.id for role in member.roles]), -1)
    if current_idx == -1 or current_idx + 1 >= len(ROLE_IDS):
        return await interaction.response.send_message("Cannot promote further.", ephemeral=True)
    old_role = interaction.guild.get_role(ROLE_IDS[current_idx])
    new_role = interaction.guild.get_role(ROLE_IDS[current_idx + 1])
    await member.remove_roles(old_role)
    await member.add_roles(new_role)
    promotions[str(member.id)] = {"old_role": old_role.id, "new_role": new_role.id, "by": interaction.user.id, "reason": reason, "timestamp": datetime.utcnow().isoformat()}
    save_promotions(promotions)
    embed = discord.Embed(title="✅ Promotion Issued", color=discord.Color.green())
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="From", value=old_role.name)
    embed.add_field(name="To", value=new_role.name)
    embed.add_field(name="Reason", value=reason)
    await interaction.response.send_message(embed=embed)

# ===================== REVIEW =====================
class ReviewModal(Modal, title="Leave a review"):
    def __init__(self, order_id: str | None, designer: discord.Member | None):
        super().__init__(timeout=None)
        self.order_id = order_id
        self.designer = designer
        self.rating = TextInput(label="Rating (1-5)", placeholder="5", max_length=1, required=True)
        self.comment = TextInput(label="Comment", style=discord.TextStyle.paragraph, placeholder="Feedback", max_length=500, required=True)
        self.add_item(self.rating)
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        embed = discord.Embed(title="⭐ New Review", color=discord.Color.gold())
        embed.add_field(name="From", value=interaction.user.mention)
        if self.designer: embed.add_field(name="Designer", value=self.designer.mention)
        if self.order_id: embed.add_field(name="Order ID", value=self.order_id)
        embed.add_field(name="Rating", value=f"{self.rating.value}/5")
        embed.add_field(name="Comment", value=self.comment.value)
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Thanks for your review!", ephemeral=True)

@bot.tree.command(name="review", description="Leave a review", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(order_id="Ticket or order ID", designer="Designer")
async def review(interaction: discord.Interaction, order_id: str | None = None, designer: discord.Member | None = None):
    await interaction.response.send_modal(ReviewModal(order_id, designer))

# ===================== TAX =====================
@bot.tree.command(name="tax", description="Calculate final price", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(amount="Amount", designs="Number of designs")
async def tax(interaction: discord.Interaction, amount: int, designs: int):
    if designs < 1: return await interaction.response.send_message("Invalid designs", ephemeral=True)
    tax = int(amount / 0.7)
    preset = 0.05 if designs < 10 else 0.10 if designs < 25 else 0.25
    dtax = int(tax * preset)
    embed = discord.Embed(title="Tax Calculator", color=discord.Color.gold())
    embed.add_field(name="Standard Tax", value=tax)
    embed.add_field(name="Designer Tax", value=dtax)
    embed.add_field(name="Total", value=tax + dtax)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ===================== USER ADD =====================
@bot.tree.command(name="useradd", description="Add a user to ticket", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User to add")
async def useradd(interaction: discord.Interaction, user: discord.Member):
    await interaction.channel.set_permissions(user, view_channel=True)
    await interaction.response.send_message(f"✅ {user.mention} added to the ticket.", ephemeral=True)

# ===================== TICKET PANEL =====================
@bot.event
async def on_ready():
    guild = bot.get_guild(GUILD_ID)
    channel = guild.get_channel(TICKET_PANEL_CHANNEL_ID)
    await channel.purge(limit=10)
    await channel.send(embed=discord.Embed(title="🎟 Ticket Panel", description="Select your service below:", color=discord.Color.green()), view=TicketView())
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

# ===================== RUN =====================
bot.run(TOKEN)
