import os
import json
import requests
import asyncio
import time
import zipfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, JobQueue

# ================= CONFIG =================
BOT_TOKEN = "7569076581:AAFkJuygMDDIeu-TRhOzDfxCT_AQioj0Q3w"
ADMIN_IDS = [6435124280]
SHOP_NAME = "Shein Coupon Shop"
SUPPORT_USERNAME = "slok_official_75"

# ✅ UPDATED API CONFIGURATION (YOUR TOKEN)
API_ACCESS_TOKEN = "58701da22f7ea435b8e226e93590e91cb6416fd0472b9bb20467c1bc43e88df5"
API_CREATE_URL = "https://earnmoneysupport.xyz/create.php"
API_CHECK_URL = "https://earnmoneysupport.xyz/checkpayment.php"

# BACKUP BOT CONFIG
BACKUP_BOT_TOKEN = "8160418885:AAHsKpVNWHxhdEy6nYzqv394eh3eYFdVXPo"
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
today_stats = {
    "date": datetime.now().strftime("%Y-%m-%d"),
    "total_orders": 0,
    "approved_orders": 0,
    "total_revenue": 0,
    "service_counts": {"500 Pe 500": 0, "1000 Pe 1000": 0, "2000 Pe 2000": 0, "4000 Pe 4000": 0},
    "total_coupons": 0
}
response_cache = {}

# Payment tracking flags (NEW ADDED)
payment_tracking = {
    'has_coupon_been_sent': {},  # order_id -> bool
    'is_checking': {}  # order_id -> bool
}

# Thread pool for high-performance operations
thread_pool = ThreadPoolExecutor(max_workers=100)

# ================= DATA SAVING/LOADING =================
DATA_FILE = "bot_data.json"

