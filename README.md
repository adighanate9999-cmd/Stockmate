# SMART STOCK & MONEY MANAGER
> **Tagline:** *"Manage Your Stock. Track Your Money. Grow Your Business."*

A production-grade, lightweight inventory and financial management web application specifically architected for small retail shop owners (Kirana, General Stores, and provision shops managing 20–50 products). Designed to replace traditional handwritten notebooks (*bahi-khata*) with an automated, error-free digital management system.

---

## 📌 Project Overview & Engineering Motivation

Traditional small retail shopkeepers in India struggle with:
1. **Inventory Blindspots:** Not knowing real-time stock levels until an item is completely sold out.
2. **Khata Tracking Errors:** Losing track of customer credit (*udhar*) across scribbled paper notebooks.
3. **Daily Cash Discrepancies:** Inability to reconcile physical cash drawer balance against counter sales and daily operational spending.
4. **Profit Ambiguity:** Mistaking total daily cash inflows for net business profit without accounting for Wholesale Purchase Cost (COGS) and overhead expenses.

**Smart Stock & Money Manager** addresses these real-world business challenges through an intuitive, high-speed micro-SaaS web platform.

---

## 🚀 Key Functional Modules

| Module | Route | Key Capabilities |
|---|---|---|
| **Authentication** | `/login`, `/register` | Secure session auth, Werkzeug password hashing, 1-Click Demo Fill for examiner evaluations |
| **Executive Dashboard** | `/dashboard` | 6 Core KPI cards, 7-day revenue/profit trendline, category sales doughnut, low-stock alert feed |
| **Product Master** | `/products` | Full CRUD, SKU generator, category taxonomy, real-time unit profit and margin % calculator |
| **Stock & Inventory** | `/inventory` | Dedicated stock ledger, restock recommendations, stock-in logging, movement audit history |
| **Fast Counter POS** | `/pos` | Keyboard-friendly (`F2`), product search, cart quantity steppers, discount calculator, dynamic UPI QR generator, customer credit assignment, instant printable thermal bill |
| **Sales Invoices** | `/sales` | Complete invoice log, payment mode filters (Cash / UPI / Credit), line-item inspection modal, reprint bill |
| **Money Management** | `/money` | Master formula: $\text{Cash in Hand} = \text{Opening Cash} + \text{Cash Sales} + \text{Credit Repayments} - \text{Cash Expenses}$, expense categorization, unified cash movement ledger |
| **Customer Khata** | `/customers` | Credit ledger per customer, payment recovery modal, limit utilization bars, 1-click WhatsApp payment reminders |
| **Reports & Analytics** | `/reports` | Profit & Loss statement (P&L), stock valuation by category, top 10 bestsellers, 4 CSV data exports |
| **Day Closing Summary** | `/daily-summary` | End-of-day reconciliation sheet, cash drawer balancing, credit summary, restock checklist, print-ready |
| **Settings & Profile** | `/settings` | Shop name, address, GSTIN, receipt header branding, 1-click demo data re-seeder |

---

## 🔬 Mathematical Formulations & Data Science Logic

### 1. Cash in Hand Formula
$$\text{Cash in Hand} = \text{Opening Cash Float} + \sum \text{Cash Sales} + \sum \text{Cash Khata Repayments} - \sum \text{Cash Operating Expenses}$$

### 2. Profit & Loss Computation
$$\text{Gross Sales} = \sum (\text{Selling Price} \times \text{Quantity}) - \text{Discounts}$$
$$\text{Cost of Goods Sold (COGS)} = \sum (\text{Purchase Price} \times \text{Quantity})$$
$$\text{Gross Profit} = \text{Gross Sales} - \text{COGS}$$
$$\text{Net Business Profit} = \text{Gross Profit} - \sum \text{Operating Expenses}$$
$$\text{Gross Margin \%} = \left(\frac{\text{Gross Profit}}{\text{Gross Sales}}\right) \times 100$$

