# Inventory Management System for Retail Stores

Flask + SQLite web application for tracking products, recording sales,
flagging low stock, and generating reports.

## Features
- Login system with hashed passwords (admin / staff roles)
- Dashboard with live metrics: total products, stock units, inventory value,
  today's sales, low-stock and out-of-stock counts
- Product CRUD (add / edit / delete / search / filter by name, category, price, supplier)
- Sales recording with automatic stock deduction and low-stock warnings
- Daily / monthly sales reports, top-selling products
- CSV export for inventory and sales history (via pandas)
- Simple, responsive UI — no build step required

## Project Structure
```
inventory_system/
├── app.py                 # Flask app: models, routes, business logic
├── requirements.txt
├── inventory.db            # created automatically on first run
├── static/
│   └── style.css
└── templates/
    ├── base.html
    ├── login.html
    ├── dashboard.html
    ├── products.html
    ├── product_form.html
    ├── sales.html
    └── reports.html
```

## Setup

1. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app**
   ```bash
   python app.py
   ```
   The database (`inventory.db`) and a default admin account are created
   automatically on first run.

4. **Open in browser**
   ```
   http://127.0.0.1:5000
   ```

## Default Login
| Username | Password | Role  |
|----------|----------|-------|
| admin    | admin123 | admin |

**Change this password (or create a new admin user) before any real / shared use.**
To add more users, use the Flask shell:
```bash
python
>>> from app import app, db, User
>>> with app.app_context():
...     u = User(username="staff1", role="staff")
...     u.set_password("your-password")
...     db.session.add(u)
...     db.session.commit()
```

## Roles
- **admin** — full access: add/edit/delete products, record sales, view reports
- **staff** — can view products, record sales, view reports (cannot add/edit/delete products)

## Notes
- Database: SQLite by default (`inventory.db` in the project folder). To use
  MySQL instead, change `SQLALCHEMY_DATABASE_URI` in `app.py`
  (e.g. `mysql+pymysql://user:pass@localhost/inventory_db`) and
  `pip install pymysql`.
- Currency is shown as ₹ (INR) — change the symbol in the templates if needed.
- For production deployment, set `debug=False`, set a strong `SECRET_KEY`,
  and run behind a proper WSGI server (e.g. gunicorn) rather than the
  Flask dev server.