def save_data():
    """Save all bot data to file"""
    try:
        # Filter out cancelled orders from saving
        filtered_orders = {}
        for order_id, order in orders.items():
            if order.get('status') == 'approved':  # SIRF APPROVED ORDERS SAVE
                filtered_orders[order_id] = order
        
        data = {
            "orders": filtered_orders,
            "services": SERVICES,
            "all_users": list(all_users),
            "order_counter": order_counter,
            "redeemed_coupons": redeemed_coupons,
            "last_backup": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "today_stats": today_stats,
            "payment_tracking": payment_tracking  # NEW: Save payment tracking
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Data saved to {DATA_FILE}")
        return True
    except Exception as e:
        print(f"❌ Error saving data: {e}")
        return False

def load_data():
    """Load bot data from file"""
    global orders, SERVICES, all_users, order_counter, redeemed_coupons, today_stats, payment_tracking
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            
            # Load only approved orders
            orders = data.get("orders", {})
            
            saved_services = data.get("services", {})
            for key in SERVICES:
                if key in saved_services:
                    SERVICES[key]["stock"] = saved_services[key].get("stock", [])
                    SERVICES[key]["price"] = saved_services[key].get("price", SERVICES[key]["price"])
            
            all_users = set(data.get("all_users", []))
            order_counter = data.get("order_counter", 1)
            redeemed_coupons = data.get("redeemed_coupons", {})
            
            loaded_stats = data.get("today_stats", {})
            today_date = datetime.now().strftime("%Y-%m-%d")
            
            # Check if today is different date
            if loaded_stats.get("date") != today_date:
                today_stats = {
                    "date": today_date,
                    "total_orders": 0,
                    "approved_orders": 0,
                    "total_revenue": 0,
                    "service_counts": {"500 Pe 500": 0, "1000 Pe 1000": 0, "2000 Pe 2000": 0, "4000 Pe 4000": 0},
                    "total_coupons": 0
                }
            else:
                today_stats = loaded_stats
            
            # Load payment tracking (NEW)
            payment_tracking = data.get("payment_tracking", {'has_coupon_been_sent': {}, 'is_checking': {}})
            
            print(f"✅ Data loaded: {len(all_users)} users, {len(orders)} orders")
            return True
            
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return False
    else:
        print("⚠️ No data file found, starting with default data")
        return True

def update_today_stats():
    """Update today's statistics - FIXED VERSION"""
    global today_stats
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    # Reset stats if it's a new day
    if today_stats["date"] != today_date:
        today_stats = {
            "date": today_date,
            "total_orders": 0,
            "approved_orders": 0,
            "total_revenue": 0,
            "service_counts": {"500 Pe 500": 0, "1000 Pe 1000": 0, "2000 Pe 2000": 0, "4000 Pe 4000": 0},
            "total_coupons": 0
        }
    
    # Recalculate stats from today's orders
    total_orders_today = 0
    approved_orders_today = 0
    total_revenue_today = 0
    total_coupons_today = 0
    service_counts_today = {"500 Pe 500": 0, "1000 Pe 1000": 0, "2000 Pe 2000": 0, "4000 Pe 4000": 0}
    
    current_date_str = datetime.now().strftime("%d %B %Y")
    
    for order_id, order in orders.items():
        order_date = order.get('date', '')
        if order_date == current_date_str:
            total_orders_today += 1
            
            if order.get('status') == 'approved':
                approved_orders_today += 1
                total_revenue_today += order.get('amount', 0)
                total_coupons_today += order.get('quantity', 0)
                
                service_name = order.get('service_name', 'Unknown')
                if service_name in service_counts_today:
                    service_counts_today[service_name] += 1
    
    # Update today_stats
    today_stats["total_orders"] = total_orders_today
    today_stats["approved_orders"] = approved_orders_today
    today_stats["total_revenue"] = total_revenue_today
    today_stats["total_coupons"] = total_coupons_today
    today_stats["service_counts"] = service_counts_today

# ================= BACKUP SYSTEM =================
def create_zip_backup():
    """Create ZIP backup of all data"""
    global backup_counter
    
    try:
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_counter += 1
        
        save_data()
        
        files_to_backup = []
        if os.path.exists(DATA_FILE):
            files_to_backup.append(DATA_FILE)
        
        backup_info = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_users": len(all_users),
            "total_orders": len(orders),
            "services": {k: {"name": v["name"], "stock_count": len(v["stock"]), "price": v["price"]} for k, v in SERVICES.items()},
            "backup_number": backup_counter,
            "today_stats": today_stats
        }
        
        info_file = f"{backup_dir}/backup_info_{timestamp}.json"
        with open(info_file, 'w') as f:
            json.dump(backup_info, f, indent=2)
        files_to_backup.append(info_file)
        
        zip_filename = f"{backup_dir}/shein_bot_backup_{timestamp}.zip"
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in files_to_backup:
                if os.path.exists(file):
                    zipf.write(file, os.path.basename(file))
        
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
        
        bot_url = f"https://api.telegram.org/bot{BACKUP_BOT_TOKEN}/sendDocument"
        
        with open(zip_file, 'rb') as file:
            files = {'document': (os.path.basename(zip_file), file)}
            data = {'chat_id': BACKUP_CHAT_ID}
            
            response = requests.post(bot_url, data=data, files=files)
            result = response.json()
            
            if result.get('ok'):
                print(f"✅ Backup sent to backup bot")
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
    """Auto backup task every 10 minutes"""
    print("🔄 Running auto backup...")
    await send_backup_to_bot()

# ================= ULTRA FAST BROADCAST =================
async def ultra_broadcast_send(bot, user_id, message):
    """Single message sender with caching"""
    cache_key = f"broadcast_{user_id}_{hash(message)}"
    if cache_key in response_cache:
        return True
        
    try:
        await bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode="Markdown",
            disable_notification=True  # Faster delivery
        )
        response_cache[cache_key] = True
        return True
    except Exception as e:
        print(f"Broadcast error for {user_id}: {e}")
        return False

async def ultra_hd_broadcast(bot, user_ids, message):
    """Ultra fast broadcast using asyncio gather with chunks"""
    if not user_ids:
        return 0, 0
    
    # Split into chunks of 1000 for better performance
    chunk_size = 1000
    chunks = [user_ids[i:i + chunk_size] for i in range(0, len(user_ids), chunk_size)]
    
    total_sent = 0
    total_failed = 0
    
    for chunk in chunks:
        # Create tasks for this chunk
        tasks = [ultra_broadcast_send(bot, uid, message) for uid in chunk]
        
        # Execute all tasks concurrently
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if result is True:
                    total_sent += 1
                else:
                    total_failed += 1
                    
            # Small delay between chunks to avoid rate limits
            if len(chunks) > 1:
                await asyncio.sleep(0.05)
                
        except Exception as e:
            print(f"Chunk broadcast error: {e}")
            total_failed += len(chunk)
    
    return total_sent, total_failed

