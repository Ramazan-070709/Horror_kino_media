import asyncio
import os
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage


BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8869719851

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi!")


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


DB_NAME = "bot.db"


# =========================
# HOLATLAR
# =========================

class AdminStates(StatesGroup):
    waiting_channel = State()
    waiting_delete_channel = State()
    waiting_movie_code = State()
    waiting_movie_file = State()
    waiting_delete_movie = State()


# =========================
# DATABASE
# =========================

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                file_id TEXT,
                caption TEXT
            )
        """)

        await db.commit()


async def get_channels():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT username FROM channels"
        )
        rows = await cursor.fetchall()

    return [row[0] for row in rows]


async def add_channel(username):
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute(
                "INSERT INTO channels (username) VALUES (?)",
                (username,)
            )
            await db.commit()
            return True
        except:
            return False


async def delete_channel(username):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "DELETE FROM channels WHERE username = ?",
            (username,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def add_movie(code, file_id, caption):
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute(
                """
                INSERT INTO movies (code, file_id, caption)
                VALUES (?, ?, ?)
                """,
                (code, file_id, caption)
            )
            await db.commit()
            return True
        except:
            return False


async def get_movie(code):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            SELECT file_id, caption
            FROM movies
            WHERE code = ?
            """,
            (code,)
        )
        return await cursor.fetchone()


async def delete_movie(code):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "DELETE FROM movies WHERE code = ?",
            (code,)
        )
        await db.commit()
        return cursor.rowcount > 0


# =========================
# KANAL TEKSHIRISH
# =========================

async def check_subscriptions(user_id):
    channels = await get_channels()

    for channel in channels:
        try:
            member = await bot.get_chat_member(
                chat_id=channel,
                user_id=user_id
            )

            if member.status in ["left", "kicked"]:
                return False

        except:
            return False

    return True


def channels_keyboard(channels):
    buttons = []

    for channel in channels:
        username = channel.replace("@", "")
        buttons.append([
            InlineKeyboardButton(
                text=f"📢 @{username}",
                url=f"https://t.me/{username}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="✅ Tekshirish",
            callback_data="check_subscription"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =========================
# START
# =========================

@dp.message(Command("start"))
async def start_handler(message: Message):

    channels = await get_channels()

    if channels:

        subscribed = await check_subscriptions(
            message.from_user.id
        )

        if not subscribed:
            await message.answer(
                "❌ Botdan foydalanish uchun quyidagi "
                "kanallarga obuna bo‘ling:",
                reply_markup=channels_keyboard(channels)
            )
            return

    await message.answer(
        "🎬 Kino botiga xush kelibsiz!\n\n"
        "Kino kodini yuboring:"
    )


# =========================
# TEKSHIRISH
# =========================

@dp.callback_query(F.data == "check_subscription")
async def check_subscription(callback: CallbackQuery):

    subscribed = await check_subscriptions(
        callback.from_user.id
    )

    if subscribed:
        await callback.message.edit_text(
            "✅ Obuna tasdiqlandi!\n\n"
            "🎬 Kino kodini yuboring:"
        )
    else:
        channels = await get_channels()

        await callback.answer(
            "❌ Hali barcha kanallarga obuna bo‘lmagansiz!",
            show_alert=True
        )

        if channels:
            await callback.message.edit_reply_markup(
                reply_markup=channels_keyboard(channels)
            )


# =========================
# KINO KODI
# =========================

@dp.message(F.text)
async def code_handler(message: Message):

    if message.text.startswith("/"):
        return

    subscribed = await check_subscriptions(
        message.from_user.id
    )

    if not subscribed:
        channels = await get_channels()

        if channels:
            await message.answer(
                "❌ Avval barcha kanallarga obuna bo‘ling:",
                reply_markup=channels_keyboard(channels)
            )
        return

    code = message.text.strip()

    movie = await get_movie(code)

    if not movie:
        await message.answer(
            "❌ Bunday kino kodi topilmadi."
        )
        return

    file_id, caption = movie

    try:
        await message.answer_video(
            video=file_id,
            caption=caption or ""
        )
    except:
        await message.answer_document(
            document=file_id,
            caption=caption or ""
        )


# =========================
# ADMIN PANEL
# =========================

@dp.message(Command("admin"))
async def admin_panel(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Kanal qo‘shish",
                    callback_data="add_channel"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Kanal o‘chirish",
                    callback_data="delete_channel"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎬 Kino qo‘shish",
                    callback_data="add_movie"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Kino o‘chirish",
                    callback_data="delete_movie"
                )
            ]
        ]
    )

    await message.answer(
        "👑 ADMIN PANEL\n\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=keyboard
    )


