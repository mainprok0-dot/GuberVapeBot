import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import 8580758584:AAFLoIN4PVFnQoC_RssMvLaWRhRtQjbep1k, 8237417166
from database import *
from keyboards import main_menu, admin_panel

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---- FSM для админки ----
class AdminStates(StatesGroup):
    waiting_cat_name = State()
    waiting_product_name = State()
    waiting_product_price = State()
    waiting_product_cat = State()
    waiting_del_cat = State()
    waiting_del_product = State()
    waiting_edit_product_id = State()
    waiting_edit_product_name = State()
    waiting_edit_product_price = State()

class OrderStates(StatesGroup):
    waiting_fio = State()
    waiting_comment = State()

# ---- Главное меню ----
@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "🔥 *GUBER JUICE VAPE SHOP* 🔥\n\nТвоя выгодная сделка!\nВыбери категорию и добавляй в корзину 💨",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

# ---- Товары (категории) ----
@dp.message(F.text == "🛍 Товары")
async def show_categories(msg: types.Message):
    cats = get_categories()
    if not cats:
        await msg.answer("⚠️ Категорий пока нет.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"cat_{cid}")] for cid, name in cats
    ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]])
    await msg.answer("📂 *Выбери категорию:*", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("cat_"))
async def show_products(call: types.CallbackQuery):
    cat_id = int(call.data.split("_")[1])
    products = get_products_by_category(cat_id)
    if not products:
        await call.message.edit_text("📭 Товаров в категории пока нет.")
        return
    text = "🧾 *Товары:*\n\n"
    for pid, name, price in products:
        text += f"• {name} — {price}₽\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"➕ {name}", callback_data=f"add_{pid}")] for pid, name, price in products
    ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_cats")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart_handler(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    add_to_cart(user_id, product_id)
    await call.answer("✅ Добавлено в корзину!", show_alert=True)

# ---- Корзина ----
@dp.message(F.text == "🛒 Корзина")
async def show_cart(msg: types.Message):
    cart = get_cart(msg.from_user.id)
    if not cart:
        await msg.answer("🛒 Корзина пуста")
        return
    text = "🛍 *Твоя корзина:*\n\n"
    total = 0
    for pid, name, price, qty in cart:
        text += f"{name} x{qty} = {price*qty}₽\n"
        total += price*qty
    text += f"\n💰 *Итого: {total}₽*"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Очистить корзину", callback_data="clear_cart")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    await msg.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "clear_cart")
async def clear_cart_handler(call: types.CallbackQuery):
    clear_cart(call.from_user.id)
    await call.message.edit_text("🗑 Корзина очищена")
    await call.answer()

# ---- Оформление заказа ----
@dp.message(F.text == "📦 Оформить заказ")
async def order_fio(msg: types.Message, state: FSMContext):
    cart = get_cart(msg.from_user.id)
    if not cart:
        await msg.answer("⚠️ Корзина пуста")
        return
    await state.update_data(cart=cart)
    await msg.answer("📝 *Введи своё ФИО:*", parse_mode="Markdown")
    await state.set_state(OrderStates.waiting_fio)

@dp.message(OrderStates.waiting_fio)
async def order_comment(msg: types.Message, state: FSMContext):
    await state.update_data(fio=msg.text)
    await msg.answer("📝 *Комментарий к заказу (можно пропустить):*\nВведи '-' если без комментария", parse_mode="Markdown")
    await state.set_state(OrderStates.waiting_comment)

@dp.message(OrderStates.waiting_comment)
async def order_finish(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    cart = data["cart"]
    fio = data["fio"]
    comment = "" if msg.text == "-" else msg.text

    items_text = "\n".join([f"{name} x{qty} = {price*qty}₽" for pid, name, price, qty in cart])
    total = sum([price*qty for pid, name, price, qty in cart])

    save_order(
        user_id=msg.from_user.id,
        fio=fio,
        tg_username=msg.from_user.username,
        comment=comment,
        cart_items=[{"name": n, "qty": q, "price": p} for pid, n, p, q in cart]
    )
    clear_cart(msg.from_user.id)

    # Отправка админу
    admin_text = f"🆕 *НОВЫЙ ЗАКАЗ!*\n\n👤 ФИО: {fio}\n🆔 TG: @{msg.from_user.username}\n💬 Коммент: {comment}\n\n🧾 Состав:\n{items_text}\n\n💰 Итого: {total}₽"
    await bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown")

    await msg.answer("✅ *Заказ оформлен!* Скоро с тобой свяжется оператор.", parse_mode="Markdown")
    await state.clear()

# ---- Админ панель (доступ только админу) ----
@dp.message(F.text == "👤 Админ панель")
async def admin_check(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("🚫 Доступ запрещён")
        return
    await msg.answer("⚙️ *Админ панель*", reply_markup=admin_panel(), parse_mode="Markdown")

# ---- Обработка админ-кнопок (сокращённо) ----
@dp.callback_query(F.data == "admin_orders")
async def admin_orders(call: types.CallbackQuery):
    orders = get_orders()
    if not orders:
        await call.message.edit_text("📭 Заказов нет")
        return
    for oid, uid, fio, tg, cmt, items, status in orders:
        await call.message.answer(
            f"📦 Заказ #{oid}\nСтатус: {status}\nФИО: {fio}\nTG: @{tg}\nСостав: {items}\nКоммент: {cmt}"
        )

# ---- Добавь здесь все остальные admin_edit, admin_delete, admin_add_cat и т.д. по аналогии ----

# ---- Назад ----
@dp.callback_query(F.data == "back_main")
async def back_main(call: types.CallbackQuery):
    await call.message.delete()
    await start(call.message)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())