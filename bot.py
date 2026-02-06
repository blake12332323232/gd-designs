# ===================== IMPORTS =====================
import os
import json
import discord
import requests
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import pandas as pd
from enum import Enum
from datetime import datetime
import asyncio
from flask import Flask
from threading import Thread

# ===================== CONFIG =====================
TOKEN = "YOUR_DISCORD_BOT_TOKEN"  # Replace with your bot token
GUILD_ID = 1467652606334734504
DATA_FILE = "data.json"

CATEGORY_MAP = {
    "Order Livery": 1467652607345688753,
    "Order ELS": 1467652607651614754,
    "Order Clothing": 1467652607345688761,
    "Order Graphics": 1467652607651614755,
    "Order Discord Server": 1467652607651614757,
    "Order Bots": 1467652607651614759,
}

ROLE_MAP = {
    "Order Livery": 1467652606850498805,
    "Order ELS": 1467652606850498804,
    "Order Clothing": 1467652606838177811,
    "Order Graphics": 1467652606838177808,
    "Order Discord Server": 1467652606838177810,
    "Order Bots": 1467652606838177807,
}

ROLE_IDS = [
    1467652606850498811,  # Junior Designer
    1467652606850498812,  # Designer
    1467652606850498813,  # Senior Designer
    1467652606859018506,  # Lead Designer
    1467652606859018510,  # Trial Admin
    1467652606859018511,  # Junior Admin
    1467652606859018512,  # Admin
    1467652606859018513,  # Senior Admin
    1467652606859018514,  # Head Admin
    1467652606867411008,  # Junior Manager
    1467652606867411009,  # Manager
    1467652606867411010,  # Senior Manager
    1467652606867411012,  # Community Manager
    1467652606875668677,  # Executive
    1467652606875668680,  # Owner / Highest
]

PROMOTION_FILE = "promotions.json"
REVIEW_CHANNEL_ID = 1467652608784339145
TICKET_PANEL_CHANNEL_ID = 1467652608603722027
infraction_channel_id = 1467652610634027317
infraction_permissions_role = 1467701603422306314

# ===================== DATA HANDLING =====================
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

# ===================== INFRACTIONS =====================
if os.path.exists('infractions.csv'):
    infraction_df = pd.read_csv('infractions.csv', dtype={'MessageID': str})
    icount = infraction_df['InfractionID'].max() if not infraction_df.empty else 0
else:
    infraction_df = pd.DataFrame(columns=[
        'InfractionID','staffID','staffMention','InfractionType','Reason',
        'IssuedBy','IssuedByID','MessageID'
    ])
    icount = 0

def save_infractions():
    infraction_df.to_csv('infractions.csv', index=False)

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

class MyBot(commands.Bot):
    async def setup_hook(self):
        self.add_view(TicketView())
        self.tree.add_command(promotion_group, guild=discord.Object(id=GUILD_ID))
        await self.tree.sync(guild=discord.Object(id=GUILD_ID))

bot = MyBot(command_prefix="!", intents=intents)

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
    embed = discord.Embed(
        title="Evil Creations Order Confirmation",
        description=f"Hey {customer.mention}! Please review and accept/reject the contract below.",
        color=0xf5a623
    )
    embed.add_field(name="👤 Customer", value=customer.mention, inline=True)
    embed.add_field(name="🎨 Designer", value=designer.mention, inline=True)
    embed.add_field(name="⭐ Designs", value=str(designs), inline=True)
    embed.add_field(name="⏱ Estimated Time", value=f"{days}d", inline=True)
    embed.add_field(name="💰 Sub-Total", value=str(subtotal), inline=True)
    embed.add_field(name="💵 Final Price", value=str(final_price), inline=True)
    embed.set_footer(text="Please review the contract details above and click Accept or Reject below.")
    contract_id = len(contracts) + 1
    contracts[contract_id] = {"customer_id": customer.id, "embed": embed}
    await interaction.response.send_message(embed=embed, view=ContractView(contract_id))

