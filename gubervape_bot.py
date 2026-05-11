import os
import json
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, \
    KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# ========== КОНФИГ (из переменных окружения Railway) ==========
TOKEN = os.environ.get("BOT_TOKEN", "8580758584:AAFLoIN4PVFnQoC_RssMvLaWRhRtQjbep1k")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 8237417166))
PRODUCTS_FILE = "products.json"

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ========== РАБОТА С ТОВАРАМИ ==========
def load_products():
    """Загружает товары из JSON"""
    if not os.path.exists(PRODUCTS_FILE):
        # Стартовые товары
        default_products = {
            "Электронки": [
                {"id": "v1", "name": "HQD Cuvie Plus", "price": 450, "desc": "1200 затяжек, 5% никотин"},
                {"id": "v2", "name": "Elf Bar 600", "price": 550, "desc": "600 затяжек, фруктовый микс"}
            ],
            "Жидкости": [
                {"id": "l1", "name": "Nasty Juice Slow Blow", "price": 350, "desc": "30мл, 3мг соли"},
                {"id": "l2", "name": "Husky Tiger Blood", "price": 290, "desc": "30мл, 20мг соли"}
            ],
            "Аксессуары": [
                {"id": "a1", "name": "Защитный колпачок", "price": 50, "desc": "силиконовый"},
                {"id": "a2", "name": "Сменный испаритель", "price": 180, "desc": "универсальный"}
            ]
        }
        save_products(default_products)
        return default_products
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_products(products):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


# Глобальная переменная для товаров (кэш)
products_cache = load_products()

# ========== КОРЗИНА (временное хранилище для каждого пользователя) ==========
user_carts = {}


# ========== FSM ДЛЯ ОФОРМЛЕНИЯ ==========
class OrderForm(StatesGroup):
    waiting_for_fullname = State()
    waiting_for_username = State()
    waiting_for_comment = State()


# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard(is_admin=False):
    buttons = [
        [KeyboardButton(text="📂 Категории")],
        [KeyboardButton(text="🛒 Корзина"), KeyboardButton(text="✅ Оформить заказ")]
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="🔧 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_categories_kb():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for category in products_cache.keys():
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=category, callback_data=f"cat_{category}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return keyboard


def get_products_kb(category):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for product in products_cache.get(category, []):
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"{product['name']} - {product['price']}₽",
                                 callback_data=f"product_{category}_{product['id']}")
        ])
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="🔙 Назад к категориям", callback_data="back_categories")])
    return keyboard


def get_product_actions_kb(category, product_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ В корзину", callback_data=f"add_{category}_{product_id}")],
        [InlineKeyboardButton(text="🔙 Назад к товарам", callback_data=f"back_products_{category}")]
    ])
    return keyboard


def get_cart_kb():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_main")]
    ])
    return keyboard


def get_admin_panel_kb():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton(text="✏️ Редактировать товар", callback_data="admin_edit")],
        [InlineKeyboardButton(text="❌ Удалить товар", callback_data="admin_delete")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    return keyboard


def get_admin_categories_kb():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for category in products_cache.keys():
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=category, callback_data=f"admin_cat_{category}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    return keyboard


def get_admin_products_kb(category, action):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for product in products_cache.get(category, []):
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text=product['name'], callback_data=f"admin_{action}_{category}_{product['id']}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад к категориям", callback_data="admin_cats")])
    return keyboard


# ========== ОТПРАВКА ЧЕКА АДМИНУ ==========
async def send_receipt(user_id, fullname, username, comment, cart_items, total):
    items_text = "\n".join([f"- {item['name']} x1 = {item['price']}₽" for item in cart_items])
    receipt = (
        f"🛒 **НОВЫЙ ЗАКАЗ**\n\n"
        f"👤 **ФИО:** {fullname}\n"
        f"📱 **TG Username:** @{username if username else 'не указан'}\n"
        f"💬 **Комментарий:** {comment if comment else 'нет'}\n\n"
        f"📦 **Товары:**\n{items_text}\n\n"
        f"💰 **ИТОГО:** {total}₽\n\n"
        f"🆔 **ID клиента:** {user_id}"
    )
    await bot.send_message(ADMIN_ID, receipt, parse_mode="Markdown")


