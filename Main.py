import io
import qrcode
import json
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ================= CONFIG =================
BOT_TOKEN = "8361909857:AAF9rpNo3ncAFgB15dyj9wc4cB4jLhbvCZc"
ADMIN_IDS = [6435124280]
UPI_ID = "slokjaat75@fam"
SHOP_NAME = "Shein Coupon Shop"
SUPPORT_USERNAME = "@slokjaat75"
CHANNEL_LINK = "https://t.me/slok_official_75"

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
pending_orders = []
redeemed_coupons = {}

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
            "pending_orders": pending_orders,
            "redeemed_coupons": redeemed_coupons
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print("✅ Data saved successfully")
    except Exception as e:
        print(f"❌ Error saving data: {e}")

def load_data():
    """Load bot data from file"""
    global orders, SERVICES, all_users, order_counter, pending_orders, redeemed_coupons
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            
            orders = data.get("orders", {})
            SERVICES = data.get("services", SERVICES)
            all_users = set(data.get("all_users", []))
            order_counter = data.get("order_counter", 1)
            pending_orders = data.get("pending_orders", [])
            redeemed_coupons = data.get("redeemed_coupons", {})
            print("✅ Bot data loaded successfully")
            print(f"📊 Loaded: {len(orders)} orders, {len(all_users)} users")
        except Exception as e:
            print(f"❌ Error loading data: {e}")

# ================= KEYBOARDS =================
USER_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🛒 Buy Coupon"), KeyboardButton("📜 History")],
        [KeyboardButton("📢 Join Channel"), KeyboardButton("📞 Support")]
    ],
    resize_keyboard=True
)

ADMIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📦 Add Coupons"), KeyboardButton("📊 View Stock")],
        [KeyboardButton("🔄 Redeem Coupon"), KeyboardButton("📋 Pending Orders")],
        [KeyboardButton("📢 Broadcast"), KeyboardButton("🔙 User Menu")]
    ],
    resize_keyboard=True
)

CANCEL_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("❌ Cancel Order")]],
    resize_keyboard=True
)

# ================= FUNCTIONS =================
def get_stock_display():
    stock_text = "🎉 **Shein Coupon Store**\n\n"
    for key, service in SERVICES.items():
        stock_text += f"🟢 {service['name']} Stock: {len(service['stock'])}\n"
    return stock_text

def get_stock_detailed():
    stock_text = "📊 **Coupon Stock Details:**\n\n"
    for key, service in SERVICES.items():
        stock_text += f"📦 **{service['name']}**\n"
        stock_text += f"   Price: ₹{service['price']} | Stock: {len(service['stock'])}\n"
        if service['stock']:
            stock_text += f"   Available: {', '.join(service['stock'][:5])}"
            if len(service['stock']) > 5:
                stock_text += f" ... and {len(service['stock']) - 5} more"
        stock_text += "\n"
    return stock_text

def get_redeemable_coupons():
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
    return user_id in ADMIN_IDS

def get_menu(user_id):
    return ADMIN_MENU if is_admin(user_id) else USER_MENU

def get_services_keyboard():
    keyboard = []
    for key, service in SERVICES.items():
        stock_count = len(service['stock'])
        button_text = f"{service['name']} | ₹{service['price']} | Stock: {stock_count}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_{key}")])
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_selection")])
    return InlineKeyboardMarkup(keyboard)

