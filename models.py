import sqlite3
from datetime import datetime, timedelta
from database import get_db

def format_currency(val):
    """Format a float as Indian Rupee string."""
    try:
        val = float(val or 0)
        return f"₹{val:,.2f}"
    except (ValueError, TypeError):
        return "₹0.00"

def get_dashboard_data():
    """Retrieve all high-level metrics for the executive dashboard."""
    conn = get_db()
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')

    # 1. Total Products & Stock Metrics
    cursor.execute("""
        SELECT 
            COUNT(*) as total_count,
            COALESCE(SUM(purchase_price * quantity), 0) as total_cost_value,
            COALESCE(SUM(selling_price * quantity), 0) as total_retail_value,
            SUM(CASE WHEN quantity <= 0 THEN 1 ELSE 0 END) as out_of_stock_count,
            SUM(CASE WHEN quantity > 0 AND quantity <= min_stock THEN 1 ELSE 0 END) as low_stock_count
        FROM products 
        WHERE is_active = 1
    """)
    prod_row = cursor.fetchone()
    total_products = prod_row['total_count'] or 0
    total_stock_value = prod_row['total_cost_value'] or 0.0
    total_retail_value = prod_row['total_retail_value'] or 0.0
    out_of_stock_count = prod_row['out_of_stock_count'] or 0
    low_stock_count = prod_row['low_stock_count'] or 0

    # 2. Today's Sales & Profit
    cursor.execute("""
        SELECT 
            COUNT(*) as order_count,
            COALESCE(SUM(grand_total), 0) as sales_total,
            COALESCE(SUM(total_cost), 0) as cost_total,
            COALESCE(SUM(profit), 0) as profit_total,
            COALESCE(SUM(CASE WHEN payment_method = 'Cash' THEN amount_paid ELSE 0 END), 0) as cash_sales,
            COALESCE(SUM(CASE WHEN payment_method = 'UPI' THEN amount_paid ELSE 0 END), 0) as upi_sales,
            COALESCE(SUM(CASE WHEN payment_method = 'Credit' THEN grand_total ELSE 0 END), 0) as credit_sales
        FROM sales 
        WHERE DATE(created_at) = ?
    """, (today_str,))
    sales_row = cursor.fetchone()
    today_sales = sales_row['sales_total'] or 0.0
    today_profit = sales_row['profit_total'] or 0.0
    today_order_count = sales_row['order_count'] or 0
    today_cash_sales = sales_row['cash_sales'] or 0.0
    today_upi_sales = sales_row['upi_sales'] or 0.0
    today_credit_sales = sales_row['credit_sales'] or 0.0

    # 3. Today's Expenses
    cursor.execute("""
        SELECT 
            COALESCE(SUM(amount), 0) as expense_total,
            COALESCE(SUM(CASE WHEN payment_method = 'Cash' THEN amount ELSE 0 END), 0) as cash_expenses
        FROM expenses 
        WHERE expense_date = ?
    """, (today_str,))
    exp_row = cursor.fetchone()
    today_expenses = exp_row['expense_total'] or 0.0
    today_cash_expenses = exp_row['cash_expenses'] or 0.0

    # Today's Net Profit = Today's Gross Profit from Sales - Today's Expenses
    today_net_profit = today_profit - today_expenses

    # 4. Today's Customer Credit Repayments
    cursor.execute("""
        SELECT 
            COALESCE(SUM(amount), 0) as repayment_total,
            COALESCE(SUM(CASE WHEN payment_method = 'Cash' THEN amount ELSE 0 END), 0) as cash_repayments
        FROM customer_payments 
        WHERE payment_date = ?
    """, (today_str,))
    cpay_row = cursor.fetchone()
    today_repayments = cpay_row['repayment_total'] or 0.0
    today_cash_repayments = cpay_row['cash_repayments'] or 0.0

    # 5. Opening Cash for Today
    cursor.execute("SELECT opening_cash FROM cash_register WHERE entry_date = ?", (today_str,))
    reg_row = cursor.fetchone()
    if reg_row:
        opening_cash = reg_row['opening_cash']
    else:
        opening_cash = 5000.0
        # Automatically insert opening cash default if not set
        cursor.execute("INSERT OR IGNORE INTO cash_register (entry_date, opening_cash, notes) VALUES (?, ?, ?)",
                       (today_str, opening_cash, 'System default opening float'))
        conn.commit()

    # Cash in Hand Formula: Opening Cash + Cash Sales + Cash Repayments - Cash Expenses
    cash_in_hand = opening_cash + today_cash_sales + today_cash_repayments - today_cash_expenses

    # 6. Total Pending Customer Credit across all customers
    cursor.execute("""
        SELECT 
            COALESCE((SELECT SUM(grand_total) FROM sales WHERE payment_method = 'Credit'), 0) -
            COALESCE((SELECT SUM(amount) FROM customer_payments), 0) as pending_credit
    """)
    credit_row = cursor.fetchone()
    pending_customer_credit = max(0.0, credit_row['pending_credit'] or 0.0)

    # 7. Low Stock Alerts List
    cursor.execute("""
        SELECT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.is_active = 1 AND p.quantity <= p.min_stock
        ORDER BY p.quantity ASC
        LIMIT 6
    """)
    low_stock_products = [dict(r) for r in cursor.fetchall()]

    # 8. Top Selling Products (Last 30 Days)
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
        LIMIT 5
    """)
    top_selling_products = [dict(r) for r in cursor.fetchall()]

    # 9. Recent Transactions (Latest 6 Sales)
    cursor.execute("""
        SELECT id, invoice_no, customer_name, grand_total, payment_method, payment_status, created_at
        FROM sales
        ORDER BY created_at DESC
        LIMIT 6
    """)
    recent_transactions = [dict(r) for r in cursor.fetchall()]

    # 10. Last 7 Days Daily Sales & Profit Trend for Chart.js
    daily_trend = []
    for i in range(6, -1, -1):
        target_day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        target_day_name = (datetime.now() - timedelta(days=i)).strftime('%a, %d %b')
        cursor.execute("""
            SELECT 
                COALESCE(SUM(grand_total), 0) as sales,
                COALESCE(SUM(profit), 0) as profit
            FROM sales
            WHERE DATE(created_at) = ?
        """, (target_day,))
        trow = cursor.fetchone()
        
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as expenses
            FROM expenses
            WHERE expense_date = ?
        """, (target_day,))
        erow = cursor.fetchone()

        daily_trend.append({
            'date': target_day,
            'label': target_day_name,
            'sales': trow['sales'] or 0.0,
            'profit': trow['profit'] or 0.0,
            'expenses': erow['expenses'] or 0.0
        })

    # 11. Category distribution for doughnut chart
    cursor.execute("""
        SELECT c.name as category_name, COALESCE(SUM(si.subtotal), 0) as total_sales
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        GROUP BY c.id
        ORDER BY total_sales DESC
        LIMIT 6
    """)
    category_sales = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        'total_products': total_products,
        'total_stock_value': total_stock_value,
        'total_retail_value': total_retail_value,
        'out_of_stock_count': out_of_stock_count,
        'low_stock_count': low_stock_count,
        'today_sales': today_sales,
        'today_profit': today_profit,
        'today_expenses': today_expenses,
        'today_net_profit': today_net_profit,
        'today_order_count': today_order_count,
        'today_cash_sales': today_cash_sales,
        'today_upi_sales': today_upi_sales,
        'today_credit_sales': today_credit_sales,
        'today_repayments': today_repayments,
        'opening_cash': opening_cash,
        'cash_in_hand': cash_in_hand,
        'pending_customer_credit': pending_customer_credit,
        'low_stock_products': low_stock_products,
        'top_selling_products': top_selling_products,
        'recent_transactions': recent_transactions,
        'daily_trend': daily_trend,
        'category_sales': category_sales
    }