# ========== ОБРАБОТЧИКИ ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    is_admin = (user_id == ADMIN_ID)
    await message.answer(
        f"🍃 Добро пожаловать в **GuberVape**!\n\n"
        f"У нас лучшие цены на одноразки, жидкости и аксессуары.\n"
        f"Выбери категорию или сразу переходи в корзину.",
        reply_markup=get_main_keyboard(is_admin),
        parse_mode="Markdown"
    )


@dp.message(lambda message: message.text == "📂 Категории")
async def show_categories(message: Message):
    await message.answer("Выбери категорию:", reply_markup=get_categories_kb())


@dp.message(lambda message: message.text == "🛒 Корзина")
async def show_cart(message: Message):
    user_id = message.from_user.id
    cart = user_carts.get(user_id, [])
    if not cart:
        await message.answer("🛍 Ваша корзина пуста. Добавьте товары через категории.")
        return

    total = sum(item['price'] for item in cart)
    items = "\n".join([f"{i + 1}. {item['name']} - {item['price']}₽" for i, item in enumerate(cart)])
    await message.answer(
        f"🛒 **Ваша корзина:**\n{items}\n\n💰 **Сумма:** {total}₽",
        reply_markup=get_cart_kb(),
        parse_mode="Markdown"
    )


@dp.message(lambda message: message.text == "✅ Оформить заказ")
async def start_order(message: Message, state: FSMContext):
    user_id = message.from_user.id
    cart = user_carts.get(user_id, [])
    if not cart:
        await message.answer("❌ Корзина пуста. Сначала добавьте товары.")
        return

    await message.answer("📝 Для оформления заказа напишите ваше **ФИО**:")
    await state.set_state(OrderForm.waiting_for_fullname)
    await state.update_data(cart=cart)


@dp.message(OrderForm.waiting_for_fullname)
async def get_fullname(message: Message, state: FSMContext):
    await state.update_data(fullname=message.text)
    await message.answer("📱 Введите ваш **Telegram username** (можно @... или просто ник, или '-' если не хотите):")
    await state.set_state(OrderForm.waiting_for_username)


@dp.message(OrderForm.waiting_for_username)
async def get_username(message: Message, state: FSMContext):
    username = message.text.strip()
    if username == "-":
        username = ""
    await state.update_data(username=username)
    await message.answer("💬 Комментарий к заказу (можно '-' если нет):")
    await state.set_state(OrderForm.waiting_for_comment)


@dp.message(OrderForm.waiting_for_comment)
async def get_comment(message: Message, state: FSMContext):
    comment = message.text.strip()
    if comment == "-":
        comment = ""
    data = await state.update_data(comment=comment)
    fullname = data['fullname']
    username = data['username']
    cart = data['cart']
    total = sum(item['price'] for item in cart)

    await send_receipt(message.from_user.id, fullname, username, comment, cart, total)
    user_carts[message.from_user.id] = []

    await message.answer(
        f"✅ **Заказ оформлен!**\n\n"
        f"Вы заказали:\n" + "\n".join([f"- {item['name']}" for item in cart]) + f"\n\n💰 Сумма: {total}₽\n\n"
                                                                                f"Наш менеджер свяжется с вами в ближайшее время. Спасибо за покупку! 🍃",
        parse_mode="Markdown"
    )
    await state.clear()


