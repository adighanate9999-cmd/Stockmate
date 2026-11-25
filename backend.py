"""
==============================================================================
StockMate / Smart Stock & Money Manager - Supabase Backend Service
==============================================================================
This module provides a unified backend layer for connecting StockMate to
Supabase (Cloud PostgreSQL & PostgREST API).

Features:
- Zero-dependency .env loader (supports python-dotenv if present, falls back cleanly)
- Official Supabase SDK support with resilient pure-Python HTTP fallback
- Full CRUD operations for Products, Customers, Sales, Expenses, Inventory, and Settings
- Connection health check & diagnostic tool (`python backend.py test`)
- 1-Click SQLite to Supabase data migration (`python backend.py migrate`)
==============================================================================
"""

import os
import sys
import json
import sqlite3
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple


# ==============================================================================
# 1. Automatic Environment Variables Loader
# ==============================================================================
def load_env(env_path: Optional[str] = None) -> None:
    """
    Load environment variables from .env file into os.environ.
    Uses `python-dotenv` if installed, otherwise parses .env natively.
    """
    if env_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(base_dir, '.env')

    # Try python-dotenv first
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)
        return
    except ImportError:
        pass

    # Built-in native parser fallback
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip()
                    # Strip wrapping quotes if present
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    if key and key not in os.environ:
                        os.environ[key] = val
    except Exception as e:
        print(f"[backend.py] Warning: Could not read {env_path}: {e}", file=sys.stderr)


# Load environment variables on module import
load_env()


# ==============================================================================
# 2. Configuration & Credentials Accessors
# ==============================================================================
def get_config() -> Dict[str, str]:
    """Retrieve Supabase and App settings from environment."""
    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_ANON_KEY', '')
    anon_key = os.environ.get('SUPABASE_ANON_KEY', '') or key
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    db_url = os.environ.get('DATABASE_URL', '')
    backend_mode = os.environ.get('DB_BACKEND', 'supabase').lower()

    return {
        'SUPABASE_URL': url,
        'SUPABASE_KEY': key,
        'SUPABASE_ANON_KEY': anon_key,
        'SUPABASE_SERVICE_ROLE_KEY': service_key,
        'DATABASE_URL': db_url,
        'DB_BACKEND': backend_mode
    }


def is_supabase_configured() -> bool:
    """Return True if valid-looking Supabase credentials are set in environment."""
    cfg = get_config()
    url = cfg['SUPABASE_URL']
    key = cfg['SUPABASE_KEY']
    if not url or not key:
        return False
    if 'your-project-id' in url or 'your-anon-or-service-role-key' in key:
        return False
    return url.startswith('https://') and len(key) > 20