# ================= KEYBOARDS =================
def get_stock_display():
    """Stock display with proper formatting"""
    stock_text = "🎉 **Shein Coupon Store**\n\n"
    for key, service in SERVICES.items():
        stock_count = len(service['stock'])
        stock_emoji = "🟢" if stock_count > 0 else "🔴"
        stock_text += f"{stock_emoji} {service['name']} Stock: {stock_count}\n"
    return stock_text

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
        [KeyboardButton("📢 Broadcast"), KeyboardButton("📈 Statistics")]
    ],
    resize_keyboard=True
)

def get_cancel_keyboard(show_cancel=False):
    """Get cancel keyboard"""
    if show_cancel:
        return ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel Order")]], resize_keyboard=True)
    return USER_MENU

# ================= STATISTICS FUNCTIONS =================
def get_general_statistics():
    """Get general statistics - FIXED"""
    total_orders = len(orders)
    approved_orders = sum(1 for order in orders.values() if order.get('status') == 'approved')
    pending_orders = sum(1 for order in orders.values() if order.get('status') == 'pending')
    cancelled_orders = sum(1 for order in orders.values() if order.get('status') in ['cancelled', 'timeout'])
    
    total_revenue = sum(order.get('amount', 0) for order in orders.values() if order.get('status') == 'approved')
    
    stats_text = f"""📈 **General Statistics:**

• 👥 Total Users: {len(all_users):,}
• 📦 Total Orders: {total_orders:,}
• ✅ Approved: {approved_orders:,}
• ⏳ Pending: {pending_orders:,}
• ❌ Cancelled: {cancelled_orders:,}
• 💰 Total Revenue: ₹{total_revenue:,}"""
    
    return stats_text

def get_today_statistics():
    """Get today's statistics - FIXED"""
    update_today_stats()
    
    today_date = datetime.now().strftime("%d %B %Y")
    
    stats_text = f"""📅 **Today's Statistics ({today_date})**

• 📦 Today's Orders: {today_stats["total_orders"]:,}
• ✅ Today's Approved: {today_stats["approved_orders"]:,}
• 🎟️ Today's Coupons Sold: {today_stats["total_coupons"]:,}
• 💰 Today's Revenue: ₹{today_stats["total_revenue"]:,}"""

    # Add service-wise breakdown
    stats_text += "\n\n**📊 Service-wise Breakdown:**"
    for service_name, count in today_stats["service_counts"].items():
        if count > 0:
            stats_text += f"\n• {service_name}: {count:,}"
        else:
            stats_text += f"\n• {service_name}: 0"
    
    return stats_text

# ================= BASIC FUNCTIONS =================
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
        stock_count = len(service['stock'])
        if stock_count > 0:
            button_text = f"✅ {service['name']} | ₹{service['price']} | Stock: {stock_count}"
        else:
            button_text = f"❌ {service['name']} | ₹{service['price']} | Out of Stock"
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

