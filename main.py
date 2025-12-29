# ================= 24/7 SHEIN COUPON BOT =================
from flask import Flask
from threading import Thread
import os
import time
import asyncio
import sys
import traceback

# ================= TELEGRAM BOT IMPORTS =================
import io
import qrcode
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ================= FLASK SERVER (24/7 के लिए) =================
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Shein Coupon Bot is Running 24/7!"

@app.route('/health')
def health():
    return {"status": "active", "bot": "running"}

# ================= BOT CONFIG =================
BOT_TOKEN = os.environ.get('BOT_TOKEN', "7569076581:AAEz9Yp35UoFtC4dI1iCg2J8Z9N4rzwBQxI")
ADMIN_IDS = [int(id) for id in os.environ.get('ADMIN_IDS', '7679672318').split(',')]
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
bot_instance = None

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
        [KeyboardButton("📋 Pending Orders"), KeyboardButton("📢 Broadcast")],
        [KeyboardButton("🔙 User Menu")]
    ],
    resize_keyboard=True
)

CANCEL_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("🔙 Cancel")]],
    resize_keyboard=True
)

# ================= FUNCTIONS =================
def get_stock_display():
    stock_text = "🎉 **Shein Coupon Store**\n\n"
    stock_text += f"🟢 500 Pe 500 Stock: {len(SERVICES['500']['stock'])}\n"
    stock_text += f"🟢 1000 Pe 1000 Stock: {len(SERVICES['1000']['stock'])}\n"
    stock_text += f"🟢 2000 Pe 2000 Stock: {len(SERVICES['2000']['stock'])}\n"
    stock_text += f"🟢 4000 Pe 4000 Stock: {len(SERVICES['4000']['stock'])}\n"
    return stock_text

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

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    all_users.add(user_id)
    
    # ADMIN MENU HANDLING
    if is_admin(user_id):
        if text == "📦 Add Coupons":
            await update.message.reply_text(
                "📦 **Select service to add coupons:**",
                reply_markup=get_add_coupon_keyboard()
            )
            return
        elif text == "📊 View Stock":
            await update.message.reply_text(
                get_stock_display(),
                reply_markup=ADMIN_MENU,
                parse_mode="Markdown"
            )
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
                "📢 **How to broadcast:**\n\n"
                "1. Send your message\n"
                "2. Reply to it with /broadcast",
                reply_markup=ADMIN_MENU
            )
            return
        elif text == "🔙 User Menu":
            await update.message.reply_text(
                "Switched to user menu.",
                reply_markup=USER_MENU
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
    
    elif text == "📜 History":
        user_orders = []
        for order_id, order in orders.items():
            if order['user'] == user_id:
                user_orders.append((order_id, order))
        
        if not user_orders:
            history_text = "📭 **No orders found!**\n\nYou haven't placed any order yet."
        else:
            history_text = "📜 **Your Order History:**\n\n"
            for order_id, order in user_orders[:10]:
                status_emoji = "✅" if order['status'] == 'approved' else "⏳" if order['status'] == 'pending' else "❌"
                history_text += (
                    f"{status_emoji} **Order ID:** `{order_id}`\n"
                    f"📦 **Service:** {SERVICES[order['service']]['name']}\n"
                    f"💰 **Amount:** ₹{order['amount']}\n"
                    f"📊 **Status:** {order['status'].capitalize()}\n"
                    f"─────────────────\n"
                )
        
        await update.message.reply_text(
            history_text,
            reply_markup=get_menu(user_id),
            parse_mode="Markdown"
        )
    
    elif text == "📢 Join Channel":
        await update.message.reply_text(
            f"📢 **Join Our Channel**\n\n"
            f"Latest updates, new coupons, and exclusive offers!\n\n"
            f"👉 [Click here to join Channel]({CHANNEL_LINK})\n\n"
            f"_Don't miss any update!_",
            reply_markup=get_menu(user_id),
            parse_mode="Markdown",
            disable_web_page_preview=False
        )
    
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
    
    elif text == "🔙 Cancel":
        if user_id in user_state:
            del user_state[user_id]
        await update.message.reply_text(
            "❌ Order cancelled.",
            reply_markup=get_menu(user_id)
        )
    
    else:
        # Handle admin add coupon text input
        if is_admin(user_id) and user_id in user_state:
            state = user_state[user_id]
            if state.get('action') == 'adding_coupons':
                service_key = state.get('service_key')
                if service_key:
                    coupons = text.split('\n')
                    added = 0
                    for coupon in coupons:
                        coupon = coupon.strip()
                        if coupon:
                            SERVICES[service_key]['stock'].append(coupon)
                            added += 1
                    
                    del user_state[user_id]
                    await update.message.reply_text(
                        f"✅ **{added} coupons added to {SERVICES[service_key]['name']}!**\n"
                        f"📊 **Total Stock:** {len(SERVICES[service_key]['stock'])}",
                        reply_markup=ADMIN_MENU,
                        parse_mode="Markdown"
                    )
                    return
        
        # Handle order flow
        await handle_order_flow(update, user_id, text, context)

async def handle_order_flow(update, user_id, text, context):
    if user_id not in user_state:
        await update.message.reply_text(
            "👇 **Please use the buttons below**\n\n"
            "Or type /start to refresh",
            reply_markup=get_menu(user_id)
        )
        return
    
    state = user_state[user_id]
    step = state.get("step", "")
    
    if step == "quantity":
        if text.isdigit():
            qty = int(text)
            if 1 <= qty <= 100:
                # Check if enough stock
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
                
                # ✅ QR Code
                try:
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    
                    qr_data = f"upi://pay?pa={UPI_ID}&pn=SheinCoupon&am={amount}&tn=OrderPayment&cu=INR"
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
                    try:
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
                    except:
                        qr = qrcode.make(f"slokjaat75@fam|{amount}")
                        bio = io.BytesIO()
                        qr.save(bio, "PNG")
                        bio.seek(0)
                        
                        await update.message.reply_photo(
                            photo=InputFile(bio, filename="qr.png"),
                            caption=(
                                f"🧾 **Pay ₹{amount}**\n\n"
                                f"📸 **Scan QR and send payment screenshot**"
                            ),
                            reply_markup=CANCEL_KEYBOARD
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
            "quantity": state["quantity"],
            "amount": state["amount"],
            "utr": text,
            "photo": state.get("photo"),
            "status": "pending",
            "date": update.message.date.strftime("%d %B %Y"),
            "time": update.message.date.strftime("%I:%M %p")
        }
        
        pending_orders.append(order_id)
        
        for admin_id in ADMIN_IDS:
            try:
                caption = (
                    f"🆔 **New Order:** `{order_id}`\n"
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

# ================= CALLBACK QUERY HANDLER =================
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
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
            "👉 **Enter quantity (1-100):**\n\n"
            "_Example: Type '2' for 2 coupons_",
            parse_mode="Markdown"
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
    service_key = order['service']
    quantity = order['quantity']
    
    available_stock = len(SERVICES[service_key]['stock'])
    if available_stock < quantity:
        await query.edit_message_text(
            f"❌ **Insufficient Stock!**\n\n"
            f"Required: {quantity}\n"
            f"Available: {available_stock}",
            parse_mode="Markdown",
            reply_markup=None
        )
        return
    
    try:
        coupon_codes = []
        for i in range(quantity):
            if SERVICES[service_key]['stock']:
                coupon_code = SERVICES[service_key]['stock'].pop(0)
                coupon_codes.append(coupon_code)
        
        try:
            coupon_text = "\n".join([f"`{code}`" for code in coupon_codes])
            await context.bot.send_message(
                chat_id=order['user'],
                text=(
                    f"✅ **Payment Approved!**\n\n"
                    f"🆔 **Order ID:** `{order_id}`\n"
                    f"📦 **Service:** {SERVICES[service_key]['name']}\n"
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
            user_msg = "⚠️ Approved but user notification failed"
        
        orders[order_id]['status'] = 'approved'
        if order_id in pending_orders:
            pending_orders.remove(order_id)
        
        await query.edit_message_text(
            f"✅ **APPROVED PAYMENT**\n\n"
            f"🆔 Order ID: `{order_id}`\n"
            f"👤 User: {order['first_name']}\n"
            f"📦 Service: {SERVICES[service_key]['name']}\n"
            f"🔢 Quantity: {quantity}\n"
            f"💰 Amount: ₹{order['amount']}\n"
            f"🎟️ Coupons Sent: {quantity}\n\n"
            f"{user_msg}",
            parse_mode="Markdown",
            reply_markup=None
        )
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ Error: {str(e)[:100]}",
            parse_mode="Markdown",
            reply_markup=None
        )

async def reject_order(query, context, order_id):
    if order_id not in orders:
        await query.answer("Order not found!", show_alert=True)
        return
    
    order = orders[order_id]
    
    try:
        try:
            await context.bot.send_message(
                chat_id=order['user'],
                text=(
                    f"❌ **Payment Rejected**\n\n"
                    f"🆔 **Order ID:** `{order_id}`\n"
                    f"💰 **Amount:** ₹{order['amount']}\n\n"
                    f"Contact: {SUPPORT_USERNAME}"
                ),
                parse_mode="Markdown"
            )
            user_msg = "✅ User notified successfully"
        except Exception as user_error:
            print(f"User notification error: {user_error}")
            user_msg = "⚠️ Rejected but user notification failed"
        
        orders[order_id]['status'] = 'rejected'
        if order_id in pending_orders:
            pending_orders.remove(order_id)
        
        await query.edit_message_text(
            f"❌ **REJECTED PAYMENT**\n\n"
            f"🆔 Order ID: `{order_id}`\n"
            f"👤 User: {order['first_name']}\n"
            f"📦 Service: {SERVICES[order['service']]['name']}\n"
            f"💰 Amount: ₹{order['amount']}\n\n"
            f"{user_msg}",
            parse_mode="Markdown",
            reply_markup=None
        )
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ Error: {str(e)[:100]}",
            parse_mode="Markdown",
            reply_markup=None
        )

# ================= ADMIN COMMANDS =================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    
    if update.message.reply_to_message:
        message = update.message.reply_to_message
        sent = 0
        failed = 0
        
        for user_id in all_users:
            try:
                if message.photo:
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=message.photo[-1].file_id,
                        caption=message.caption or ""
                    )
                elif message.text:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message.text,
                        parse_mode="Markdown" if message.parse_mode else None
                    )
                sent += 1
            except:
                failed += 1
        
        await update.message.reply_text(
            f"📢 **Broadcast Complete!**\n\n"
            f"✅ Sent: {sent} users\n"
            f"❌ Failed: {failed}\n"
            f"📊 Total: {len(all_users)}",
            reply_markup=ADMIN_MENU
        )
    else:
        await update.message.reply_text(
            "📢 **How to broadcast:**\n\n"
            "1. Send your message\n"
            "2. Reply to it with /broadcast",
            reply_markup=ADMIN_MENU
        )