def get_admin_approval_keyboard(order_id):
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{order_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_add_coupon_keyboard():
    keyboard = [
        [InlineKeyboardButton("500 Pe 500", callback_data="add_500")],
        [InlineKeyboardButton("1000 Pe 1000", callback_data="add_1000")],
        [InlineKeyboardButton("2000 Pe 2000", callback_data="add_2000")],
        [InlineKeyboardButton("4000 Pe 4000", callback_data="add_4000")],
        [InlineKeyboardButton("🔙 Cancel", callback_data="cancel_add")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_redeem_keyboard():
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

# ================= COMMAND HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    all_users.add(user_id)
    
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
    user_id = update.effective_user.id
    text = update.message.text
    
    all_users.add(user_id)
    
    # ✅ Handle Cancel Order button
    if text == "❌ Cancel Order":
        if user_id in user_state:
            state = user_state[user_id]
            service_name = state.get('service_name', 'Unknown')
            
            # Create cancelled order record
            global order_counter
            order_id = f"CANC{order_counter:06d}"
            order_counter += 1
            
            orders[order_id] = {
                "user": user_id,
                "username": update.effective_user.username,
                "first_name": update.effective_user.first_name,
                "service": state.get('service', ''),
                "service_name": service_name,
                "quantity": state.get('quantity', 0),
                "amount": state.get('amount', 0),
                "status": "cancelled",
                "date": update.message.date.strftime("%d %B %Y"),
                "time": update.message.date.strftime("%I:%M %p"),
                "coupon_codes": []
            }
            
            # Clear user state
            del user_state[user_id]
            
            await update.message.reply_text(
                f"❌ **Order Cancelled Successfully!**\n\n"
                f"🆔 **Cancellation ID:** `{order_id}`\n"
                f"📦 **Service:** {service_name}\n\n"
                f"✅ **No payment was processed.**\n"
                f"✅ **No coupons were generated.**",
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
    
    # ADMIN MENU HANDLING
    if is_admin(user_id):
        if text == "📦 Add Coupons":
            await update.message.reply_text(
                "📦 **Select service to add coupons:**",
                reply_markup=get_add_coupon_keyboard()
            )
            return
            text == "💰 Change Price" and is_admin(user_id):
        # Service selection keyboard बनाओ
        price_keyboard = []
        for key, service in SERVICES.items():
            price_keyboard.append([
                InlineKeyboardButton(
                    f"{service['name']} - Current: ₹{service['price']}",
                    callback_data=f"price_{key}"
                )
            ])
        
        await update.message.reply_text(
            "💰 **Select service to change price:**\n\n"
            "Current prices are shown below. Tap to change:",
            reply_markup=InlineKeyboardMarkup(price_keyboard),
            parse_mode="Markdown"
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
                redeem_text += "\n\n**How to redeem:**\n"
                redeem_text += "1. **Quantity based:** Enter number (e.g., '5' for 5 coupons)\n"
                redeem_text += "2. **Select service:** Use buttons below\n\n"
                redeem_text += "👉 **Enter quantity or select service:**"
                
                await update.message.reply_text(
                    redeem_text,
                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Cancel")]], resize_keyboard=True),
                    parse_mode="Markdown"
                )
                user_state[user_id] = {"action": "redeem_all_view"}
            return
        elif text == "📋 Pending Orders":
            if not pending_orders:
                await update.message.reply_text(
                    "📭 **No pending orders!**",
                    reply_markup=ADMIN_MENU
                )
                return
            
            pending_text = "⏳ **Pending Orders:**\n\n"
            for order_id in pending_orders[:10]:
                order = orders.get(order_id)
                if order:
                    pending_text += (
                        f"🆔 **Order ID:** `{order_id}`\n"
                        f"👤 **User:** {order['first_name']}\n"
                        f"📦 **Service:** {SERVICES[order['service']]['name']}\n"
                        f"💰 **Amount:** ₹{order['amount']}\n"
                        f"─────────────────\n"
                    )
            
            await update.message.reply_text(
                pending_text,
                reply_markup=ADMIN_MENU,
                parse_mode="Markdown"
            )
            return
        elif text == "📢 Broadcast":
            await update.message.reply_text(
                "📢 **Broadcast Message**\n\n"
                "Send the message you want to broadcast:\n\n"
                "Example: `New coupons added! Check out the store.`",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Cancel")]], resize_keyboard=True),
                parse_mode="Markdown"
            )
            user_state[user_id] = {"action": "broadcast"}
            return
        elif text == "🔙 User Menu":
enu":
            if user_id in user_state:
                del user_state[user_id]
            await update.message.reply_text(
                "Switched to user menu.",
                reply_markup=USER_MENU
            )
            return
        elif text == "🔙 Cancel":
            if user_id in user_state:
                del user_state[user_id]
            await update.message.reply_text(
                "Operation cancelled.",
                reply_markup=ADMIN_MENU
            )
            return
    
    # USER MENU HANDLING
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
                status_emoji = "✅" if order['status'] == 'approved' else "❌" if order['status'] == 'cancelled' else "⏳" if order['status'] == 'pending' else "🔄"
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
                
                history_text += f"📊 **Status:** {order['status'].capitalize()}\n"
                history_text += f"📅 **Date:** {order.get('date', 'N/A')}\n"
                history_text += f"─────────────────\n"
        
        await update.message.reply_text(
            history_text,
            reply_markup=get_menu(user_id),
            parse_mode="Markdown"
        )
        r    
    elif text == "📢 Join Channel":
        await update.message.reply_text(
            f"📢 **Join Our Channel**\n\n"
            f"Latest updates, new coupons, and exclusive offers!\n\n"
            f"👉 [Click here to join Channel]({CHANNEL_LINK})\n\n"
            f"_Don't miss any update!_",
            reply_markup=get_menu(user_id),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return
    
    elif text == "📞 Support":
        await update.message.reply_text(
            f"📞 **Support Center**\n\n"
            f"**For help with:**\n"
            f"• Order issues\n"
            f"• Payment problems\n"
            f"• Coupon delivery\n"
            f"• Refund requests\n\n"
            f"**Contact:** {SUPPORT_USERNAME}\n\n"
            f"🕐 **Available:** 10:00 AM - 10:00 PM",
            reply_markup=get_menu(user_id),
            parse_mode="Markdown"
        )
        return
    
    # Handle admin broadcast
    if is_admin(user_id) and user_id in user_state and user_state[user_id].get('action') == 'broadcast':
        broadcast_message = text
        
        sent = 0
        failed = 0
        
        for uid in list(all_users):
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=broadcast_message,
                    parse_mode="Markdown"
                )
                sent += 1
            except Exception as e:
                print(f"Broadcast error to user {uid}: {e}")
                failed += 1
        
        del user_state[user_id]
        
        await update.message.reply_text(
            f"📢 **Broadcast Complete!**\n\n"
            f"✅ Sent: {sent} users\n"
            f"❌ Failed: {failed}\n"
            f"📊 Total Users: {len(all_users)}",
            reply_markup=ADMIN_MENU,
            parse_mode="Markdown"
        )
        save_data()
        return
    
    # Handle admin add coupons
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
    
    # Handle redeem quantity input
    if is_admin(user_id) and user_id in user_state and user_state[user_id].get('action') == 'redeem_all_view':
        if text.isdigit():
            quantity = int(text)
            if quantity <= 0:
                await update.message.reply_text(
                    "❌ Quantity must be greater than 0",
                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Cancel")]], resize_keyboard=True)
                )
                return
            
            # Show services with enough stock
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
    
    # Handle quantity redeem user input
    if is_admin(user_id) and user_id in user_state and user_state[user_id].get('action') == 'quantity_redeem':
        try:
            target_user_id = int(text.strip())
            service_key = user_state[user_id].get('service_key')
            quantity = user_state[user_id].get('quantity')
            
            # Check stock
            if len(SERVICES[service_key]['stock']) < quantity:
                await update.message.reply_text(
                    f"❌ Not enough coupons available!\n"
                    f"Available: {len(SERVICES[service_key]['stock'])}\n"
                    f"Requested: {quantity}",
                    reply_markup=ADMIN_MENU
                )
                del user_state[user_id]
                return
            
            # Get coupons
            coupon_codes = []
            for i in range(quantity):
                if SERVICES[service_key]['stock']:
                    coupon = SERVICES[service_key]['stock'].pop(0)
                    coupon_codes.append(coupon)
                    redeemed_coupons[coupon] = {
                        'redeemed_by': target_user_id,
                        'service': SERVICES[service_key]['name'],
                        'date': update.message.date.strftime("%d %B %Y"),
                        'time': update.message.date.strftime("%I:%M %p")
                    }
            
            # Send to user
            try:
                coupon_text = "\n".join([f"`{code}`" for code in coupon_codes])
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=(
                        f"🎁 **Coupons Redeemed for You!**\n\n"
                        f"🎟️ **Quantity:** {quantity}\n"
                        f"📦 **Service:** {SERVICES[service_key]['name']}\n\n"
                        f"**Your Coupon Codes:**\n\n"
                        f"{coupon_text}\n\n"
                        f"Thank you! ❤️"
                    ),
                    parse_mode="Markdown"
                )
                user_msg = "✅ Coupons sent successfully!"
            except:
                user_msg = "⚠️ Failed to send (user may have blocked bot)"
            
            del user_state[user_id]
            
            await update.message.reply_text(
                f"✅ **Redemption Complete!**\n\n"
                f"📦 **Service:** {SERVICES[service_key]['name']}\n"
                f"🎟️ **Coupons Redeemed:** {quantity}\n"
                f"👤 **Target User:** {target_user_id}\n"
                f"{user_msg}\n\n"
                f"📊 **Remaining Stock:** {len(SERVICES[service_key]['stock'])}",
                reply_markup=ADMIN_MENU,
                parse_mode="Markdown"
            )
            save_data()
            
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid User ID. Please enter a valid numeric User ID.",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Cancel")]], resize_keyboard=True)
            )
        return
    
    # Handle order flow
    await handle_order_flow(update, user_id, text, context)