# ===================== TICKET =====================
class TicketSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Choose a service",
            options=[discord.SelectOption(label=k, value=k) for k in CATEGORY_MAP],
            custom_id="ticket-select"
        )

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
        embed = discord.Embed(
            title="Order Ticket",
            description="Thank you for choosing Evil Creations. Fill out the format accurately.\n\n**Format:**\n```Order Description:\nBudget:\nDeadline:\nReferences:```",
            color=discord.Color.green()
        )
        await channel.send(content=f"{role.mention} {interaction.user.mention}", embed=embed)
        await interaction.response.send_message(f"🎟 Ticket created: {channel.mention}", ephemeral=True)

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# ===================== CLAIM / UNCLAIM =====================
@bot.tree.command(name="claimticket", guild=discord.Object(id=GUILD_ID))
async def claimticket(interaction: discord.Interaction):
    data = load_data()
    cid = str(interaction.channel.id)
    if cid in data["claims"]:
        return await interaction.response.send_message("❌ Already claimed.", ephemeral=True)
    data["claims"][cid] = interaction.user.id
    save_data(data)
    await interaction.channel.edit(name=interaction.channel.name.replace("🔴", "🟢"))
    embed = discord.Embed(title="Ticket Claimed", description=f"Ticket claimed by {interaction.user.mention}", color=discord.Color.green())
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Ticket successfully claimed.", ephemeral=True)

@bot.tree.command(name="unclaimticket", guild=discord.Object(id=GUILD_ID))
async def unclaimticket(interaction: discord.Interaction):
    data = load_data()
    cid = str(interaction.channel.id)
    if data["claims"].get(cid) != interaction.user.id:
        return await interaction.response.send_message("❌ Not your ticket.", ephemeral=True)
    del data["claims"][cid]
    save_data(data)
    await interaction.channel.edit(name=interaction.channel.name.replace("🟢", "🔴"))
    embed = discord.Embed(title="Ticket Unclaimed", description=f"Ticket unclaimed by {interaction.user.mention}", color=discord.Color.orange())
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("🔓 Ticket unclaimed.", ephemeral=True)