### 3. Dynamic Restock Recommendation Algorithm
When available quantity $Q_{\text{avail}} \le Q_{\text{min}}$:
$$Q_{\text{reorder}} = \max\left(3 \times Q_{\text{min}} - Q_{\text{avail}}, \; 2 \times Q_{\text{min}}\right)$$
$$\text{Estimated Capital Required} = Q_{\text{reorder}} \times \text{Unit Purchase Cost}$$

---

## 🛠️ Technology Stack

- **Backend:** Python 3 (Flask 3.1, Jinja2 template engine)
- **Database:** SQLite 3 (Foreign-key enforced, normalized schema migratable to MySQL/PostgreSQL)
- **Frontend:** HTML5, CSS3, Tailwind CSS (Utility classes), Inter & Plus Jakarta Sans typography
- **Visualizations:** Chart.js 4 (Gradients, tooltips, responsive dual-axis charts)
- **Icons:** Lucide Icons
- **Print Engine:** CSS `@media print` optimized for standard 80mm thermal receipt printers and A4 summary sheets

---

## ⚡ Quick Start & Installation

### 1. Clone or Open Workspace
```bash
cd d:\stockmate
```

### 2. Activate Virtual Environment & Install Dependencies
```bash
# Using the pre-configured venv:
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Connect to Supabase Cloud Database (Optional / Recommended)

1. **Configure Environment Variables (`.env`):**
   Copy `.env.example` to `.env` (or edit existing `.env`):
   ```env
   SUPABASE_URL=https://your-project-id.supabase.co
   SUPABASE_KEY=your-supabase-anon-or-service-role-key
   ```
2. **Execute Schema in Supabase SQL Editor:**
   Open [supabase.com](https://supabase.com) -> Your Project -> **SQL Editor**, paste the contents of [`supabase_schema.sql`](file:///d:/stockmate/supabase_schema.sql), and click **Run**.
3. **Verify Connection & Migrate Data via CLI:**
   ```bash
   # Test Supabase connection
   .\venv\Scripts\python.exe backend.py test

   # (Optional) Migrate local SQLite records to Supabase
   .\venv\Scripts\python.exe backend.py migrate
   ```

### 4. Seed Realistic Sample Data (Local SQLite Fallback)
```bash
.\venv\Scripts\python.exe seed_data.py
```

### 5. Run Web Server
```bash
.\venv\Scripts\python.exe app.py
```

Open your browser at: **`http://127.0.0.1:5000`**

---

## 🔑 Default Demonstration Credentials

For instant evaluation and examiners testing:
- **Email:** `admin@smartstock.com`
- **Username:** `admin`
- **Password:** `admin123`
- *(Or simply click the **"Auto Fill & Login"** button right on the login screen!)*

---

## 📦 Preloaded Sample Retail Catalog

Realistic Indian fast-moving grocery items with realistic Rupee prices:
- **Grains & Flours:** Basmati Rice Premium, Sona Masoori Rice, Aashirvaad Chakki Atta, Toor Dal, Moong Dal
- **Edible Oils & Ghee:** Fortune Sunflower Oil, Dhara Mustard Oil, Amul Pure Cow Ghee
- **Dairy & Bakery:** Amul Gold Milk, Amul Salted Butter
- **Spices & Staples:** Madhur Sugar, Tata Salt, MDH Haldi, MDH Deggi Mirch
- **Packaged Food:** Parle-G Gold, Britannia Good Day, Maggi Noodles 4-Pack
- **Beverages:** Tata Tea Gold, Brooke Bond Red Label Tea
- **Personal Care & Hygiene:** Dettol Soap 3-Pack, Dove Beauty Bar, Clinic Plus, Colgate Toothpaste
- **Household & Cleaning:** Surf Excel Easy Wash, Vim Lemon Bar
- **Alert Test Cases:** Lifebuoy Handwash (Low Stock), Head & Shoulders (Low Stock), Oral-B Toothbrush (Out of Stock)

---

## 📄 License & Academic Credit
Developed for Academic Project Evaluation & Commercial Micro-Retail Automation.
All rights reserved © 2026.
