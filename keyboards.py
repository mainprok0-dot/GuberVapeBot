from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Товары")],
            [KeyboardButton(text="🛒 Корзина"), KeyboardButton(text="📦 Оформить заказ")],
            [KeyboardButton(text="👤 Админ панель")]
        ],
        resize_keyboard=True
    )

def admin_panel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить категорию", callback_data="admin_add_cat")],
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add_product")],
        [InlineKeyboardButton(text="🗑 Удалить категорию/товар", callback_data="admin_delete")],
        [InlineKeyboardButton(text="✏️ Редактировать товар", callback_data="admin_edit")],
        [InlineKeyboardButton(text="📋 Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])