import json
import os
import requests
import asyncio
import time
import zipfile
import qrcode
import io
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, JobQueue

# ================= CONFIG =================
BOT_TOKEN = "7569076581:AAGHyTIAq1Yv0Q4Svg-nmBOOe_inLkAUo5k"
ADMIN_IDS = [7679672318]
SHOP_NAME = "Shein Coupon Shop"
SUPPORT_USERNAME = "@Slok_Official_75"

# UPI CONFIG
UPI_ID = "slokjaat67@ybl"

# BACKUP BOT CONFIG
BACKUP_BOT_TOKEN = "8576475682:AAHIpzZCgU4YQCCrtnLCz5EX9PH2KkxJ6gA"
BACKUP_CHAT_ID = ADMIN_IDS[0]

# Initial services
SERVICES = {
    "500": {"name": "500 Pe 500", "price": 8, "stock": []},
    "1000": {"name": "1000 Pe 1000", "price": 30, "stock": []},
    "2000": {"name": "2000 Pe 2000", "price": 37, "stock": []},
    "4000": {"name": "4000 Pe 4000", "price": 90, "stock": []},
}

# ================= GLOBALS =================
user_state = {}
orders = {}
order_counter = 1
all_users = set()
redeemed_coupons = {}
backup_counter = 0
payment_proofs = {}  # Store payment proofs

# ================= BACKUP SYSTEM =================
def create_zip_backup():
    """Create ZIP backup of all data"""
    global backup_counter
    
    try:
        # Create backup directory
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # Create timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_counter += 1
        
        # Save current data
        save_data()
        
        # Files to include in backup
        files_to_backup = []
        if os.path.exists(DATA_FILE):
            files_to_backup.append(DATA_FILE)
        
        # Create backup info file
        backup_info = {
            "timestamp": datetime.now().isoformat(),
            "total_users": len(all_users),
            "total_orders": len(orders),
            "services": {k: {"name": v["name"], "stock_count": len(v["stock"]), "price": v["price"]} for k, v in SERVICES.items()},
            "backup_number": backup_counter
        }
        
        info_file = f"{backup_dir}/backup_info_{timestamp}.json"
        with open(info_file, 'w') as f:
            json.dump(backup_info, f, indent=2)
        files_to_backup.append(info_file)
        
        # Create ZIP file
        zip_filename = f"{backup_dir}/shein_bot_backup_{timestamp}.zip"
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in files_to_backup:
                if os.path.exists(file):
                    zipf.write(file, os.path.basename(file))
        
        # Cleanup temp files
        if os.path.exists(info_file):
            os.remove(info_file)
        
        print(f"✅ Backup created: {zip_filename}")
        return zip_filename
        
    except Exception as e:
        print(f"❌ Backup error: {e}")
        return None

async def send_backup_to_bot():
    """Send backup to backup bot"""
    try:
        zip_file = create_zip_backup()
        if not zip_file:
            return False
        
        # Send via backup bot
        bot_url = f"https://api.telegram.org/bot{BACKUP_BOT_TOKEN}/sendDocument"
        
        with open(zip_file, 'rb') as file:
            files = {'document': (os.path.basename(zip_file), file)}
            data = {'chat_id': BACKUP_CHAT_ID}
            
            response = requests.post(bot_url, data=data, files=files)
            result = response.json()
            
            if result.get('ok'):
                print(f"✅ Backup sent to backup bot")
                
                # Delete local backup after sending (optional)
                try:
                    os.remove(zip_file)
                except:
                    pass
                    
                return True
            else:
                print(f"❌ Failed to send backup: {result}")
                return False
                
    except Exception as e:
        print(f"❌ Error sending backup: {e}")
        return False

async def auto_backup_task(context: ContextTypes.DEFAULT_TYPE):
    """Auto backup task every 5 minutes"""
    print("🔄 Running auto backup...")
    await send_backup_to_bot()

# ================= ULTRA-FAST BROADCAST =================
async def ultra_broadcast_send(bot, user_id, message):
    """Ultra-fast single message sender"""
    try:
        await bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode="Markdown"
        )
        return True
    except:
        return False

# ================= DATA SAVING/LOADING =================
DATA_FILE = "bot_data.json"

def save_data():
    """Save all bot data to file"""
    try:
        data = {
            "orders": orders,
            "services": SERVICES,
            "all_users": list(all_users),
            "order_counter": order_counter,
            "redeemed_coupons": redeemed_coupons,
            "payment_proofs": payment_proofs,
            "last_backup": datetime.now().isoformat()
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"✅ Data saved to {DATA_FILE}")
    except Exception as e:
        print(f"❌ Error saving data: {e}")

def load_data():
    """Load bot data from file"""
    global orders, SERVICES, all_users, order_counter, redeemed_coupons, payment_proofs
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            
            orders = data.get("orders", {})
            
            saved_services = data.get("services", {})
            for key in SERVICES:
                if key in saved_services:
                    SERVICES[key]["stock"] = saved_services[key].get("stock", [])
                    SERVICES[key]["price"] = saved_services[key].get("price", SERVICES[key]["price"])
            
            all_users = set(data.get("all_users", []))
            order_counter = data.get("order_counter", 1)
            redeemed_coupons = data.get("redeemed_coupons", {})
            payment_proofs = data.get("payment_proofs", {})
            
            print(f"✅ Data loaded: {len(all_users)} users, {len(orders)} orders")
            
        except Exception as e:
            print(f"❌ Error loading data: {e}")
    else:
        print("⚠️ No data file found, starting with default data")