# ================= PAYMENT CHECKING FUNCTIONS (UPDATED) =================
async def check_single_payment(api_order_id, user_id, context, qr_msg_id):
    """Single payment check when user clicks "I Have Paid" button"""
    try:
        # ✅ Check: Order exists and is pending
        if api_order_id not in orders:
            return False
        
        if orders[api_order_id].get('status') != 'pending':
            return False
        
        # ✅ Check if coupon already sent
        if payment_tracking['has_coupon_been_sent'].get(api_order_id):
            print(f"⚠️ Coupon already sent for {api_order_id}")
            return True
        
        # ✅ Set checking flag to prevent multiple checks
        if payment_tracking['is_checking'].get(api_order_id):
            print(f"⚠️ Already checking for {api_order_id}")
            return False
        
        payment_tracking['is_checking'][api_order_id] = True
        
        # ✅ Wait 5 seconds before checking
        await asyncio.sleep(5)
        
        # ✅ Check payment status
        response = requests.get(
            API_CHECK_URL, 
            params={"access_token": API_ACCESS_TOKEN, "orderid": api_order_id},
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # ✅ Check for payment success
                    if data.get("STATUS") == "TXN_SUCCESS" or data.get("success") == True:
                        # ✅ Check again if coupon already sent
                        if payment_tracking['has_coupon_been_sent'].get(api_order_id):
                            break
                        
                        order = orders.get(api_order_id)
                        if not order: 
                            break
                        
                        # ✅ Mark coupon as sent
                        payment_tracking['has_coupon_been_sent'][api_order_id] = True
                        
                        # ✅ Delete QR message
                        try: 
                            await context.bot.delete_message(chat_id=user_id, message_id=qr_msg_id)
                        except: 
                            pass

                        service_key = order.get('service')
                        quantity = order.get('quantity', 1)
                        coupon_codes = []
                        
                        # ✅ Safely get coupons from stock
                        for _ in range(quantity):
                            if SERVICES[service_key]['stock']:
                                coupon_codes.append(SERVICES[service_key]['stock'].pop(0))
                        
                        # ✅ Update order
                        orders[api_order_id]['status'] = 'approved'
                        orders[api_order_id]['coupon_codes'] = coupon_codes
                        
                        # ✅ Update today's stats
                        today_stats["approved_orders"] += 1
                        today_stats["total_revenue"] += order.get('amount', 0)
                        today_stats["total_coupons"] += quantity
                        
                        service_name = order.get('service_name', 'Unknown')
                        if service_name in today_stats["service_counts"]:
                            today_stats["service_counts"][service_name] += 1
                    
                        # ✅ Format coupon codes
                        if coupon_codes:
                            coupon_text = "\n".join([f"• `{code}`" for code in coupon_codes])
                        else:
                            coupon_text = "No coupons received"
                        
                        # ✅ Send success message
                        success_message = (
                            f"✅ **Payment Approved!**\n\n"
                            f"🆔 **Order ID:** `{api_order_id}`\n"
                            f"📦 **Service:** {order.get('service_name', service_key)}\n"
                            f"🔢 **Quantity:** {quantity}\n"
                            f"💰 **Amount:** ₹{order.get('amount', 0)}\n"
                            f"📅 **Date:** {order.get('date', 'N/A')}\n"
                            f"🎟️ **Your Coupon Codes:**\n"
                            f"{coupon_text}\n\n"
                            f"💾 **Thanks for your purchase**"
                        )
                        
                        await context.bot.send_message(
                            chat_id=order['user'],
                            text=success_message,
                            parse_mode="Markdown",
                            reply_markup=get_menu(order['user'])
                        )
                        save_data()
                        return
            
        except Exception as e: 
            print(f"Payment check error: {e}")
        
        await asyncio.sleep(5)
        checks += 1
    
    # ✅ UPDATED: Timeout after 5 minutes with new message format
    if api_order_id in orders and orders[api_order_id].get('status') == 'pending':
        orders[api_order_id]['status'] = 'timeout'
        
        try: 
            await context.bot.delete_message(chat_id=user_id, message_id=qr_msg_id)
        except: 
            pass
        
        # ✅ NEW TIMEOUT MESSAGE FORMAT
        timeout_message = (
            f"⏰ PAYMENT TIMEOUT\n\n"
            f"Payment verification timed out for order {api_order_id}.\n\n"
            f"❌ This order has been cancelled.\n"
            f"If you have already paid, please contact support with your order ID.\n"
            f"We apologize for the inconvenience."
        )
        
        await context.bot.send_message(
            chat_id=user_id,
            text=timeout_message,
            reply_markup=get_menu(user_id)
        )
        save_data()

# ================= COMMAND HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user_id = update.effective_user.id
    all_users.add(user_id)
    
    # Clear user state if exists
    if user_id in user_state:
        internal_order_id = user_state[user_id].get('internal_order_id')
        if internal_order_id and internal_order_id in orders:
            if orders[internal_order_id].get('status') == 'pending':
                orders[internal_order_id]['status'] = 'cancelled'
        del user_state[user_id]
    
    # Get stock display
    stock_display = get_stock_display()
    
    welcome_text = f"""{stock_display}

Hello, **{update.effective_user.first_name}!** 👋

Select the coupon service you want to purchase👇"""
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_menu(user_id),
        parse_mode="Markdown"
    )
    save_data()

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Message handler"""
    user_id = update.effective_user.id
    text = update.message.text if update.message else ""
    
    if not text:
        return
    
    # Add user to all_users
    all_users.add(user_id)
    
    # Clear state if user types /start
    if "/start" in text:
        if user_id in user_state:
            internal_order_id = user_state[user_id].get('internal_order_id')
            if internal_order_id and internal_order_id in orders:
                if orders[internal_order_id].get('status') == 'pending':
                    orders[internal_order_id]['status'] = 'cancelled'
            del user_state[user_id]
    
    # Cancel Order
    if text == "❌ Cancel Order":
        if user_id in user_state:
            state = user_state[user_id]
            service_name = state.get('service_name', 'Unknown')
            
            current_order_id = state.get('internal_order_id')
            if current_order_id and current_order_id in orders:
                orders[current_order_id]['status'] = 'cancelled'
                # ✅ Also remove from payment tracking
                payment_tracking['has_coupon_been_sent'].pop(current_order_id, None)
                payment_tracking['is_checking'].pop(current_order_id, None)
            
            await update.message.reply_text(
                f"❌ **Order Cancelled Successfully!**\n\n"
                f"📦 **Service:** {service_name}\n"
                f"✅ **Process stopped.**",
                reply_markup=get_menu(user_id),
                parse_mode="Markdown"
            )
            del user_state[user_id]
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
                "📢 **Ultra Fast Broadcast System**\n\n"
                "Send the message you want to broadcast:\n"
                f"• Total Users: {len(all_users):,}\n"
                f"• Speed: ~50k users in 5 seconds",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Cancel")]], resize_keyboard=True),
                parse_mode="Markdown"
            )
            user_state[user_id] = {"action": "broadcast"}
            return
        elif text == "📈 Statistics":
            stats_text = get_general_statistics() + "\n\n" + get_today_statistics()
            await update.message.reply_text(
                stats_text,
                reply_markup=ADMIN_MENU,
                parse_mode="Markdown"
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
            if order.get('user') == user_id and order.get('status') == 'approved':
                user_orders.append((order_id, order))
        
        if not user_orders:
            history_text = "📭 **No orders found!**\n\nYou haven't placed any approved order yet."
        else:
            history_text = "📜 **Your Order History:**\n\n"
            for order_id, order in user_orders[:15]:  # Limit to 15 orders
                coupon_codes = order.get('coupon_codes', [])
                
                if coupon_codes:
                    if len(coupon_codes) <= 3:
                        coupons_display = ", ".join([f"`{code}`" for code in coupon_codes])
                    else:
                        coupons_display = ", ".join([f"`{code}`" for code in coupon_codes[:3]]) + f" ... and {len(coupon_codes)-3} more"
                else:
                    coupons_display = "No coupons"
                
                history_text += (
                    f"✅ **Order ID:** `{order_id}`\n"
                    f"📦 **Service:** {order.get('service_name', 'Unknown')}\n"
                    f"🔢 **Quantity:** {order.get('quantity', 1)}\n"
                    f"💰 **Amount:** ₹{order.get('amount', 0)}\n"
                    f"📅 **Date:** {order.get('date', 'N/A')}\n"
                    f"🎟️ **Coupons:** {coupons_display}\n"
                    f"─────────────────\n"
                )
        
        await update.message.reply_text(
            history_text,
            reply_markup=get_menu(user_id),
            parse_mode="Markdown"
        )
        return
    
    elif text == "📞 Support":
        support_text = (
            f"📞 **Support Contact**\n\n"
            f"For any queries or issues:\n\n"
            f"⏰ **Response Time:** 1-2 hours\n\n"
            f"**Contact Support**"
        )
        
        support_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📲 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton("❌ Close", callback_data="close_support")]
        ])
        
        await update.message.reply_text(
            support_text,
            reply_markup=support_keyboard,
            parse_mode="Markdown"
        )
        return
    
    # ULTRA FAST BROADCAST handling
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
        if total_users == 0:
            await update.message.reply_text(
                "❌ **No users to broadcast to!**",
                reply_markup=ADMIN_MENU
            )
            del user_state[user_id]
            return
        
        start_time = time.time()
        msg = await update.message.reply_text(f"📤 Ultra Fast Broadcasting to {total_users:,} users...")
        
        # Get user list
        user_list = list(all_users)
        
        # Use ultra fast broadcast function
        total_sent, total_failed = await ultra_hd_broadcast(context.bot, user_list, broadcast_message)
        
        end_time = time.time()
        time_taken = end_time - start_time
        
        success_rate = (total_sent / total_users * 100) if total_users > 0 else 0
        
        report = f"""✅ **Ultra Fast Broadcast Complete!**

