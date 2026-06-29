import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.config import settings
from app.models.expert import Expert
from app.models.category import Category
from app.models.user import User, UserRole
from app.models.expert_document import ExpertDocument
from app.ai.tasks import generate_document_embedding_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


BTN_ADD  = "➕ Yangi ma'lumot kiritish"
BTN_DOCS = "📂 Mening ma'lumotlarim"
BTN_DEL  = "🗑 Ma'lumot o'chirish"
BTN_CAT  = "💼 Kasb yo'nalishim"
BTN_BACK = "⬅️ Orqaga"

DEFAULT_CATEGORIES = [
    ("👨‍⚕️ Shifokor",         "Tibbiyot"),
    ("⚖️ Huquqshunos",        "Huquq"),
    ("💰 Moliyachi",           "Moliya"),
    ("💻 IT mutaxassisi",      "Axborot texnologiyalari"),
    ("🏗 Muhandis",            "Muhandislik"),
    ("📚 O'qituvchi",          "Ta'lim"),
    ("🏢 Biznes maslahatchi",  "Biznes"),
    ("🔬 Ilmiy tadqiqotchi",   "Fan"),
]



def get_or_create_bot_user(db: Session, telegram_id: int, full_name: str) -> int:
    """
    Telegram foydalanuvchisi uchun User yozuvini topadi yoki yaratadi.
    email = telegram_{id}@bot.local formatida saqlanadi.
    """
    fake_email = f"telegram_{telegram_id}@bot.local"
    user = db.query(User).filter(User.email == fake_email).first()
    if not user:
        user = User(
            email=fake_email,
            password="telegram_bot_user",  # parol kerak emas, bot orqali kiradi
            role=UserRole.expert,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user.id

def get_db() -> Session:
    db = SessionLocal()
    return db


def main_keyboard():
    """Asosiy pastki tugmalar paneli — doim ko'rinib turadi."""
    keyboard = [
        [KeyboardButton(BTN_ADD)],
        [KeyboardButton(BTN_DOCS)],
        [KeyboardButton(BTN_DEL)],
        [KeyboardButton(BTN_CAT)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def back_keyboard():
    """Faqat Orqaga tugmasi — kiritish/o'chirish rejimida."""
    keyboard = [[KeyboardButton(BTN_BACK)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def category_inline_keyboard(db: Session) -> InlineKeyboardMarkup:
    """
    DB dagi kategoriyalardan InlineKeyboard yaratadi.
    DB bo'sh bo'lsa — default ro'yxatdan foydalanadi.
    """
    categories = db.query(Category).all()

    if categories:
        buttons = [
            [InlineKeyboardButton(
                f"{cat.icon or ''} {cat.name}".strip(),
                callback_data=f"cat_{cat.id}"
            )]
            for cat in categories
        ]
    else:
        buttons = [
            [InlineKeyboardButton(label, callback_data=f"catname_{label}")]
            for label, _ in DEFAULT_CATEGORIES
        ]

    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    telegram_id = update.effective_user.id
    db = get_db()
    expert = db.query(Expert).filter(Expert.telegram_id == telegram_id).first()

    if expert:
        cat_label = ""
        if expert.category_id:
            cat = db.query(Category).filter(Category.id == expert.category_id).first()
            if cat:
                cat_label = f" | {cat.icon or ''} {cat.name}".strip()
        db.close()
        await update.message.reply_text(
            f"Xush kelibsiz, {expert.full_name}! 👋{cat_label}\n\n"
            "Quyidagi amallardan birini tanlang:",
            reply_markup=main_keyboard()
        )
    else:
        db.close()
        context.user_data["awaiting_name"] = True
        await update.message.reply_text(
            "Salom! ExpertHub botiga xush kelibsiz. 🎓\n\n"
            "Ro'yxatdan o'tish uchun to'liq ismingizni (Ism Familiya) yuboring:",
            reply_markup=ReplyKeyboardRemove()
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    text = update.message.text
    db = get_db()


    if text == BTN_BACK:
        context.user_data.clear()
        db.close()
        await update.message.reply_text("Asosiy menyu:", reply_markup=main_keyboard())
        return

    if context.user_data.get("awaiting_name"):
        existing = db.query(Expert).filter(Expert.telegram_id == telegram_id).first()
        if existing:
            db.close()
            context.user_data.clear()
            await update.message.reply_text(
                "Siz allaqachon ro'yxatdan o'tgansiz!",
                reply_markup=main_keyboard()
            )
            return

        context.user_data["awaiting_name"] = False
        context.user_data["pending_name"] = text
        context.user_data["awaiting_category"] = True

        await update.message.reply_text(
            f"Rahmat, {text}! 👋\n\n"
            "Endi kasb yo'nalishingizni tanlang:",
            reply_markup=ReplyKeyboardRemove()
        )
        await update.message.reply_text(
            "⬇️ Quyidagi kasb turlaridan birini bosing:",
            reply_markup=category_inline_keyboard(db)
        )
        db.close()
        return

    if text == BTN_ADD:
        expert = db.query(Expert).filter(Expert.telegram_id == telegram_id).first()
        db.close()
        if not expert:
            await update.message.reply_text("Avval ro'yxatdan o'ting: /start")
            return
        context.user_data["adding_info"] = True
        await update.message.reply_text(
            "📝 Ma'lumotingizni yuboring:\n\n"
            "(Bekor qilish uchun ⬅️ Orqaga tugmasini bosing)",
            reply_markup=back_keyboard()
        )
        return

    if text == BTN_DOCS:
        expert = db.query(Expert).filter(Expert.telegram_id == telegram_id).first()
        if not expert:
            db.close()
            await update.message.reply_text("Avval ro'yxatdan o'ting: /start")
            return
        docs = db.query(ExpertDocument).filter(ExpertDocument.expert_id == expert.id).all()
        cat_label = ""
        if expert.category_id:
            cat = db.query(Category).filter(Category.id == expert.category_id).first()
            if cat:
                cat_label = f" ({cat.icon or ''} {cat.name})".strip()
        db.close()

        if not docs:
            await update.message.reply_text(
                f"📂 {expert.full_name}{cat_label} ning hujjatlari:\n\n"
                "Hozircha hech qanday ma'lumot kiritilmagan.",
                reply_markup=main_keyboard()
            )
            return

        result = f"📂 {expert.full_name}{cat_label} ning hujjatlari:\n\n"
        for doc in docs:
            preview = doc.content[:80] + "..." if len(doc.content) > 80 else doc.content
            result += f"🔹 #{doc.id}: {preview}\n\n"
        await update.message.reply_text(result, reply_markup=main_keyboard())
        return

    if text == BTN_DEL:
        expert = db.query(Expert).filter(Expert.telegram_id == telegram_id).first()
        if not expert:
            db.close()
            await update.message.reply_text("Avval ro'yxatdan o'ting: /start")
            return
        docs = db.query(ExpertDocument).filter(ExpertDocument.expert_id == expert.id).all()
        db.close()

        if not docs:
            await update.message.reply_text(
                "O'chirish uchun hech qanday ma'lumot yo'q.",
                reply_markup=main_keyboard()
            )
            return

        result = "🗑 O'chirmoqchi bo'lgan ma'lumot raqamini yuboring:\n\n"
        for doc in docs:
            preview = doc.content[:60] + "..." if len(doc.content) > 60 else doc.content
            result += f"#{doc.id}: {preview}\n"
        context.user_data["deleting_doc"] = True
        await update.message.reply_text(result, reply_markup=back_keyboard())
        return

    if text == BTN_CAT:
        expert = db.query(Expert).filter(Expert.telegram_id == telegram_id).first()
        if not expert:
            db.close()
            await update.message.reply_text("Avval ro'yxatdan o'ting: /start")
            return

        current_label = "Belgilanmagan"
        if expert.category_id:
            cat = db.query(Category).filter(Category.id == expert.category_id).first()
            if cat:
                current_label = f"{cat.icon or ''} {cat.name}".strip()

        context.user_data["awaiting_category"] = True
        context.user_data["pending_name"] = expert.full_name
        context.user_data["changing_category"] = True
        await update.message.reply_text(
            f"Hozirgi kasb yo'nalishingiz: {current_label}\n\n"
            "Yangi kasb yo'nalishini tanlang:",
            reply_markup=ReplyKeyboardRemove()
        )
        await update.message.reply_text(
            "⬇️ Quyidagi kasb turlaridan birini bosing:",
            reply_markup=category_inline_keyboard(db)
        )
        db.close()
        return


    if context.user_data.get("adding_info"):
        expert = db.query(Expert).filter(Expert.telegram_id == telegram_id).first()
        if not expert:
            db.close()
            context.user_data.clear()
            await update.message.reply_text("Avval ro'yxatdan o'ting: /start")
            return
        doc = ExpertDocument(expert_id=expert.id, content=text, source="telegram_bot")
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id
        db.close()
        generate_document_embedding_task.delay(doc_id)
        context.user_data.clear()
        await update.message.reply_text(
            "✅ Ma'lumot saqlandi!",
            reply_markup=main_keyboard()
        )
        return


    if context.user_data.get("deleting_doc"):
        expert = db.query(Expert).filter(Expert.telegram_id == telegram_id).first()
        if not expert:
            db.close()
            context.user_data.clear()
            await update.message.reply_text("Avval ro'yxatdan o'ting: /start")
            return

        try:
            doc_id = int(text.strip())
            doc = db.query(ExpertDocument).filter(
                ExpertDocument.id == doc_id,
                ExpertDocument.expert_id == expert.id
            ).first()
            if doc:
                db.delete(doc)
                db.commit()
                db.close()
                context.user_data.clear()
                await update.message.reply_text(
                    f"🗑 #{doc_id} raqamli ma'lumot o'chirildi.",
                    reply_markup=main_keyboard()
                )
            else:
                db.close()
                await update.message.reply_text(
                    "❌ Bunday raqamli ma'lumot topilmadi.",
                    reply_markup=back_keyboard()
                )
        except ValueError:
            db.close()
            await update.message.reply_text(
                "Iltimos, faqat raqam yuboring.",
                reply_markup=back_keyboard()
            )
        return

    db.close()
    await update.message.reply_text(
        "Quyidagi tugmalardan foydalaning:",
        reply_markup=main_keyboard()
    )



async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not context.user_data.get("awaiting_category"):
        return

    telegram_id = query.from_user.id
    full_name = context.user_data.get("pending_name", "Noma'lum")
    db = get_db()

    category_id = None
    category_label = ""
    data = query.data

    if data.startswith("cat_"):
        cat_id = int(data.replace("cat_", ""))
        cat = db.query(Category).filter(Category.id == cat_id).first()
        if cat:
            category_id = cat.id
            category_label = f"{cat.icon or ''} {cat.name}".strip()

    elif data.startswith("catname_"):
        label = data.replace("catname_", "")
        category_label = label
        existing_cat = db.query(Category).filter(Category.name == label).first()
        if existing_cat:
            category_id = existing_cat.id
        else:
            new_cat = Category(name=label, icon="")
            db.add(new_cat)
            db.commit()
            db.refresh(new_cat)
            category_id = new_cat.id

    is_changing = context.user_data.get("changing_category", False)

    if is_changing:
        expert = db.query(Expert).filter(Expert.telegram_id == telegram_id).first()
        if expert:
            expert.category_id = category_id
            db.commit()
        db.close()
        context.user_data.clear()
        await query.edit_message_text(
            f"✅ Kasb yo'nalishi yangilandi!\n\n"
            f"👤 Ism: {full_name}\n"
            f"💼 Yangi kasb: {category_label}"
        )
    else:
        user_id = get_or_create_bot_user(db, telegram_id, full_name)
        expert = Expert(
            user_id=user_id,
            full_name=full_name,
            telegram_id=telegram_id,
            category_id=category_id
        )
        db.add(expert)
        db.commit()
        db.close()
        context.user_data.clear()
        await query.edit_message_text(
            f"✅ Ro'yxatdan muvaffaqiyatli o'tdingiz!\n\n"
            f"👤 Ism: {full_name}\n"
            f"💼 Kasb: {category_label}"
        )

    await query.message.reply_text(
        "Quyidagi amallardan birini tanlang:",
        reply_markup=main_keyboard()
    )


def main():
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(category_callback, pattern="^cat"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot ishga tushdi...")
    application.run_polling()


if __name__ == "__main__":
    main()