import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from database import Database

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "123456789").split(",")))
DATABASE_URL = os.getenv("DATABASE_URL")

db = Database(DATABASE_URL)

# States
(
    MAIN_MENU, CATALOG, CART, ENTER_PAYMENT,
    ADMIN_MENU, ADMIN_ADD_NAME, ADMIN_ADD_PRICE, ADMIN_ADD_PHOTO, ADMIN_ADD_CONFIRM,
    CLIENT_PHONE
) = range(10)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def main_menu_keyboard(is_admin_user: bool = False):
    buttons = [
        [KeyboardButton("🛍 Katalog"), KeyboardButton("🛒 Savatcha")],
        [KeyboardButton("💰 Mening qarzim"), KeyboardButton("📋 Buyurtmalarim")],
    ]
    if is_admin_user:
        buttons.append([KeyboardButton("⚙️ Admin panel")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def admin_menu_keyboard():
    buttons = [
        [KeyboardButton("➕ Mahsulot qo'shish"), KeyboardButton("📦 Mahsulotlar")],
        [KeyboardButton("👥 Mijozlar"), KeyboardButton("💳 Qarzlar")],
        [KeyboardButton("✅ To'lovlarni tasdiqlash"), KeyboardButton("🔙 Asosiy menyu")],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing = await db.get_user(user.id)

    if not existing:
        await db.create_user(user.id, user.full_name, user.username)
        await update.message.reply_text(
            f"Assalomu alaykum, {user.first_name}! 👋\n\nDo'konimizga xush kelibsiz!\nIltimos, telefon raqamingizni yuboring.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)]],
                resize_keyboard=True
            )
        )
        return CLIENT_PHONE
    else:
        await update.message.reply_text(
            f"Xush kelibsiz, {user.first_name}! 🛍",
            reply_markup=main_menu_keyboard(is_admin(user.id))
        )
        return MAIN_MENU


async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if contact:
        await db.update_user_phone(update.effective_user.id, contact.phone_number)
    await update.message.reply_text(
        "Rahmat! Ro'yxatdan o'tdingiz ✅",
        reply_markup=main_menu_keyboard(is_admin(update.effective_user.id))
    )
    return MAIN_MENU


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🛍 Katalog":
        return await show_catalog(update, context)
    elif text == "🛒 Savatcha":
        return await show_cart(update, context)
    elif text == "💰 Mening qarzim":
        return await show_my_debt(update, context)
    elif text == "📋 Buyurtmalarim":
        return await show_my_orders(update, context)
    elif text == "⚙️ Admin panel" and is_admin(user_id):
        await update.message.reply_text("Admin panel:", reply_markup=admin_menu_keyboard())
        return ADMIN_MENU
    return MAIN_MENU


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = await db.get_all_products()
    if not products:
        await update.message.reply_text("Hozircha mahsulotlar mavjud emas.")
        return MAIN_MENU

    await update.message.reply_text("📦 Mahsulotlar katalogi:")
    for product in products:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Savatga qo'shish", callback_data=f"add_cart_{product['id']}")]
        ])
        caption = f"*{product['name']}*\n💵 Narx: {product['price']:,} so'm"
        if product['photo_id']:
            await update.message.reply_photo(
                photo=product['photo_id'],
                caption=caption,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(caption, parse_mode='Markdown', reply_markup=keyboard)
    return CATALOG


async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cart_items = await db.get_cart(user_id)

    if not cart_items:
        await update.message.reply_text("🛒 Savatchingiz bo'sh.")
        return MAIN_MENU

    total = sum(item['price'] * item['quantity'] for item in cart_items)
    text = "🛒 *Savatchangiz:*\n\n"
    for item in cart_items:
        text += f"• {item['name']} x{item['quantity']} = {item['price'] * item['quantity']:,} so'm\n"
    text += f"\n💰 *Jami: {total:,} so'm*"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Buyurtma berish", callback_data="checkout")],
        [InlineKeyboardButton("🗑 Savatchani tozalash", callback_data="clear_cart")]
    ])
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=keyboard)
    return CART


async def show_my_debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    payments = await db.get_user_payments(user_id)

    debt = user['total_debt'] if user else 0
    text = "💰 *Sizning qarzingiz:*\n\n"
    text += f"Jami qarz: *{debt:,} so'm*\n\n"

    if payments:
        text += "📋 So'nggi to'lovlar:\n"
        for p in payments[:5]:
            if p['confirmed']:
                status = "✅"
            elif p['rejected']:
                status = "❌"
            else:
                status = "⏳"
            text += f"{status} {p['amount']:,} so'm — {p['created_at'].strftime('%d.%m.%Y')}\n"

    if debt > 0:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 To'lov qilish", callback_data="make_payment")]
        ])
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=keyboard)
    else:
        text += "\n✅ Qarzingiz yo'q!"
        await update.message.reply_text(text, parse_mode='Markdown')
    return MAIN_MENU