@dp.callback_query()
async def handle_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_admin = (user_id == ADMIN_ID)
    data = callback.data

    if data == "back_main":
        await callback.message.edit_text("🍃 Главное меню:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[]))
        await callback.message.answer("Возврат в главное меню.", reply_markup=get_main_keyboard(is_admin))
        await callback.answer()
        return

    if data == "back_categories":
        await callback.message.edit_text("Выберите категорию:", reply_markup=get_categories_kb())
        await callback.answer()
        return

    if data.startswith("cat_"):
        category = data[4:]
        await callback.message.edit_text(f"📦 Товары в категории **{category}**:",
                                         reply_markup=get_products_kb(category), parse_mode="Markdown")
        await callback.answer()
        return

    if data.startswith("back_products_"):
        category = data[14:]
        await callback.message.edit_text(f"📦 Товары в категории **{category}**:",
                                         reply_markup=get_products_kb(category), parse_mode="Markdown")
        await callback.answer()
        return

    if data.startswith("product_"):
        _, category, product_id = data.split("_", 2)
        product = next((p for p in products_cache.get(category, []) if p['id'] == product_id), None)
        if product:
            text = f"🍃 **{product['name']}**\n💵 Цена: {product['price']}₽\n📝 {product['desc']}"
            await callback.message.edit_text(text, reply_markup=get_product_actions_kb(category, product_id),
                                             parse_mode="Markdown")
        await callback.answer()
        return

    if data.startswith("add_"):
        _, category, product_id = data.split("_", 2)
        product = next((p for p in products_cache.get(category, []) if p['id'] == product_id), None)
        if product:
            if user_id not in user_carts:
                user_carts[user_id] = []
            user_carts[user_id].append({
                "id": product['id'],
                "name": product['name'],
                "price": product['price'],
                "category": category
            })
            await callback.answer(f"✅ {product['name']} добавлен в корзину!", show_alert=True)
        else:
            await callback.answer("❌ Товар не найден", show_alert=True)
        return

    if data == "clear_cart":
        user_carts[user_id] = []
        await callback.message.edit_text("🛒 Корзина очищена.", reply_markup=get_cart_kb())
        await callback.answer()
        return

    # ========== АДМИНКА ==========
    if not is_admin:
        await callback.answer("⛔ У вас нет прав администратора.", show_alert=True)
        return

    if data == "admin_panel":
        await callback.message.edit_text("🔧 Админ-панель:", reply_markup=get_admin_panel_kb())
        await callback.answer()
        return

    if data == "admin_back":
        await callback.message.edit_text("🔧 Админ-панель:", reply_markup=get_admin_panel_kb())
        await callback.answer()
        return

    if data == "admin_cats":
        await callback.message.edit_text("Выберите категорию:", reply_markup=get_admin_categories_kb())
        await callback.answer()
        return

    if data.startswith("admin_cat_"):
        category = data[10:]
        await state.update_data(admin_category=category)
        await callback.message.edit_text(f"Категория **{category}**. Что делаем?",
                                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                             [InlineKeyboardButton(text="➕ Добавить",
                                                                   callback_data="admin_add_in_cat")],
                                             [InlineKeyboardButton(text="✏️ Редактировать",
                                                                   callback_data="admin_edit_in_cat")],
                                             [InlineKeyboardButton(text="❌ Удалить",
                                                                   callback_data="admin_delete_in_cat")],
                                             [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_cats")]
                                         ]))
        await callback.answer()
        return

    if data == "admin_add":
        await callback.message.answer(
            "Введите команду:\n`/add_category Название` - создать новую категорию\n`/add_product Категория | Название | Цена | Описание`\n\nПример:\n`/add_product Электронки | HQD New | 500 | 1500 затяжек`",
            parse_mode="Markdown")
        await callback.answer()
        return

    if data == "admin_edit":
        await callback.message.edit_text("Выберите категорию для редактирования:",
                                         reply_markup=get_admin_categories_kb())
        await callback.answer()
        return

    if data == "admin_delete":
        await callback.message.edit_text("Выберите категорию для удаления товара:",
                                         reply_markup=get_admin_categories_kb())
        await callback.answer()
        return

    if data == "admin_add_in_cat":
        data_state = await state.get_data()
        category = data_state.get('admin_category')
        await callback.message.answer(
            f"Добавление в категорию **{category}**.\nВведите данные в формате:\n`Название | Цена | Описание`\nПример:\n`Новая жидкость | 400 | 30мл, фрукты`",
            parse_mode="Markdown")
        await state.set_state("waiting_add_product")
        await callback.answer()
        return

    if data == "admin_edit_in_cat":
        data_state = await state.get_data()
        category = data_state.get('admin_category')
        await callback.message.edit_text(f"Выберите товар для редактирования в **{category}**",
                                         reply_markup=get_admin_products_kb(category, "edit"))
        await callback.answer()
        return

    if data == "admin_delete_in_cat":
        data_state = await state.get_data()
        category = data_state.get('admin_category')
        await callback.message.edit_text(f"Выберите товар для удаления в **{category}**",
                                         reply_markup=get_admin_products_kb(category, "delete"))
        await callback.answer()
        return

    if data.startswith("admin_edit_"):
        parts = data.split("_", 3)
        category = parts[2]
        product_id = parts[3]
        await state.update_data(edit_category=category, edit_product_id=product_id)
        await callback.message.answer("Введите новые данные в формате:\n`Название | Цена | Описание`")
        await state.set_state("waiting_edit_product")
        await callback.answer()
        return

    if data.startswith("admin_delete_"):
        parts = data.split("_", 3)
        category = parts[2]
        product_id = parts[3]
        products_cache[category] = [p for p in products_cache.get(category, []) if p['id'] != product_id]
        if not products_cache[category]:
            del products_cache[category]
        save_products(products_cache)
        await callback.message.edit_text(f"✅ Товар удален из **{category}**", reply_markup=get_admin_panel_kb())
        await callback.answer()
        return