# ================= KEYBOARDS =================
USER_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🛒 Buy Coupon"), KeyboardButton("📜 History")],
        [KeyboardButton("📞 Support")]
    ],
    resize_keyboard=True
)

ADMIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📦 Add Coupons"), KeyboardButton("📊 View Stock")],
        [KeyboardButton("🔄 Redeem Coupon"), KeyboardButton("💰 Change Prices")],
        [KeyboardButton("📢 Broadcast"), KeyboardButton("🔍 View Proofs")]
    ],
    resize_keyboard=True
)

CANCEL_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("❌ Cancel Order")]],
    resize_keyboard=True
)

def get_admin_approve_keyboard(order_id):
    """Approve/Reject keyboard for admin"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{order_id}")],
        [InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{order_id}")]
    ])

def get_support_keyboard():
    """Support keyboard - ONLY Contact button"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👉 Contact", url=f"https://t.me/{SUPPORT_USERNAME[1:]}")]
    ])

# ================= ULTRA-FAST FUNCTIONS =================
def get_stock_display():
    """Ultra-fast stock display"""
    stock_text = "🎉 **Shein Coupon Store**\n\n"
    for key, service in SERVICES.items():
        stock_count = len(service['stock'])
        stock_emoji = "🟢" if stock_count > 0 else "🔴"
        stock_text += f"{stock_emoji} {service['name']} Stock: {stock_count}\n"
    return stock_text

def get_stock_detailed():
    """Detailed stock view"""
    stock_text = "📊 **Coupon Stock Details:**\n\n"
    for key, service in SERVICES.items():
        stock_count = len(service['stock'])
        stock_status = "✅ Available" if stock_count > 0 else "❌ Out of Stock"
        stock_text += f"📦 **{service['name']}**\n"
        stock_text += f"   Price: ₹{service['price']} | Stock: {stock_count} | Status: {stock_status}\n"
        if service['stock']:
            stock_text += f"   Available: {', '.join(service['stock'][:5])}"
            if len(service['stock']) > 5:
                stock_text += f" ... and {len(service['stock']) - 5} more"
        stock_text += "\n"
    return stock_text

def get_current_prices():
    """Current prices"""
    price_text = "💰 **Current Coupon Prices:**\n\n"
    for key, service in SERVICES.items():
        price_text += f"📦 **{service['name']}**\n"
        price_text += f"   Current Price: ₹{service['price']}\n"
        price_text += f"   Stock Available: {len(service['stock'])}\n\n"
    return price_text

def get_redeemable_coupons():
    """Coupons available for redemption"""
    redeem_text = "🎟️ **Available Coupons for Redemption:**\n\n"
    has_coupons = False
    
    for key, service in SERVICES.items():
        if service['stock']:
            has_coupons = True
            redeem_text += f"📦 **{service['name']}** (₹{service['price']})\n"
            redeem_text += f"   Stock: {len(service['stock'])} coupons\n"
            
            if service['stock']:
                coupons_list = []
                for i, coupon in enumerate(service['stock'][:10], 1):
                    coupons_list.append(f"{i}. {coupon}")
                redeem_text += f"   Codes: {', '.join(coupons_list)}\n"
                
                if len(service['stock']) > 10:
                    redeem_text += f"   ... and {len(service['stock']) - 10} more\n"
            
            redeem_text += "\n"
    
    if not has_coupons:
        redeem_text = "❌ **No coupons available for redemption!**"
    
    return redeem_text

def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

def get_menu(user_id):
    """Get appropriate menu"""
    return ADMIN_MENU if is_admin(user_id) else USER_MENU

def get_services_keyboard():
    """Services keyboard"""
    keyboard = []
    for key, service in SERVICES.items():
        button_text = f"✅ {service['name']} | ₹{service['price']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_{key}")])
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_selection")])
    return InlineKeyboardMarkup(keyboard)