async def show_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    orders = await db.get_user_orders(user_id)

    if not orders:
        await update.message.reply_text("📋 Buyurtmalaringiz yo'q.")
        return MAIN_MENU

    text = "📋 *Buyurtmalaringiz:*\n\n"
    for order in orders[:10]:
        text += f"✅ #{order['id']} — {order['total_amount']:,} so'm\n"
        if order['debt_amount'] > 0:
            text += f"   💰 Qarz qoldi: {order['debt_amount']:,} so'm\n"
        text += f"   📅 {order['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"

    await update.message.reply_text(text, parse_mode='Markdown')
    return MAIN_MENU


# --- CALLBACK HANDLERS ---

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("add_cart_"):
        product_id = int(data.split("_")[2])
        product = await db.get_product(product_id)
        await db.add_to_cart(user_id, product_id)
        await query.answer(f"✅ {product['name']} savatga qo'shildi!", show_alert=True)

    elif data == "clear_cart":
        await db.clear_cart(user_id)
        await query.edit_message_text("🗑 Savatcha tozalandi.")

    elif data.startswith("confirm_payment_"):
        payment_id = int(data.split("_")[2])
        payment = await db.get_payment(payment_id)
        if payment and payment['confirmed']:
            await query.edit_message_text("ℹ️ Bu to'lov allaqachon tasdiqlangan.")
            return
        await db.confirm_payment(payment_id)
        await query.edit_message_text(f"✅ To'lov tasdiqlandi! ({payment['amount']:,} so'm)")
        if payment:
            try:
                await context.bot.send_message(
                    payment['user_id'],
                    f"✅ Sizning *{payment['amount']:,} so'm*lik to'lovingiz tasdiqlandi!",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"User ga xabar yuborishda xato: {e}")

    elif data.startswith("reject_payment_"):
        payment_id = int(data.split("_")[2])
        payment = await db.get_payment(payment_id)
        await db.reject_payment(payment_id)
        await query.edit_message_text("❌ To'lov rad etildi.")
        if payment:
            try:
                await context.bot.send_message(
                    payment['user_id'],
                    f"❌ Sizning *{payment['amount']:,} so'm*lik to'lov so'rovingiz rad etildi.\nAdmin bilan bog'laning.",
                    parse_mode='Markdown'
                )
            except:
                pass

    elif data.startswith("delete_product_"):
        product_id = int(data.split("_")[2])
        await db.delete_product(product_id)
        try:
            if query.message.photo:
                await query.edit_message_caption("🗑 Mahsulot o'chirildi.")
            else:
                await query.edit_message_text("🗑 Mahsulot o'chirildi.")
        except:
            pass


