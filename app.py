import os
import csv
import io
import json
from datetime import datetime, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
)
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db
import models
import seed_data
import backend

# Ensure environment variables from .env are loaded
backend.load_env()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'smart-stock-money-manager-secret-key-2026')

# Initialize DB on start
init_db()

def login_required(f):
    """Decorator to protect internal routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please sign in to access your shop dashboard.', 'info')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_current_shop():
    """Retrieve current shop profile details from DB."""
    conn = get_db()
    cursor = conn.cursor()
    user_id = session.get('user_id', 1)
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if not user:
        return {
            'shop_name': 'Smart Kirana & General Store',
            'shop_tagline': 'Manage Your Stock. Track Your Money. Grow Your Business.',
            'owner_name': 'Rajesh Sharma',
            'phone': '+91 98765 43210',
            'address': 'Shop #12, Market Road, Sector 4, Gandhinagar',
            'gstin': '24AAACP1234M1Z5',
            'currency_symbol': '₹'
        }
    return dict(user)

@app.context_processor
def inject_global_data():
    """Inject shop profile and low-stock count across all Jinja templates."""
    if 'user_id' in session:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM products WHERE is_active = 1 AND quantity <= min_stock")
        row = cursor.fetchone()
        conn.close()
        low_count = row['count'] if row else 0
        session['low_stock_count'] = low_count
    return {
        'current_year': datetime.now().year,
        'today_str': datetime.now().strftime('%Y-%m-%d'),
        'shop_profile': get_current_shop()
    }

# ==============================================================================
# AUTHENTICATION ROUTES
# ==============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['owner_name'] = user['owner_name']
            session['shop_name'] = user['shop_name']
            session['shop_tagline'] = user['shop_tagline']
            session['phone'] = user['phone']
            session['address'] = user['address']
            session['gstin'] = user['gstin']

            flash(f"Welcome back, {user['owner_name']}!", 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'error')

    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        shop_name = request.form.get('shop_name', '').strip()
        owner_name = request.form.get('owner_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        gstin = request.form.get('gstin', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if cursor.fetchone():
            conn.close()
            flash('Username or email is already registered.', 'error')
            return render_template('auth/register.html')

        hashed = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, shop_name, owner_name, phone, address, gstin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (username, email, hashed, shop_name, owner_name, phone, address, gstin))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        session['user_id'] = user_id
        session['username'] = username
        session['owner_name'] = owner_name
        session['shop_name'] = shop_name
        session['shop_tagline'] = 'Manage Your Stock. Track Your Money. Grow Your Business.'
        session['phone'] = phone
        session['address'] = address
        session['gstin'] = gstin

        flash('Store account created successfully! Welcome to Smart Stock & Money Manager.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('auth/register.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        flash(f"If {email} is registered with us, a password reset link has been dispatched.", 'success')
        return redirect(url_for('login'))
    return render_template('auth/forgot_password.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out securely.', 'info')
    return redirect(url_for('login'))

# ==============================================================================
# DASHBOARD
# ==============================================================================

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    data = models.get_dashboard_data()
    return render_template('dashboard.html', active_page='dashboard', data=data)

# ==============================================================================
# PRODUCT MANAGEMENT
# ==============================================================================

@app.route('/products')
@login_required
def products_view():
    search_query = request.args.get('q', '').strip()
    category_filter = request.args.get('category', '').strip()
    status_filter = request.args.get('status', '').strip()
    sort_by = request.args.get('sort', 'name_asc').strip()

    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.is_active = 1
    """
    params = []

    if search_query:
        query += " AND (p.name LIKE ? OR p.product_code LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    if category_filter:
        query += " AND p.category_id = ?"
        params.append(category_filter)

    if status_filter == 'in_stock':
        query += " AND p.quantity > p.min_stock"
    elif status_filter == 'low_stock':
        query += " AND p.quantity > 0 AND p.quantity <= p.min_stock"
    elif status_filter == 'out_of_stock':
        query += " AND p.quantity <= 0"

    # Sorting
    if sort_by == 'stock_asc':
        query += " ORDER BY p.quantity ASC"
    elif sort_by == 'stock_desc':
        query += " ORDER BY p.quantity DESC"
    elif sort_by == 'profit_desc':
        query += " ORDER BY (p.selling_price - p.purchase_price) DESC"
    else:
        query += " ORDER BY p.name ASC"

    cursor.execute(query, params)
    products = cursor.fetchall()

    # Calculate overall inventory valuation KPIs
    cursor.execute("""
        SELECT 
            COUNT(*) as total_skus,
            COALESCE(SUM(quantity), 0) as total_units,
            COALESCE(SUM(purchase_price * quantity), 0) as total_cost_val,
            COALESCE(SUM(selling_price * quantity), 0) as total_retail_val
        FROM products WHERE is_active = 1
    """)
    sum_row = cursor.fetchone()
    total_skus = sum_row['total_skus'] or 0
    total_units = sum_row['total_units'] or 0.0
    total_cost_val = sum_row['total_cost_val'] or 0.0
    total_retail_val = sum_row['total_retail_val'] or 0.0
    expected_profit = total_retail_val - total_cost_val
    avg_margin = (expected_profit / total_retail_val * 100) if total_retail_val > 0 else 0

    categories = models.get_product_categories()
    conn.close()

    summary = {
        'total_skus': total_skus,
        'total_units': total_units,
        'total_cost_val': total_cost_val,
        'total_retail_val': total_retail_val,
        'expected_profit': expected_profit,
        'avg_margin': avg_margin
    }

    return render_template(
        'products.html',
        active_page='products',
        products=products,
        categories=categories,
        summary=summary,
        search_query=search_query,
        selected_category=category_filter,
        selected_status=status_filter,
        sort_by=sort_by
    )