async def handle_order_flow(update, user_id, text, context):
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
            if 1 <= qty <= 100:
                service_key = state["service"]
                stock_count = len(SERVICES[service_key]['stock'])
                if stock_count < qty:
                    await update.message.reply_text(
                        f"❌ **Insufficient Stock!**\n\n"
                        f"Available: {stock_count}\n"
                        f"Requested: {qty}\n\n"
                        "Please enter a smaller quantity.",
                        reply_markup=CANCEL_KEYBOARD
                    )
                    return
                
                amount = state["price"] * qty
                state.update({
                    "quantity": qty,
                    "amount": amount,
                    "step": "screenshot"
                })
                
                # Generate QR
                try:
                    qr_data = f"upi://pay?pa={UPI_ID}&pn=SheinCoupon&am={amount}&tn=OrderPayment&cu=INR"
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(qr_data)
                    qr.make(fit=True)
                    
                    img = qr.make_image(fill_color="black", back_color="white")
                    bio = io.BytesIO()
                    img.save(bio, "PNG")
                    bio.seek(0)
                    
                    await update.message.reply_photo(
                        photo=InputFile(bio, filename="payment_qr.png"),
                        caption=(
                            f"🧾 **Order Summary**\n\n"
                            f"**Service:** {state['service_name']}\n"
                            f"**Quantity:** {qty}\n"
                            f"**Total Amount:** ₹{amount}\n\n"
                            f"📸 **Scan QR and send payment screenshot**"
                        ),
                        reply_markup=CANCEL_KEYBOARD,
                        parse_mode="Markdown"
                    )
                    
                except Exception as e:
                    print(f"QR Error: {e}")
                    qr = qrcode.make(f"upi://pay?pa={UPI_ID}&am={amount}")
                    bio = io.BytesIO()
                    qr.save(bio, "PNG")
                    bio.seek(0)
                    
                    await update.message.reply_photo(
                        photo=InputFile(bio, filename="qr.png"),
                        caption=(
                            f"🧾 **Pay ₹{amount}**\n\n"
                            f"**Service:** {state['service_name']}\n"
                            f"**Quantity:** {qty}\n"
                            f"📸 **Scan and send screenshot**"
                        ),
                        reply_markup=CANCEL_KEYBOARD,
                        parse_mode="Markdown"
                    )
            else:
                await update.message.reply_text(
                    "❌ Quantity must be 1-100",
                    reply_markup=CANCEL_KEYBOARD
                )
        else:
            await update.message.reply_text(
                "❌ Please enter a valid number (1-100)",
                reply_markup=CANCEL_KEYBOARD
            )
    
    elif step == "screenshot" and update.message.photo:
        state.update({
            "photo": update.message.photo[-1].file_id,
            "step": "utr"
        })
        
        await update.message.reply_text(
            "✅ **Screenshot received!**\n\n"
            "🔢 **Now send UTR/Transaction ID:**\n\n"
            "_12 digit number from payment receipt_",
            reply_markup=CANCEL_KEYBOARD
        )
    
    elif step == "utr" and text:
        global order_counter
        order_id = f"ORD{order_counter:06d}"
        order_counter += 1
        
        orders[order_id] = {
            "user": user_id,
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name,
            "service": state["service"],
            "service_name": state["service_name"],
            "quantity": state["quantity"],
            "amount": state["amount"],
            "utr": text,
            "photo": state.get("photo"),
            "status": "pending",
            "date": update.message.date.strftime("%d %B %Y"),
            "time": update.message.date.strftime("%I:%M %p"),
            "coupon_codes": []
        }
        
        pending_orders.append(order_id)
        
        # Notify admins
        for admin_id in ADMIN_IDS:
            try:
                caption = (
                    f"🆔 **Order:** `{order_id}`\n"
                    f"👤 **User:** {update.effective_user.first_name}\n"
                    f"📧 **Username:** @{update.effective_user.username or 'N/A'}\n"
                    f"📦 **Service:** {state['service_name']}\n"
                    f"🔢 **Quantity:** {state['quantity']}\n"
                    f"💰 **Amount:** ₹{state['amount']}\n"
                    f"🔢 **UTR:** `{text}`\n"
                    f"📊 **Status:** ⏳ Pending"
                )
                
                if state.get("photo"):
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=state["photo"],
                        caption=caption,
                        reply_markup=get_admin_approval_keyboard(order_id),
                        parse_mode="Markdown"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=caption,
                        reply_markup=get_admin_approval_keyboard(order_id),
                        parse_mode="Markdown"
                    )
            except Exception as e:
                print(f"Admin notify error: {e}")
        
        if user_id in user_state:
            del user_state[user_id]
        
        await update.message.reply_text(
            f"✅ **Order Created Successfully!**\n\n"
            f"🆔 **Order ID:** `{order_id}`\n"
            f"📦 **Service:** {state['service_name']}\n"
            f"💰 **Amount:** ₹{state['amount']}\n\n"
            "🔍 **Payment under verification**\n"
            "⏱️ **Please wait 5-10 minutes**",
            reply_markup=get_menu(user_id),
            parse_mode="Markdown"
        )
        save_data()

