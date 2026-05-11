import asyncio
import logging
import os
import socket
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
import aiohttp

# --- 1. ЗАГРУЗКА ПЕРЕМЕННЫХ ---
load_dotenv()
BOT_TOKEN = os.getenv("8580758584:AAFLoIN4PVFnQoC_RssMvLaWRhRtQjbep1k")
ADMIN_ID = int(os.getenv("8237417166"))

# Включаем логирование (чтобы видеть ошибки и статус)
logging.basicConfig(level=logging.INFO)

# --- 2. ПРИНУДИТЕЛЬНОЕ ПОДКЛЮЧЕНИЕ ТОЛЬКО ЧЕРЕЗ IPv4 (РЕШЕНИЕ ПРОБЛЕМ 504 ДЛЯ РФ) ---
# Это самый важный блок для работы в России [citation:6]
connector = aiohttp.TCPConnector(family=socket.AF_INET)  # force IPv4
session = aiohttp.ClientSession(connector=connector)
bot = Bot(token=BOT_TOKEN, session=session)

# Хранилище состояний (FSM) - для простоты используем MemoryStorage.
# Если бот будет падать от перегрузок, замените на SQLiteStorage из библиотеки aiogram-fsm-storage [citation:3]
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- 3. ОПРЕДЕЛЯЕМ СОСТОЯНИЯ (ДЛЯ ПРОЦЕССА ЗАКАЗА) ---
class OrderStates(StatesGroup):
    waiting_for_product_name = State()  # ждем, когда пользователь напишет название товара

# --- 4. КЛАВИАТУРЫ ---

# Главное меню (Reply Keyboard — привязана к полю ввода, но мы делаем Inline-кнопками для удобства)
def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🛍️ КАТАЛОГ", callback_data="catalog")
    builder.button(text="ℹ️ О магазине", callback_data="about")
    builder.adjust(1)
    return builder.as_markup()

# Клавиатура внутри каталога (кнопки под фото)
def get_catalog_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 СДЕЛАТЬ ЗАКАЗ", callback_data="make_order")
    builder.button(text="🔙 НАЗАД", callback_data="back_to_main")
    builder.adjust(1)  # в один столбик
    return builder.as_markup()

# --- 5. ОБРАБОТЧИКИ КОМАНД ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🌸 *Добро пожаловать в наш цветочный магазин!*\n\n"
        "Здесь вы можете выбрать букеты из нашего ассортимента.\n"
        "Используйте кнопку *Каталог*, чтобы посмотреть цены и сделать заказ.\n\n"
        "💰 *Оплата:* При заказе с вами свяжется оператор.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "about")
async def about_shop(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🏪 *О нас:*\n\nСвежие цветы с доставкой по городу.\n"
        "Работаем ежедневно с 9:00 до 21:00.\n\n"
        "По вопросам сотрудничества пишите администратору.",
        parse_mode="Markdown"
    )
    await callback.answer()

# --- 6. ЛОГИКА КАТАЛОГА ---

@dp.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    await callback.answer()
    # ПУТЬ К ФАЙЛУ С ФОТОГРАФИЕЙ
    # Вы можете менять этот файл когда угодно. Просто замените "price.jpg" на сервере.
    photo_path = "price.jpg"
    
    # Проверяем, существует ли файл
    if not os.path.exists(photo_path):
        await callback.message.answer("⚠️ Ошибка: Фотография прайса не найдена. Пожалуйста, сообщите администратору.")
        logging.error("File price.jpg not found!")
        return
    
    photo = FSInputFile(photo_path)
    
    # Отправляем фото с подписью и кнопками
    await callback.message.answer_photo(
        photo=photo,
        caption="📸 *Наш прайс-лист:*\n\nВыберите действие ниже 👇",
        parse_mode="Markdown",
        reply_markup=get_catalog_keyboard()
    )
    # Удаляем предыдущее сообщение с главным меню (чтобы не было мусора)
    try:
        await callback.message.delete()
    except Exception:
        pass  # если не удалилось, игнорируем

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Главное меню:",
        reply_markup=get_main_keyboard()
    )
    await callback.message.delete()

# --- 7. ОФОРМЛЕНИЕ ЗАКАЗА (FSM) ---

@dp.callback_query(F.data == "make_order")
async def order_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "✏️ *Оформление заказа*\n\n"
        "Введите *название товара*, который хотите заказать.\n"
        "Пример: *Букет 'Нежность' 101 роза*",
        parse_mode="Markdown"
    )
    await state.set_state(OrderStates.waiting_for_product_name)

# Хэндлер, который ловит текст от пользователя, когда мы в состоянии ожидания товара
@dp.message(OrderStates.waiting_for_product_name)
async def get_product_name(message: Message, state: FSMContext):
    product_name = message.text
    user = message.from_user
    
    # Формируем отчет для администратора (вам в личку)
    admin_text = (
        f"✅ *НОВЫЙ ЗАКАЗ!*\n\n"
        f"👤 *Клиент:* {user.full_name}\n"
        f"🆔 *User ID:* `{user.id}`\n"
        f"👤 *Username:* @{user.username if user.username else 'Нет username'}\n"
        f"📝 *Товар:* {product_name}\n"
        f"🔗 *Ссылка:* tg://user?id={user.id}"
    )
    
    try:
        # Отправляем вам в Telegram отчет
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown")
        
        # Пересылаем исходное сообщение пользователя (удобно, если он прислал фото или голосовое) [citation:1]
        await message.forward(ADMIN_ID)
        
        # Подтверждение пользователю
        await message.answer(
            "✅ *Заказ принят!*\n\n"
            "Спасибо! Наш специалист свяжется с вами в ближайшее время для уточнения деталей оплаты и доставки.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке админу: {e}")
        await message.answer("⚠️ Произошла техническая ошибка. Пожалуйста, попробуйте позже или напишите администратору напрямую.")
    
    # Выходим из состояния (чтобы бот снова реагировал на кнопки)
    await state.clear()

# --- 8. ОБРАБОТКА ЛЮБЫХ ДРУГИХ СООБЩЕНИЙ (ЧТОБЫ БОТ НЕ ТУПИЛ) ---
@dp.message(F.text)
async def handle_other_messages(message: Message):
    await message.answer(
        "Пожалуйста, используйте кнопки меню для навигации.",
        reply_markup=get_main_keyboard()
    )

# --- 9. ЗАПУСК БОТА ---
async def main():
    logging.info("Бот запускается...")
    # Настройка polling: handle_as_tasks=True позволяет обрабатывать несколько сообщений параллельно (без лагов) [citation:1][citation:10]
    await dp.start_polling(bot, handle_as_tasks=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен вручную")