@app.route('/products/add', methods=['POST'])
@login_required
def add_product():
    product_code = request.form.get('product_code', '').strip().upper()
    name = request.form.get('name', '').strip()
    category_id = request.form.get('category_id')
    purchase_price = float(request.form.get('purchase_price', 0))
    selling_price = float(request.form.get('selling_price', 0))
    quantity = float(request.form.get('quantity', 0))
    min_stock = float(request.form.get('min_stock', 5))
    unit = request.form.get('unit', 'pcs').strip()
    description = request.form.get('description', '').strip()

    conn = get_db()
    cursor = conn.cursor()

    # Check unique code
    cursor.execute("SELECT id FROM products WHERE product_code = ?", (product_code,))
    if cursor.fetchone():
        conn.close()
        flash(f'Product Code {product_code} already exists. Please use a unique code.', 'error')
        return redirect(url_for('products_view'))

    cursor.execute("""
        INSERT INTO products (product_code, name, category_id, purchase_price, selling_price, quantity, min_stock, unit, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (product_code, name, category_id, purchase_price, selling_price, quantity, min_stock, unit, description))
    prod_id = cursor.lastrowid

    # Record initial stock in movement if quantity > 0
    if quantity > 0:
        cursor.execute("""
            INSERT INTO stock_movements (product_id, movement_type, quantity, previous_qty, new_qty, unit_cost, reference_id, reference_type, notes)
            VALUES (?, 'Stock In', ?, 0, ?, ?, 'INIT-STOCK', 'Product Creation', 'Initial opening inventory')
        """, (prod_id, quantity, quantity, purchase_price))

    conn.commit()
    conn.close()

    flash(f'Product "{name}" added successfully to catalog!', 'success')
    return redirect(url_for('products_view'))

@app.route('/products/edit/<int:id>', methods=['POST'])
@login_required
def edit_product(id):
    name = request.form.get('name', '').strip()
    category_id = request.form.get('category_id')
    purchase_price = float(request.form.get('purchase_price', 0))
    selling_price = float(request.form.get('selling_price', 0))
    min_stock = float(request.form.get('min_stock', 5))
    unit = request.form.get('unit', 'pcs').strip()
    description = request.form.get('description', '').strip()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE products 
        SET name = ?, category_id = ?, purchase_price = ?, selling_price = ?, min_stock = ?, unit = ?, description = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (name, category_id, purchase_price, selling_price, min_stock, unit, description, id))
    conn.commit()
    conn.close()

    flash(f'Product "{name}" updated successfully!', 'success')
    return redirect(url_for('products_view'))

@app.route('/products/delete/<int:id>', methods=['POST'])
@login_required
def delete_product(id):
    conn = get_db()
    cursor = conn.cursor()
    # Check if this product has sales records
    cursor.execute("SELECT COUNT(*) as count FROM sale_items WHERE product_id = ?", (id,))
    count = cursor.fetchone()['count']
    if count > 0:
        # Soft delete to preserve sales history
        cursor.execute("UPDATE products SET is_active = 0 WHERE id = ?", (id,))
        flash('Product deactivated and archived. Sales history preserved.', 'info')
    else:
        cursor.execute("DELETE FROM products WHERE id = ?", (id,))
        flash('Product permanently deleted from database.', 'success')
    conn.commit()
    conn.close()
    return redirect(url_for('products_view'))

@app.route('/api/products/<int:id>')
@login_required
def get_product_json(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (id,))
    prod = cursor.fetchone()
    conn.close()
    if prod:
        return jsonify(dict(prod))
    return jsonify({'error': 'Not found'}), 404

# ==============================================================================
# STOCK MANAGEMENT & INVENTORY
# ==============================================================================

@app.route('/inventory')
@login_required
def inventory_view():
    conn = get_db()
    cursor = conn.cursor()

    # Product list with stock details
    cursor.execute("""
        SELECT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.is_active = 1
        ORDER BY (p.quantity <= p.min_stock) DESC, p.quantity ASC
    """)
    products = cursor.fetchall()

    # Counts
    total_skus = len(products)
    total_units = sum(p['quantity'] for p in products)
    in_stock_count = sum(1 for p in products if p['quantity'] > p['min_stock'])
    low_stock_count = sum(1 for p in products if 0 < p['quantity'] <= p['min_stock'])
    out_of_stock_count = sum(1 for p in products if p['quantity'] <= 0)

    # Restock recommendations: products with quantity <= min_stock
    restock_recommendations = []
    for p in products:
        if p['quantity'] <= p['min_stock']:
            target = p['min_stock'] * 3
            reorder_qty = max(target - p['quantity'], p['min_stock'] * 2)
            est_cost = reorder_qty * p['purchase_price']
            restock_recommendations.append({
                'id': p['id'],
                'product_code': p['product_code'],
                'name': p['name'],
                'quantity': p['quantity'],
                'min_stock': p['min_stock'],
                'unit': p['unit'],
                'purchase_price': p['purchase_price'],
                'recommended_reorder': reorder_qty,
                'estimated_cost': est_cost
            })

    # Recent stock movements
    cursor.execute("""
        SELECT sm.*, p.name as product_name
        FROM stock_movements sm
        JOIN products p ON sm.product_id = p.id
        ORDER BY sm.created_at DESC
        LIMIT 25
    """)
    movements = cursor.fetchall()

    conn.close()

    return render_template(
        'inventory.html',
        active_page='inventory',
        products=products,
        total_skus=total_skus,
        total_units=total_units,
        in_stock_count=in_stock_count,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        restock_recommendations=restock_recommendations,
        movements=movements
    )

@app.route('/inventory/stock-in', methods=['POST'])
@login_required
def stock_in():
    product_id = int(request.form.get('product_id'))
    quantity = float(request.form.get('quantity', 0))
    new_cost_str = request.form.get('new_cost', '').strip()
    notes = request.form.get('notes', 'Stock arrival').strip()

    if quantity <= 0:
        flash('Quantity must be greater than zero.', 'error')
        return redirect(url_for('inventory_view'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    prod = cursor.fetchone()
    if not prod:
        conn.close()
        flash('Product not found.', 'error')
        return redirect(url_for('inventory_view'))

    prev_qty = prod['quantity']
    new_qty = prev_qty + quantity
    purchase_price = float(new_cost_str) if new_cost_str else prod['purchase_price']

    cursor.execute("""
        UPDATE products 
        SET quantity = ?, purchase_price = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (new_qty, purchase_price, product_id))

    cursor.execute("""
        INSERT INTO stock_movements (product_id, movement_type, quantity, previous_qty, new_qty, unit_cost, reference_id, reference_type, notes)
        VALUES (?, 'Stock In', ?, ?, ?, ?, 'STOCK-IN-ENTRY', 'Restock', ?)
    """, (product_id, quantity, prev_qty, new_qty, purchase_price, notes))

    conn.commit()
    conn.close()

    flash(f"Stock-in of {quantity} {prod['unit']} for \"{prod['name']}\" recorded successfully! New stock: {new_qty}", 'success')
    return redirect(url_for('inventory_view'))