# ================= CALLBACK QUERY HANDLER =================
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Service selection
    if data.startswith("select_"):
        key = data.split("_")[1]
        
        if not SERVICES[key]["stock"]:
            await query.edit_message_text(
                f"❌ **{SERVICES[key]['name']} Out of Stock!**\n\nPlease check back later.",
                parse_mode="Markdown"
            )
            return
        
        user_state[user_id] = {
            "service": key,
            "service_name": SERVICES[key]['name'],
            "price": SERVICES[key]['price'],
            "step": "quantity"
        }
        
        await query.edit_message_text(
            f"✅ **Selected:** {SERVICES[key]['name']}\n"
            f"💰 **Price:** ₹{SERVICES[key]['price']} per coupon\n\n"
            "👉 **Enter quantity (1-100):**",
            parse_mode="Markdown"
        )
    
    elif data == "cancel_selection":
        if user_id in user_state:
            del user_state[user_id]
        
        await query.edit_message_text(
            "❌ Service selection cancelled.",
            reply_markup=get_menu(user_id)
        )
    
    elif data.startswith("qty_redeem_"):
        if not is_admin(user_id):
            await query.answer("❌ Admin only!", show_alert=True)
            return
        
        parts = data.split("_")
        service_key = parts[2]
        quantity = int(parts[3])
        
        user_state[user_id] = {
            'action': 'quantity_redeem',
            'service_key': service_key,
            'quantity': quantity
        }
        
        await query.edit_message_text(
            f"🔄 **Redeem {quantity} coupons from {SERVICES[service_key]['name']}**\n\n"
            f"Enter User ID to send {quantity} coupons:",
            parse_mode="Markdown"
        )
    
    elif data == "cancel_redeem":
        if user_id in user_state:
            del user_state[user_id]
        
        await query.edit_message_text(
            "❌ Redeem cancelled.",
            reply_markup=ADMIN_MENU
        )
    
    elif data.startswith("approve_"):
        if not is_admin(user_id):
            await query.answer("❌ Admin only!", show_alert=True)
            return
        
        order_id = data.split("_")[1]
        await approve_order(query, context, order_id)
    
    elif data.startswith("reject_"):
        if not is_admin(user_id):
            await query.answer("❌ Admin only!", show_alert=True)
            return
        
        order_id = data.split("_")[1]
        await reject_order(query, context, order_id)
    
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
            "Send coupon codes (one per line):\n\n"
            "_Example:_\n"
            "COUPON123\n"
            "COUPON456\n"
            "COUPON789",
            parse_mode="Markdown"
        )
    
    elif data == "cancel_add":
        if user_id in user_state:
            del user_state[user_id]
        await query.edit_message_text(
            "❌ Coupon addition cancelled.",
            reply_markup=ADMIN_MENU
        )