📊 **Results:**
• Total Users: {total_users:,}
• ✅ Sent: {total_sent:,} users
• ❌ Failed: {total_failed:,} users
• 📈 Success Rate: {success_rate:.1f}%
• ⚡ Time Taken: {time_taken:.2f} seconds
• 🚀 Speed: ~{total_users/time_taken:.0f} users/second"""

        await msg.edit_text(report, parse_mode="Markdown")
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
    
    # Order flow handling
    if user_id in user_state:
        state = user_state[user_id]
        
        if state.get("step") == "quantity":
            if text.isdigit():
                qty = int(text)
                service_key = state.get("service")
                
                if not service_key or service_key not in SERVICES:
                    await update.message.reply_text(
                        "❌ Service not found. Please start over.",
                        reply_markup=get_menu(user_id)
                    )
                    del user_state[user_id]
                    return
                
                stock_count = len(SERVICES[service_key]['stock'])
                
                if qty < 1:
                    await update.message.reply_text(
                        "❌ **Quantity must be at least 1!**\n\n"
                        "Please enter a valid quantity:",
                        reply_markup=get_cancel_keyboard(True)
                    )
                    return
                
                # Apply quantity limit: min(stock, 100)
                max_quantity = min(stock_count, 100)
                if qty > max_quantity:
                    await update.message.reply_text(
                        f"❌ **Quantity limit exceeded!**\n\n"
                        f"Maximum allowed: {max_quantity}\n"
                        f"Your input: {qty}\n\n"
                        "Please enter a smaller quantity:",
                        reply_markup=get_cancel_keyboard(True)
                    )
                    return
                
                amount = state.get("price", 0) * qty
                
                # ✅ Generate payment with YOUR API
                try:
                    response = requests.get(
                        API_CREATE_URL,
                        params={
                            "access_token": API_ACCESS_TOKEN,
                            "amount": amount,
                            "note": f"Shein-{user_id}"
                        },
                        timeout=10
                    )
                    
                    if response.status_code != 200:
                        await update.message.reply_text(
                            "❌ Payment gateway error. Please try again.",
                            reply_markup=get_menu(user_id)
                        )
                        del user_state[user_id]
                        return
                    
                    api_data = response.json()
                    
                    # ✅ Handle YOUR API response format
                    if not api_data.get("success"):
                        await update.message.reply_text(
                            "❌ Error generating payment. Please try again later.",
                            reply_markup=get_menu(user_id)
                        )
                        del user_state[user_id]
                        return
                    
                    order_id = str(api_data.get("order_id", ""))
                    qr_code_url = api_data.get("qr_code", "")
                    
                    if not order_id or not qr_code_url:
                        await update.message.reply_text(
                            "❌ Invalid payment response. Please try again.",
                            reply_markup=get_menu(user_id)
                        )
                        del user_state[user_id]
                        return
                    
                    # Initialize payment tracking for this order
                    payment_tracking['has_coupon_been_sent'][order_id] = False
                    payment_tracking['is_checking'][order_id] = False
                    
                    # Create order
                    orders[order_id] = {
                        "user": user_id,
                        "username": update.effective_user.username,
                        "first_name": update.effective_user.first_name,
                        "service": service_key,
                        "service_name": state.get("service_name", "Unknown"),
                        "quantity": qty,
                        "amount": amount,
                        "status": "pending",
                        "api_order_id": order_id,
                        "date": datetime.now().strftime("%d %B %Y"),
                        "time": datetime.now().strftime("%I:%M %p"),
                        "coupon_codes": []
                    }
                    
                    # Update today's stats for pending order
                    today_stats["total_orders"] += 1
                    
                    user_state[user_id]['internal_order_id'] = order_id
                    user_state[user_id]['step'] = 'waiting_payment'
                    
                    # ✅ Send QR with TWO BUTTONS
                    payment_keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ I Have Paid", callback_data=f"paid_{order_id}"),
                            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}")
                        ]
                    ])
                    
                    qr_message = await update.message.reply_photo(
                        photo=qr_code_url,
                        caption=(
                            f"🧾 **Pay ₹{amount}**\n\n"
                            f"**Service:** {state.get('service_name', 'Unknown')}\n"
                            f"**Quantity:** {qty}\n"
                            f"**Order ID:** `{order_id}`\n\n"
                            f"⏰ QR expires in 5 minutes"
                        ),
                        reply_markup=payment_keyboard,
                        parse_mode="Markdown"
                    )
                    
                    qr_message_id = qr_message.message_id
                    
                    # Start payment check in background (30-second intervals)
                    asyncio.create_task(
                        check_payment_background(order_id, qr_message_id, user_id, context)
                    )
                    
                except Exception as e:
                    print(f"API Error: {e}")
                    await update.message.reply_text(
                        "❌ Payment gateway error. Please try again later.",
                        reply_markup=get_menu(user_id)
                    )
                    del user_state[user_id]
            else:
                await update.message.reply_text(
                    "❌ Please enter a valid number",
                    reply_markup=get_cancel_keyboard(True)
                )
        elif state.get("step") == "waiting_payment":
            await update.message.reply_text(
                "⏳ **Payment is being verified automatically.**\n"
                "Please wait, do not send screenshots.",
                reply_markup=get_cancel_keyboard(True)
            )
        else:
            await update.message.reply_text(
                "Please select an option from the menu.",
                reply_markup=get_menu(user_id)
            )
    else:
        await update.message.reply_text(
            "Please select an option from the menu.",
            reply_markup=get_menu(user_id)
        )

# ================= CALLBACK HANDLER (UPDATED) =================
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback handler with updated payment logic"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # ✅ Handle "I Have Paid" button
    if data.startswith("paid_"):
        api_order_id = data.split("_")[1]
        
        if api_order_id not in orders:
            await query.answer("Order not found!", show_alert=True)
            return
        
        if orders[api_order_id].get('user') != user_id:
            await query.answer("This is not your order!", show_alert=True)
            return
        
        if orders[api_order_id].get('status') != 'pending':
            await query.answer("Order already processed!", show_alert=True)
            return
        
        # ✅ Check if coupon already sent
        if payment_tracking['has_coupon_been_sent'].get(api_order_id):
            await query.answer("Payment already verified! Check your messages.", show_alert=True)
            return
        
        # ✅ Check if already checking
        if payment_tracking['is_checking'].get(api_order_id):
            await query.answer("Already checking payment... Please wait.", show_alert=True)
            return
        
        # ✅ Set checking flag
        payment_tracking['is_checking'][api_order_id] = True
        
        # Start single payment check
        await query.answer("✅ Checking payment... Please wait 5 seconds.", show_alert=True)
        
        # Start check in background
        asyncio.create_task(
            check_single_payment(api_order_id, user_id, context, query.message.message_id)
        )
        return
    
    # ✅ Handle "Cancel" button
    elif data.startswith("cancel_"):
        api_order_id = data.split("_")[1]
        
        if api_order_id not in orders:
            await query.answer("Order not found!", show_alert=True)
            return
        
        if orders[api_order_id].get('user') != user_id:
            await query.answer("This is not your order!", show_alert=True)
            return
        
        if orders[api_order_id].get('status') != 'pending':
            await query.answer("Order already processed!", show_alert=True)
            return
        
        # Cancel the order
        orders[api_order_id]['status'] = 'cancelled'
        
        # ✅ Remove from payment tracking
        payment_tracking['has_coupon_been_sent'].pop(api_order_id, None)
        payment_tracking['is_checking'].pop(api_order_id, None)
        
        # Delete QR message
        try:
            await query.message.delete()
        except:
            pass
        
        # ✅ Send ONLY ONE cancellation message
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Your order has been cancelled.",
            reply_markup=get_menu(user_id)
        )
        
        # ✅ Clear user state if exists
        if user_id in user_state:
            if user_state[user_id].get('internal_order_id') == api_order_id:
                del user_state[user_id]
        
        save_data()
        return
    
    # Rest of your existing callback handler
    elif data.startswith("select_"):
        key = data.split("_")[1]
        
        if key not in SERVICES:
            await query.edit_message_text("❌ Service not found!")
            return
        
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
        
        max_quantity = min(stock_count, 100)
        await query.edit_message_text(
            f"✅ **Selected:** {SERVICES[key]['name']}\n"
            f"💰 **Price:** ₹{SERVICES[key]['price']} per coupon\n"
            f"👉 **Enter quantity (max {max_quantity}):**",
            parse_mode="Markdown"
        )
    
    elif data == "cancel_selection":
        if user_id in user_state:
            del user_state[user_id]
        
        await query.edit_message_text(
            "❌ **Selection Cancelled!**\n\nOrder process has been cancelled.",
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
            "❌ **Cancelled!**\n\nCoupon addition has been cancelled.",
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
            "❌ **Cancelled!**\n\nPrice change has been cancelled.",
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
            "❌ **Cancelled!**\n\nRedemption has been cancelled.",
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
        welcome_text = f"""{stock_display}