# ==============================================================================
# FAST POS BILLING & SALES
# ==============================================================================

@app.route('/pos')
@login_required
def pos_view():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.is_active = 1
        ORDER BY p.name ASC
    """)
    products = cursor.fetchall()

    categories = models.get_product_categories()

    cursor.execute("SELECT id, name, phone FROM customers ORDER BY name ASC")
    customers = cursor.fetchall()
    conn.close()

    return render_template(
        'pos.html',
        active_page='pos',
        products=products,
        categories=categories,
        customers=customers
    )

@app.route('/api/pos/complete-sale', methods=['POST'])
@login_required
def api_complete_sale():
    data = request.get_json()
    if not data or 'items' not in data or not data['items']:
        return jsonify({'success': False, 'message': 'Cart is empty!'}), 400

    items = data['items']
    customer_id = data.get('customer_id')
    customer_name = data.get('customer_name', 'Walk-in Customer')
    payment_method = data.get('payment_method', 'Cash')
    discount_type = data.get('discount_type', 'fixed')
    discount_val = float(data.get('discount_val', 0))
    notes = data.get('notes', 'Counter POS billing')

    conn = get_db()
    cursor = conn.cursor()

    try:
        # Validate stock availability for each item
        line_items_data = []
        subtotal = 0.0
        total_cost = 0.0

        for it in items:
            pid = int(it['product_id'])
            req_qty = float(it['quantity'])
            cursor.execute("SELECT * FROM products WHERE id = ? AND is_active = 1", (pid,))
            p = cursor.fetchone()
            if not p:
                conn.close()
                return jsonify({'success': False, 'message': f"Product {it.get('name')} not found."}), 400
            if p['quantity'] < req_qty:
                conn.close()
                return jsonify({'success': False, 'message': f"Insufficient stock for {p['name']}. Available: {p['quantity']} {p['unit']}."}), 400

            item_cost = p['purchase_price'] * req_qty
            item_subtotal = p['selling_price'] * req_qty
            subtotal += item_subtotal
            total_cost += item_cost

            line_items_data.append({
                'product_id': p['id'],
                'name': p['name'],
                'cost_price': p['purchase_price'],
                'unit_price': p['selling_price'],
                'quantity': req_qty,
                'unit': p['unit'],
                'subtotal': item_subtotal,
                'profit': item_subtotal - item_cost,
                'prev_qty': p['quantity']
            })

        # Calculate discount
        if discount_type == 'percent':
            discount_amount = (subtotal * min(discount_val, 100)) / 100.0
        else:
            discount_amount = min(discount_val, subtotal)

        grand_total = max(0.0, subtotal - discount_amount)
        gross_profit = (subtotal - total_cost) - discount_amount

        # Payment status
        if payment_method == 'Credit':
            payment_status = 'Pending'
            amount_paid = 0.0
        else:
            payment_status = 'Paid'
            amount_paid = grand_total

        # Generate Invoice Number
        now = datetime.now()
        prefix = f"INV-{now.strftime('%Y%m')}"
        cursor.execute("SELECT COUNT(*) as count FROM sales WHERE invoice_no LIKE ?", (f"{prefix}%",))
        cnt = cursor.fetchone()['count'] + 1
        invoice_no = f"{prefix}-{1000 + cnt}"

        # Insert Sale record
        cursor.execute("""
            INSERT INTO sales (invoice_no, customer_id, customer_name, subtotal, discount_type, discount_value,
                               discount_amount, grand_total, total_cost, profit, payment_method, payment_status,
                               amount_paid, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice_no, customer_id, customer_name, subtotal, discount_type, discount_val,
            discount_amount, grand_total, total_cost, gross_profit, payment_method, payment_status,
            amount_paid, notes, now.strftime('%Y-%m-%d %H:%M:%S')
        ))
        sale_id = cursor.lastrowid

        # Insert Line items & Deduct Stock
        for it in line_items_data:
            cursor.execute("""
                INSERT INTO sale_items (sale_id, product_id, product_name, unit_price, cost_price, quantity, unit, subtotal, profit, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sale_id, it['product_id'], it['name'], it['unit_price'], it['cost_price'],
                it['quantity'], it['unit'], it['subtotal'], it['profit'], now.strftime('%Y-%m-%d %H:%M:%S')
            ))

            new_qty = it['prev_qty'] - it['quantity']
            cursor.execute("UPDATE products SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_qty, it['product_id']))

            cursor.execute("""
                INSERT INTO stock_movements (product_id, movement_type, quantity, previous_qty, new_qty, unit_cost, reference_id, reference_type, notes)
                VALUES (?, 'Sale Deduction', ?, ?, ?, ?, ?, 'Sale Invoice', 'Counter billing sale')
            """, (it['product_id'], it['quantity'], it['prev_qty'], new_qty, it['cost_price'], invoice_no))

        conn.commit()

        # Build response payload for receipt
        invoice_payload = {
            'sale_id': sale_id,
            'invoice_no': invoice_no,
            'date_str': now.strftime('%d %b %Y, %I:%M %p'),
            'customer_name': customer_name,
            'payment_method': payment_method,
            'subtotal': subtotal,
            'discount_amount': discount_amount,
            'grand_total': grand_total,
            'items': [{
                'name': it['name'],
                'quantity': it['quantity'],
                'unit': it['unit'],
                'unit_price': it['unit_price'],
                'subtotal': it['subtotal']
            } for it in line_items_data]
        }

        conn.close()
        return jsonify({
            'success': True,
            'invoice_no': invoice_no,
            'invoice': invoice_payload
        })

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/sales')
@login_required
def sales_view():
    search_query = request.args.get('q', '').strip()
    selected_method = request.args.get('method', '').strip()
    selected_period = request.args.get('period', 'all').strip()

    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT s.*, COUNT(si.id) as item_count
        FROM sales s
        LEFT JOIN sale_items si ON s.id = si.sale_id
        WHERE 1=1
    """
    params = []

    if search_query:
        query += " AND (s.invoice_no LIKE ? OR s.customer_name LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    if selected_method:
        query += " AND s.payment_method = ?"
        params.append(selected_method)

    if selected_period == 'today':
        query += " AND DATE(s.created_at) = DATE('now', 'localtime')"
    elif selected_period == 'yesterday':
        query += " AND DATE(s.created_at) = DATE('now', '-1 day', 'localtime')"
    elif selected_period == 'last7':
        query += " AND DATE(s.created_at) >= DATE('now', '-7 days', 'localtime')"
    elif selected_period == 'month':
        query += " AND strftime('%Y-%m', s.created_at) = strftime('%Y-%m', 'now', 'localtime')"

    query += " GROUP BY s.id ORDER BY s.created_at DESC"

    cursor.execute(query, params)
    sales = cursor.fetchall()

    # Overall totals
    total_sales_amount = sum(s['grand_total'] for s in sales)
    cash_sales_amount = sum(s['grand_total'] for s in sales if s['payment_method'] == 'Cash')
    upi_sales_amount = sum(s['grand_total'] for s in sales if s['payment_method'] == 'UPI')
    credit_sales_amount = sum(s['grand_total'] for s in sales if s['payment_method'] == 'Credit')

    conn.close()

    return render_template(
        'sales.html',
        active_page='sales',
        sales=sales,
        total_invoices_count=len(sales),
        total_sales_amount=total_sales_amount,
        cash_sales_amount=cash_sales_amount,
        upi_sales_amount=upi_sales_amount,
        credit_sales_amount=credit_sales_amount,
        search_query=search_query,
        selected_method=selected_method,
        selected_period=selected_period
    )

@app.route('/sales/invoice/<int:id>')
@login_required
def print_invoice(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sales WHERE id = ?", (id,))
    sale = cursor.fetchone()
    if not sale:
        conn.close()
        flash('Invoice not found.', 'error')
        return redirect(url_for('sales_view'))

    cursor.execute("SELECT * FROM sale_items WHERE sale_id = ?", (id,))
    items = cursor.fetchall()
    conn.close()

    shop = get_current_shop()
    return render_template('invoice_print.html', sale=sale, items=items, shop=shop)

@app.route('/api/sales/<int:id>')
@login_required
def get_sale_details_json(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sales WHERE id = ?", (id,))
    sale = cursor.fetchone()
    if not sale:
        conn.close()
        return jsonify({'error': 'Invoice not found'}), 404

    cursor.execute("SELECT * FROM sale_items WHERE sale_id = ?", (id,))
    items = cursor.fetchall()
    conn.close()

    return jsonify({
        'sale': dict(sale),
        'items': [dict(it) for it in items]
    })

# ==============================================================================
# MONEY MANAGEMENT & EXPENSES
# ==============================================================================

@app.route('/money')
@login_required
def money_view():
    conn = get_db()
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')

    # 1. Opening Cash
    cursor.execute("SELECT opening_cash FROM cash_register WHERE entry_date = ?", (today_str,))
    reg = cursor.fetchone()
    opening_cash = reg['opening_cash'] if reg else 5000.0

    # 2. Today's Cash Inflows: Cash Sales + Cash Credit Repayments
    cursor.execute("SELECT COALESCE(SUM(amount_paid), 0) as amt FROM sales WHERE payment_method = 'Cash' AND DATE(created_at) = ?", (today_str,))
    today_cash_sales = cursor.fetchone()['amt'] or 0.0

    cursor.execute("SELECT COALESCE(SUM(amount), 0) as amt FROM customer_payments WHERE payment_method = 'Cash' AND payment_date = ?", (today_str,))
    today_cash_repayments = cursor.fetchone()['amt'] or 0.0

    # 3. Today's Cash Outflows: Cash Expenses
    cursor.execute("SELECT COALESCE(SUM(amount), 0) as amt FROM expenses WHERE payment_method = 'Cash' AND expense_date = ?", (today_str,))
    today_cash_expenses = cursor.fetchone()['amt'] or 0.0

    # 4. Master Cash in Hand Formula
    cash_in_hand = opening_cash + today_cash_sales + today_cash_repayments - today_cash_expenses

    # 5. List all expenses
    cursor.execute("SELECT * FROM expenses ORDER BY expense_date DESC, id DESC LIMIT 30")
    expenses = cursor.fetchall()
    total_expenses_all = sum(e['amount'] for e in expenses)

    # 6. Expenses by Category for Donut Chart
    cursor.execute("""
        SELECT category as category_name, SUM(amount) as total_sales
        FROM expenses
        GROUP BY category
        ORDER BY total_sales DESC
    """)
    expense_categories = [dict(r) for r in cursor.fetchall()]

    # 7. Unified Cash Movement Ledger (Latest 25 transactions)
    cash_ledger = []

    # Opening float
    cash_ledger.append({
        'date_str': f"{today_str} 08:00 AM",
        'description': "Morning Cash Float (Opening Balance)",
        'flow': "IN",
        'amount': opening_cash,
        'reference': "DRAWER-FLOAT"
    })

    # Cash sales
    cursor.execute("SELECT invoice_no, customer_name, grand_total, created_at FROM sales WHERE payment_method = 'Cash' ORDER BY created_at DESC LIMIT 15")
    for s in cursor.fetchall():
        cash_ledger.append({
            'date_str': s['created_at'],
            'description': f"Cash Counter Sale - {s['customer_name']}",
            'flow': "IN",
            'amount': s['grand_total'],
            'reference': s['invoice_no']
        })

    # Cash repayments
    cursor.execute("""
        SELECT cp.amount, cp.payment_date, cp.reference_no, c.name as customer_name
        FROM customer_payments cp
        JOIN customers c ON cp.customer_id = c.id
        WHERE cp.payment_method = 'Cash'
        ORDER BY cp.payment_date DESC LIMIT 10
    """)
    for cp in cursor.fetchall():
        cash_ledger.append({
            'date_str': cp['payment_date'],
            'description': f"Customer Khata Repayment - {cp['customer_name']}",
            'flow': "IN",
            'amount': cp['amount'],
            'reference': cp['reference_no'] or "CASH-REPAY"
        })

    # Cash expenses
    cursor.execute("SELECT title, amount, expense_date, receipt_ref FROM expenses WHERE payment_method = 'Cash' ORDER BY expense_date DESC LIMIT 15")
    for exp in cursor.fetchall():
        cash_ledger.append({
            'date_str': exp['expense_date'],
            'description': f"Operating Expense - {exp['title']}",
            'flow': "OUT",
            'amount': exp['amount'],
            'reference': exp['receipt_ref'] or "EXP-VOUCHER"
        })

    # Sort unified ledger descending by date
    cash_ledger.sort(key=lambda x: str(x['date_str']), reverse=True)

    conn.close()

    fin = {
        'cash_in_hand': cash_in_hand,
        'opening_cash': opening_cash,
        'today_cash_sales': today_cash_sales,
        'today_cash_repayments': today_cash_repayments,
        'today_cash_expenses': today_cash_expenses
    }

    return render_template(
        'money.html',
        active_page='money',
        fin=fin,
        expenses=expenses,
        total_expenses_all=total_expenses_all,
        expense_categories=expense_categories,
        cash_ledger=cash_ledger
    )

@app.route('/expenses/add', methods=['POST'])
@login_required
def add_expense():
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'Miscellaneous')
    amount = float(request.form.get('amount', 0))
    payment_method = request.form.get('payment_method', 'Cash')
    expense_date = request.form.get('expense_date', datetime.now().strftime('%Y-%m-%d'))
    receipt_ref = request.form.get('receipt_ref', '').strip()
    notes = request.form.get('notes', '').strip()

    if amount <= 0:
        flash('Expense amount must be greater than zero.', 'error')
        return redirect(url_for('money_view'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO expenses (title, category, amount, payment_method, expense_date, receipt_ref, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (title, category, amount, payment_method, expense_date, receipt_ref, notes))
    conn.commit()
    conn.close()

    flash(f'Expense "{title}" for ₹{amount:.2f} recorded successfully!', 'success')
    return redirect(url_for('money_view'))

@app.route('/expenses/delete/<int:id>', methods=['POST'])
@login_required
def delete_expense(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash('Expense entry deleted.', 'info')
    return redirect(url_for('money_view'))

@app.route('/money/set-opening-cash', methods=['POST'])
@login_required
def set_opening_cash():
    amount = float(request.form.get('opening_cash', 5000))
    notes = request.form.get('notes', 'Shop owner manual adjustment')
    today_str = datetime.now().strftime('%Y-%m-%d')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cash_register (entry_date, opening_cash, notes)
        VALUES (?, ?, ?)
        ON CONFLICT(entry_date) DO UPDATE SET opening_cash = excluded.opening_cash, notes = excluded.notes
    """, (today_str, amount, notes))
    conn.commit()
    conn.close()

    flash(f"Today's opening cash drawer float updated to ₹{amount:,.2f}!", 'success')
    return redirect(url_for('money_view'))

# ==============================================================================
# CUSTOMER CREDIT MANAGEMENT (KHATA)
# ==============================================================================

@app.route('/customers')
@login_required
def customers_view():
    customers, total_pending_credit = models.get_customer_summary()
    active_credit_customers_count = sum(1 for c in customers if c['balance'] > 0)
    total_credit_given = sum(c['total_credit'] for c in customers)
    total_credit_repaid = sum(c['total_paid'] for c in customers)

    return render_template(
        'customers.html',
        active_page='customers',
        customers=customers,
        total_pending_credit=total_pending_credit,
        active_credit_customers_count=active_credit_customers_count,
        total_credit_given=total_credit_given,
        total_credit_repaid=total_credit_repaid
    )

@app.route('/customers/add', methods=['POST'])
@login_required
def add_customer():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    credit_limit = float(request.form.get('credit_limit', 5000))
    notes = request.form.get('notes', '').strip()

    if not name or not phone:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Name and phone are required'}), 400
        flash('Customer name and phone number are required.', 'error')
        return redirect(url_for('customers_view'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO customers (name, phone, address, credit_limit, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (name, phone, address, credit_limit, notes))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'customer': {
                'id': new_id,
                'name': name,
                'phone': phone
            }
        })

    flash(f'Customer account for "{name}" created successfully!', 'success')
    return redirect(url_for('customers_view'))

@app.route('/customers/repay', methods=['POST'])
@login_required
def customer_repay():
    customer_id = int(request.form.get('customer_id'))
    amount = float(request.form.get('amount', 0))
    payment_method = request.form.get('payment_method', 'Cash')
    payment_date = request.form.get('payment_date', datetime.now().strftime('%Y-%m-%d'))
    reference_no = request.form.get('reference_no', '').strip()
    notes = request.form.get('notes', 'Credit Repayment').strip()

    if amount <= 0:
        flash('Repayment amount must be positive.', 'error')
        return redirect(url_for('customers_view'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO customer_payments (customer_id, amount, payment_method, payment_date, reference_no, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (customer_id, amount, payment_method, payment_date, reference_no, notes))
    conn.commit()

    # Get customer name for toast
    cursor.execute("SELECT name FROM customers WHERE id = ?", (customer_id,))
    c = cursor.fetchone()
    cname = c['name'] if c else 'Customer'
    conn.close()

    flash(f"Repayment of ₹{amount:,.2f} recorded for {cname}! Balance updated.", 'success')
    return redirect(url_for('customers_view'))

@app.route('/api/customers/<int:id>/ledger')
@login_required
def get_customer_ledger(id):
    conn = get_db()
    cursor = conn.cursor()

    # Total Credit purchases
    cursor.execute("SELECT COALESCE(SUM(grand_total), 0) as total FROM sales WHERE customer_id = ? AND payment_method = 'Credit'", (id,))
    total_credit = cursor.fetchone()['total'] or 0.0

    # Total repayments
    cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM customer_payments WHERE customer_id = ?", (id,))
    total_paid = cursor.fetchone()['total'] or 0.0

    balance = max(0.0, total_credit - total_paid)

    # Combined timeline
    history = []
    cursor.execute("SELECT invoice_no, grand_total, created_at FROM sales WHERE customer_id = ? AND payment_method = 'Credit'", (id,))
    for s in cursor.fetchall():
        history.append({
            'date_str': s['created_at'],
            'description': f"Credit Purchase ({s['invoice_no']})",
            'type': "DEBIT",
            'amount': s['grand_total']
        })

    cursor.execute("SELECT amount, payment_method, payment_date, reference_no, notes FROM customer_payments WHERE customer_id = ?", (id,))
    for p in cursor.fetchall():
        history.append({
            'date_str': p['payment_date'],
            'description': f"Payment via {p['payment_method']} ({p['reference_no'] or p['notes'] or 'Repayment'})",
            'type': "CREDIT",
            'amount': p['amount']
        })

    history.sort(key=lambda x: str(x['date_str']), reverse=True)
    conn.close()

    return jsonify({
        'total_credit': total_credit,
        'total_paid': total_paid,
        'balance': balance,
        'history': history
    })

# ==============================================================================
# REPORTS & ANALYTICS
# ==============================================================================

@app.route('/reports')
@login_required
def reports_view():
    period = request.args.get('period', 'last7')
    conn = get_db()
    cursor = conn.cursor()

    # Determine date condition
    if period == 'today':
        period_label = 'Today'
        date_cond_sales = "DATE(created_at) = DATE('now', 'localtime')"
        date_cond_expenses = "expense_date = DATE('now', 'localtime')"
        num_days = 1
    elif period == 'month':
        period_label = 'This Month'
        date_cond_sales = "strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now', 'localtime')"
        date_cond_expenses = "strftime('%Y-%m', expense_date) = strftime('%Y-%m', 'now', 'localtime')"
        num_days = 30
    elif period == 'all':
        period_label = 'All Time'
        date_cond_sales = "1=1"
        date_cond_expenses = "1=1"
        num_days = 14
    else: # last7
        period = 'last7'
        period_label = 'Last 7 Days'
        date_cond_sales = "DATE(created_at) >= DATE('now', '-7 days', 'localtime')"
        date_cond_expenses = "expense_date >= DATE('now', '-7 days', 'localtime')"
        num_days = 7

    # Profit & Loss metrics for this period
    cursor.execute(f"""
        SELECT 
            COUNT(*) as order_count,
            COALESCE(SUM(grand_total), 0) as gross_sales,
            COALESCE(SUM(total_cost), 0) as cost_of_goods,
            COALESCE(SUM(profit), 0) as gross_profit,
            COALESCE(SUM(CASE WHEN payment_method = 'Cash' THEN grand_total ELSE 0 END), 0) as cash_sales,
            COALESCE(SUM(CASE WHEN payment_method = 'UPI' THEN grand_total ELSE 0 END), 0) as upi_sales,
            COALESCE(SUM(CASE WHEN payment_method = 'Credit' THEN grand_total ELSE 0 END), 0) as credit_sales
        FROM sales
        WHERE {date_cond_sales}
    """)
    srow = cursor.fetchone()

    cursor.execute(f"SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE {date_cond_expenses}")
    erow = cursor.fetchone()

    gross_sales = srow['gross_sales'] or 0.0
    cost_of_goods = srow['cost_of_goods'] or 0.0
    gross_profit = srow['gross_profit'] or 0.0
    operating_expenses = erow['total'] or 0.0
    net_profit = gross_profit - operating_expenses
    gross_margin_pct = (gross_profit / gross_sales * 100) if gross_sales > 0 else 0
    net_margin_pct = (net_profit / gross_sales * 100) if gross_sales > 0 else 0

    pnl = {
        'gross_sales': gross_sales,
        'cost_of_goods': cost_of_goods,
        'gross_profit': gross_profit,
        'operating_expenses': operating_expenses,
        'net_profit': net_profit,
        'gross_margin_pct': gross_margin_pct,
        'net_margin_pct': net_margin_pct,
        'order_count': srow['order_count'] or 0,
        'cash_sales': srow['cash_sales'] or 0.0,
        'upi_sales': srow['upi_sales'] or 0.0,
        'credit_sales': srow['credit_sales'] or 0.0
    }

    # Daily trend progression for chart
    reports_trend = []
    days_range = 7 if num_days <= 7 else 14
    for i in range(days_range - 1, -1, -1):
        target_day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        target_label = (datetime.now() - timedelta(days=i)).strftime('%d %b')
        cursor.execute("SELECT COALESCE(SUM(grand_total), 0) as sales, COALESCE(SUM(profit), 0) as profit FROM sales WHERE DATE(created_at) = ?", (target_day,))
        tr = cursor.fetchone()
        reports_trend.append({
            'date': target_day,
            'label': target_label,
            'sales': tr['sales'] or 0.0,
            'profit': tr['profit'] or 0.0
        })

    # Stock valuation by category
    cursor.execute("""
        SELECT 
            c.name as category_name,
            COUNT(p.id) as sku_count,
            COALESCE(SUM(p.quantity), 0) as total_qty,
            COALESCE(SUM(p.purchase_price * p.quantity), 0) as cost_val,
            COALESCE(SUM(p.selling_price * p.quantity), 0) as retail_val
        FROM categories c
        JOIN products p ON p.category_id = c.id
        WHERE p.is_active = 1
        GROUP BY c.id
        ORDER BY retail_val DESC
    """)
    category_valuation = [dict(r) for r in cursor.fetchall()]

    # Best-selling products
    cursor.execute("""
        SELECT 
            product_name,
            SUM(quantity) as total_qty,
            unit,
            SUM(subtotal) as total_revenue,
            SUM(profit) as total_profit
        FROM sale_items
        GROUP BY product_name
        ORDER BY total_qty DESC
        LIMIT 10
    """)
    top_products = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return render_template(
        'reports.html',
        active_page='reports',
        period=period,
        period_label=period_label,
        pnl=pnl,
        reports_trend=reports_trend,
        category_valuation=category_valuation,
        top_products=top_products
    )

# --- CSV EXPORT ENDPOINTS ---

@app.route('/reports/export/sales')
@login_required
def export_sales_csv():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT invoice_no, customer_name, subtotal, discount_amount, grand_total, profit, payment_method, payment_status, created_at
        FROM sales ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Invoice No', 'Customer Name', 'Subtotal (INR)', 'Discount (INR)', 'Grand Total (INR)', 'Gross Profit (INR)', 'Payment Mode', 'Status', 'Date Time'])
    for r in rows:
        writer.writerow([r['invoice_no'], r['customer_name'], f"{r['subtotal']:.2f}", f"{r['discount_amount']:.2f}", f"{r['grand_total']:.2f}", f"{r['profit']:.2f}", r['payment_method'], r['payment_status'], r['created_at']])

    output.seek(0)
    filename = f"sales_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(output, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={filename}'})

@app.route('/reports/export/expenses')
@login_required
def export_expenses_csv():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT title, category, amount, payment_method, expense_date, receipt_ref, notes FROM expenses ORDER BY expense_date DESC")
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Title', 'Category', 'Amount (INR)', 'Paid Via', 'Expense Date', 'Receipt Ref', 'Notes'])
    for r in rows:
        writer.writerow([r['title'], r['category'], f"{r['amount']:.2f}", r['payment_method'], r['expense_date'], r['receipt_ref'], r['notes']])

    output.seek(0)
    filename = f"expenses_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(output, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={filename}'})

@app.route('/reports/export/inventory')
@login_required
def export_inventory_csv():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.product_code, p.name, c.name as category, p.purchase_price, p.selling_price, p.quantity, p.unit, p.min_stock
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.is_active = 1
        ORDER BY p.name ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['SKU Code', 'Product Name', 'Category', 'Cost Price (INR)', 'Retail Price (INR)', 'Stock Qty', 'Unit', 'Min Threshold', 'Total Cost Value (INR)', 'Potential Retail Value (INR)'])
    for r in rows:
        cost_val = r['purchase_price'] * r['quantity']
        ret_val = r['selling_price'] * r['quantity']
        writer.writerow([r['product_code'], r['name'], r['category'], f"{r['purchase_price']:.2f}", f"{r['selling_price']:.2f}", r['quantity'], r['unit'], r['min_stock'], f"{cost_val:.2f}", f"{ret_val:.2f}"])

    output.seek(0)
    filename = f"inventory_valuation_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(output, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={filename}'})

@app.route('/reports/export/customers')
@login_required
def export_customers_csv():
    customers, _ = models.get_customer_summary()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Customer Name', 'Phone', 'Address', 'Credit Limit (INR)', 'Total Credit Purchases (INR)', 'Total Paid (INR)', 'Outstanding Balance (INR)'])
    for c in customers:
        writer.writerow([c['name'], c['phone'], c['address'], f"{c['credit_limit']:.2f}", f"{c['total_credit']:.2f}", f"{c['total_paid']:.2f}", f"{c['balance']:.2f}"])

    output.seek(0)
    filename = f"customer_khata_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(output, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={filename}'})

# ==============================================================================
# DAILY SUMMARY (END-OF-DAY CLOSING)
# ==============================================================================

@app.route('/daily-summary')
@login_required
def daily_summary_view():
    target_date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    conn = get_db()
    cursor = conn.cursor()

    # 1. Sales metrics for target date
    cursor.execute("""
        SELECT 
            COUNT(*) as order_count,
            COALESCE(SUM(grand_total), 0) as total_sales,
            COALESCE(SUM(total_cost), 0) as total_cost,
            COALESCE(SUM(profit), 0) as gross_profit,
            COALESCE(SUM(CASE WHEN payment_method = 'Cash' THEN amount_paid ELSE 0 END), 0) as cash_sales,
            COALESCE(SUM(CASE WHEN payment_method = 'UPI' THEN amount_paid ELSE 0 END), 0) as upi_sales,
            COALESCE(SUM(CASE WHEN payment_method = 'Credit' THEN grand_total ELSE 0 END), 0) as credit_given_today
        FROM sales
        WHERE DATE(created_at) = ?
    """, (target_date_str,))
    sales_row = cursor.fetchone()

    # 2. Expenses for target date
    cursor.execute("SELECT * FROM expenses WHERE expense_date = ?", (target_date_str,))
    day_expenses = cursor.fetchall()
    total_expenses = sum(e['amount'] for e in day_expenses)
    cash_expenses = sum(e['amount'] for e in day_expenses if e['payment_method'] == 'Cash')

    # 3. Credit repayments received on target date
    cursor.execute("SELECT COALESCE(SUM(amount), 0) as total, COALESCE(SUM(CASE WHEN payment_method = 'Cash' THEN amount ELSE 0 END), 0) as cash_repay FROM customer_payments WHERE payment_date = ?", (target_date_str,))
    rep_row = cursor.fetchone()
    total_repayments = rep_row['total'] or 0.0
    cash_repayments = rep_row['cash_repay'] or 0.0

    # 4. Opening Cash
    cursor.execute("SELECT opening_cash FROM cash_register WHERE entry_date = ?", (target_date_str,))
    reg_row = cursor.fetchone()
    opening_cash = reg_row['opening_cash'] if reg_row else 5000.0

    # 5. Calculations
    total_sales = sales_row['total_sales'] or 0.0
    gross_profit = sales_row['gross_profit'] or 0.0
    net_profit = gross_profit - total_expenses
    cash_sales = sales_row['cash_sales'] or 0.0
    upi_sales = sales_row['upi_sales'] or 0.0
    credit_given_today = sales_row['credit_given_today'] or 0.0
    total_cash_inflow = cash_sales + cash_repayments
    closing_cash_in_hand = opening_cash + total_cash_inflow - cash_expenses

    # 6. Overall market pending customer credit
    cursor.execute("""
        SELECT 
            COALESCE((SELECT SUM(grand_total) FROM sales WHERE payment_method = 'Credit'), 0) -
            COALESCE((SELECT SUM(amount) FROM customer_payments), 0) as pending_credit
    """)
    total_pending_credit = max(0.0, cursor.fetchone()['pending_credit'] or 0.0)

    # 7. Products requiring restocking
    cursor.execute("""
        SELECT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.is_active = 1 AND p.quantity <= p.min_stock
        ORDER BY p.quantity ASC
    """)
    restock_items = cursor.fetchall()

    conn.close()

    summary = {
        'total_sales': total_sales,
        'order_count': sales_row['order_count'] or 0,
        'total_expenses': total_expenses,
        'expense_count': len(day_expenses),
        'gross_profit': gross_profit,
        'net_profit': net_profit,
        'cash_sales': cash_sales,
        'upi_sales': upi_sales,
        'total_cash_inflow': total_cash_inflow,
        'credit_given_today': credit_given_today,
        'cash_repayments': cash_repayments,
        'opening_cash': opening_cash,
        'cash_expenses': cash_expenses,
        'closing_cash_in_hand': closing_cash_in_hand,
        'total_pending_credit': total_pending_credit,
        'day_expenses': day_expenses,
        'restock_items': restock_items
    }

    try:
        dt = datetime.strptime(target_date_str, '%Y-%m-%d')
        date_display = dt.strftime('%A, %d %B %Y')
    except Exception:
        date_display = target_date_str

    shop = get_current_shop()

    return render_template(
        'daily_summary.html',
        active_page='daily_summary',
        selected_date=target_date_str,
        date_display=date_display,
        current_timestamp=datetime.now().strftime('%d %b %Y, %I:%M %p'),
        summary=summary,
        shop=shop
    )

# ==============================================================================
# SETTINGS & DEMO MANAGEMENT
# ==============================================================================

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings_view():
    conn = get_db()
    cursor = conn.cursor()
    user_id = session.get('user_id', 1)

    if request.method == 'POST':
        shop_name = request.form.get('shop_name', '').strip()
        shop_tagline = request.form.get('shop_tagline', '').strip()
        owner_name = request.form.get('owner_name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        gstin = request.form.get('gstin', '').strip()

        cursor.execute("""
            UPDATE users
            SET shop_name = ?, shop_tagline = ?, owner_name = ?, phone = ?, address = ?, gstin = ?
            WHERE id = ?
        """, (shop_name, shop_tagline, owner_name, phone, address, gstin, user_id))
        conn.commit()

        session['shop_name'] = shop_name
        session['shop_tagline'] = shop_tagline
        session['owner_name'] = owner_name
        session['phone'] = phone
        session['address'] = address
        session['gstin'] = gstin

        flash('Store profile settings updated successfully!', 'success')

    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    shop = cursor.fetchone()
    conn.close()

    supabase_status = backend.test_connection()
    return render_template(
        'settings.html',
        active_page='settings',
        shop=shop or get_current_shop(),
        supabase_status=supabase_status
    )

@app.route('/settings/reseed', methods=['POST'])
@login_required
def reseed_data_route():
    seed_data.seed()
    flash('Sample retail data reloaded successfully! 26 Products, 5 Customers, 60+ Sales, Expenses, and Stock Movements ready for demonstration.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/settings/migrate-supabase', methods=['POST'])
@login_required
def migrate_supabase_route():
    success = backend.migrate_sqlite_to_supabase()
    if success:
        flash('Data migrated successfully to Supabase cloud!', 'success')
    else:
        flash('Supabase migration failed. Please ensure your credentials in .env are valid and the schema is created.', 'danger')
    return redirect(url_for('settings_view'))

@app.route('/api/supabase/status')
def api_supabase_status():
    """API endpoint to check Supabase configuration and connectivity."""
    return jsonify(backend.test_connection())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