def get_add_coupon_keyboard():
    """Add coupon keyboard"""
    keyboard = [
        [InlineKeyboardButton("500 Pe 500", callback_data="add_500")],
        [InlineKeyboardButton("1000 Pe 1000", callback_data="add_1000")],
        [InlineKeyboardButton("2000 Pe 2000", callback_data="add_2000")],
        [InlineKeyboardButton("4000 Pe 4000", callback_data="add_4000")],
        [InlineKeyboardButton("🔙 Cancel", callback_data="cancel_add")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_change_price_keyboard():
    """Change price keyboard"""
    keyboard = [
        [InlineKeyboardButton("500 Pe 500", callback_data="price_500")],
        [InlineKeyboardButton("1000 Pe 1000", callback_data="price_1000")],
        [InlineKeyboardButton("2000 Pe 2000", callback_data="price_2000")],
        [InlineKeyboardButton("4000 Pe 4000", callback_data="price_4000")],
        [InlineKeyboardButton("🔙 Cancel", callback_data="cancel_price")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_redeem_keyboard():
    """Redeem keyboard"""
    keyboard = []
    for key, service in SERVICES.items():
        stock_count = len(service['stock'])
        if stock_count > 0:
            button_text = f"🎟️ {service['name']} (Stock: {stock_count})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"redeem_{key}")])
    
    if not keyboard:
        return None
    
    keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cancel_redeem")])
    return InlineKeyboardMarkup(keyboard)

def generate_upi_qr(amount, order_id):
    """Generate UPI QR code for exact amount"""
    upi_link = f"upi://pay?pa={UPI_ID}&pn=SheinCoupon&am={amount}&tn=Order_{order_id}&cu=INR"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(upi_link)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes

# ================= ULTRA-FAST COMMAND HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ultra-fast start command"""
    user_id = update.effective_user.id
    all_users.add(user_id)
    
    # Clear user state if exists
    if user_id in user_state:
        internal_order_id = user_state[user_id].get('internal_order_id')
        if internal_order_id and internal_order_id in orders:
            if orders[internal_order_id]['status'] == 'pending':
                orders[internal_order_id]['status'] = 'cancelled'
        del user_state[user_id]
    
    welcome_text = f"""
{get_stock_display()}

Hello, **{update.effective_user.first_name}!** 👋

If you want to buy coupons, select from the buttons below:
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_menu(user_id),
        parse_mode="Markdown"
    )
    save_data()

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ultra-fast message handler"""
    global orders, all_users, order_counter, redeemed_coupons, payment_proofs
    
    user_id = update.effective_user.id
    text = update.message.text
    
    # Clear state if user types /start
    if text and ("/start" in text or text == "start"):
        if user_id in user_state:
            internal_order_id = user_state[user_id].get('internal_order_id')
            if internal_order_id and internal_order_id in orders:
                if orders[internal_order_id]['status'] == 'pending':
                    orders[internal_order_id]['status'] = 'cancelled'
            del user_state[user_id]
    
    all_users.add(user_id)
    
    # Check if user is sending payment proof
    if user_id in user_state and user_state[user_id].get('action') == 'waiting_payment_proof':
        order_id = user_state[user_id].get('order_id')
        
        if update.message.photo:  # User sent screenshot
            # Store proof
            payment_proofs[order_id] = {
                'type': 'screenshot',
                'user_id': user_id,
                'username': update.effective_user.username,
                'first_name': update.effective_user.first_name,
                'timestamp': datetime.now().isoformat()
            }
            
            # Notify user
            await update.message.reply_text(
                "✅ **Screenshot received!**\n\n"
                "Verification ke liye gaya hai, 5–10 min wait karein.",
                reply_markup=get_menu(user_id)
            )
            
            # Notify all admins
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=update.message.photo[-1].file_id,
                        caption=f"🆕 **Payment Proof Received!**\n\n"
                               f"📋 **Order ID:** {order_id}\n"
                               f"👤 **User:** {update.effective_user.first_name}\n"
                               f"📸 **Type:** Screenshot\n"
                               f"🕒 **Time:** {datetime.now().strftime('%I:%M %p')}",
                        reply_markup=get_admin_approve_keyboard(order_id)
                    )
                except:
                    pass
            
            del user_state[user_id]
            save_data()
            return
            
        elif text and text.strip():  # User sent UTR
            payment_proofs[order_id] = {
                'type': 'utr',
                'utr': text.strip(),
                'user_id': user_id,
                'username': update.effective_user.username,
                'first_name': update.effective_user.first_name,
                'timestamp': datetime.now().isoformat()
            }
            
            # Notify user
            await update.message.reply_text(
                "✅ **UTR received!**\n\n"
                "Verification ke liye gaya hai, 5–10 min wait karein.",
                reply_markup=get_menu(user_id)
            )
            
            # Notify all admins
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"🆕 **Payment Proof Received!**\n\n"
                             f"📋 **Order ID:** {order_id}\n"
                             f"👤 **User:** {update.effective_user.first_name}\n"
                             f"📝 **Type:** UTR\n"
                             f"🔢 **UTR:** `{text.strip()}`\n"
                             f"🕒 **Time:** {datetime.now().strftime('%I:%M %p')}",
                        parse_mode="Markdown",
                        reply_markup=get_admin_approve_keyboard(order_id)
                    )
                except:
                    pass
            
            del user_state[user_id]
            save_data()
            return
    
    # Cancel Order
    if text == "❌ Cancel Order":
        if user_id in user_state:
            state = user_state[user_id]
            service_name = state.get('service_name', 'Unknown')
            
            current_order_id = state.get('internal_order_id')
            if current_order_id and current_order_id in orders:
                orders[current_order_id]['status'] = 'cancelled'
            
            await update.message.reply_text(
                f"❌ **Order Cancelled Successfully!**\n\n"
                f"📦 **Service:** {service_name}\n"
                f"✅ **Process stopped.**",
                reply_markup=get_menu(user_id),
                parse_mode="Markdown"
            )
            save_data()
            return
        else:
            await update.message.reply_text(
                "⚠️ No active order to cancel.",
                reply_markup=get_menu(user_id)
            )
            return
    
    # ADMIN MENU
    if is_admin(user_id):
        if text == "📦 Add Coupons":
            await update.message.reply_text(
                "📦 **Select service to add coupons:**",
                reply_markup=get_add_coupon_keyboard()
            )
            return
        elif text == "📊 View Stock":
            await update.message.reply_text(
                get_stock_detailed(),
                reply_markup=ADMIN_MENU,
                parse_mode="Markdown"
            )
            return
        elif text == "🔄 Redeem Coupon":
            redeem_text = get_redeemable_coupons()
            
            if "No coupons" in redeem_text:
                await update.message.reply_text(
                    redeem_text,
                    reply_markup=ADMIN_MENU,
                    parse_mode="Markdown"
                )
            else:
                redeem_text += "\n\n**How many coupons do you want to redeem?**\n"
                redeem_text += "Enter quantity:"
                
                await update.message.reply_text(
                    redeem_text,
                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Cancel")]], resize_keyboard=True),
                    parse_mode="Markdown"
                )
                user_state[user_id] = {"action": "redeem_quantity"}
            return
        elif text == "💰 Change Prices":
            await update.message.reply_text(
                get_current_prices() + "\n👇 **Select service to change price:**",
                reply_markup=get_change_price_keyboard(),
                parse_mode="Markdown"
            )
            return
        elif text == "📢 Broadcast":
            await update.message.reply_text(
                "📢 **Ultra-Fast Broadcast**\n\n"
                "Send the message you want to broadcast:",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Cancel")]], resize_keyboard=True),
                parse_mode="Markdown"
            )
            user_state[user_id] = {"action": "broadcast"}
            return
        elif text == "🔍 View Proofs":
            proofs_text = "📋 **Pending Payment Proofs:**\n\n"
            pending_count = 0
            
            for order_id, proof in payment_proofs.items():
                if order_id in orders and orders[order_id]['status'] == 'pending_proof':
                    pending_count += 1
                    order = orders[order_id]
                    proofs_text += f"🆔 **Order ID:** {order_id}\n"
                    proofs_text += f"👤 **User:** {proof.get('first_name', 'Unknown')}\n"
                    proofs_text += f"📦 **Service:** {order.get('service_name', 'Unknown')}\n"
                    proofs_text += f"💰 **Amount:** ₹{order.get('amount', 0)}\n"
                    proofs_text += f"📸 **Proof Type:** {proof.get('type', 'Unknown')}\n"
                    
                    if proof.get('type') == 'utr':
                        proofs_text += f"🔢 **UTR:** `{proof.get('utr', 'N/A')}`\n"
                    
                    proofs_text += f"🕒 **Received:** {proof.get('timestamp', 'N/A')}\n"
                    proofs_text += f"─────────────────\n"
            
            if pending_count == 0:
                proofs_text = "✅ **No pending payment proofs!**"
            
            await update.message.reply_text(
                proofs_text,
                parse_mode="Markdown",
                reply_markup=ADMIN_MENU
            )
            return
    
    # USER MENU
    if text == "🛒 Buy Coupon":
        services_text = "**🛒 Select Service:**\n\n"
        services_text += get_stock_display()
        services_text += "\n👇 **Click on service below**"
        
        await update.message.reply_text(
            services_text,
            reply_markup=get_services_keyboard(),
            parse_mode="Markdown"
        )
        return
    
    elif text == "📜 History":
        user_orders = []
        for order_id, order in orders.items():
            if order['user'] == user_id:
                user_orders.append((order_id, order))
        
        if not user_orders:
            history_text = "📭 **No orders found!**\n\nYou haven't placed any order yet."
        else:
            history_text = "📜 **Your Order History:**\n\n"
            for order_id, order in user_orders[:15]:
                status_emoji = "✅" if order['status'] == 'approved' else "❌" if order['status'] == 'rejected' else "⏳" if order['status'] == 'pending_proof' else "🔄"
                status_text = "Approved" if order['status'] == 'approved' else "Rejected" if order['status'] == 'rejected' else "Pending Proof" if order['status'] == 'pending_proof' else order['status'].capitalize()
                
                history_text += (
                    f"{status_emoji} **Order ID:** `{order_id}`\n"
                    f"📦 **Service:** {order.get('service_name', 'Unknown')}\n"
                    f"💰 **Amount:** ₹{order.get('amount', 0)}\n"
                )
                
                if 'coupon_codes' in order and order['coupon_codes']:
                    coupon_list = ", ".join([f"`{code}`" for code in order['coupon_codes'][:3]])
                    history_text += f"🎟️ **Coupons:** {coupon_list}\n"
                    if len(order['coupon_codes']) > 3:
                        history_text += f"   ... and {len(order['coupon_codes']) - 3} more\n"
                
                history_text += f"📊 **Status:** {status_text}\n"
                history_text += f"📅 **Date:** {order.get('date', 'N/A')}\n"
                history_text += f"─────────────────\n"
        
        await update.message.reply_text(
            history_text,
            reply_markup=get_menu(user_id),
            parse_mode="Markdown"
        )
        return
    
    elif text == "📞 Support":
        # VERY CLEAR: Only fixed message and Contact button
        support_text = "**Reply 1–2 ghante mein**"
        
        await update.message.reply_text(
            support_text,
            reply_markup=get_support_keyboard(),
            parse_mode="Markdown"
        )
        return
    
    # Broadcast handling
    if is_admin(user_id) and user_id in user_state and user_state[user_id].get('action') == 'broadcast':
        if text == "🔙 Cancel":
            await update.message.reply_text(
                "❌ **Broadcast Cancelled!**\n\nNo messages were sent.",
                reply_markup=ADMIN_MENU,
                parse_mode="Markdown"
            )
            del user_state[user_id]
            return
        
        broadcast_message = text
        
        total_users = len(all_users)
        start_time = time.time()
        user_list = list(all_users)
        
        # Mega-fast processing
        chunk_size = 200
        chunks = [user_list[i:i + chunk_size] for i in range(0, total_users, chunk_size)]
        
        total_sent = 0
        total_failed = 0
        
        for chunk_num, chunk in enumerate(chunks, 1):
            tasks = []
            for uid in chunk:
                tasks.append(ultra_broadcast_send(context.bot, uid, broadcast_message))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if result:
                    total_sent += 1
                else:
                    total_failed += 1
        
        total_time = time.time() - start_time
        avg_speed = total_sent / total_time if total_time > 0 else 0
        success_rate = (total_sent / total_users * 100) if total_users > 0 else 0
        
        report = f"""✅ **Ultra-Fast Broadcast Complete!**

⚡️ **Performance:**
• Total Users: {total_users:,}
• Time Taken: {total_time:.2f} seconds
• Speed: {avg_speed:.0f} users/second

📊 **Results:**
• ✅ Sent: {total_sent:,} users
• ❌ Failed: {total_failed:,} users
• 📈 Success Rate: {success_rate:.1f}%"""
        
        await update.message.reply_text(
            report,
            parse_mode="Markdown",
            reply_markup=ADMIN_MENU
        )
        
        del user_state[user_id]
        save_data()
        return
    
    # Add coupons handling
    if is_admin(user_id) and user_id in user_state and user_state[user_id].get('action') == 'adding_coupons':
        service_key = user_state[user_id].get('service_key')
        if service_key:
            coupons = text.split('\n')
            added = 0
            for coupon in coupons:
                coupon = coupon.strip().upper()
                if coupon and coupon not in SERVICES[service_key]['stock']:
                    SERVICES[service_key]['stock'].append(coupon)
                    added += 1
            
            del user_state[user_id]
            await update.message.reply_text(
                f"✅ **{added} coupons added to {SERVICES[service_key]['name']}!**\n"
                f"📊 **Total Stock:** {len(SERVICES[service_key]['stock'])}",
                reply_markup=ADMIN_MENU,
                parse_mode="Markdown"
            )
            save_data()
            return
    
    # Change price handling
    if is_admin(user_id) and user_id in user_state and user_state[user_id].get('action') == 'changing_price':
        service_key = user_state[user_id].get('service_key')
        if service_key:
            try:
                new_price = int(text.strip())
                if new_price < 1 or new_price > 10000:
                    await update.message.reply_text(
                        "❌ Price must be between ₹1 and ₹10,000",
                        reply_markup=ADMIN_MENU
                    )
                    del user_state[user_id]
                    return
                
                old_price = SERVICES[service_key]['price']
                SERVICES[service_key]['price'] = new_price
                
                del user_state[user_id]
                
                await update.message.reply_text(
                    f"✅ **Price Updated Successfully!**\n\n"
                    f"📦 **Service:** {SERVICES[service_key]['name']}\n"
                    f"💰 **Old Price:** ₹{old_price}\n"
                    f"💰 **New Price:** ₹{new_price}",
                    reply_markup=ADMIN_MENU,
                    parse_mode="Markdown"
                )
                save_data()
                return
            except ValueError:
                await update.message.reply_text(
                    "❌ Please enter a valid number",
                    reply_markup=ADMIN_MENU
                )
                del user_state[user_id]
                return
    
    # Redeem quantity handling
    if is_admin(user_id) and user_id in user_state and user_state[user_id].get('action') == 'redeem_quantity':
        if text.isdigit():
            quantity = int(text)
            if quantity <= 0:
                await update.message.reply_text(
                    "❌ Quantity must be greater than 0",
                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Cancel")]], resize_keyboard=True)
                )
                return
            
            options_keyboard = []
            for key, service in SERVICES.items():
                if service['stock'] and len(service['stock']) >= quantity:
                    button_text = f"{service['name']} ({len(service['stock'])} available)"
                    options_keyboard.append([InlineKeyboardButton(button_text, callback_data=f"qty_redeem_{key}_{quantity}")])
            
            if not options_keyboard:
                await update.message.reply_text(
                    f"❌ **Not enough coupons available!**\n\n"
                    f"Requested: {quantity} coupons\n"
                    f"No service has {quantity} or more coupons.",
                    reply_markup=ADMIN_MENU,
                    parse_mode="Markdown"
                )
                del user_state[user_id]
                return
            
            options_keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cancel_redeem")])
            
            await update.message.reply_text(
                f"🔄 **Select service to redeem {quantity} coupons:**",
                reply_markup=InlineKeyboardMarkup(options_keyboard),
                parse_mode="Markdown"
            )
            del user_state[user_id]
        else:
            await update.message.reply_text(
                "❌ Please enter a valid number",
                reply_markup=ADMIN_MENU
            )
            del user_state[user_id]
        return
    
    # Order flow
    await handle_order_flow(update, user_id, text, context)

async def handle_order_flow(update, user_id, text, context):
    """Ultra-fast order flow"""
    if user_id not in user_state:
        await update.message.reply_text(
            "Please select an option from the menu.",
            reply_markup=get_menu(user_id)
        )
        return
    
    state = user_state[user_id]
    step = state.get("step", "")
    
    if step == "quantity":
        if text.isdigit():
            qty = int(text)
            service_key = state["service"]
            stock_count = len(SERVICES[service_key]['stock'])
            
            if qty < 1:
                await update.message.reply_text(
                    "❌ **Quantity must be at least 1!**\n\n"
                    "Please enter a valid quantity:",
                    reply_markup=CANCEL_KEYBOARD
                )
                return
            elif qty > stock_count:
                await update.message.reply_text(
                    f"❌ **Not enough stock!**\n\n"
                    f"Available stock: {stock_count}\n"
                    f"Your input: {qty}\n\n"
                    "Please enter a smaller quantity:",
                    reply_markup=CANCEL_KEYBOARD
                )
                return
            
            amount = state["price"] * qty
            
            # Generate order ID
            global order_counter
            order_id = f"ORD{order_counter:06d}"
            order_counter += 1
            
            # Generate QR code
            qr_image = generate_upi_qr(amount, order_id)
            
            # Store order
            orders[order_id] = {
                "user": user_id,
                "username": update.effective_user.username,
                "first_name": update.effective_user.first_name,
                "service": service_key,
                "service_name": state["service_name"],
                "quantity": qty,
                "amount": amount,
                "status": "pending_proof",
                "date": update.message.date.strftime("%d %B %Y"),
                "time": update.message.date.strftime("%I:%M %p"),
                "coupon_codes": []
            }
            
            user_state[user_id]['internal_order_id'] = order_id
            user_state[user_id]['order_id'] = order_id
            user_state[user_id]['action'] = 'waiting_payment_proof'
            
            # Send QR code
            await update.message.reply_photo(
                photo=qr_image,
                caption=(
                    f"🧾 **Pay ₹{amount}**\n\n"
                    f"**Service:** {state['service_name']}\n"
                    f"**Quantity:** {qty}\n"
                    f"**Order ID:** `{order_id}`\n"
                    f"**UPI ID:** `{UPI_ID}`\n\n"
                    f"⚠️ **Important:**\n"
                    f"• Send EXACT ₹{amount} only\n"
                    f"• After payment, send screenshot OR UTR\n"
                    f"• Do NOT send both\n\n"
                    f"⏳ Waiting for payment proof..."
                ),
                reply_markup=CANCEL_KEYBOARD,
                parse_mode="Markdown"
            )
            
            save_data()

        else:
            await update.message.reply_text(
                "❌ Please enter a valid number",
                reply_markup=CANCEL_KEYBOARD
            )
            
    elif step == "waiting_payment":
        await update.message.reply_text(
            "⏳ **Payment is being verified automatically.**\n"
            "Please wait, do not send screenshots.",
            reply_markup=CANCEL_KEYBOARD
        )

# ================= ULTRA-FAST CALLBACK HANDLER =================
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ultra-fast callback handler"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith("select_"):
        key = data.split("_")[1]
        
        if not SERVICES[key]["stock"]:
            await query.edit_message_text(
                f"❌ **{SERVICES[key]['name']} Out of Stock!**\n\nPlease Wait For Stock!",
                parse_mode="Markdown"
            )
            return
        
        stock_count = len(SERVICES[key]['stock'])
        
        user_state[user_id] = {
            "service": key,
            "service_name": SERVICES[key]['name'],
            "price": SERVICES[key]['price'],
            "step": "quantity"
        }
        
        await query.edit_message_text(
            f"✅ **Selected:** {SERVICES[key]['name']}\n"
            f"💰 **Price:** ₹{SERVICES[key]['price']} per coupon\n"
            f"📊 **Available Stock:** {stock_count}\n\n"
            f"👉 **Enter quantity (max {stock_count}):**",
            parse_mode="Markdown"
        )
    
    elif data == "cancel_selection":
        if user_id in user_state:
            del user_state[user_id]
        
        await query.edit_message_text(
            "❌ **Cancelled Order!**\n\nOrder process has been cancelled.",
            parse_mode="Markdown"
        )
        
        await context.bot.send_message(
            chat_id=user_id,
            text="Please select an option from the menu below:",
            reply_markup=get_menu(user_id)
        )
    
    elif data == "cancel_add":
        if user_id in user_state:
            del user_state[user_id]
        
        await query.edit_message_text(
            "❌ **Cancelled Order!**\n\nCoupon addition has been cancelled.",
            parse_mode="Markdown"
        )
        
        if is_admin(user_id):
            await context.bot.send_message(
                chat_id=user_id,
                text="Admin menu:",
                reply_markup=ADMIN_MENU
            )
    
    elif data == "cancel_price":
        if user_id in user_state:
            del user_state[user_id]
        
        await query.edit_message_text(
            "❌ **Cancelled Order!**\n\nPrice change has been cancelled.",
            parse_mode="Markdown"
        )
        
        if is_admin(user_id):
            await context.bot.send_message(
                chat_id=user_id,
                text="Admin menu:",
                reply_markup=ADMIN_MENU
            )
    
    elif data == "cancel_redeem":
        if user_id in user_state:
            del user_state[user_id]
        
        await query.edit_message_text(
            "❌ **Cancelled Order!**\n\nRedemption has been cancelled.",
            parse_mode="Markdown"
        )
        
        if is_admin(user_id):
            await context.bot.send_message(
                chat_id=user_id,
                text="Admin menu:",
                reply_markup=ADMIN_MENU
            )
    
    elif data == "close_support":
        await query.edit_message_text(
            "✅ **Support window closed.**\n\nReturning to main menu...",
            parse_mode="Markdown"
        )
        
        stock_display = get_stock_display()
        welcome_text = f"""
{stock_display}

Hello, **{query.from_user.first_name}!** 👋

If you want to buy coupons, select from the buttons below:
        """
        
        await context.bot.send_message(
            chat_id=user_id,
            text=welcome_text,
            reply_markup=get_menu(user_id),
            parse_mode="Markdown"
        )
    
    elif data.startswith("price_"):
        if not is_admin(user_id):
            await query.answer("❌ Admin only!", show_alert=True)
            return
        
        service_key = data.split("_")[1]
        current_price = SERVICES[service_key]['price']
        
        user_state[user_id] = {
            'action': 'changing_price',
            'service_key': service_key
        }
        
        await query.edit_message_text(
            f"💰 **Change Price for {SERVICES[service_key]['name']}**\n\n"
            f"Current Price: ₹{current_price}\n\n"
            "Enter new price (in ₹):",
            parse_mode="Markdown"
        )
    
    elif data.startswith("qty_redeem_"):
        if not is_admin(user_id):
            await query.answer("❌ Admin only!", show_alert=True)
            return
        
        parts = data.split("_")
        service_key = parts[2]
        quantity = int(parts[3])
        
        if len(SERVICES[service_key]['stock']) < quantity:
            await query.edit_message_text(
                f"❌ **Not enough coupons available!**\n\n"
                f"Available: {len(SERVICES[service_key]['stock'])}\n"
                f"Requested: {quantity}",
                parse_mode="Markdown"
            )
            return
        
        coupon_codes = []
        for i in range(quantity):
            if SERVICES[service_key]['stock']:
                coupon = SERVICES[service_key]['stock'].pop(0)
                coupon_codes.append(coupon)
        
        coupon_text = "\n".join([f"`{code}`" for code in coupon_codes])
        
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"🎁 **Coupons Redeemed Successfully!**\n\n"
                f"🎟️ **Quantity:** {quantity}\n"
                f"📦 **Service:** {SERVICES[service_key]['name']}\n\n"
                f"**Your Redeemed Coupon Codes:**\n\n"
                f"{coupon_text}\n\n"
                f"📊 **Remaining Stock:** {len(SERVICES[service_key]['stock'])}"
            ),
            parse_mode="Markdown"
        )
        
        await query.edit_message_text(
            f"✅ **{quantity} coupons redeemed from {SERVICES[service_key]['name']}!**\n\n"
            f"Coupons have been sent to you directly.",
            parse_mode="Markdown"
        )
        
        if user_id in user_state:
            del user_state[user_id]
        
        save_data()
    
    elif data.startswith("add_"):
        if not is_admin(user_id):
            await query.answer("❌ Admin only!", show_alert=True)
            return
        
        service_key = data.split("_")[1]
        user_state[user_id] = {
            'action': 'adding_coupons',
            'service_key': service_key
        }
        
        await query.edit_message_text(
            f"📝 **Adding coupons for {SERVICES[service_key]['name']}**\n\n"
            "Send coupon codes (one per line):",
            parse_mode="Markdown"
        )
    
    # Admin approve/reject
    elif data.startswith("admin_approve_"):
        if not is_admin(user_id):
            await query.answer("❌ Admin only!", show_alert=True)
            return
        
        order_id = data.split("_")[2]
        
        if order_id not in orders:
            await query.answer("❌ Order not found!", show_alert=True)
            return
        
        order = orders[order_id]
        service_key = order['service']
        quantity = order['quantity']
        
        # Check stock
        if len(SERVICES[service_key]['stock']) < quantity:
            await query.answer("❌ Not enough stock!", show_alert=True)
            return
        
        # Get coupons
        coupon_codes = []
        for i in range(quantity):
            if SERVICES[service_key]['stock']:
                coupon = SERVICES[service_key]['stock'].pop(0)
                coupon_codes.append(coupon)
        
        # Update order
        orders[order_id]['status'] = 'approved'
        orders[order_id]['coupon_codes'] = coupon_codes
        
        # Send coupons to user
        coupon_text = "\n".join([f"`{code}`" for code in coupon_codes])
        
        await context.bot.send_message(
            chat_id=order['user'],
            text=(
                f"✅ **Payment Verified & Approved!**\n\n"
                f"🆔 **Order ID:** `{order_id}`\n"
                f"📦 **Service:** {order.get('service_name', service_key)}\n"
                f"🔢 **Quantity:** {quantity}\n"
                f"💰 **Amount:** ₹{order['amount']}\n\n"
                f"🎟️ **Your Coupon Codes:**\n"
                f"{coupon_text}"
            ),
            parse_mode="Markdown",
            reply_markup=get_menu(order['user'])
        )
        
        # Update admin message
        await query.edit_message_text(
            f"✅ **Order Approved!**\n\n"
            f"🆔 **Order ID:** {order_id}\n"
            f"👤 **User:** {order.get('first_name', 'Unknown')}\n"
            f"💰 **Amount:** ₹{order['amount']}\n"
            f"🎟️ **Coupons Sent:** {quantity}\n\n"
            f"✅ **Status:** COMPLETED",
            parse_mode="Markdown"
        )
        
        # Remove proof
        if order_id in payment_proofs:
            del payment_proofs[order_id]
        
        save_data()
    
    elif data.startswith("admin_reject_"):
        if not is_admin(user_id):
            await query.answer("❌ Admin only!", show_alert=True)
            return
        
        order_id = data.split("_")[2]
        
        if order_id not in orders:
            await query.answer("❌ Order not found!", show_alert=True)
            return
        
        order = orders[order_id]
        
        # Update order
        orders[order_id]['status'] = 'rejected'
        
        # Send rejection to user
        await context.bot.send_message(
            chat_id=order['user'],
            text=(
                f"❌ **Payment Rejected!**\n\n"
                f"🆔 **Order ID:** `{order_id}`\n"
                f"📦 **Service:** {order.get('service_name', 'Unknown')}\n"
                f"💰 **Amount:** ₹{order['amount']}\n\n"
                f"⚠️ **Reason:** Payment verification failed.\n\n"
                f"📞 **Support:** Contact admin for appeal."
            ),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [
                    [KeyboardButton("📞 Support")]
                ],
                resize_keyboard=True
            )
        )
        
        # Update admin message
        await query.edit_message_text(
            f"❌ **Order Rejected!**\n\n"
            f"🆔 **Order ID:** {order_id}\n"
            f"👤 **User:** {order.get('first_name', 'Unknown')}\n"
            f"💰 **Amount:** ₹{order['amount']}\n\n"
            f"❌ **Status:** REJECTED\n"
            f"User has been notified.",
            parse_mode="Markdown"
        )
        
        # Remove proof
        if order_id in payment_proofs:
            del payment_proofs[order_id]
        
        save_data()

