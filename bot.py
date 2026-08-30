import asyncio
import os
import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8869719851

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

DB_NAME = "bot.db"

# ==================== STATES ====================
class AdminStates(StatesGroup):
    waiting_channel = State()
    waiting_movie_code = State()
    waiting_movie_file = State()
    waiting_delete_code = State()

class UserStates(StatesGroup):
    waiting_code = State()

# ==================== DATABASE ====================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE,
                channel_link TEXT,
                channel_title TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                code TEXT PRIMARY KEY,
                file_id TEXT,
                caption TEXT
            )
        """)
        await db.commit()

async def add_channel(channel_id: str, link: str, title: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO channels (channel_id, channel_link, channel_title) VALUES (?, ?, ?)",
            (channel_id, link, title)
        )
        await db.commit()

async def remove_channel(channel_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        await db.commit()

async def get_channels():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT channel_id, channel_link, channel_title FROM channels") as cursor:
            return await cursor.fetchall()

async def add_movie(code: str, file_id: str, caption: str = ""):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO movies (code, file_id, caption) VALUES (?, ?, ?)",
            (code.lower(), file_id, caption)
        )
        await db.commit()

async def get_movie(code: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT file_id, caption FROM movies WHERE code = ?", (code.lower(),)) as cursor:
            return await cursor.fetchone()

async def delete_movie(code: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM movies WHERE code = ?", (code.lower(),))
        await db.commit()

# ==================== KEYBOARDS ====================
def get_channels_keyboard(channels):
    buttons = []
    for ch_id, link, title in channels:
        buttons.append([InlineKeyboardButton(text=f"📢 {title}", url=link)])
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo‘shish", callback_data="admin_add_channel")],
        [InlineKeyboardButton(text="➖ Kanal o‘chirish", callback_data="admin_remove_channel")],
        [InlineKeyboardButton(text="🎬 Kino qo‘shish", callback_data="admin_add_movie")],
        [InlineKeyboardButton(text="🗑 Kino o‘chirish", callback_data="admin_delete_movie")],
        [InlineKeyboardButton(text="📋 Kanallar ro‘yxati", callback_data="admin_list_channels")],
    ])

# ==================== SUBSCRIPTION CHECK ====================
async def check_subscriptions(user_id: int) -> bool:
    channels = await get_channels()
    if not channels:
        return True
    for ch_id, _, _ in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            return False
    return True

# ==================== USER HANDLERS ====================
@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    channels = await get_channels()
    
    if not channels:
        await message.answer("Botga xush kelibsiz!\nKodni yuboring:")
        await state.set_state(UserStates.waiting_code)
        return
    
    text = "🎬 <b>Kino botiga xush kelibsiz!</b>\n\n"
    text += "Botdan foydalanish uchun quyidagi kanallarga obuna bo‘ling:\n\n"
    
    kb = get_channels_keyboard(channels)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "check_sub")
async def check_sub_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_subscribed = await check_subscriptions(user_id)
    
    if is_subscribed:
        await callback.message.edit_text("✅ Obuna tasdiqlandi!\n\nEndi <b>kodni</b> yuboring:", parse_mode="HTML")
        await state.set_state(UserStates.waiting_code)
    else:
        channels = await get_channels()
        kb = get_channels_keyboard(channels)
        await callback.message.edit_text(
            "❌ Siz hali barcha kanallarga obuna bo‘lmadingiz.\nIltimos, obuna bo‘ling va qayta tekshiring.",
            reply_markup=kb
        )
    await callback.answer()

@dp.message(UserStates.waiting_code)
async def code_handler(message: Message, state: FSMContext):
    code = message.text.strip()
    movie = await get_movie(code)
    
    if movie:
        file_id, caption = movie
        try:
            await message.answer_video(file_id, caption=caption or f"Kod: {code}")
        except Exception:
            await message.answer_document(file_id, caption=caption or f"Kod: {code}")
        await state.clear()
    else:
        await message.answer("❌ Bunday kod topilmadi. Qaytadan urinib ko‘ring.")

# ==================== ADMIN HANDLERS ====================
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🔧 <b>Admin panel</b>", reply_markup=get_admin_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_add_channel")
async def admin_add_channel(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.answer(
        "Kanal qo‘shish uchun quyidagi formatda yuboring:\n\n"
        "<code>@kanal_username</code>\n\nyoki\n\n"
        "<code>-100xxxxxxxxxx</code>\n\n"
        "Keyin bot shu kanalga admin qilib qo‘ying."
    , parse_mode="HTML")
    await state.set_state(AdminStates.waiting_channel)
    await callback.answer()

@dp.message(AdminStates.waiting_channel)
async def process_add_channel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    channel = message.text.strip()
    try:
        chat = await bot.get_chat(channel)
        link = f"https://t.me/{chat.username}" if chat.username else (await bot.create_chat_invite_link(chat.id)).invite_link
        await add_channel(str(chat.id), link, chat.title or channel)
        await message.answer(f"✅ Kanal qo‘shildi: {chat.title}")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}\nBotni kanalga admin qilib qo‘ying.")
    await state.clear()

@dp.callback_query(F.data == "admin_remove_channel")
async def admin_remove_channel(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    channels = await get_channels()
    if not channels:
        await callback.message.answer("Hozircha kanal yo‘q.")
        await callback.answer()
        return
    text = "O‘chirish uchun kanal ID sini yuboring:\n\n"
    for ch_id, link, title in channels:
        text += f"{title} → <code>{ch_id}</code>\n"
    await callback.message.answer(text, parse_mode="HTML")
    await state.set_state(AdminStates.waiting_channel)  # reuse
    await callback.answer()

@dp.callback_query(F.data == "admin_list_channels")
async def admin_list_channels(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    channels = await get_channels()
    if not channels:
        await callback.message.answer("Kanallar yo‘q.")
    else:
        text = "📋 <b>Kanallar:</b>\n\n"
        for ch_id, link, title in channels:
            text += f"• {title}\n  ID: <code>{ch_id}</code>\n  Link: {link}\n\n"
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_add_movie")
async def admin_add_movie(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.answer("Kino kodini yuboring (masalan: film01):")
    await state.set_state(AdminStates.waiting_movie_code)
    await callback.answer()

@dp.message(AdminStates.waiting_movie_code)
async def process_movie_code(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    code = message.text.strip()
    await state.update_data(movie_code=code)
    await message.answer("Endi video yoki faylni yuboring:")
    await state.set_state(AdminStates.waiting_movie_file)

@dp.message(AdminStates.waiting_movie_file, F.video | F.document)
async def process_movie_file(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    code = data.get("movie_code")
    
    file_id = message.video.file_id if message.video else message.document.file_id
    caption = message.caption or ""
    
    await add_movie(code, file_id, caption)
    await message.answer(f"✅ Kino qo‘shildi!\nKod: <b>{code}</b>", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "admin_delete_movie")
async def admin_delete_movie(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.answer("O‘chirmoqchi bo‘lgan kino kodini yuboring:")
    await state.set_state(AdminStates.waiting_delete_code)
    await callback.answer()

@dp.message(AdminStates.waiting_delete_code)
async def process_delete_movie(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    code = message.text.strip()
    await delete_movie(code)
    await message.answer(f"✅ Kod o‘chirildi: {code}")
    await state.clear()

# ==================== START ====================
async def main():
    await init_db()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