# ========== КОМАНДЫ АДМИНА ==========
@dp.message(Command("add_category"))
async def add_category(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: `/add_category Название категории`")
        return
    new_cat = args[1].strip()
    if new_cat in products_cache:
        await message.answer("❌ Такая категория уже существует")
        return
    products_cache[new_cat] = []
    save_products(products_cache)
    await message.answer(f"✅ Категория **{new_cat}** создана!")


@dp.message(Command("add_product"))
async def add_product(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: `/add_product Категория | Название | Цена | Описание`")
        return
    parts = args[1].split("|")
    if len(parts) < 4:
        await message.answer("❌ Неверный формат. Нужно: `Категория | Название | Цена | Описание`")
        return
    category = parts[0].strip()
    name = parts[1].strip()
    try:
        price = int(parts[2].strip())
    except:
        await message.answer("❌ Цена должна быть числом")
        return
    desc = parts[3].strip()

    if category not in products_cache:
        products_cache[category] = []
    new_id = f"{category[:2]}{len(products_cache[category]) + 1}"
    products_cache[category].append({
        "id": new_id,
        "name": name,
        "price": price,
        "desc": desc
    })
    save_products(products_cache)
    await message.answer(f"✅ Товар **{name}** добавлен в категорию **{category}**")


@dp.message(state="waiting_add_product")
async def process_add_product(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    category = data.get('admin_category')
    if not category:
        await message.answer("❌ Ошибка, начните заново через админ-панель")
        await state.clear()
        return

    parts = message.text.split("|")
    if len(parts) < 3:
        await message.answer("❌ Формат: `Название | Цена | Описание`")
        return
    name = parts[0].strip()
    try:
        price = int(parts[1].strip())
    except:
        await message.answer("❌ Цена должна быть числом")
        return
    desc = parts[2].strip()

    new_id = f"{category[:2]}{len(products_cache.get(category, [])) + 1}"
    if category not in products_cache:
        products_cache[category] = []
    products_cache[category].append({
        "id": new_id,
        "name": name,
        "price": price,
        "desc": desc
    })
    save_products(products_cache)
    await message.answer(f"✅ Товар **{name}** добавлен в **{category}**")
    await state.clear()


@dp.message(state="waiting_edit_product")
async def process_edit_product(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    category = data.get('edit_category')
    product_id = data.get('edit_product_id')
    if not category or not product_id:
        await message.answer("❌ Ошибка, начните заново")
        await state.clear()
        return

    parts = message.text.split("|")
    if len(parts) < 3:
        await message.answer("❌ Формат: `Название | Цена | Описание`")
        return
    name = parts[0].strip()
    try:
        price = int(parts[1].strip())
    except:
        await message.answer("❌ Цена должна быть числом")
        return
    desc = parts[2].strip()

    for idx, p in enumerate(products_cache.get(category, [])):
        if p['id'] == product_id:
            products_cache[category][idx] = {
                "id": product_id,
                "name": name,
                "price": price,
                "desc": desc
            }
            break
    save_products(products_cache)
    await message.answer(f"✅ Товар **{name}** обновлен в **{category}**")
    await state.clear()


# ========== ЗАПУСК ДЛЯ RAILWAY ==========
async def main():
    # Удаляем старый вебхук (важно для Railway)
    await bot.delete_webhook(drop_pending_updates=True)
    print("🍃 Бот GuberVape запущен на Railway!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())