# ================= ULTRA-FAST COMMANDS =================
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ultra-fast broadcast command"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📢 **Ultra-Fast Broadcast System**\n\n"
            "Usage: `/broadcast your message here`",
            parse_mode="Markdown",
            reply_markup=ADMIN_MENU
        )
        return
    
    broadcast_message = " ".join(context.args)
    user_id = update.effective_user.id
    
    total_users = len(all_users)
    start_time = time.time()
    user_list = list(all_users)
    
    chunk_size = 200
    chunks = [user_list[i:i + chunk_size] for i in range(0, total_users, chunk_size)]
    
    total_sent = 0
    total_failed = 0
    
    for chunk_num, chunk in enumerate(chunks, 1):
        tasks = []
        for uid in chunk:
            tasks.append(ultra_broadcast_send(context.bot, uid, broadcast_message))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if result:
                total_sent += 1
            else:
                total_failed += 1
    
    total_time = time.time() - start_time
    avg_speed = total_sent / total_time if total_time > 0 else 0
    success_rate = (total_sent / total_users * 100) if total_users > 0 else 0
    
    report = f"""✅ **Ultra-Fast Broadcast Complete!**

⚡️ **Performance:**
• Total Users: {total_users:,}
• Time Taken: {total_time:.2f} seconds
• Speed: {avg_speed:.0f} users/second

📊 **Results:**
• ✅ Sent: {total_sent:,} users
• ❌ Failed: {total_failed:,} users
• 📈 Success Rate: {success_rate:.1f}%"""
    
    await update.message.reply_text(
        report,
        parse_mode="Markdown",
        reply_markup=ADMIN_MENU
    )
    save_data()

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redeem command"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    redeem_kb = get_redeem_keyboard()
    if redeem_kb:
        await update.message.reply_text(
            "🔄 **Select service to redeem coupons:**",
            reply_markup=redeem_kb
        )
    else:
        await update.message.reply_text(
            "❌ **No coupons available for redemption!**",
            reply_markup=ADMIN_MENU
        )

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restart bot"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    cancelled_count = 0
    for order_id, order in list(orders.items()):
        if order['status'] == 'pending_proof':
            orders[order_id]['status'] = 'cancelled'
            cancelled_count += 1
    
    user_state.clear()
    save_data()
    
    await update.message.reply_text(
        f"🔄 **Bot Restarting...**\n\n"
        f"✅ **{cancelled_count}** pending orders cancelled\n"
        f"🧹 All user sessions cleared\n"
        f"⚡ Bot restarting...",
        parse_mode="Markdown"
    )
    
    await asyncio.sleep(2)
    
    import sys
    os.execv(sys.executable, ['python'] + sys.argv)

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual backup command"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    msg = await update.message.reply_text("🔄 Creating backup...")
    
    success = await send_backup_to_bot()
    
    if success:
        await msg.edit_text("✅ Backup created and sent successfully!")
    else:
        await msg.edit_text("❌ Backup failed!")