def get_customer_summary():
    """Get customer list with total credit purchases, payments, and live balance."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            c.id, c.name, c.phone, c.email, c.address, c.credit_limit, c.notes, c.created_at,
            COALESCE((SELECT SUM(grand_total) FROM sales WHERE customer_id = c.id AND payment_method = 'Credit'), 0) as total_credit,
            COALESCE((SELECT SUM(amount) FROM customer_payments WHERE customer_id = c.id), 0) as total_paid
        FROM customers c
        ORDER BY (COALESCE((SELECT SUM(grand_total) FROM sales WHERE customer_id = c.id AND payment_method = 'Credit'), 0) - 
                  COALESCE((SELECT SUM(amount) FROM customer_payments WHERE customer_id = c.id), 0)) DESC, c.name ASC
    """)
    raw_customers = cursor.fetchall()
    customers = []
    total_credit_market = 0.0
    for row in raw_customers:
        bal = max(0.0, (row['total_credit'] or 0.0) - (row['total_paid'] or 0.0))
        total_credit_market += bal
        customers.append({
            'id': row['id'],
            'name': row['name'],
            'phone': row['phone'],
            'email': row['email'],
            'address': row['address'],
            'credit_limit': row['credit_limit'],
            'notes': row['notes'],
            'created_at': row['created_at'],
            'total_credit': row['total_credit'] or 0.0,
            'total_paid': row['total_paid'] or 0.0,
            'balance': bal
        })
    conn.close()
    return customers, total_credit_market

def get_product_categories():
    """Retrieve all categories."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories ORDER BY name ASC")
    categories = cursor.fetchall()
    conn.close()
    return categories