async def handle_payment_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.user_data.get('in_payment'):
        return await handle_main_menu(update, context)

    try:
        amount = int(update.message.text.replace(" ", "").replace(",", ""))
    except ValueError:
        await update.message.reply_text("❗ Iltimos, to'g'ri raqam kiriting (faqat sonlar).")
        return ENTER_PAYMENT

    if amount <= 0:
        await update.message.reply_text("❗ Miqdor 0 dan katta bo'lishi kerak.")
        return ENTER_PAYMENT

    checkout_total = context.user_data.get('checkout_total')

    if checkout_total is not None:
        cart_items = await db.get_cart(user_id)
        if not cart_items:
            await update.message.reply_text("❗ Savatcha bo'sh.", reply_markup=main_menu_keyboard(is_admin(user_id)))
            context.user_data.clear()
            return MAIN_MENU

        paid = min(amount, checkout_total)
        debt_amount = max(0, checkout_total - paid)
        order_id = await db.create_order(user_id, cart_items, checkout_total, paid, debt_amount)
        await db.clear_cart(user_id)
        context.user_data.clear()

        text = f"✅ *Buyurtma #{order_id} qabul qilindi!*\n\n"
        text += f"💵 Jami: {checkout_total:,} so'm\n"
        text += f"💳 To'landi: {paid:,} so'm\n"
        text += f"💰 Qarz: {debt_amount:,} so'm" if debt_amount > 0 else "✅ To'liq to'landi!"

        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_menu_keyboard(is_admin(user_id)))

        for admin_id in ADMIN_IDS:
            try:
                user_info = await db.get_user(user_id)
                await context.bot.send_message(
                    admin_id,
                    "🛍 *Yangi buyurtma #{}*\n👤 {}\n📱 {}\n💵 Jami: {:,} so'm\n💳 To'landi: {:,} so'm\n💰 Qarz: {:,} so'm".format(
                        order_id, user_info['full_name'],
                        user_info.get('phone') or "noma'lum",
                        checkout_total, paid, debt_amount),
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Admin {admin_id}ga xabar: {e}")
    else:
        user = await db.get_user(user_id)
        if user and amount > user['total_debt']:
            await update.message.reply_text(
                f"❗ Qarzingiz {user['total_debt']:,} so'm. Undan ko'p kirita olmaysiz."
            )
            return ENTER_PAYMENT

        payment_id = await db.create_payment(user_id, amount)
        context.user_data.clear()

        await update.message.reply_text(
            f"✅ To'lov so'rovi yuborildi!\n💳 Miqdor: *{amount:,} so'm*\nAdmin tasdiqlashini kuting ⏳",
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard(is_admin(user_id))
        )

        for admin_id in ADMIN_IDS:
            try:
                user_info = await db.get_user(user_id)
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_payment_{payment_id}"),
                        InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_payment_{payment_id}")
                    ]
                ])
                await context.bot.send_message(
                    admin_id,
                    "💳 *To'lov so'rovi #{}*\n👤 {}\n📱 {}\n💵 Miqdor: *{:,} so'm*".format(
                        payment_id, user_info['full_name'],
                        user_info.get('phone') or "noma'lum", amount),
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Admin {admin_id}ga xabar: {e}")

    return MAIN_MENU


# --- ADMIN ---

async def handle_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return MAIN_MENU

    if text == "➕ Mahsulot qo'shish":
        await update.message.reply_text("Mahsulot nomini kiriting:")
        return ADMIN_ADD_NAME
    elif text == "📦 Mahsulotlar":
        return await admin_show_products(update, context)
    elif text == "👥 Mijozlar":
        return await admin_show_clients(update, context)
    elif text == "💳 Qarzlar":
        return await admin_show_debts(update, context)
    elif text == "✅ To'lovlarni tasdiqlash":
        return await admin_pending_payments(update, context)
    elif text == "🔙 Asosiy menyu":
        await update.message.reply_text("Asosiy menyu:", reply_markup=main_menu_keyboard(True))
        return MAIN_MENU
    return ADMIN_MENU


async def admin_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_product'] = {'name': update.message.text}
    await update.message.reply_text(f"✅ Nom: *{update.message.text}*\n\nNarxni kiriting (so'mda):", parse_mode='Markdown')
    return ADMIN_ADD_PRICE


async def admin_add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text.replace(" ", "").replace(",", ""))
        context.user_data['new_product']['price'] = price
        await update.message.reply_text(
            f"✅ Narx: *{price:,} so'm*\n\nRasmini yuboring yoki /skip bosing:",
            parse_mode='Markdown'
        )
        return ADMIN_ADD_PHOTO
    except ValueError:
        await update.message.reply_text("❗ To'g'ri narx kiriting (faqat raqam):")
        return ADMIN_ADD_PRICE


async def admin_add_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data['new_product']['photo_id'] = update.message.photo[-1].file_id
    else:
        context.user_data['new_product']['photo_id'] = None
    return await show_product_confirm(update, context)


async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'new_product' not in context.user_data:
        return ADMIN_MENU
    context.user_data['new_product']['photo_id'] = None
    return await show_product_confirm(update, context)


async def show_product_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product = context.user_data['new_product']
    text = f"📦 *Mahsulot ma'lumotlari:*\n\nNom: *{product['name']}*\nNarx: *{product['price']:,} so'm*"
    if not product.get('photo_id'):
        text += "\nRasm: yo'q"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Saqlash", callback_data="save_product"),
         InlineKeyboardButton("❌ Bekor", callback_data="cancel_product")]
    ])
    if product.get('photo_id'):
        await update.message.reply_photo(product['photo_id'], caption=text, parse_mode='Markdown', reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=keyboard)
    return ADMIN_ADD_CONFIRM


async def admin_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "save_product":
        product = context.user_data.get('new_product', {})
        if not product:
            await query.edit_message_text("❗ Xato. Qaytadan boshlang.")
            return ADMIN_MENU
        await db.add_product(product['name'], product['price'], product.get('photo_id'))
        try:
            if query.message.photo:
                await query.edit_message_caption("✅ Mahsulot saqlandi!")
            else:
                await query.edit_message_text("✅ Mahsulot saqlandi!")
        except:
            pass
        context.user_data.pop('new_product', None)
    elif query.data == "cancel_product":
        try:
            await query.edit_message_text("❌ Bekor qilindi.")
        except:
            pass
        context.user_data.pop('new_product', None)
    return ADMIN_MENU


async def admin_show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = await db.get_all_products()
    if not products:
        await update.message.reply_text("📦 Hozircha mahsulotlar yo'q.")
        return ADMIN_MENU
    await update.message.reply_text(f"📦 Jami {len(products)} ta mahsulot:")
    for product in products:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 O'chirish", callback_data=f"delete_product_{product['id']}")]
        ])
        text = f"*{product['name']}*\n💵 {product['price']:,} so'm"
        if product['photo_id']:
            await update.message.reply_photo(product['photo_id'], caption=text, parse_mode='Markdown', reply_markup=keyboard)
        else:
            await update.message.reply_text(text, parse_mode='Markdown', reply_markup=keyboard)
    return ADMIN_MENU