# ===================== CLOSE TICKET =====================
class CloseRequestView(View):
    def __init__(self, ticket_channel, staff_role, user):
        super().__init__(timeout=60)
        self.ticket_channel = ticket_channel
        self.staff_role = staff_role
        self.user = user

    @discord.ui.button(label='✅ Confirm Closure', style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.ticket_channel.send('The ticket has been closed.')
        await self.ticket_channel.delete()
        await interaction.response.edit_message(content='The ticket has been successfully closed.', view=None)

    @discord.ui.button(label='❌ Cancel Closure', style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.edit_message(content='The request to close the ticket has been canceled.', view=None)

@bot.tree.command(name='closerequest', description='Request to close the current order.', guild=discord.Object(id=GUILD_ID))
async def close_request(interaction: discord.Interaction):
    ticket_channel = interaction.channel
    if ticket_channel.name.startswith('🔴') or ticket_channel.name.startswith('🟢'):
        await interaction.response.send_message('A staff member has requested this ticket to be closed.', ephemeral=True)
        staff_role = discord.utils.get(interaction.guild.roles, id=1467652606850498808)
        embed = discord.Embed(title="Ticket Closure Request", description=f"{interaction.user.mention} has requested to close this ticket.", color=discord.Color.blue())
        embed.add_field(name="Action Required", value="Confirm or cancel the closure using buttons below.", inline=False)
        await ticket_channel.send(embed=embed, view=CloseRequestView(ticket_channel, staff_role, interaction.user))
    else:
        await interaction.response.send_message('This command can only be used in ticket channels.', ephemeral=True)

@bot.tree.command(name='closeticket', description='Close the current ticket.', guild=discord.Object(id=GUILD_ID))
async def closeticket(interaction: discord.Interaction):
    if interaction.channel.name.startswith('🔴') or interaction.channel.name.startswith('🟢'):
        await interaction.channel.send('Ticket closed.')
        await interaction.channel.delete()
    else:
        await interaction.response.send_message('This command can only be used in ticket channels.', ephemeral=True)

# ===================== PAYMENT COMMAND =====================
@bot.tree.command(name='payment', description='Send a payment link for order confirmation', guild=discord.Object(id=GUILD_ID))
@app_commands.describe(payment_link='Link to your payment page')
async def payment(interaction: discord.Interaction, payment_link: str):
    embed = discord.Embed(title="💰 Payment Required", description=f"Please complete your payment to confirm your order:\n[Click here]({payment_link})", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

# ===================== ORDER LOG =====================
@bot.tree.command(name="orderlog", description="Log a completed order", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(customer="Customer", designer="Designer", price="Final price", notes="Extra notes (optional)")
async def orderlog(interaction: discord.Interaction, customer: discord.Member, designer: discord.Member, price: int, notes: str = "None"):
    channel = interaction.guild.get_channel(1467652610147225743)
    if not channel:
        return await interaction.response.send_message("❌ Order log channel not found.", ephemeral=True)
    product = None
    for role_name, role_id in ROLE_MAP.items():
        if discord.utils.get(customer.roles, id=role_id):
            product = role_name
            break
    if not product:
        return await interaction.response.send_message("❌ Customer does not have a valid order role.", ephemeral=True)
    embed = discord.Embed(title="✅ Order Logged", color=discord.Color.green())
    embed.add_field(name="Customer", value=customer.mention, inline=True)
    embed.add_field(name="Designer", value=designer.mention, inline=True)
    embed.add_field(name="Order Type", value=product, inline=False)
    embed.add_field(name="Price", value=str(price), inline=True)
    embed.add_field(name="Notes", value=notes, inline=False)
    embed.set_footer(text=f"Logged by {interaction.user} • ID: {interaction.user.id}")
    embed.timestamp = datetime.utcnow()
    await channel.send(embed=embed)
    await interaction.response.send_message("🧾 Order logged.", ephemeral=True)

# ===================== REVIEW =====================
class ReviewModal(Modal, title="Leave a review"):
    def __init__(self, order_id: str | None, designer: discord.Member | None):
        super().__init__(timeout=None)
        self.order_id = order_id
        self.designer = designer
        self.rating = TextInput(label="Rating (1-5)", placeholder="5", max_length=1, required=True)
        self.comment = TextInput(label="Comment", style=discord.TextStyle.paragraph, placeholder="What did you like / dislike?", max_length=500, required=True)
        self.add_item(self.rating)
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        if not channel:
            return await interaction.response.send_message("❌ Review log channel not found.", ephemeral=True)
        embed = discord.Embed(title="⭐ New Review", color=discord.Color.gold())
        embed.add_field(name="From", value=interaction.user.mention, inline=True)
        if self.designer:
            embed.add_field(name="Designer", value=self.designer.mention, inline=True)
        if self.order_id:
            embed.add_field(name="Order ID", value=self.order_id, inline=True)
        embed.add_field(name="Rating", value=f"{self.rating.value}/5", inline=False)
        embed.add_field(name="Comment", value=self.comment.value, inline=False)
        embed.timestamp = datetime.utcnow()
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Thanks for your review!", ephemeral=True)

@bot.tree.command(name="review", description="Leave a review for your order", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(order_id="Ticket or order ID (optional)", designer="Designer you are reviewing (optional)")
async def review(interaction: discord.Interaction, order_id: str | None = None, designer: discord.Member | None = None):
    modal = ReviewModal(order_id=order_id, designer=designer)
    await interaction.response.send_modal(modal)

# ===================== TAX =====================
@bot.tree.command(name="tax", guild=discord.Object(id=GUILD_ID))
async def tax(interaction: discord.Interaction, amount: int, designs: int):
    if designs < 1:
        await interaction.response.send_message('Invalid order amount.', ephemeral=True)
        return
    tax = int(amount/0.7)
    if designs < 10:
        preset = 0.05
    elif designs < 25:
        preset = 0.10
    else:
        preset = 0.25
    dtax = int(tax * preset)
    embed = discord.Embed(title='Tax Calculator', color=discord.Color.gold())
    embed.add_field(name='Standard Tax', value=tax, inline=True)
    embed.add_field(name='Designer Tax', value=dtax, inline=True)
    embed.add_field(name='Total', value=tax+dtax, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ===================== USER ADD =====================
@bot.tree.command(name="useradd", guild=discord.Object(id=GUILD_ID))
async def useradd(interaction: discord.Interaction, user: discord.Member):
    await interaction.channel.set_permissions(user, view_channel=True)
    await interaction.response.send_message(f"{user.mention} added to ticket.", ephemeral=True)

# ===================== PROMOTIONS =====================
promotion_group = app_commands.Group(name="promotion", description="Manage promotions")

@promotion_group.command(name="issue", description="Issue a promotion")
@app_commands.describe(user="User to promote", role="Role to give")
async def issue(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    await user.add_roles(role)
    await interaction.response.send_message(f"✅ {user.mention} promoted with {role.name}", ephemeral=True)

@promotion_group.command(name="view", description="View current promotions")
async def view(interaction: discord.Interaction):
    data = load_promotions()
    await interaction.response.send_message(f"Promotions: {data}", ephemeral=True)

@promotion_group.command(name="void", description="Void a promotion")
@app_commands.describe(user="User to remove promotion")
async def void(interaction: discord.Interaction, user: discord.Member):
    # Remove all roles in ROLE_IDS if user has them
    roles_removed = [r.name for r in user.roles if r.id in ROLE_IDS]
    await user.remove_roles(*[r for r in user.roles if r.id in ROLE_IDS])
    await interaction.response.send_message(f"✅ Promotions voided: {roles_removed}", ephemeral=True)

# ===================== INFRACTIONS COMMANDS =====================
infraction_group = app_commands.Group(name="infraction", description="Manage infractions")

@infraction_group.command(name="issue", description="Issue an infraction to a user")
@app_commands.describe(user="User to infract", type="Type of infraction", reason="Reason for infraction")
async def issue(interaction: discord.Interaction, user: discord.Member, type: str, reason: str):
    global icount, infraction_df
    icount += 1
    infraction_id = icount
    issued_by_id = interaction.user.id
    issued_by_mention = interaction.user.mention
    timestamp = datetime.utcnow()
    new_row = {
        'InfractionID': infraction_id,
        'staffID': issued_by_id,
        'staffMention': issued_by_mention,
        'InfractionType': type,
        'Reason': reason,
        'IssuedBy': issued_by_mention,
        'IssuedByID': issued_by_id,
        'MessageID': '',
        'UserID': user.id,
        'UserMention': user.mention,
        'Timestamp': timestamp.isoformat()
    }
    infraction_df = pd.concat([infraction_df, pd.DataFrame([new_row])], ignore_index=True)
    save_infractions()
    embed = discord.Embed(title="⚠️ Infraction Issued", color=discord.Color.red())
    embed.add_field(name="User", value=user.mention, inline=True)
    embed.add_field(name="Type", value=type, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"Issued by {interaction.user}")
    await interaction.response.send_message(embed=embed)

@infraction_group.command(name="view", description="View infractions for a user")
@app_commands.describe(user="User to view infractions")
async def view(interaction: discord.Interaction, user: discord.Member):
    user_infractions = infraction_df[infraction_df['UserID'] == user.id]
    if user_infractions.empty:
        return await interaction.response.send_message(f"✅ {user.mention} has no infractions.", ephemeral=True)
    description = ""
    for _, row in user_infractions.iterrows():
        description += f"ID: {row['InfractionID']} | Type: {row['InfractionType']} | Reason: {row['Reason']} | By: {row['IssuedBy']}\n"
    embed = discord.Embed(title=f"📄 Infractions for {user}", description=description, color=discord.Color.orange())
    await interaction.response.send_message(embed=embed, ephemeral=True)

@infraction_group.command(name="void", description="Void a user's infraction")
@app_commands.describe(infraction_id="ID of the infraction to void")
async def void(interaction: discord.Interaction, infraction_id: int):
    global infraction_df
    if infraction_id not in infraction_df['InfractionID'].values:
        return await interaction.response.send_message("❌ Infraction ID not found.", ephemeral=True)
    infraction_df = infraction_df[infraction_df['InfractionID'] != infraction_id]
    save_infractions()
    await interaction.response.send_message(f"✅ Infraction {infraction_id} has been voided.", ephemeral=True)

bot.tree.add_command(infraction_group, guild=discord.Object(id=GUILD_ID))


# ===================== KEEP BOT ALIVE =====================
app = Flask("")

@app.route("/")
def home():
    return "Bot is alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ===================== RUN =====================
keep_alive()
bot.run(TOKEN)