Hello, **{query.from_user.first_name}!** 👋

Select the coupon service you want to purchase👇"""
        
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
        if service_key not in SERVICES:
            await query.edit_message_text("❌ Service not found!")
            return
        
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
        if len(parts) < 4:
            await query.edit_message_text("❌ Invalid data!")
            return
        
        service_key = parts[2]
        quantity = int(parts[3])
        
        if service_key not in SERVICES:
            await query.edit_message_text("❌ Service not found!")
            return
        
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
        if service_key not in SERVICES:
            await query.edit_message_text("❌ Service not found!")
            return
        
        user_state[user_id] = {
            'action': 'adding_coupons',
            'service_key': service_key
        }
        
        await query.edit_message_text(
            f"📝 **Adding coupons for {SERVICES[service_key]['name']}**\n\n"
            "Send coupon codes (one per line):",
            parse_mode="Markdown"
        )

# ================= COMMANDS =================
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast command - ULTRA FAST"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📢 **Ultra Fast Broadcast System**\n\n"
            "Usage: `/broadcast your message here`\n"
            f"• Total Users: {len(all_users):,}\n"
            f"• Speed: ~50k users in 5 seconds",
            parse_mode="Markdown",
            reply_markup=ADMIN_MENU
        )
        return
    
    broadcast_message = " ".join(context.args)
    
    total_users = len(all_users)
    if total_users == 0:
        await update.message.reply_text(
            "❌ **No users to broadcast to!**",
            reply_markup=ADMIN_MENU
        )
        return
    
    start_time = time.time()
    msg = await update.message.reply_text(f"📤 Ultra Fast Broadcasting to {total_users:,} users...")
    
    # Get user list
    user_list = list(all_users)
    
    # Use ultra fast broadcast function
    total_sent, total_failed = await ultra_hd_broadcast(context.bot, user_list, broadcast_message)
    
    end_time = time.time()
    time_taken = end_time - start_time
    
    success_rate = (total_sent / total_users * 100) if total_users > 0 else 0
    
    report = f"""✅ **Ultra Fast Broadcast Complete!**