# ================= ORDER APPROVAL/REJECTION =================
async def approve_order(query, context, order_id):
    if order_id not in orders:
        await query.answer("Order not found!", show_alert=True)
        return
    
    order = orders[order_id]
    
    if order['status'] == 'approved':
        await query.answer("Order already approved!", show_alert=True)
        return
    if order['status'] == 'rejected':
        await query.answer("Order already rejected!", show_alert=True)
        return
    if order['status'] == 'cancelled':
        await query.answer("Order was cancelled!", show_alert=True)
        return
    
    service_key = order['service']
    quantity = order['quantity']
    
    if len(SERVICES[service_key]['stock']) < quantity:
        updated_text = (
            f"🆔 **Order:** `{order_id}`\n"
            f"👤 **User:** {order['first_name']}\n"
            f"📦 **Service:** {SERVICES[service_key]['name']}\n"
            f"💰 **Amount:** ₹{order['amount']}\n\n"
            f"❌ **INSUFFICIENT STOCK!**\n"
            f"Required: {quantity}\n"
            f"Available: {len(SERVICES[service_key]['stock'])}"
        )
        
        if query.message.photo:
            await query.edit_message_caption(caption=updated_text, parse_mode="Markdown")
        else:
            await query.edit_message_text(text=updated_text, parse_mode="Markdown")
        
        if query.message.reply_markup:
            await query.edit_message_reply_markup(reply_markup=None)
        return
    
    try:
        coupon_codes = []
        for i in range(quantity):
            if SERVICES[service_key]['stock']:
                coupon_code = SERVICES[service_key]['stock'].pop(0)
                coupon_codes.append(coupon_code)
        
        orders[order_id]['coupon_codes'] = coupon_codes
        
        try:
            coupon_text = "\n".join([f"`{code}`" for code in coupon_codes])
            await context.bot.send_message(
                chat_id=order['user'],
                text=(
                    f"✅ **Payment Approved!**\n\n"
                    f"🆔 **Order ID:** `{order_id}`\n"
                    f"📦 **Service:** {order['service_name']}\n"
                    f"🔢 **Quantity:** {quantity}\n"
                    f"💰 **Amount:** ₹{order['amount']}\n\n"
                    f"🎟️ **Your Coupon Codes:**\n\n"
                    f"{coupon_text}\n\n"
                    f"Thank you! ❤️"
                ),
                parse_mode="Markdown"
            )
            user_msg = "✅ User notified successfully"
        except Exception as user_error:
            print(f"User notification error: {user_error}")
            user_msg = "⚠️ User notification failed"
        
        orders[order_id]['status'] = 'approved'
        if order_id in pending_orders:
            pending_orders.remove(order_id)
        
        updated_text = (
            f"🆔 **Order:** `{order_id}`\n"
            f"👤 **User:** {order['first_name']}\n"
            f"📧 **Username:** @{order.get('username', 'N/A')}\n"
            f"📦 **Service:** {SERVICES[service_key]['name']}\n"
            f"🔢 **Quantity:** {quantity}\n"
            f"💰 **Amount:** ₹{order['amount']}\n"
            f"🔢 **UTR:** `{order['utr']}`\n\n"
            f"✅ **STATUS: APPROVED**\n"
            f"📊 **Action:** {user_msg}\n"
            f"🎟️ **Coupons Sent:** {quantity}\n"
            f"📝 **Coupon Codes:** {', '.join(coupon_codes[:3])}"
            f"{'...' if len(coupon_codes) > 3 else ''}"
        )
        
        if query.message.photo:
            await query.edit_message_caption(caption=updated_text, parse_mode="Markdown")
        else:
            await query.edit_message_text(text=updated_text, parse_mode="Markdown")
        
        if query.message.reply_markup:
            await query.edit_message_reply_markup(reply_markup=None)
        
        save_data()
        
    except Exception as e:
        if "message is not modified" in str(e).lower():
            if query.message.reply_markup:
                await query.edit_message_reply_markup(reply_markup=None)
            return
        
        error_text = f"❌ **Error:** {str(e)[:100]}"
        if query.message.photo:
            await query.edit_message_caption(caption=error_text, parse_mode="Markdown")
        else:
            await query.edit_message_text(text=error_text, parse_mode="Markdown")
        
        if query.message.reply_markup:
            await query.edit_message_reply_markup(reply_markup=None)