async def proofs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View pending proofs command"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    proofs_text = "📋 **Pending Payment Proofs:**\n\n"
    pending_count = 0
    
    for order_id, proof in payment_proofs.items():
        if order_id in orders and orders[order_id]['status'] == 'pending_proof':
            pending_count += 1
            order = orders[order_id]
            proofs_text += f"🆔 **Order ID:** {order_id}\n"
            proofs_text += f"👤 **User:** {proof.get('first_name', 'Unknown')}\n"
            proofs_text += f"📦 **Service:** {order.get('service_name', 'Unknown')}\n"
            proofs_text += f"💰 **Amount:** ₹{order.get('amount', 0)}\n"
            proofs_text += f"📸 **Proof Type:** {proof.get('type', 'Unknown')}\n"
            
            if proof.get('type') == 'utr':
                proofs_text += f"🔢 **UTR:** `{proof.get('utr', 'N/A')}`\n"
            
            proofs_text += f"🕒 **Received:** {proof.get('timestamp', 'N/A')}\n"
            
            # Add approve/reject buttons
            proofs_text += f"[Approve](https://t.me/{context.bot.username}?start=approve_{order_id}) | "
            proofs_text += f"[Reject](https://t.me/{context.bot.username}?start=reject_{order_id})\n"
            
            proofs_text += f"─────────────────\n"
    
    if pending_count == 0:
        proofs_text = "✅ **No pending payment proofs!**"
    
    await update.message.reply_text(
        proofs_text,
        parse_mode="Markdown",
        reply_markup=ADMIN_MENU
    )