# =========================
# KANAL QO‘SHISH
# =========================

@dp.callback_query(F.data == "add_channel")
async def add_channel_start(
    callback: CallbackQuery,
    state: FSMContext
):

    if callback.from_user.id != ADMIN_ID:
        return

    await state.set_state(
        AdminStates.waiting_channel
    )

    await callback.message.answer(
        "📢 Kanal username'ini yuboring.\n\n"
        "Masalan:\n"
        "@horror_kanal"
    )

    await callback.answer()


@dp.message(AdminStates.waiting_channel)
async def add_channel_finish(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    username = message.text.strip()

    if not username.startswith("@"):
        username = "@" + username

    result = await add_channel(username)

    if result:
        await message.answer(
            f"✅ Kanal qo‘shildi:\n{username}"
        )
    else:
        await message.answer(
            "❌ Bu kanal allaqachon qo‘shilgan."
        )

    await state.clear()


# =========================
# KANAL O‘CHIRISH
# =========================

@dp.callback_query(F.data == "delete_channel")
async def delete_channel_start(
    callback: CallbackQuery,
    state: FSMContext
):

    if callback.from_user.id != ADMIN_ID:
        return

    await state.set_state(
        AdminStates.waiting_delete_channel
    )

    await callback.message.answer(
        "🗑 O‘chiriladigan kanal username'ini yuboring.\n\n"
        "Masalan:\n"
        "@horror_kanal"
    )

    await callback.answer()


@dp.message(AdminStates.waiting_delete_channel)
async def delete_channel_finish(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    username = message.text.strip()

    if not username.startswith("@"):
        username = "@" + username

    result = await delete_channel(username)

    if result:
        await message.answer(
            f"✅ Kanal o‘chirildi:\n{username}"
        )
    else:
        await message.answer(
            "❌ Bunday kanal topilmadi."
        )

    await state.clear()


# =========================
# KINO QO‘SHISH
# =========================

@dp.callback_query(F.data == "add_movie")
async def add_movie_start(
    callback: CallbackQuery,
    state: FSMContext
):

    if callback.from_user.id != ADMIN_ID:
        return

    await state.set_state(
        AdminStates.waiting_movie_code
    )

    await callback.message.answer(
        "🎬 Kino kodini yuboring.\n\n"
        "Masalan:\n"
        "123"
    )

    await callback.answer()


@dp.message(AdminStates.waiting_movie_code)
async def movie_code_received(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    code = message.text.strip()

    await state.update_data(code=code)

    await state.set_state(
        AdminStates.waiting_movie_file
    )

    await message.answer(
        "🎥 Endi kino videosini yuboring."
    )


@dp.message(AdminStates.waiting_movie_file)
async def movie_file_received(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    if not message.video and not message.document:
        await message.answer(
            "❌ Iltimos, video yoki fayl yuboring."
        )
        return

    data = await state.get_data()
    code = data["code"]

    if message.video:
        file_id = message.video.file_id
    else:
        file_id = message.document.file_id

    caption = message.caption or ""

    result = await add_movie(
        code,
        file_id,
        caption
    )

    if result:
        await message.answer(
            f"✅ Kino qo‘shildi!\n\n"
            f"🎬 Kod: {code}"
        )
    else:
        await message.answer(
            "❌ Bu kod allaqachon mavjud."
        )

    await state.clear()


# =========================
# KINO O‘CHIRISH
# =========================

@dp.callback_query(F.data == "delete_movie")
async def delete_movie_start(
    callback: CallbackQuery,
    state: FSMContext
):

    if callback.from_user.id != ADMIN_ID:
        return

    await state.set_state(
        AdminStates.waiting_delete_movie
    )

    await callback.message.answer(
        "🗑 O‘chiriladigan kino kodini yuboring."
    )

    await callback.answer()


@dp.message(AdminStates.waiting_delete_movie)
async def delete_movie_finish(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    code = message.text.strip()

    result = await delete_movie(code)

    if result:
        await message.answer(
            f"✅ Kino o‘chirildi.\n"
            f"Kod: {code}"
        )
    else:
        await message.answer(
            "❌ Bunday kino kodi topilmadi."
        )

    await state.clear()


# =========================
# ISHGA TUSHIRISH
# =========================

async def main():

    await init_db()

    print("Bot ishga tushdi...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
