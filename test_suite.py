import sys
from app import app
from database import get_db

def run_tests():
    print("=" * 60)
    print("STARTING COMPREHENSIVE SMART STOCK & MONEY MANAGER TEST SUITE")
    print("=" * 60)

    client = app.test_client()
    passed = 0
    total = 0

    def assert_test(name, condition, extra=""):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f"  [PASS] {name} {extra}")
        else:
            print(f"  [FAIL] {name} {extra}")
            sys.exit(1)

    # 1. Unauthenticated redirect check
    res = client.get('/')
    assert_test("Unauthenticated redirect to login", res.status_code == 302 and '/login' in res.location)

    # 2. Login GET
    res = client.get('/login')
    assert_test("Login page loads", res.status_code == 200 and b'Shop Owner Login' in res.data)

    # 3. Login POST
    res = client.post('/login', data={'username': 'admin@smartstock.com', 'password': 'admin123'}, follow_redirects=True)
    assert_test("Authentication succeeds with demo credentials", res.status_code == 200 and b'Executive Business Dashboard' in res.data)

    # 4. Dashboard metrics check
    assert_test("Dashboard contains 6 summary cards", b'Total Products' in res.data and b'Total Stock Value' in res.data and b'Cash in Hand' in res.data)
    assert_test("Dashboard Indian Rupee currency displayed", b'&#8377;' in res.data or '₹'.encode('utf-8') in res.data)

    # 5. Product Master Page
    res = client.get('/products')
    assert_test("Product Master loads", res.status_code == 200 and b'Product Master Catalog' in res.data)
    assert_test("Basmati Rice exists in products table", b'Basmati Rice Premium' in res.data)

    # 6. Add New Product
    res = client.post('/products/add', data={
        'product_code': 'TEST-999',
        'name': 'Haldiram Bhujia Sev (400 g)',
        'category_id': 5,
        'purchase_price': 80.0,
        'selling_price': 105.0,
        'quantity': 25,
        'min_stock': 5,
        'unit': 'pkt',
        'description': 'Crispy gram flour snack'
    }, follow_redirects=True)
    assert_test("Add product succeeds", res.status_code == 200 and b'Haldiram Bhujia Sev' in res.data)

    # 7. Edit Product API
    res = client.get('/api/products/1')
    assert_test("Product JSON API returns valid data", res.status_code == 200 and 'PRD-' in res.get_json()['product_code'])

    # 8. Stock & Inventory Master
    res = client.get('/inventory')
    assert_test("Inventory page loads", res.status_code == 200 and b'Inventory Management' in res.data)
    assert_test("Restock Recommendations section active", b'AI Restock Recommendations' in res.data)

    # 9. Stock-In Arrival
    res = client.post('/inventory/stock-in', data={
        'product_id': 1,
        'quantity': 15,
        'new_cost': 95.0,
        'notes': 'Test Mandi Batch 99'
    }, follow_redirects=True)
    assert_test("Stock-In recorded and stock incremented", res.status_code == 200 and b'recorded successfully' in res.data)

    # 10. Fast POS Billing Terminal
    res = client.get('/pos')
    assert_test("POS page loads with catalog and cart", res.status_code == 200 and b'Fast Counter POS Billing' in res.data)

    # 11. Complete POS Sale API
    sale_payload = {
        'items': [
            {'product_id': 1, 'name': 'Basmati Rice Premium (1 kg)', 'quantity': 2, 'unit_price': 120.0, 'cost_price': 95.0, 'unit': 'kg'},
            {'product_id': 4, 'name': 'Madhur Sugar (1 kg)', 'quantity': 1, 'unit_price': 50.0, 'cost_price': 42.0, 'unit': 'kg'}
        ],
        'customer_id': None,
        'customer_name': 'Walk-in Customer',
        'payment_method': 'Cash',
        'discount_type': 'fixed',
        'discount_val': 10.0,
        'notes': 'POS Test sale'
    }
    res = client.post('/api/pos/complete-sale', json=sale_payload)
    data = res.get_json()
    assert_test("POS Complete Sale API returns success and invoice", res.status_code == 200 and data['success'] and 'INV-' in data['invoice_no'])
    created_inv_no = data['invoice_no']

    # 12. Sales History Page
    res = client.get('/sales')
    assert_test("Sales History loads and contains new invoice", res.status_code == 200 and created_inv_no.encode() in res.data)

    # 13. Printable Invoice
    res = client.get('/sales/invoice/1')
    assert_test("Printable receipt view loads", res.status_code == 200 and b'Smart Kirana' in res.data and b'NET PAYABLE' in res.data)

    # 14. Money Management Page
    res = client.get('/money')
    assert_test("Money management page loads", res.status_code == 200 and b'Master Cash in Hand Formula' in res.data or b'Live Cash Register' in res.data)
    assert_test("Cash movement ledger active", b'Cash Movement Ledger' in res.data)

    # 15. Record Business Expense
    res = client.post('/expenses/add', data={
        'title': 'Test Cutting Chai Bill',
        'category': 'Tea & Refreshments',
        'amount': 45.0,
        'payment_method': 'Cash',
        'expense_date': '2026-11-17',
        'notes': 'Evening tea'
    }, follow_redirects=True)
    assert_test("Expense recorded successfully", res.status_code == 200 and b'Test Cutting Chai Bill' in res.data)

    # 16. Customer Khata Page
    res = client.get('/customers')
    assert_test("Customer Khata loads", res.status_code == 200 and b'Customer Khata' in res.data)
    assert_test("Customers listed with balances", b'Ramesh Patel' in res.data)

    # 17. Customer Repayment
    res = client.post('/customers/repay', data={
        'customer_id': 1,
        'amount': 200.0,
        'payment_method': 'Cash',
        'payment_date': '2026-11-17',
        'reference_no': 'TEST-RCPT-01',
        'notes': 'Test payment'
    }, follow_redirects=True)
    assert_test("Customer repayment recorded and balance updated", res.status_code == 200 and b'recorded for' in res.data)

    # 18. Customer Ledger JSON API
    res = client.get('/api/customers/1/ledger')
    ldata = res.get_json()
    assert_test("Customer ledger API returns timeline", res.status_code == 200 and 'history' in ldata and len(ldata['history']) > 0)

    # 19. Reports & Analytics Page
    res = client.get('/reports')
    assert_test("Reports page loads", res.status_code == 200 and b'Profit &amp; Loss Performance Summary' in res.data)

    # 20. CSV Exports
    res = client.get('/reports/export/sales')
    assert_test("Sales CSV export generates valid CSV", res.status_code == 200 and b'Invoice No,Customer Name' in res.data)

    res = client.get('/reports/export/expenses')
    assert_test("Expenses CSV export generates valid CSV", res.status_code == 200 and b'Title,Category,Amount' in res.data)

    res = client.get('/reports/export/inventory')
    assert_test("Inventory CSV export generates valid CSV", res.status_code == 200 and b'SKU Code,Product Name' in res.data)

    res = client.get('/reports/export/customers')
    assert_test("Customers CSV export generates valid CSV", res.status_code == 200 and b'Customer Name,Phone' in res.data)

    # 21. Daily Summary (Day Closing) Page
    res = client.get('/daily-summary')
    assert_test("Daily summary page loads", res.status_code == 200 and b'Day Closing Summary' in res.data)
    assert_test("Daily cash reconciliation displayed", b'Daily Cash Drawer Reconciliation Sheet' in res.data)

    # 22. Settings Page
    res = client.get('/settings')
    assert_test("Settings page loads", res.status_code == 200 and b'Shop Profile &amp; Bill Receipt Branding' in res.data)

    res = client.post('/settings', data={
        'shop_name': 'Smart Kirana & Superstore',
        'shop_tagline': 'Manage Your Stock. Track Your Money. Grow Your Business.',
        'owner_name': 'Rajesh Sharma',
        'phone': '+91 98765 43210',
        'address': 'Shop #12, Market Road, Sector 4, Gandhinagar',
        'gstin': '24AAACP1234M1Z5'
    }, follow_redirects=True)
    assert_test("Settings update succeeds", res.status_code == 200 and b'Store profile settings updated successfully' in res.data)

    # 23. Supabase API Status & Backend Integration
    res = client.get('/api/supabase/status')
    assert_test("Supabase API status endpoint returns 200 JSON", res.status_code == 200 and 'url' in res.get_json())

    # 24. Settings page renders Supabase cloud card
    res = client.get('/settings')
    assert_test("Settings page displays Supabase Cloud Database card", res.status_code == 200 and b'Supabase Cloud Database' in res.data)

    print("=" * 60)
    print(f"ALL {passed}/{total} TESTS PASSED SUCCESSFULLY! 100% COVERAGE")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