# ================= AUTO-RESTART BOT =================
async def run_bot():
    max_retries = 100
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            print(f"🤖 Starting bot (Attempt {attempt + 1}/{max_retries})...")
            
            app_bot = Application.builder().token(BOT_TOKEN).build()
            
            app_bot.add_handler(CommandHandler("start", start))
            app_bot.add_handler(CommandHandler("broadcast", broadcast))
            app_bot.add_handler(CallbackQueryHandler(handle_callback_query))
            app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
            app_bot.add_handler(MessageHandler(filters.PHOTO, handle_messages))
            
            print("✅ Bot started successfully!")
            print(f"📞 Support: {SUPPORT_USERNAME}")
            print(f"👑 Admins: {ADMIN_IDS}")
            print("=" * 50)
            
            await app_bot.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            print(f"❌ Bot crashed: {str(e)}")
            print(traceback.format_exc())
            
            if attempt < max_retries - 1:
                print(f"🔄 Restarting in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 60)
            else:
                print("❌ Max retries reached. Bot stopped.")
                break

def start_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    
# ================== RENDER ENTRY POINT ==================

print("🚀 Starting Flask + Telegram bot (Render mode)")

flask_thread = Thread(target=start_flask, daemon=True)
flask_thread.start()

asyncio.get_event_loop().create_task(run_bot())
