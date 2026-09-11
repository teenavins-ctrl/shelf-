"""
ShelfSync - Intelligent Retail Inventory & Point of Sale Suite
Flask + SQLite/PostgreSQL/MySQL Web Application

Run:
    python app.py
"""

import os
import io
import csv
from datetime import datetime, date, timedelta

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, Response
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# App & DB Configuration
# ---------------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "shelfsync-enterprise-secret-key-2026")

default_sqlite = "sqlite:///" + os.path.join(BASE_DIR, "inventory.db")
db_uri = os.getenv("DATABASE_URL", default_sqlite)
if db_uri.startswith("sqlite:///") and not db_uri.startswith("sqlite:////") and not ":" in db_uri[10:]:
    db_filename = db_uri.replace("sqlite:///", "")
    db_uri = "sqlite:///" + os.path.join(BASE_DIR, db_filename)

app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ---------------------------------------------------------------------------
# Database Models
# ---------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="staff")  # admin / staff
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Supplier(db.Model):
    __tablename__ = "suppliers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    contact_person = db.Column(db.String(100))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship("Product", backref="supplier_rel", lazy=True)


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=True)
    barcode = db.Column(db.String(100), unique=True, nullable=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(100))
    supplier = db.Column(db.String(150))
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    cost_price = db.Column(db.Float, nullable=False, default=0.0)
    price = db.Column(db.Float, nullable=False, default=0.0)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    min_stock = db.Column(db.Integer, nullable=False, default=5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_low_stock(self):
        return self.quantity <= self.min_stock and self.quantity > 0

    @property
    def is_out_of_stock(self):
        return self.quantity <= 0


class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30), unique=True)
    email = db.Column(db.String(100))
    loyalty_points = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoices = db.relationship("Invoice", backref="customer_rel", lazy=True)


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SalesReturn(db.Model):
    __tablename__ = "sales_returns"
    id = db.Column(db.Integer, primary_key=True)
    return_number = db.Column(db.String(50), unique=True, nullable=False)
    invoice_number = db.Column(db.String(50), nullable=False)
    product_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    refund_amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"
    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(50), unique=True, nullable=False)
    supplier_name = db.Column(db.String(150), nullable=False)
    product_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_cost = db.Column(db.Float, nullable=False, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(30), default="Pending")  # Pending, Received, Cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    received_at = db.Column(db.DateTime, nullable=True)




class StockMovement(db.Model):
    __tablename__ = "stock_movements"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    type = db.Column(db.String(30), nullable=False)  # Restock, Sale, Return, Adjustment
    quantity_change = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    note = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product", backref=db.backref("movements", lazy=True))
    user = db.relationship("User", backref=db.backref("movements", lazy=True))


class Invoice(db.Model):
    __tablename__ = "invoices"
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_name = db.Column(db.String(100), default="Walk-in Customer")
    customer_phone = db.Column(db.String(30), default="")
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    subtotal = db.Column(db.Float, nullable=False, default=0.0)
    discount = db.Column(db.Float, nullable=False, default=0.0)
    tax = db.Column(db.Float, nullable=False, default=0.0)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    payment_method = db.Column(db.String(50), default="Cash")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    items = db.relationship("InvoiceItem", backref="invoice", cascade="all, delete-orphan")
    user = db.relationship("User")


class InvoiceItem(db.Model):
    __tablename__ = "invoice_items"
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)

    product = db.relationship("Product")


class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=True)

    product = db.relationship("Product", backref=db.backref("sales", lazy=True))


# ---------------------------------------------------------------------------
# Auth Helpers & Context Processor
# ---------------------------------------------------------------------------
def login_required(view_func):
    from functools import wraps
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access ShelfSync.", "error")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped


def admin_required(view_func):
    from functools import wraps
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Admin access required for this action.", "error")
            return redirect(url_for("dashboard"))
        return view_func(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_user():
    low_count = Product.query.filter(Product.quantity <= Product.min_stock).count()
    return {
        "current_username": session.get("username"),
        "current_role": session.get("role"),
        "critical_alert_count": low_count
    }


# ---------------------------------------------------------------------------
# Authentication Routes
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            flash(f"Welcome back to ShelfSync, {user.username}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out of ShelfSync.", "success")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Dashboard Analytics
# ---------------------------------------------------------------------------
@app.route("/")
@login_required
def dashboard():
    total_products = Product.query.count()
    total_stock_units = db.session.query(func.coalesce(func.sum(Product.quantity), 0)).scalar()
    low_stock_items = Product.query.filter(Product.quantity <= Product.min_stock, Product.quantity > 0).all()
    out_of_stock_items = Product.query.filter(Product.quantity <= 0).all()

    today = date.today()
    today_sales = (
        db.session.query(func.coalesce(func.sum(Sale.amount), 0))
        .filter(func.date(Sale.sale_date) == today.isoformat())
        .scalar()
    )
    today_sales_count = (
        db.session.query(func.count(Sale.id))
        .filter(func.date(Sale.sale_date) == today.isoformat())
        .scalar()
    )

    total_revenue = db.session.query(func.coalesce(func.sum(Sale.amount), 0)).scalar()
    total_sold_units = db.session.query(func.coalesce(func.sum(Sale.quantity), 0)).scalar()

    # Net Profit / Loss
    total_cost_of_goods_sold = (
        db.session.query(func.coalesce(func.sum(Sale.quantity * Product.cost_price), 0))
        .join(Product, Sale.product_id == Product.id)
        .scalar()
    )
    net_profit = round(total_revenue - total_cost_of_goods_sold, 2)
    inventory_value = db.session.query(func.coalesce(func.sum(Product.price * Product.quantity), 0)).scalar()

    # Top Bestsellers
    bestsellers = (
        db.session.query(
            Product.name,
            Product.category,
            func.sum(Sale.quantity).label("total_qty"),
            func.sum(Sale.amount).label("total_rev")
        )
        .join(Sale, Sale.product_id == Product.id)
        .group_by(Product.id)
        .order_by(func.sum(Sale.quantity).desc())
        .limit(5)
        .all()
    )

    # 7-day sales trend
    chart_dates, chart_sales = [], []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.isoformat()
        day_val = (
            db.session.query(func.coalesce(func.sum(Sale.amount), 0))
            .filter(func.date(Sale.sale_date) == day_str)
            .scalar()
        )
        chart_dates.append(day.strftime("%b %d"))
        chart_sales.append(round(day_val, 2))

    recent_invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(6).all()

    return render_template(
        "dashboard.html",
        total_products=total_products,
        total_stock_units=total_stock_units,
        low_stock_items=low_stock_items,
        out_of_stock_items=out_of_stock_items,
        today_sales=today_sales,
        today_sales_count=today_sales_count,
        total_revenue=total_revenue,
        total_sold_units=total_sold_units,
        net_profit=net_profit,
        inventory_value=inventory_value,
        bestsellers=bestsellers,
        chart_dates=chart_dates,
        chart_sales=chart_sales,
        recent_invoices=recent_invoices,
    )


# ---------------------------------------------------------------------------
# Product & Inventory CRUD
# ---------------------------------------------------------------------------
@app.route("/products")
@login_required
def products():
    query = Product.query

    name_q = request.args.get("name", "").strip()
    category_q = request.args.get("category", "").strip()
    supplier_q = request.args.get("supplier", "").strip()
    sku_q = request.args.get("sku", "").strip()

    if name_q:
        query = query.filter(Product.name.ilike(f"%{name_q}%"))
    if category_q:
        query = query.filter(Product.category.ilike(f"%{category_q}%"))
    if supplier_q:
        query = query.filter(Product.supplier.ilike(f"%{supplier_q}%"))
    if sku_q:
        query = query.filter((Product.sku.ilike(f"%{sku_q}%")) | (Product.barcode.ilike(f"%{sku_q}%")))

    product_list = query.order_by(Product.name.asc()).all()
    categories = [c[0] for c in db.session.query(Product.category).distinct() if c[0]]
    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()

    return render_template(
        "products.html",
        products=product_list,
        categories=categories,
        suppliers=suppliers,
        filters={"name": name_q, "category": category_q, "supplier": supplier_q, "sku": sku_q},
    )


@app.route("/products/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_product():
    if request.method == "POST":
        try:
            sku = request.form.get("sku", "").strip() or None
            barcode = request.form.get("barcode", "").strip() or None
            name = request.form["name"].strip()
            category = request.form.get("category", "").strip()
            supplier_name = request.form.get("supplier", "").strip()
            cost_price = float(request.form.get("cost_price", 0) or 0)
            price = float(request.form.get("price", 0) or 0)
            quantity = int(request.form.get("quantity", 0) or 0)
            min_stock = int(request.form.get("min_stock", 5) or 5)

            product = Product(
                sku=sku,
                barcode=barcode,
                name=name,
                category=category,
                supplier=supplier_name,
                cost_price=cost_price,
                price=price,
                quantity=quantity,
                min_stock=min_stock,
            )
            db.session.add(product)
            db.session.commit()

            if quantity > 0:
                movement = StockMovement(
                    product_id=product.id,
                    type="Initial Stock",
                    quantity_change=quantity,
                    unit_cost=cost_price,
                    user_id=session.get("user_id"),
                    note="Initial product creation"
                )
                db.session.add(movement)
                db.session.commit()

            flash(f'Product "{product.name}" added to ShelfSync.', "success")
            return redirect(url_for("products"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding product: {str(e)}", "error")

    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    return render_template("product_form.html", product=None, action="Add", suppliers=suppliers)


@app.route("/products/edit/<int:product_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == "POST":
        try:
            old_qty = product.quantity
            product.sku = request.form.get("sku", "").strip() or None
            product.barcode = request.form.get("barcode", "").strip() or None
            product.name = request.form["name"].strip()
            product.category = request.form.get("category", "").strip()
            product.supplier = request.form.get("supplier", "").strip()
            product.cost_price = float(request.form.get("cost_price", 0) or 0)
            product.price = float(request.form.get("price", 0) or 0)
            product.quantity = int(request.form.get("quantity", 0) or 0)
            product.min_stock = int(request.form.get("min_stock", 5) or 5)

            qty_diff = product.quantity - old_qty
            if qty_diff != 0:
                movement = StockMovement(
                    product_id=product.id,
                    type="Adjustment",
                    quantity_change=qty_diff,
                    unit_cost=product.cost_price,
                    user_id=session.get("user_id"),
                    note="Manual stock update"
                )
                db.session.add(movement)

            db.session.commit()
            flash(f'Product "{product.name}" updated successfully.', "success")
            return redirect(url_for("products"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating product: {str(e)}", "error")

    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    return render_template("product_form.html", product=product, action="Edit", suppliers=suppliers)


@app.route("/products/restock/<int:product_id>", methods=["GET", "POST"])
@login_required
def restock_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == "POST":
        try:
            add_qty = int(request.form.get("quantity", 0))
            cost_price = float(request.form.get("cost_price", product.cost_price))
            note = request.form.get("note", "").strip()

            if add_qty <= 0:
                flash("Restock quantity must be greater than zero.", "error")
                return redirect(url_for("restock_product", product_id=product.id))

            product.quantity += add_qty
            product.cost_price = cost_price

            movement = StockMovement(
                product_id=product.id,
                type="Restock",
                quantity_change=add_qty,
                unit_cost=cost_price,
                user_id=session.get("user_id"),
                note=note or f"Restocked {add_qty} units"
            )
            db.session.add(movement)
            db.session.commit()

            flash(f"Restocked {add_qty} units of {product.name}.", "success")
            return redirect(url_for("products"))
        except Exception as e:
            db.session.rollback()
            flash(f"Restock error: {str(e)}", "error")

    return render_template("restock.html", product=product)


@app.route("/products/delete/<int:product_id>", methods=["POST"])
@login_required
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    name = product.name
    db.session.delete(product)
    db.session.commit()
    flash(f'Product "{name}" deleted from ShelfSync.', "success")
    return redirect(url_for("products"))


# ---------------------------------------------------------------------------
# NEW FEATURE 1: Suppliers Directory & Management
# ---------------------------------------------------------------------------
@app.route("/suppliers", methods=["GET", "POST"])
@login_required
def suppliers():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        contact = request.form.get("contact_person", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()

        if not name:
            flash("Supplier name is required.", "error")
        else:
            supplier = Supplier(name=name, contact_person=contact, phone=phone, email=email, address=address)
            db.session.add(supplier)
            db.session.commit()
            flash(f'Supplier "{name}" added successfully.', "success")
            return redirect(url_for("suppliers"))

    supplier_list = Supplier.query.order_by(Supplier.name.asc()).all()
    return render_template("suppliers.html", suppliers=supplier_list)


@app.route("/orders", methods=["GET", "POST"])
@login_required
def purchase_orders():
    if request.method == "POST":
        po_no = "PO-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
        supplier_name = request.form.get("supplier_name", "").strip()
        product_name = request.form.get("product_name", "").strip()
        qty = int(request.form.get("quantity", 1))
        unit_cost = float(request.form.get("unit_cost", 0))

        if supplier_name and product_name:
            po = PurchaseOrder(
                po_number=po_no,
                supplier_name=supplier_name,
                product_name=product_name,
                quantity=qty,
                unit_cost=unit_cost,
                total_amount=round(qty * unit_cost, 2),
                status="Pending"
            )
            db.session.add(po)
            db.session.commit()
            flash(f"Purchase Order {po_no} issued to {supplier_name}.", "success")
            return redirect(url_for("purchase_orders"))

    pos_list = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).all()
    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    products = Product.query.order_by(Product.name.asc()).all()
    return render_template("orders.html", orders=pos_list, suppliers=suppliers, products=products)


@app.route("/orders/receive/<int:order_id>", methods=["POST"])
@login_required
def receive_order(order_id):
    po = PurchaseOrder.query.get_or_404(order_id)
    if po.status != "Received":
        po.status = "Received"
        po.received_at = datetime.utcnow()

        # Update product inventory stock
        prod = Product.query.filter(Product.name.ilike(f"%{po.product_name}%")).first()
        if prod:
            prod.quantity += po.quantity
            prod.cost_price = po.unit_cost

            # Log stock movement
            sm = StockMovement(
                product_id=prod.id,
                type="PO Restock",
                quantity_change=po.quantity,
                unit_cost=po.unit_cost,
                user_id=session.get("user_id"),
                note=f"Received PO #{po.po_number}"
            )
            db.session.add(sm)

        db.session.commit()
        flash(f"Purchase Order #{po.po_number} marked as Received. Stock updated!", "success")

    return redirect(url_for("purchase_orders"))


# ---------------------------------------------------------------------------
# Categories Management
# ---------------------------------------------------------------------------
@app.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        desc = request.form.get("description", "").strip()
        if name:
            if not Category.query.filter_by(name=name).first():
                cat = Category(name=name, description=desc)
                db.session.add(cat)
                db.session.commit()
                flash(f'Category "{name}" created.', "success")
            else:
                flash("Category already exists.", "error")
            return redirect(url_for("categories"))

    cat_list = Category.query.order_by(Category.name.asc()).all()
    return render_template("categories.html", categories=cat_list)


# ---------------------------------------------------------------------------
# Sales Returns & Refund Processing
# ---------------------------------------------------------------------------
@app.route("/returns", methods=["GET", "POST"])
@login_required
def sales_returns():
    if request.method == "POST":
        inv_no = request.form.get("invoice_number", "").strip()
        prod_name = request.form.get("product_name", "").strip()
        qty = int(request.form.get("quantity", 1))
        refund = float(request.form.get("refund_amount", 0))
        reason = request.form.get("reason", "").strip()

        ret_no = "RET-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
        s_return = SalesReturn(
            return_number=ret_no,
            invoice_number=inv_no,
            product_name=prod_name,
            quantity=qty,
            refund_amount=refund,
            reason=reason
        )
        db.session.add(s_return)

        # Restock returned product
        prod = Product.query.filter(Product.name.ilike(f"%{prod_name}%")).first()
        if prod:
            prod.quantity += qty
            sm = StockMovement(
                product_id=prod.id,
                type="Return",
                quantity_change=qty,
                unit_cost=prod.cost_price,
                user_id=session.get("user_id"),
                note=f"Sales Return: {ret_no} ({reason})"
            )
            db.session.add(sm)

        db.session.commit()
        flash(f"Sales Return {ret_no} processed. Stock restocked!", "success")
        return redirect(url_for("sales_returns"))

    returns_list = SalesReturn.query.order_by(SalesReturn.created_at.desc()).all()
    invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(50).all()
    return render_template("returns.html", returns=returns_list, invoices=invoices)




# ---------------------------------------------------------------------------
# NEW FEATURE 2: Customers & Loyalty Points Portal
# ---------------------------------------------------------------------------
@app.route("/customers")
@login_required
def customers():
    customer_list = Customer.query.order_by(Customer.total_spent.desc()).all()
    return render_template("customers.html", customers=customer_list)


# ---------------------------------------------------------------------------
# Point of Sale (POS) Billing & Customer Loyalty Integration
# ---------------------------------------------------------------------------
@app.route("/pos")
@login_required
def pos():
    products = Product.query.filter(Product.quantity > 0).order_by(Product.name.asc()).all()
    customers = Customer.query.order_by(Customer.name.asc()).all()
    return render_template("pos.html", products=products, customers=customers)


@app.route("/pos/checkout", methods=["POST"])
@login_required
def pos_checkout():
    data = request.get_json()
    if not data or not data.get("cart"):
        return jsonify({"success": False, "message": "Cart is empty."}), 400

    try:
        customer_name = data.get("customer_name", "").strip() or "Walk-in Customer"
        customer_phone = data.get("customer_phone", "").strip()
        discount = float(data.get("discount", 0))
        tax_pct = float(data.get("tax_pct", 0))
        payment_method = data.get("payment_method", "Cash")

        inv_no = "INV-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")

        subtotal = 0.0
        invoice_items = []

        # Find or create customer for loyalty tracking
        cust_obj = None
        if customer_phone:
            cust_obj = Customer.query.filter_by(phone=customer_phone).first()
            if not cust_obj:
                cust_obj = Customer(name=customer_name, phone=customer_phone)
                db.session.add(cust_obj)

        for item in data["cart"]:
            prod_id = int(item["id"])
            qty = int(item["qty"])

            # Handle ad-hoc custom POS items
            if prod_id < 0:
                item_total = round(qty * float(item.get("price", 0)), 2)
                subtotal += item_total
                inv_item = InvoiceItem(
                    product_id=1,
                    product_name=item.get("name", "Custom Item"),
                    quantity=qty,
                    unit_price=float(item.get("price", 0)),
                    total_price=item_total
                )
                invoice_items.append(inv_item)
                continue

            product = Product.query.get(prod_id)
            if not product or product.quantity < qty:
                return jsonify({
                    "success": False,
                    "message": f"Insufficient stock for '{product.name if product else prod_id}'"
                }), 400

            item_total = round(qty * product.price, 2)
            subtotal += item_total
            product.quantity -= qty

            sale = Sale(product_id=product.id, quantity=qty, amount=item_total)
            movement = StockMovement(
                product_id=product.id,
                type="Sale",
                quantity_change=-qty,
                unit_cost=product.cost_price,
                user_id=session.get("user_id"),
                note=f"POS Sale: {inv_no}"
            )
            db.session.add(sale)
            db.session.add(movement)

            inv_item = InvoiceItem(
                product_id=product.id,
                product_name=product.name,
                quantity=qty,
                unit_price=product.price,
                total_price=item_total
            )
            invoice_items.append(inv_item)


        tax = round((subtotal - discount) * (tax_pct / 100.0), 2)
        if tax < 0: tax = 0.0
        total_amount = round(subtotal - discount + tax, 2)

        # Update customer loyalty points (1 point per ₹100 spent)
        if cust_obj:
            cust_obj.total_spent += total_amount
            cust_obj.loyalty_points += int(total_amount // 100)

        invoice = Invoice(
            invoice_number=inv_no,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_id=cust_obj.id if cust_obj else None,
            subtotal=subtotal,
            discount=discount,
            tax=tax,
            total_amount=total_amount,
            payment_method=payment_method,
            user_id=session.get("user_id"),
            items=invoice_items
        )
        db.session.add(invoice)
        db.session.commit()

        return jsonify({
            "success": True,
            "invoice_id": invoice.id,
            "invoice_number": inv_no
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Checkout error: {str(e)}"}), 500


@app.route("/invoices/<int:invoice_id>")
@login_required
def view_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template("invoice.html", invoice=invoice)


@app.route("/sales")
@login_required
def sales():
    invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(100).all()
    return render_template("sales.html", invoices=invoices)


@app.route("/movements")
@login_required
def stock_movements():
    movements = StockMovement.query.order_by(StockMovement.timestamp.desc()).limit(150).all()
    return render_template("movements.html", movements=movements)


# ---------------------------------------------------------------------------
# User Management (Admin Only)
# ---------------------------------------------------------------------------
@app.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def users():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "staff")

        if not username or not password:
            flash("Username and password are required.", "error")
        elif User.query.filter_by(username=username).first():
            flash("Username already exists.", "error")
        else:
            user = User(username=username, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash(f'User "{username}" created successfully.', "success")
            return redirect(url_for("users"))

    user_list = User.query.order_by(User.username.asc()).all()
    return render_template("users.html", users=user_list)


@app.route("/users/delete/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == session.get("user_id"):
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("users"))

    user = User.query.get_or_404(user_id)
    name = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{name}" deleted.', "success")
    return redirect(url_for("users"))


# ---------------------------------------------------------------------------
# Reports & CSV Export/Import
# ---------------------------------------------------------------------------
@app.route("/reports")
@login_required
def reports():
    period = request.args.get("period", "daily")

    if period == "monthly":
        bucket_expr = func.strftime("%Y-%m", Sale.sale_date).label("bucket")
        rows = (
            db.session.query(
                bucket_expr,
                func.sum(Sale.quantity).label("total_qty"),
                func.sum(Sale.amount).label("total_amount"),
                func.count(Sale.id).label("num_sales"),
            )
            .group_by(bucket_expr)
            .order_by(bucket_expr.desc())
            .limit(12)
            .all()
        )
    else:
        bucket_expr = func.strftime("%Y-%m-%d", Sale.sale_date).label("bucket")
        rows = (
            db.session.query(
                bucket_expr,
                func.sum(Sale.quantity).label("total_qty"),
                func.sum(Sale.amount).label("total_amount"),
                func.count(Sale.id).label("num_sales"),
            )
            .group_by(bucket_expr)
            .order_by(bucket_expr.desc())
            .limit(30)
            .all()
        )

    top_products = (
        db.session.query(
            Product.name,
            func.sum(Sale.quantity).label("total_qty"),
            func.sum(Sale.amount).label("total_amount"),
        )
        .join(Sale, Sale.product_id == Product.id)
        .group_by(Product.id)
        .order_by(func.sum(Sale.quantity).desc())
        .limit(10)
        .all()
    )

    low_stock_items = Product.query.filter(Product.quantity <= Product.min_stock).order_by(Product.quantity.asc()).all()

    return render_template(
        "reports.html",
        rows=rows,
        period=period,
        top_products=top_products,
        low_stock_items=low_stock_items,
    )


@app.route("/reports/export/<report_type>")
@login_required
def export_report(report_type):
    import pandas as pd
    if report_type == "inventory":
        data = [
            {
                "ID": p.id,
                "SKU": p.sku or "",
                "Barcode": p.barcode or "",
                "Name": p.name,
                "Category": p.category,
                "Supplier": p.supplier,
                "Cost Price": p.cost_price,
                "Selling Price": p.price,
                "Quantity": p.quantity,
                "Min Stock": p.min_stock,
                "Status": "Out of Stock" if p.is_out_of_stock else ("Low Stock" if p.is_low_stock else "OK"),
            }
            for p in Product.query.order_by(Product.name.asc()).all()
        ]
        filename = "shelfsync_inventory_report.csv"
    elif report_type == "sales":
        data = [
            {
                "Invoice No": inv.invoice_number,
                "Customer": inv.customer_name,
                "Payment Method": inv.payment_method,
                "Subtotal": inv.subtotal,
                "Discount": inv.discount,
                "Tax": inv.tax,
                "Total Amount": inv.total_amount,
                "Date": inv.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for inv in Invoice.query.order_by(Invoice.created_at.desc()).all()
        ]
        filename = "shelfsync_sales_report.csv"
    else:
        flash("Unknown report type.", "error")
        return redirect(url_for("reports"))

    df = pd.DataFrame(data)
    csv_data = df.to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/products/import", methods=["POST"])
@login_required
@admin_required
def import_products():
    if "csv_file" not in request.files:
        flash("No file selected.", "error")
        return redirect(url_for("products"))

    file = request.files["csv_file"]
    if not file.filename.endswith(".csv"):
        flash("File must be a .csv format.", "error")
        return redirect(url_for("products"))

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        added_count = 0

        for row in csv_input:
            name = row.get("Name", "").strip()
            if not name: continue

            product = Product(
                sku=row.get("SKU", "").strip() or None,
                barcode=row.get("Barcode", "").strip() or None,
                name=name,
                category=row.get("Category", "").strip(),
                supplier=row.get("Supplier", "").strip(),
                cost_price=float(row.get("Cost Price", 0) or 0),
                price=float(row.get("Selling Price", row.get("Price", 0)) or 0),
                quantity=int(row.get("Quantity", 0) or 0),
                min_stock=int(row.get("Min Stock", 5) or 5),
            )
            db.session.add(product)
            added_count += 1

        db.session.commit()
        flash(f"Imported {added_count} products into ShelfSync.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error importing CSV: {str(e)}", "error")

    return redirect(url_for("products"))


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------
def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", role="admin")
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            print("ShelfSync Admin created: admin / admin123")


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
