import sqlite3
import json

conn = sqlite3.connect("shop.db", check_same_thread=False)
cursor = conn.cursor()

# Таблицы
cursor.execute("""
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    price INTEGER,
    category_id INTEGER,
    FOREIGN KEY(category_id) REFERENCES categories(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS cart (
    user_id INTEGER,
    product_id INTEGER,
    quantity INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    fio TEXT,
    tg_username TEXT,
    comment TEXT,
    items TEXT,
    status TEXT DEFAULT "new"
)
""")
conn.commit()

# --- Категории ---
def get_categories():
    cursor.execute("SELECT id, name FROM categories")
    return cursor.fetchall()

def add_category(name):
    cursor.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
    conn.commit()

def delete_category(cat_id):
    cursor.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit()

# --- Товары ---
def get_products_by_category(cat_id):
    cursor.execute("SELECT id, name, price FROM products WHERE category_id=?", (cat_id,))
    return cursor.fetchall()

def add_product(name, price, category_id):
    cursor.execute("INSERT INTO products (name, price, category_id) VALUES (?,?,?)", (name, price, category_id))
    conn.commit()

def delete_product(product_id):
    cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()

def update_product(product_id, name, price):
    cursor.execute("UPDATE products SET name=?, price=? WHERE id=?", (name, price, product_id))
    conn.commit()

def get_all_products():
    cursor.execute("SELECT id, name, price, category_id FROM products")
    return cursor.fetchall()

# --- Корзина ---
def add_to_cart(user_id, product_id):
    cursor.execute("SELECT quantity FROM cart WHERE user_id=? AND product_id=?", (user_id, product_id))
    res = cursor.fetchone()
    if res:
        cursor.execute("UPDATE cart SET quantity = quantity + 1 WHERE user_id=? AND product_id=?", (user_id, product_id))
    else:
        cursor.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?,?,1)", (user_id, product_id))
    conn.commit()

def remove_from_cart(user_id, product_id):
    cursor.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (user_id, product_id))
    conn.commit()

def clear_cart(user_id):
    cursor.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()

def get_cart(user_id):
    cursor.execute("""
        SELECT p.id, p.name, p.price, c.quantity
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id=?
    """, (user_id,))
    return cursor.fetchall()

# --- Заказы ---
def save_order(user_id, fio, tg_username, comment, cart_items):
    items_json = json.dumps(cart_items)
    cursor.execute("""
        INSERT INTO orders (user_id, fio, tg_username, comment, items)
        VALUES (?,?,?,?,?)
    """, (user_id, fio, tg_username, comment, items_json))
    conn.commit()

def get_orders():
    cursor.execute("SELECT id, user_id, fio, tg_username, comment, items, status FROM orders ORDER BY id DESC")
    return cursor.fetchall()

def update_order_status(order_id, status):
    cursor.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()