async def reject_order(query, context, order_id):
    if order_id not in orders:
        await query.answer("Order not found!", show_alert=True)
        return
    
    order = orders[order_id]
    
    if order['status'] == 'approved':
        await query.answer("Order already approved!", show_alert=True)
        return
    if order['status'] == 'rejected':
        await query.answer("Order already rejected!", show_alert=True)
        return
    if order['status'] == 'cancelled':
        await query.answer("Order was cancelled!", show_alert=True)
        return
    
    try:
        try:
            await context.bot.send_message(
                chat_id=order['user'],
                text=(
                    f"❌ **Payment Rejected**\n\n"
                    f"🆔 **Order ID:** `{order_id}`\n"
                    f"💰 **Amount:** ₹{order['amount']}\n\n"
                    f"📞 **Support:** {SUPPORT_USERNAME}\n\n"
                    f"⚠️ **अगर आपने payment कर दिया है,**\n"
                    f"तो कृपया ऊपर दिए गए support से contact करें।"
                ),
                parse_mode="Markdown"
            )
            user_msg = "✅ User notified successfully"
        except Exception as user_error:
            print(f"User notification error: {user_error}")
            user_msg = "⚠️ User notification failed"
        
        orders[order_id]['status'] = 'rejected'
        if order_id in pending_orders:
            pending_orders.remove(order_id)
        
        updated_text = (
            f"🆔 **Order:** `{order_id}`\n"
            f"👤 **User:** {order['first_name']}\n"
            f"📧 **Username:** @{order.get('username', 'N/A')}\n"
            f"📦 **Service:** {SERVICES[order['service']]['name']}\n"
            f"🔢 **Quantity:** {order['quantity']}\n"
            f"💰 **Amount:** ₹{order['amount']}\n"
            f"🔢 **UTR:** `{order['utr']}`\n\n"
            f"❌ **STATUS: REJECTED**\n"
            f"📊 **Action:** {user_msg}"
        )
        
        if query.message.photo:
            await query.edit_message_caption(caption=updated_text, parse_mode="Markdown")
        else:
            await query.edit_message_text(text=updated_text, parse_mode="Markdown")
        
        if query.message.reply_markup:
            await query.edit_message_reply_markup(reply_markup=None)
        
        save_data()
        
    except Exception as e:
        if "message is not modified" in str(e).lower():
            if query.message.reply_markup:
                await query.edit_message_reply_markup(reply_markup=None)
            return
        
        error_text = f"❌ **Error:** {str(e)[:100]}"
        if query.message.photo:
            await query.edit_message_caption(caption=error_text, parse_mode="Markdown")
        else:
            await query.edit_message_text(text=error_text, parse_mode="Markdown")
        
        if query.message.reply_markup:
            await query.edit_message_reply_markup(reply_markup=None)