# ================= ULTRA-FAST MAIN =================
def main():
    """Ultra-fast bot main function"""
    load_data()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add job queue for auto backup
    app.job_queue.run_repeating(
        auto_backup_task,
        interval=300,   # 5 minutes
        first=300
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("redeem", redeem_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("backup", backup_command))
    app.add_handler(CommandHandler("proofs", proofs_command))
    
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_messages))
    
    print("=" * 70)
    print("⚡ ULTRA-FAST SHEIN COUPON BOT STARTED")
    print("=" * 70)
    print(f"✅ Token: {BOT_TOKEN[:10]}...")
    print(f"✅ Response Time: < 0.1 seconds")
    print(f"✅ Broadcast Speed: 200 users/chunk")
    print(f"✅ Support: {SUPPORT_USERNAME}")
    print(f"✅ Admins: {ADMIN_IDS}")
    print(f"✅ UPI ID: {UPI_ID}")
    print(f"✅ Auto Backup: Active (every 5 minutes)")
    print(f"✅ Payment Proof System: ACTIVE")
    print(f"✅ Admin Approve/Reject: ACTIVE")
    print("=" * 70)
    print("🚀 Bot is running at MAXIMUM SPEED!")
    
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"❌ Bot error: {e}")
        print("🔄 Restarting...")
        main()

if __name__ == "__main__":
    main()
