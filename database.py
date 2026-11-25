import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash
import backend

# Ensure .env variables are loaded
backend.load_env()

# On Vercel Serverless environment, project root is read-only. Use /tmp for writable SQLite.
if os.environ.get('VERCEL'):
    DB_PATH = '/tmp/smart_stock.db'
    if not os.path.exists(DB_PATH):
        bundle_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smart_stock.db')
        if os.path.exists(bundle_db):
            import shutil
            shutil.copy2(bundle_db, DB_PATH)
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smart_stock.db')

def get_db():
    """Get a database connection with Row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Initialize the database schema if tables do not exist."""
    conn = get_db()
    cursor = conn.cursor()

    # Users / Shop Owner table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        shop_name TEXT NOT NULL DEFAULT 'Smart Kirana & General Store',
        shop_tagline TEXT DEFAULT 'Manage Your Stock. Track Your Money. Grow Your Business.',
        owner_name TEXT NOT NULL DEFAULT 'Rajesh Sharma',
        phone TEXT DEFAULT '+91 98765 43210',
        address TEXT DEFAULT 'Shop #12, Market Road, Sector 4, Gandhinagar',
        gstin TEXT DEFAULT '24AAACP1234M1Z5',
        currency_symbol TEXT DEFAULT '₹',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Product Categories
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        icon TEXT DEFAULT 'package'
    )
    """)

    # Products table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        category_id INTEGER,
        purchase_price REAL NOT NULL,
        selling_price REAL NOT NULL,
        quantity REAL NOT NULL DEFAULT 0,
        min_stock REAL NOT NULL DEFAULT 5,
        unit TEXT NOT NULL DEFAULT 'pcs',
        description TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL
    )
    """)

    # Customers (Khata / Credit book)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT,
        address TEXT,
        credit_limit REAL DEFAULT 10000.0,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Sales Invoices
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_no TEXT UNIQUE NOT NULL,
        customer_id INTEGER,
        customer_name TEXT DEFAULT 'Walk-in Customer',
        subtotal REAL NOT NULL,
        discount_type TEXT DEFAULT 'fixed',
        discount_value REAL DEFAULT 0,
        discount_amount REAL DEFAULT 0,
        grand_total REAL NOT NULL,
        total_cost REAL NOT NULL DEFAULT 0,
        profit REAL NOT NULL DEFAULT 0,
        payment_method TEXT NOT NULL CHECK(payment_method IN ('Cash', 'UPI', 'Credit')),
        payment_status TEXT NOT NULL DEFAULT 'Paid' CHECK(payment_status IN ('Paid', 'Pending', 'Partial')),
        amount_paid REAL NOT NULL DEFAULT 0,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE SET NULL
    )
    """)

    # Sale Items (Line items for each invoice)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        product_id INTEGER,
        product_name TEXT NOT NULL,
        unit_price REAL NOT NULL,
        cost_price REAL NOT NULL,
        quantity REAL NOT NULL,
        unit TEXT DEFAULT 'pcs',
        subtotal REAL NOT NULL,
        profit REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE SET NULL
    )
    """)

    # Stock Movement History (Audit log of inventory additions, deductions, adjustments)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        movement_type TEXT NOT NULL CHECK(movement_type IN ('Stock In', 'Sale Deduction', 'Adjustment', 'Return')),
        quantity REAL NOT NULL,
        previous_qty REAL NOT NULL,
        new_qty REAL NOT NULL,
        unit_cost REAL,
        reference_id TEXT,
        reference_type TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
    )
    """)

    # Expenses (Daily shop operating expenses)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        payment_method TEXT NOT NULL DEFAULT 'Cash' CHECK(payment_method IN ('Cash', 'UPI', 'Bank')),
        expense_date DATE NOT NULL,
        receipt_ref TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Customer Payments (Khata Repayment entries)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customer_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        payment_method TEXT NOT NULL DEFAULT 'Cash' CHECK(payment_method IN ('Cash', 'UPI', 'Bank')),
        payment_date DATE NOT NULL,
        reference_no TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
    )
    """)

    # Cash Register (Daily opening cash settings and audit)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cash_register (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_date DATE UNIQUE NOT NULL,
        opening_cash REAL NOT NULL DEFAULT 0,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database schema initialized successfully at:", DB_PATH)