# ================= COMMANDS =================
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    if context.args:
        broadcast_message = " ".join(context.args)
        
        sent = 0
        failed = 0
        
        for uid in list(all_users):
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=broadcast_message,
                    parse_mode="Markdown"
                )
                sent += 1
            except Exception as e:
                print(f"Broadcast error to user {uid}: {e}")
                failed += 1
        
        await update.message.reply_text(
            f"📢 **Broadcast Complete!**\n\n"
            f"✅ Sent: {sent} users\n"
            f"❌ Failed: {failed}\n"
            f"📊 Total Users: {len(all_users)}",
            reply_markup=ADMIN_MENU
        )
        save_data()
    else:
        await update.message.reply_text(
            "📢 **Broadcast Message**\n\n"
            "Usage:\n"
            "1. `/broadcast Your message here`\n"
            "2. Or use the Broadcast button from admin menu",
            parse_mode="Markdown",
            reply_markup=ADMIN_MENU
        )

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    redeem_kb = get_redeem_keyboard()
    if redeem_kb:
        await update.message.reply_text(
            "🔄 **Select service to redeem coupons:**\n\n"
            "Choose a service to redeem coupons from.",
            reply_markup=redeem_kb
        )
    else:
        await update.message.reply_text(
            "❌ **No coupons available for redemption!**\n\n"
            "All coupon stocks are empty.",
            reply_markup=ADMIN_MENU
        )

# ================= MAIN =================
def main():
    load_data()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("redeem", redeem_command))
    
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    app.add_handler(MessageHandler(filters.PHOTO, handle_messages))
    
    print("=" * 70)
    print("🤖 SHEIN COUPON BOT STARTED")
    print("=" * 70)
    print(f"✅ Token: {BOT_TOKEN[:10]}...")
    print(f"✅ UPI: {UPI_ID}")
    print(f"✅ Support: {SUPPORT_USERNAME}")
    print(f"✅ Admins: {ADMIN_IDS}")
    print("✅ All errors fixed")
    print("=" * 70)
    print("🚀 Bot is running! Press Ctrl+C to stop.")
    
    app.run_polling()

if __name__ == "__main__":
    main()