# ==============================================================================
# 3. Resilient PostgREST HTTP Client (Zero-Dependency Standard Library)
# ==============================================================================
class SupabaseRestClient:
    """
    Lightweight REST client for Supabase PostgREST endpoints.
    Allows queries, inserts, updates, and deletes without requiring third-party wheels.
    """
    def __init__(self, supabase_url: str, supabase_key: str):
        self.base_url = supabase_url.rstrip('/')
        self.api_url = f"{self.base_url}/rest/v1"
        self.key = supabase_key

    def _headers(self, prefer: Optional[str] = None) -> Dict[str, str]:
        headers = {
            'apikey': self.key,
            'Authorization': f'Bearer {self.key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if prefer:
            headers['Prefer'] = prefer
        return headers

    def request(self, method: str, endpoint: str, params: Optional[Dict[str, str]] = None,
                data: Optional[Any] = None, prefer: Optional[str] = None) -> Tuple[int, Any]:
        """Send an HTTP request to Supabase PostgREST."""
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        if params:
            query_str = urllib.parse.urlencode(params)
            url = f"{url}?{query_str}"

        body_bytes = None
        if data is not None:
            body_bytes = json.dumps(data).encode('utf-8')

        req = urllib.request.Request(url, data=body_bytes, headers=self._headers(prefer), method=method)
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                status_code = response.getcode()
                res_body = response.read().decode('utf-8')
                res_json = json.loads(res_body) if res_body else None
                return status_code, res_json
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8') if e.fp else str(e)
            try:
                err_json = json.loads(err_body)
            except Exception:
                err_json = {'message': err_body}
            return e.code, err_json
        except Exception as e:
            return 0, {'error': str(e)}

    # Table Operations
    def select(self, table: str, query: str = '*', filters: Optional[Dict[str, str]] = None,
               order: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {'select': query}
        if filters:
            for k, v in filters.items():
                params[k] = v
        if order:
            params['order'] = order
        if limit:
            params['limit'] = str(limit)

        status, data = self.request('GET', table, params=params)
        if status in (200, 206) and isinstance(data, list):
            return data
        return []

    def insert(self, table: str, record_or_list: Any) -> Optional[Any]:
        status, data = self.request('POST', table, data=record_or_list, prefer='return=representation')
        if status in (200, 201):
            return data
        return None

    def update(self, table: str, updates: Dict[str, Any], match_column: str, match_value: Any) -> Optional[Any]:
        params = {f"{match_column}": f"eq.{match_value}"}
        status, data = self.request('PATCH', table, params=params, data=updates, prefer='return=representation')
        if status in (200, 204):
            return data
        return None

    def delete(self, table: str, match_column: str, match_value: Any) -> bool:
        params = {f"{match_column}": f"eq.{match_value}"}
        status, _ = self.request('DELETE', table, params=params)
        return status in (200, 204)


# ==============================================================================
# 4. Supabase Client Factory
# ==============================================================================
_client_instance = None

def get_supabase_client():
    """
    Get the active Supabase client.
    Prefers the official `supabase` package if available; otherwise uses SupabaseRestClient.
    """
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    cfg = get_config()
    url = cfg['SUPABASE_URL']
    key = cfg['SUPABASE_KEY']

    if not url or not key:
        return None

    # Try official SDK
    try:
        from supabase import create_client
        _client_instance = create_client(url, key)
        return _client_instance
    except ImportError:
        pass

    # Use native REST Client fallback
    _client_instance = SupabaseRestClient(url, key)
    return _client_instance


# ==============================================================================
# 5. Diagnostic & Connection Health Check
# ==============================================================================
def test_connection() -> Dict[str, Any]:
    """
    Test connectivity to Supabase and verify required tables exist.
    Returns a dict with detailed status and troubleshooting tips.
    """
    cfg = get_config()
    url = cfg['SUPABASE_URL']
    key = cfg['SUPABASE_KEY']

    result = {
        'configured': False,
        'connected': False,
        'status_code': 0,
        'url': url or '(not set in .env)',
        'key_set': bool(key),
        'tables_found': [],
        'missing_tables': [],
        'error': None,
        'message': ''
    }

    if not is_supabase_configured():
        result['message'] = "Supabase is not configured yet. Please edit .env with your project URL and API key."
        return result

    result['configured'] = True
    client = SupabaseRestClient(url, key)

    # Test basic connection via PostgREST OpenAPI spec or ping
    status, data = client.request('GET', '')
    result['status_code'] = status

    if status != 200:
        result['error'] = data
        result['message'] = f"Failed to connect to Supabase (HTTP {status}). Check your SUPABASE_URL and SUPABASE_KEY."
        return result

    result['connected'] = True

    # Check key tables
    expected_tables = [
        'users', 'categories', 'products', 'customers', 'sales',
        'sale_items', 'stock_movements', 'expenses', 'customer_payments', 'cash_register'
    ]

    for tbl in expected_tables:
        s, _ = client.request('GET', tbl, params={'select': 'id', 'limit': '1'})
        if s in (200, 206):
            result['tables_found'].append(tbl)
        else:
            result['missing_tables'].append(tbl)

    if result['missing_tables']:
        result['message'] = (
            f"Connected to Supabase! However, {len(result['missing_tables'])} tables are missing. "
            "Run 'supabase_schema.sql' in the Supabase SQL Editor to create them."
        )
    else:
        result['message'] = "Successfully connected to Supabase! All 10 tables are verified and ready."

    return result


# ==============================================================================
# 6. High-Level Data Service Layer (Products, Customers, Sales, Expenses)
# ==============================================================================
class SupabaseService:
    """High-level backend methods for business operations in StockMate."""

    @staticmethod
    def _client():
        return get_supabase_client()

    # --- Categories ---
    @classmethod
    def get_categories(cls) -> List[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return []
        if isinstance(client, SupabaseRestClient):
            return client.select('categories', order='name.asc')
        res = client.table('categories').select('*').order('name').execute()
        return res.data or []

    @classmethod
    def create_category(cls, name: str, description: str = '', icon: str = 'package') -> Optional[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return None
        payload = {'name': name, 'description': description, 'icon': icon}
        if isinstance(client, SupabaseRestClient):
            res = client.insert('categories', payload)
            return res[0] if isinstance(res, list) and res else res
        res = client.table('categories').insert(payload).execute()
        return res.data[0] if res.data else None

    # --- Products ---
    @classmethod
    def get_products(cls, active_only: bool = True) -> List[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return []
        if isinstance(client, SupabaseRestClient):
            filters = {'is_active': 'eq.1'} if active_only else None
            return client.select('products', filters=filters, order='name.asc')
        q = client.table('products').select('*')
        if active_only:
            q = q.eq('is_active', 1)
        res = q.order('name').execute()
        return res.data or []

    @classmethod
    def get_product(cls, product_id: int) -> Optional[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return None
        if isinstance(client, SupabaseRestClient):
            rows = client.select('products', filters={'id': f'eq.{product_id}'}, limit=1)
            return rows[0] if rows else None
        res = client.table('products').select('*').eq('id', product_id).limit(1).execute()
        return res.data[0] if res.data else None

    @classmethod
    def create_product(cls, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return None
        if isinstance(client, SupabaseRestClient):
            res = client.insert('products', data)
            return res[0] if isinstance(res, list) and res else res
        res = client.table('products').insert(data).execute()
        return res.data[0] if res.data else None

    @classmethod
    def update_product(cls, product_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return None
        updates['updated_at'] = datetime.utcnow().isoformat()
        if isinstance(client, SupabaseRestClient):
            res = client.update('products', updates, 'id', product_id)
            return res[0] if isinstance(res, list) and res else res
        res = client.table('products').update(updates).eq('id', product_id).execute()
        return res.data[0] if res.data else None

    @classmethod
    def delete_product(cls, product_id: int) -> bool:
        client = cls._client()
        if not client:
            return False
        # Soft-delete by setting is_active = 0
        return cls.update_product(product_id, {'is_active': 0}) is not None

    # --- Customers (Khata) ---
    @classmethod
    def get_customers(cls) -> List[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return []
        if isinstance(client, SupabaseRestClient):
            return client.select('customers', order='name.asc')
        res = client.table('customers').select('*').order('name').execute()
        return res.data or []

    @classmethod
    def create_customer(cls, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return None
        if isinstance(client, SupabaseRestClient):
            res = client.insert('customers', data)
            return res[0] if isinstance(res, list) and res else res
        res = client.table('customers').insert(data).execute()
        return res.data[0] if res.data else None

    @classmethod
    def record_customer_payment(cls, customer_id: int, amount: float,
                                payment_method: str = 'Cash',
                                payment_date: Optional[str] = None,
                                reference_no: str = '',
                                notes: str = '') -> Optional[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return None
        payload = {
            'customer_id': customer_id,
            'amount': float(amount),
            'payment_method': payment_method,
            'payment_date': payment_date or datetime.now().strftime('%Y-%m-%d'),
            'reference_no': reference_no,
            'notes': notes
        }
        if isinstance(client, SupabaseRestClient):
            res = client.insert('customer_payments', payload)
            return res[0] if isinstance(res, list) and res else res
        res = client.table('customer_payments').insert(payload).execute()
        return res.data[0] if res.data else None

    # --- Sales & Invoicing (POS) ---
    @classmethod
    def create_sale(cls, sale_data: Dict[str, Any], items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return None

        # 1. Insert sale record
        if isinstance(client, SupabaseRestClient):
            sale_res = client.insert('sales', sale_data)
            created_sale = sale_res[0] if isinstance(sale_res, list) and sale_res else sale_res
            sale_id = created_sale.get('id') if isinstance(created_sale, dict) else None
        else:
            res = client.table('sales').insert(sale_data).execute()
            created_sale = res.data[0] if res.data else None
            sale_id = created_sale.get('id') if created_sale else None

        if not sale_id:
            return None

        # 2. Insert line items
        for item in items:
            item['sale_id'] = sale_id
        if isinstance(client, SupabaseRestClient):
            client.insert('sale_items', items)
        else:
            client.table('sale_items').insert(items).execute()

        # 3. Decrement stock & log stock movements
        for item in items:
            prod_id = item.get('product_id')
            qty = float(item.get('quantity', 0))
            if prod_id:
                prod = cls.get_product(prod_id)
                if prod:
                    prev_qty = float(prod.get('quantity', 0))
                    new_qty = max(0.0, prev_qty - qty)
                    cls.update_product(prod_id, {'quantity': new_qty})
                    cls.record_stock_movement(
                        product_id=prod_id,
                        movement_type='Sale Deduction',
                        quantity=qty,
                        previous_qty=prev_qty,
                        new_qty=new_qty,
                        reference_id=sale_data.get('invoice_no', ''),
                        reference_type='Invoice'
                    )

        return created_sale

    @classmethod
    def get_sales(cls, limit: int = 50) -> List[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return []
        if isinstance(client, SupabaseRestClient):
            return client.select('sales', order='created_at.desc', limit=limit)
        res = client.table('sales').select('*').order('created_at', desc=True).limit(limit).execute()
        return res.data or []

    # --- Expenses ---
    @classmethod
    def get_expenses(cls, limit: int = 50) -> List[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return []
        if isinstance(client, SupabaseRestClient):
            return client.select('expenses', order='expense_date.desc', limit=limit)
        res = client.table('expenses').select('*').order('expense_date', desc=True).limit(limit).execute()
        return res.data or []

    @classmethod
    def create_expense(cls, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return None
        if isinstance(client, SupabaseRestClient):
            res = client.insert('expenses', data)
            return res[0] if isinstance(res, list) and res else res
        res = client.table('expenses').insert(data).execute()
        return res.data[0] if res.data else None

    # --- Stock Movements ---
    @classmethod
    def record_stock_movement(cls, product_id: int, movement_type: str, quantity: float,
                              previous_qty: float, new_qty: float, unit_cost: Optional[float] = None,
                              reference_id: str = '', reference_type: str = '', notes: str = '') -> Optional[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return None
        payload = {
            'product_id': product_id,
            'movement_type': movement_type,
            'quantity': float(quantity),
            'previous_qty': float(previous_qty),
            'new_qty': float(new_qty),
            'unit_cost': float(unit_cost) if unit_cost is not None else None,
            'reference_id': reference_id,
            'reference_type': reference_type,
            'notes': notes
        }
        if isinstance(client, SupabaseRestClient):
            res = client.insert('stock_movements', payload)
            return res[0] if isinstance(res, list) and res else res
        res = client.table('stock_movements').insert(payload).execute()
        return res.data[0] if res.data else None

    # --- Shop Profile ---
    @classmethod
    def get_shop_profile(cls, user_id: int = 1) -> Dict[str, Any]:
        client = cls._client()
        default_profile = {
            'id': 1,
            'shop_name': 'Smart Kirana & General Store',
            'shop_tagline': 'Manage Your Stock. Track Your Money. Grow Your Business.',
            'owner_name': 'Rajesh Sharma',
            'phone': '+91 98765 43210',
            'address': 'Shop #12, Market Road, Sector 4, Gandhinagar',
            'gstin': '24AAACP1234M1Z5',
            'currency_symbol': '₹'
        }
        if not client:
            return default_profile
        try:
            if isinstance(client, SupabaseRestClient):
                rows = client.select('users', filters={'id': f'eq.{user_id}'}, limit=1)
                return rows[0] if rows else default_profile
            res = client.table('users').select('*').eq('id', user_id).limit(1).execute()
            return res.data[0] if res.data else default_profile
        except Exception:
            return default_profile

    @classmethod
    def update_shop_profile(cls, user_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        client = cls._client()
        if not client:
            return None
        if isinstance(client, SupabaseRestClient):
            res = client.update('users', updates, 'id', user_id)
            return res[0] if isinstance(res, list) and res else res
        res = client.table('users').update(updates).eq('id', user_id).execute()
        return res.data[0] if res.data else None


# ==============================================================================
# 7. SQLite -> Supabase 1-Click Migration Utility
# ==============================================================================
def migrate_sqlite_to_supabase(sqlite_db_path: Optional[str] = None) -> bool:
    """
    Export all data from the local SQLite database (smart_stock.db)
    and insert into Supabase cloud database.
    """
    if sqlite_db_path is None:
        sqlite_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smart_stock.db')

    if not os.path.exists(sqlite_db_path):
        print(f"[Migration Error] SQLite database not found at: {sqlite_db_path}")
        return False

    cfg = get_config()
    if not is_supabase_configured():
        print("[Migration Error] Supabase is not configured. Please fill SUPABASE_URL and SUPABASE_KEY in .env first.")
        return False

    client = SupabaseRestClient(cfg['SUPABASE_URL'], cfg['SUPABASE_KEY'])

    print(f"\n============================================================")
    print(f"MIGRATING LOCAL SQLITE ({sqlite_db_path}) -> SUPABASE")
    print(f"Target: {cfg['SUPABASE_URL']}")
    print(f"============================================================")

    conn = sqlite3.connect(sqlite_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Tables in foreign-key dependency order
    tables = [
        'users',
        'categories',
        'products',
        'customers',
        'sales',
        'sale_items',
        'stock_movements',
        'expenses',
        'customer_payments',
        'cash_register'
    ]

    total_synced = 0
    for tbl in tables:
        try:
            cursor.execute(f"SELECT * FROM {tbl}")
            rows = cursor.fetchall()
            if not rows:
                print(f"  • {tbl.ljust(20)}: 0 rows (skipped)")
                continue

            records = [dict(r) for r in rows]
            status, res = client.request('POST', tbl, data=records, prefer='resolution=merge-duplicates')

            if status in (200, 201, 204):
                print(f"  ✓ {tbl.ljust(20)}: {len(records)} rows synced successfully")
                total_synced += len(records)
            else:
                print(f"  ✗ {tbl.ljust(20)}: failed (HTTP {status}) -> {res}")
        except Exception as e:
            print(f"  ✗ {tbl.ljust(20)}: error reading sqlite: {e}")

    conn.close()
    print(f"============================================================")
    print(f"Migration completed! Total rows processed: {total_synced}")
    print(f"============================================================\n")
    return True


# ==============================================================================
# 8. Command Line Interface
# ==============================================================================
def main():
    args = sys.argv[1:]
    command = args[0].lower() if args else 'test'

    if command in ('test', 'check', 'status'):
        print("\nChecking Supabase Connection...")
        report = test_connection()
        print(f"• Supabase URL:       {report['url']}")
        print(f"• Key Configured:     {'Yes' if report['key_set'] else 'No'}")
        print(f"• Connection Active:  {'YES' if report['connected'] else 'NO'}")
        if report['status_code']:
            print(f"• HTTP Status Code:   {report['status_code']}")
        if report['tables_found']:
            print(f"• Tables Verified:    {len(report['tables_found'])}/10 tables found ({', '.join(report['tables_found'])})")
        if report['missing_tables']:
            print(f"• Missing Tables:     {', '.join(report['missing_tables'])}")
        print(f"\nMessage: {report['message']}\n")

    elif command in ('migrate', 'sync'):
        migrate_sqlite_to_supabase()

    elif command in ('schema', 'sql'):
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'supabase_schema.sql')
        if os.path.exists(schema_path):
            print(f"\nSupabase schema SQL file located at: {schema_path}")
            print("Copy this file contents into Supabase Dashboard -> SQL Editor and click 'Run'.\n")
        else:
            print(f"\nsupabase_schema.sql not found at: {schema_path}\n")

    elif command in ('help', '--help', '-h'):
        print("""
StockMate Supabase Backend CLI
------------------------------
Usage:
  python backend.py test       Test connection to Supabase and verify tables
  python backend.py migrate    Migrate all data from smart_stock.db to Supabase
  python backend.py schema     Display location of Supabase SQL setup schema
  python backend.py help       Display this help message
""")
    else:
        print(f"Unknown command: '{command}'. Run 'python backend.py help' for available commands.")


if __name__ == '__main__':
    main()