📊 **Results:**
• Total Users: {total_users:,}
• ✅ Sent: {total_sent:,} users
• ❌ Failed: {total_failed:,} users
• 📈 Success Rate: {success_rate:.1f}%
• ⚡ Time Taken: {time_taken:.2f} seconds
• 🚀 Speed: ~{total_users/time_taken:.0f} users/second"""
    
    await msg.edit_text(report, parse_mode="Markdown")

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

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistics command"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    stats_text = get_general_statistics() + "\n\n" + get_today_statistics()
    
    await update.message.reply_text(
        stats_text,
        parse_mode="Markdown",
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
        if order.get('status') == 'pending':
            orders[order_id]['status'] = 'cancelled'
            cancelled_count += 1
    
    # Clear payment tracking
    payment_tracking['has_coupon_been_sent'].clear()
    payment_tracking['is_checking'].clear()
    
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

# ================= MAIN =================
def main():
    """Main function"""
    # Load data first
    load_data()
    
    # Create application with optimized settings
    app = Application.builder() \
        .token(BOT_TOKEN) \
        .pool_timeout(30) \
        .connect_timeout(30) \
        .read_timeout(30) \
        .write_timeout(30) \
        .get_updates_read_timeout(30) \
        .get_updates_write_timeout(30) \
        .get_updates_connect_timeout(30) \
        .get_updates_pool_timeout(30) \
        .build()
    
    # Add job queue for auto backup (every 10 minutes)
    app.job_queue.run_repeating(
        auto_backup_task,
        interval=600,
        first=10
    )
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("redeem", redeem_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("backup", backup_command))
    
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    
    print("=" * 70)
    print("⚡ ULTRA FAST SHEIN COUPON BOT STARTED")
    print("=" * 70)
    print(f"✅ Token: {BOT_TOKEN[:10]}...")
    print(f"✅ Support: @{SUPPORT_USERNAME}")
    print(f"✅ Admins: {ADMIN_IDS}")
    print(f"✅ API Token: {API_ACCESS_TOKEN[:10]}...")
    print(f"✅ Auto Backup: Active (every 10 minutes)")
    print(f"✅ Max Workers: 100 threads")
    print(f"✅ Broadcast Speed: ~50k users/5 seconds")
    print("=" * 70)
    print("🚀 Bot is running at MAX SPEED...")
    
    try:
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            close_loop=False,
            stop_signals=None
        )
    except Exception as e:
        print(f"❌ Bot error: {e}")
        print("🔄 Restarting in 3 seconds...")
        time.sleep(3)
        main()

if __name__ == "__main__":
    main()