async def admin_show_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = await db.get_all_users()
    if not users:
        await update.message.reply_text("👥 Mijozlar yo'q.")
        return ADMIN_MENU
    text = f"👥 *Mijozlar ({len(users)} ta):*\n\n"
    for i, user in enumerate(users, 1):
        debt = user.get('total_debt', 0) or 0
        text += f"{i}. {user['full_name']}"
        if user.get('phone'):
            text += f" | {user['phone']}"
        if debt > 0:
            text += f"\n   💰 Qarz: {debt:,} so'm"
        text += "\n"
    await update.message.reply_text(text, parse_mode='Markdown')
    return ADMIN_MENU


async def admin_show_debts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debtors = await db.get_all_debtors()
    if not debtors:
        await update.message.reply_text("✅ Qarzlar yo'q!")
        return ADMIN_MENU
    total_debt = sum(d['total_debt'] for d in debtors)
    text = f"💰 *Qarzlar ({len(debtors)} ta mijoz):*\n"
    text += f"Umumiy: *{total_debt:,} so'm*\n\n"
    for i, d in enumerate(debtors, 1):
        text += f"{i}. {d['full_name']}: *{d['total_debt']:,} so'm*"
        if d.get('phone'):
            text += f" | {d['phone']}"
        text += "\n"
    await update.message.reply_text(text, parse_mode='Markdown')
    return ADMIN_MENU


async def admin_pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payments = await db.get_pending_payments()
    if not payments:
        await update.message.reply_text("✅ Kutilayotgan to'lovlar yo'q!")
        return ADMIN_MENU
    await update.message.reply_text(f"⏳ {len(payments)} ta kutilayotgan to'lov:")
    for payment in payments:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_payment_{payment['id']}"),
                InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_payment_{payment['id']}")
            ]
        ])
        await update.message.reply_text(
            f"💳 *To'lov #{payment['id']}*\n"
            f"👤 {payment['full_name']}\n"
            f"💵 *{payment['amount']:,} so'm*\n"
            f"📅 {payment['created_at'].strftime('%d.%m.%Y %H:%M')}",
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    return ADMIN_MENU



async def checkout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    cart_items = await db.get_cart(user_id)
    if not cart_items:
        await query.answer("Savatcha bo'sh!", show_alert=True)
        return CART
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    context.user_data['checkout_total'] = total
    context.user_data['in_payment'] = True
    await query.edit_message_text(
        "💰 Jami summa: *{:,} so'm*\n\n"
        "Qancha to'laysiz? (so'mda yozing)\n"
        "Qolgan qismi qarz sifatida saqlanadi.\n\n"
        "To'liq to'lash uchun {} yozing".format(total, total),
        parse_mode='Markdown'
    )
    return ENTER_PAYMENT


async def make_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = await db.get_user(user_id)
    context.user_data['in_payment'] = True
    context.user_data['checkout_total'] = None
    await query.edit_message_text(
        "💳 Joriy qarz: *{:,} so'm*\n\nTo'lov miqdorini kiriting (so'mda):".format(user['total_debt']),
        parse_mode='Markdown'
    )
    return ENTER_PAYMENT


async def post_init(application: Application):
    await db.connect()
    logger.info("✅ Ma'lumotlar bazasi ulandi")


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CLIENT_PHONE: [
                MessageHandler(filters.CONTACT, handle_phone),
            ],
            CATALOG: [
                CallbackQueryHandler(callback_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu),
            ],
            CART: [
                CallbackQueryHandler(checkout_callback, pattern="^checkout$"),
                CallbackQueryHandler(callback_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu),
            ],
            ENTER_PAYMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_payment_input),
                CallbackQueryHandler(callback_handler),
            ],
            MAIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu),
                CallbackQueryHandler(make_payment_callback, pattern="^make_payment$"),
                CallbackQueryHandler(callback_handler),
            ],
            ADMIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_menu),
                CallbackQueryHandler(admin_product_callback, pattern="^(save_product|cancel_product)$"),
                CallbackQueryHandler(callback_handler),
            ],
            ADMIN_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_name)],
            ADMIN_ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_price)],
            ADMIN_ADD_PHOTO: [
                MessageHandler(filters.PHOTO, admin_add_photo),
                CommandHandler("skip", skip_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_photo),
            ],
            ADMIN_ADD_CONFIRM: [
                CallbackQueryHandler(admin_product_callback, pattern="^(save_product|cancel_product)$"),
                CallbackQueryHandler(callback_handler),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("🚀 Bot ishga tushdi...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
