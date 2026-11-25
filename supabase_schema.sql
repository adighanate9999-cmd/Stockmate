-- ==============================================================================
-- StockMate / Smart Stock & Money Manager - Supabase SQL Schema
-- ==============================================================================
-- Run this script in the Supabase Dashboard -> SQL Editor to initialize all tables,
-- constraints, indexes, and Row Level Security (RLS) policies.
-- ==============================================================================

-- 1. Users / Shop Profile
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
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
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. Product Categories
CREATE TABLE IF NOT EXISTS categories (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    icon TEXT DEFAULT 'package',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3. Products Master
CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    product_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category_id BIGINT REFERENCES categories(id) ON DELETE SET NULL,
    purchase_price NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    selling_price NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    quantity NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    min_stock NUMERIC(12, 2) NOT NULL DEFAULT 5.00,
    unit TEXT NOT NULL DEFAULT 'pcs',
    description TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 4. Customers (Khata / Credit Book)
CREATE TABLE IF NOT EXISTS customers (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    address TEXT,
    credit_limit NUMERIC(12, 2) DEFAULT 10000.00,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 5. Sales Invoices
CREATE TABLE IF NOT EXISTS sales (
    id BIGSERIAL PRIMARY KEY,
    invoice_no TEXT UNIQUE NOT NULL,
    customer_id BIGINT REFERENCES customers(id) ON DELETE SET NULL,
    customer_name TEXT DEFAULT 'Walk-in Customer',
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    discount_type TEXT DEFAULT 'fixed',
    discount_value NUMERIC(12, 2) DEFAULT 0.00,
    discount_amount NUMERIC(12, 2) DEFAULT 0.00,
    grand_total NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    total_cost NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    profit NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    payment_method TEXT NOT NULL CHECK(payment_method IN ('Cash', 'UPI', 'Credit')),
    payment_status TEXT NOT NULL DEFAULT 'Paid' CHECK(payment_status IN ('Paid', 'Pending', 'Partial')),
    amount_paid NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 6. Sale Line Items
CREATE TABLE IF NOT EXISTS sale_items (
    id BIGSERIAL PRIMARY KEY,
    sale_id BIGINT NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id BIGINT REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    cost_price NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    quantity NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    unit TEXT DEFAULT 'pcs',
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    profit NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 7. Stock Movements (Inventory Audit Ledger)
CREATE TABLE IF NOT EXISTS stock_movements (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    movement_type TEXT NOT NULL CHECK(movement_type IN ('Stock In', 'Sale Deduction', 'Adjustment', 'Return')),
    quantity NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    previous_qty NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    new_qty NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    unit_cost NUMERIC(12, 2),
    reference_id TEXT,
    reference_type TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 8. Operating Expenses
CREATE TABLE IF NOT EXISTS expenses (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    payment_method TEXT NOT NULL DEFAULT 'Cash' CHECK(payment_method IN ('Cash', 'UPI', 'Bank')),
    expense_date DATE NOT NULL,
    receipt_ref TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 9. Customer Payments (Khata Repayments)
CREATE TABLE IF NOT EXISTS customer_payments (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    payment_method TEXT NOT NULL DEFAULT 'Cash' CHECK(payment_method IN ('Cash', 'UPI', 'Bank')),
    payment_date DATE NOT NULL,
    reference_no TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 10. Cash Register (Daily Opening Float)
CREATE TABLE IF NOT EXISTS cash_register (
    id BIGSERIAL PRIMARY KEY,
    entry_date DATE UNIQUE NOT NULL,
    opening_cash NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- Indexes for High Performance Querying
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_code ON products(product_code);
CREATE INDEX IF NOT EXISTS idx_sales_invoice ON sales(invoice_no);
CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales(created_at);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product ON sale_items(product_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_prod ON stock_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_customer_payments_cust ON customer_payments(customer_id);

-- ==============================================================================
-- Row Level Security (RLS) Configuration
-- ==============================================================================
-- Enable RLS and grant full CRUD to anon & authenticated clients (service key always bypasses)
DO $$
DECLARE
    t text;
BEGIN
    FOR t IN 
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
          AND table_name IN ('users', 'categories', 'products', 'customers', 'sales', 
                             'sale_items', 'stock_movements', 'expenses', 'customer_payments', 'cash_register')
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', t);
        EXECUTE format('DROP POLICY IF EXISTS "Public access policy" ON %I;', t);
        EXECUTE format('CREATE POLICY "Public access policy" ON %I FOR ALL USING (true) WITH CHECK (true);', t);
    END LOOP;
END $$;

-- ==============================================================================
-- Initial Seed Data (Default Admin User and Base Categories)
-- ==============================================================================
INSERT INTO users (username, email, password_hash, shop_name, shop_tagline, owner_name, phone, address, gstin)
VALUES (
    'admin',
    'admin@smartstock.com',
    'scrypt:32768:8:1$kXpM6X4B2mJq$a9b1c7d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1',
    'Smart Kirana & General Store',
    'Manage Your Stock. Track Your Money. Grow Your Business.',
    'Rajesh Sharma',
    '+91 98765 43210',
    'Shop #12, Market Road, Sector 4, Gandhinagar, Gujarat - 382004',
    '24AAACP1234M1Z5'
) ON CONFLICT (email) DO NOTHING;

INSERT INTO categories (name, description, icon) VALUES
    ('Grains & Flours', 'Wheat flour, premium basmati rice, lentils, and pulses', 'wheat'),
    ('Edible Oils & Ghee', 'Sunflower oil, mustard oil, cow ghee and butter', 'droplet'),
    ('Dairy & Bakery', 'Fresh packaged milk, curd, bread and artisan toast', 'milk'),
    ('Spices & Seasonings', 'Whole and ground Indian spices, iodized salt and condiments', 'flame'),
    ('Packaged Food & Snacks', 'Biscuits, noodles, instant mixes and ready-to-eat snacks', 'cookie'),
    ('Beverages & Tea', 'Premium tea leaves, roast coffee powder, health drinks', 'coffee'),
    ('Personal Care & Hygiene', 'Soaps, shampoos, hair oils, body washes, and dental care', 'sparkles'),
    ('Cleaning & Household', 'Detergent powders, dishwash bars, floor disinfectants', 'spray-can')
ON CONFLICT (name) DO NOTHING;
