import sqlite3
from datetime import datetime, timedelta
import random
from werkzeug.security import generate_password_hash
from database import get_db, init_db

def seed():
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    # Clear existing data to allow clean re-seeding
    tables = [
        'sale_items', 'sales', 'stock_movements', 'customer_payments',
        'expenses', 'cash_register', 'products', 'categories', 'customers', 'users'
    ]
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")
        cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")

    print("Cleared existing tables. Seeding fresh realistic data...")

    # 1. Create Default Shop Owner User
    admin_password = generate_password_hash('admin123')
    cursor.execute("""
        INSERT INTO users (username, email, password_hash, shop_name, shop_tagline, owner_name, phone, address, gstin)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'admin',
        'admin@smartstock.com',
        admin_password,
        'Smart Kirana & General Store',
        'Manage Your Stock. Track Your Money. Grow Your Business.',
        'Rajesh Sharma',
        '+91 98765 43210',
        'Shop #12, Market Road, Sector 4, Gandhinagar, Gujarat - 382004',
        '24AAACP1234M1Z5'
    ))

    # 2. Categories
    categories = [
        ('Grains & Flours', 'Wheat flour, premium basmati rice, lentils, and pulses', 'wheat'),
        ('Edible Oils & Ghee', 'Sunflower oil, mustard oil, cow ghee and butter', 'droplet'),
        ('Dairy & Bakery', 'Fresh packaged milk, curd, bread and artisan toast', 'milk'),
        ('Spices & Seasonings', 'Whole and ground Indian spices, iodized salt and condiments', 'flame'),
        ('Packaged Food & Snacks', 'Biscuits, noodles, instant mixes and ready-to-eat snacks', 'cookie'),
        ('Beverages & Tea', 'Premium tea leaves, roast coffee powder, health drinks', 'coffee'),
        ('Personal Care & Hygiene', 'Soaps, shampoos, hair oils, body washes, and dental care', 'sparkles'),
        ('Cleaning & Household', 'Detergent powders, dishwash bars, floor disinfectants', 'spray-can')
    ]
    category_id_map = {}
    for name, desc, icon in categories:
        cursor.execute("INSERT INTO categories (name, description, icon) VALUES (?, ?, ?)", (name, desc, icon))
        category_id_map[name] = cursor.lastrowid

    # 3. Products (26 high-velocity Indian Kirana items)
    products_data = [
        # Grains & Flours
        ('PRD-101', 'Basmati Rice Premium (1 kg)', 'Grains & Flours', 95.0, 120.0, 48.0, 10.0, 'kg', 'Aged aromatic long-grain basmati rice'),
        ('PRD-102', 'Sona Masoori Rice (5 kg)', 'Grains & Flours', 270.0, 330.0, 22.0, 6.0, 'bag', 'Lightweight polished south Indian rice bag'),
        ('PRD-103', 'Aashirvaad Shudh Chakki Atta (5 kg)', 'Grains & Flours', 215.0, 255.0, 20.0, 6.0, 'bag', '100% whole wheat grain chakki fresh flour'),
        ('PRD-104', 'Toor Dal Premium Desi (1 kg)', 'Grains & Flours', 138.0, 168.0, 30.0, 8.0, 'kg', 'Unpolished protein-rich pigeon peas'),
        ('PRD-105', 'Moong Dal Dhuli (1 kg)', 'Grains & Flours', 115.0, 142.0, 18.0, 6.0, 'kg', 'Yellow split moong dal for everyday cooking'),

        # Edible Oils & Ghee
        ('PRD-201', 'Fortune Sunlite Sunflower Oil (1 L)', 'Edible Oils & Ghee', 135.0, 160.0, 28.0, 8.0, 'ltr', 'Refined sunflower cooking oil pouch'),
        ('PRD-202', 'Dhara Kachi Ghani Mustard Oil (1 L)', 'Edible Oils & Ghee', 142.0, 172.0, 24.0, 6.0, 'ltr', 'Pure cold pressed pungent sarson tel'),
        ('PRD-203', 'Amul Pure Cow Ghee Tin (1 L)', 'Edible Oils & Ghee', 560.0, 640.0, 14.0, 4.0, 'tin', 'Traditional granulated pure cow butter ghee'),

        # Dairy & Bakery
        ('PRD-301', 'Amul Gold Full Cream Milk (500 ml)', 'Dairy & Bakery', 31.0, 33.0, 30.0, 10.0, 'pkt', 'Pasteurized homogenized 6% fat milk'),
        ('PRD-302', 'Amul Butter Salted (100 g)', 'Dairy & Bakery', 50.0, 58.0, 25.0, 8.0, 'pcs', 'Utterly butterly delicious salted table butter'),

        # Spices & Seasonings
        ('PRD-401', 'Madhur Pure Refined Sugar (1 kg)', 'Spices & Seasonings', 42.0, 50.0, 55.0, 15.0, 'kg', 'Sulphur-free pharmaceutical grade white sugar'),
        ('PRD-402', 'Tata Salt Vacuum Evaporated (1 kg)', 'Spices & Seasonings', 22.0, 28.0, 45.0, 10.0, 'pkt', 'Desh ka namak with iodine guarantee'),
        ('PRD-403', 'MDH Agmark Haldi Turmeric (100 g)', 'Spices & Seasonings', 30.0, 38.0, 32.0, 8.0, 'pkt', 'Finely ground turmeric root powder'),
        ('PRD-404', 'MDH Deggi Mirch (100 g)', 'Spices & Seasonings', 44.0, 56.0, 26.0, 8.0, 'pkt', 'Natural Kashmiri red chilli powder for rich colour'),

        # Packaged Food & Snacks
        ('PRD-501', 'Parle-G Gold Glucose Biscuits (250 g)', 'Packaged Food & Snacks', 24.0, 30.0, 52.0, 15.0, 'pkt', 'India\'s favorite tea companion biscuit'),
        ('PRD-502', 'Britannia Good Day Butter (200 g)', 'Packaged Food & Snacks', 32.0, 40.0, 38.0, 10.0, 'pkt', 'Rich butter cashew cookies'),
        ('PRD-503', 'Maggi 2-Minute Masala Noodles (280 g 4-pack)', 'Packaged Food & Snacks', 50.0, 60.0, 35.0, 10.0, 'pack', 'Original tastemaker instant noodle bundle'),

        # Beverages & Tea
        ('PRD-601', 'Tata Tea Gold Leaf Tea (250 g)', 'Beverages & Tea', 130.0, 160.0, 25.0, 6.0, 'pkt', 'Assam teas with gently rolled aromatic long leaves'),
        ('PRD-602', 'Brooke Bond Red Label Tea (500 g)', 'Beverages & Tea', 240.0, 290.0, 18.0, 5.0, 'pkt', 'Strong CTC black tea blend for rich kadak chai'),

        # Personal Care & Hygiene
        ('PRD-701', 'Dettol Original Bathing Soap (100 g x 3)', 'Personal Care & Hygiene', 115.0, 140.0, 22.0, 6.0, 'pack', 'Antibacterial trusted antiseptic bath bar value pack'),
        ('PRD-702', 'Dove Cream Beauty Bar (100 g)', 'Personal Care & Hygiene', 52.0, 65.0, 16.0, 5.0, 'pcs', '1/4th moisturizing cream gentle bathing bar'),
        ('PRD-703', 'Clinic Plus Strong & Long Shampoo (340 ml)', 'Personal Care & Hygiene', 185.0, 225.0, 15.0, 4.0, 'btl', 'Milk protein formula family hair shampoo'),
        ('PRD-704', 'Colgate Strong Teeth Toothpaste (200 g)', 'Personal Care & Hygiene', 98.0, 120.0, 20.0, 6.0, 'pcs', 'Amino shakti formula calcium boost dental paste'),

        # Cleaning & Household
        ('PRD-801', 'Surf Excel Easy Wash Detergent (1 kg)', 'Cleaning & Household', 125.0, 150.0, 26.0, 6.0, 'pkt', 'Superfine powder removes tough stains easily'),
        ('PRD-802', 'Vim Lemon Dishwash Bar (300 g)', 'Cleaning & Household', 25.0, 32.0, 42.0, 10.0, 'pcs', 'Power of 100 lemons grease cutter bar'),

        # Intentional Low-Stock & Out-of-Stock for realistic Alert validation
        ('PRD-705', 'Lifebuoy Handwash Refill Pouch (180 ml)', 'Personal Care & Hygiene', 45.0, 58.0, 3.0, 8.0, 'pkt', 'Fast germ protection liquid refill (LOW STOCK)'),
        ('PRD-706', 'Head & Shoulders Cool Menthol (180 ml)', 'Personal Care & Hygiene', 160.0, 198.0, 2.0, 5.0, 'btl', 'Anti-dandruff cool blast hair wash (LOW STOCK)'),
        ('PRD-707', 'Oral-B Shiny Clean Toothbrush (4-Pack)', 'Personal Care & Hygiene', 72.0, 95.0, 0.0, 5.0, 'pack', 'End rounded bristles multi-pack (OUT OF STOCK)')
    ]

    product_id_map = {}
    for code, name, cat_name, cost, price, qty, min_stk, unit, desc in products_data:
        cat_id = category_id_map.get(cat_name)
        cursor.execute("""
            INSERT INTO products (product_code, name, category_id, purchase_price, selling_price, quantity, min_stock, unit, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (code, name, cat_id, cost, price, qty, min_stk, unit, desc))
        product_id_map[code] = {
            'id': cursor.lastrowid,
            'name': name,
            'cost': cost,
            'price': price,
            'unit': unit,
            'qty': qty
        }

        # Initial stock movement entry
        cursor.execute("""
            INSERT INTO stock_movements (product_id, movement_type, quantity, previous_qty, new_qty, unit_cost, reference_id, reference_type, notes)
            VALUES (?, 'Stock In', ?, 0, ?, ?, 'INIT-BATCH-01', 'Initial Setup', 'Initial store opening inventory audit')
        """, (cursor.lastrowid, qty + 15, qty + 15, cost))

    # 4. Customers
    customers_data = [
        ('Ramesh Patel', '+91 98250 11223', 'ramesh.patel@gmail.com', 'Flat 202, Gokul Residency, Sector 4', 5000.0, 'Regular grocery customer, pays every Friday'),
        ('Sunita Sharma', '+91 97240 55667', 'sunita.sharma@yahoo.com', 'B-14, Shivalik Society, Sector 4', 6000.0, 'Primary school teacher, pays by 1st of month'),
        ('Amit Verma', '+91 99090 33445', 'amit.verma@tea.in', 'Near Old Bus Stand, Stall #3', 10000.0, 'Tea stall owner, buys milk & sugar daily on weekly credit'),
        ('Priya Desai', '+91 98980 77889', 'priya.desai@outlook.com', 'Row House #7, Green Park', 5000.0, 'Prompt payer via UPI QR code'),
        ('Vikram Singh', '+91 97123 44556', 'vikram.contractor@gmail.com', 'Plot 45, GIDC Industrial Estate', 15000.0, 'Civil contractor, buys cleaning & personal supplies for camp')
    ]
    customer_ids = []
    for name, phone, email, addr, limit, notes in customers_data:
        cursor.execute("""
            INSERT INTO customers (name, phone, email, address, credit_limit, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, phone, email, addr, limit, notes))
        customer_ids.append((cursor.lastrowid, name))

    # 5. Seed Historical Sales, Expenses & Cash Registers for the past 14 days up to today
    base_date = datetime.now()
    inv_counter = 1001

    # Daily opening cash balances
    for day_offset in range(14, -1, -1):
        day = (base_date - timedelta(days=day_offset)).strftime('%Y-%m-%d')
        cursor.execute("""
            INSERT OR IGNORE INTO cash_register (entry_date, opening_cash, notes)
            VALUES (?, 5000.0, 'Morning cash drawer float')
        """, (day,))

    # Seed realistic sales across the last 14 days
    for day_offset in range(14, -1, -1):
        cur_day = base_date - timedelta(days=day_offset)
        day_date_str = cur_day.strftime('%Y-%m-%d')
        
        # Number of transactions on this day (e.g. 3 to 7 sales per day)
        num_sales = 5 if day_offset == 0 else random.randint(3, 6)
        
        for s in range(num_sales):
            inv_no = f"INV-{cur_day.strftime('%Y%m')}-{inv_counter}"
            inv_counter += 1

            # Determine customer
            is_credit = False
            if random.random() < 0.25:
                # Credit sale to registered customer
                cust = random.choice(customer_ids)
                cust_id, cust_name = cust[0], cust[1]
                pay_method = 'Credit'
                pay_status = 'Pending'
                is_credit = True
            else:
                pay_method = random.choice(['Cash', 'UPI', 'Cash'])
                pay_status = 'Paid'
                if random.random() < 0.3:
                    cust = random.choice(customer_ids)
                    cust_id, cust_name = cust[0], cust[1]
                else:
                    cust_id, cust_name = None, 'Walk-in Customer'

            # Pick 2 to 5 random products for this bill
            chosen_codes = random.sample(list(product_id_map.keys()), random.randint(2, 4))
            line_items = []
            subtotal = 0.0
            total_cost = 0.0

            for code in chosen_codes:
                pinfo = product_id_map[code]
                qty = random.randint(1, 3)
                cost = pinfo['cost'] * qty
                selling = pinfo['price'] * qty
                subtotal += selling
                total_cost += cost
                line_items.append({
                    'product_id': pinfo['id'],
                    'name': pinfo['name'],
                    'cost_price': pinfo['cost'],
                    'unit_price': pinfo['price'],
                    'quantity': qty,
                    'unit': pinfo['unit'],
                    'subtotal': selling,
                    'profit': selling - cost
                })

            discount = 0.0
            if subtotal > 500 and random.random() < 0.3:
                discount = round(subtotal * 0.05, 2)
            grand_total = subtotal - discount
            profit = (subtotal - total_cost) - discount
            amt_paid = 0.0 if is_credit else grand_total

            sale_time = cur_day.replace(hour=random.randint(9, 21), minute=random.randint(0, 59)).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("""
                INSERT INTO sales (invoice_no, customer_id, customer_name, subtotal, discount_type, discount_value,
                                   discount_amount, grand_total, total_cost, profit, payment_method, payment_status,
                                   amount_paid, notes, created_at)
                VALUES (?, ?, ?, ?, 'fixed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                inv_no, cust_id, cust_name, subtotal, discount, discount, grand_total,
                total_cost, profit, pay_method, pay_status, amt_paid, 'Counter POS billing', sale_time
            ))
            sale_id = cursor.lastrowid

            for item in line_items:
                cursor.execute("""
                    INSERT INTO sale_items (sale_id, product_id, product_name, unit_price, cost_price, quantity, unit, subtotal, profit, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sale_id, item['product_id'], item['name'], item['unit_price'], item['cost_price'],
                    item['quantity'], item['unit'], item['subtotal'], item['profit'], sale_time
                ))

    # 6. Seed Realistic Operating Expenses across the last 14 days
    expense_templates = [
        ('Shop Electricity Bill', 'Utilities', 2450.0, 'UPI', 12, 'Torrent Power commercial connection'),
        ('Store Boy Helper Wages', 'Salaries', 3000.0, 'Cash', 7, 'Weekly assistant staff allowance'),
        ('Wholesale Mandi Tempo Transport', 'Transportation', 450.0, 'Cash', 10, 'Tempo freight from Kalupur Mandi'),
        ('Wholesale Mandi Tempo Transport', 'Transportation', 400.0, 'Cash', 3, 'Stock delivery freight charges'),
        ('Tea & Snacks for Customers & Staff', 'Tea & Refreshments', 140.0, 'Cash', 6, 'Local tea stall bill'),
        ('Tea & Snacks for Customers & Staff', 'Tea & Refreshments', 180.0, 'Cash', 1, 'Cutting chai & biscuits'),
        ('Packaging Carry Bags & Boxes', 'Packaging', 650.0, 'UPI', 8, 'Eco-friendly paper bags & poly rolls'),
        ('Shop Cleaning Supplies & Phenyl', 'Maintenance', 320.0, 'Cash', 5, 'Broom, mop, and floor cleaner concentrate'),
        ('Monthly Shop Rental Advance', 'Rent', 8500.0, 'Bank', 14, 'Commercial landlord shop rent')
    ]

    for title, cat, amt, pay_meth, days_ago, notes in expense_templates:
        exp_date = (base_date - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        cursor.execute("""
            INSERT INTO expenses (title, category, amount, payment_method, expense_date, receipt_ref, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, cat, amt, pay_meth, exp_date, f"EXP-REF-{random.randint(100, 999)}", notes))

    # 7. Customer Repayments (Khata payments made by customers against their credit)
    repayments = [
        (customer_ids[0][0], 1200.0, 'UPI', 5, 'UPI-REF-98741', 'Friday weekly settlement'),
        (customer_ids[1][0], 800.0, 'Cash', 4, 'CASH-RCPT-12', 'Partial repayment by Sunita Sharma'),
        (customer_ids[2][0], 2500.0, 'Cash', 2, 'CASH-RCPT-15', 'Tea stall weekly part clearance'),
        (customer_ids[4][0], 1500.0, 'UPI', 1, 'UPI-REF-65412', 'Site ration bill clearance')
    ]
    for cid, amt, meth, days_ago, ref, notes in repayments:
        pdate = (base_date - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        cursor.execute("""
            INSERT INTO customer_payments (customer_id, amount, payment_method, payment_date, reference_no, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cid, amt, meth, pdate, ref, notes))

    conn.commit()
    conn.close()
    print("Seed completed successfully! 26 Products, 5 Customers, 60+ Sales, Expenses, and Repayments initialized.")

if __name__ == '__main__':
    seed()
