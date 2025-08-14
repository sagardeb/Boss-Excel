from flask import Flask, request, redirect, url_for, render_template_string, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
import os
import io
import pandas as pd
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sales_stock.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Models ---
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('Product')
    __table_args__ = (db.UniqueConstraint('year','product_id', name='uix_year_product'),)

class Sales(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('Product')
    __table_args__ = (db.UniqueConstraint('year','month','product_id', name='uix_year_month_product'),)

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# --- Base Template ---
BASE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Sales & Stock App</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
</head>
<body class="p-4">
<div class="container">
    <h1 class="mb-4">Sales & Stock App</h1>
    <nav class="mb-4">
        <a href="{{ url_for('index') }}" class="btn btn-secondary btn-sm">Home</a>
        <a href="{{ url_for('products') }}" class="btn btn-secondary btn-sm">Products</a>
        <a href="{{ url_for('enter_stock') }}" class="btn btn-secondary btn-sm">Enter Annual Stock</a>
        <a href="{{ url_for('enter_sales') }}" class="btn btn-secondary btn-sm">Enter Monthly Sales</a>
        <a href="{{ url_for('report') }}" class="btn btn-secondary btn-sm">Reports</a>
    </nav>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <div class="alert alert-info">
          {% for m in messages %}{{ m }}<br>{% endfor %}
        </div>
      {% endif %}
    {% endwith %}
    {{ content|safe }}
</div>
</body>
</html>"""

# --- Routes ---
@app.route('/')
def index():
    return render_template_string(BASE_HTML, content="<p>Welcome! Use the navigation buttons above.</p>")

@app.route('/products', methods=['GET','POST'])
def products():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            try:
                db.session.add(Product(name=name))
                db.session.commit()
                flash("Product added.")
            except Exception as e:
                db.session.rollback()
                flash(f"Error adding product: {e}")
        return redirect(url_for('products'))
    rows = Product.query.all()
    table = "<h3>Products</h3><ul>" + "".join(f"<li>{p.name}</li>" for p in rows) + "</ul>"
    form = """
    <form method="post">
    <input name="name" placeholder="Product name" required>
    <button class="btn btn-primary btn-sm">Add</button>
    </form>
    """
    return render_template_string(BASE_HTML, content=table+form)

@app.route('/enter_stock', methods=['GET','POST'])
def enter_stock():
    year = datetime.now().year
    products = Product.query.all()
    existing = Stock.query.filter_by(year=year).count()
    if request.method == 'POST' and existing == 0:
        for p in products:
            qty = request.form.get(f'prod_{p.id}')
            if qty:
                db.session.add(Stock(year=year, product_id=p.id, quantity=float(qty)))
        db.session.commit()
        flash("Stock saved for the year.")
        return redirect(url_for('enter_stock'))
    stocks = {s.product_id: s.quantity for s in Stock.query.filter_by(year=year).all()}
    rows = "<form method='post'><table class='table'><tr><th>Product</th><th>Stock Qty</th></tr>"
    for p in products:
        val = stocks.get(p.id,"")
        disabled = "disabled" if existing else ""
        rows += f"<tr><td>{p.name}</td><td><input name='prod_{p.id}' value='{val}' {disabled}></td></tr>"
    rows += "</table>"
    if existing == 0:
        rows += "<button class='btn btn-primary'>Save Stock</button>"
    rows += "</form>"
    return render_template_string(BASE_HTML, content=f"<h3>Annual Stock for {year}</h3>"+rows)

@app.route('/enter_sales', methods=['GET','POST'])
def enter_sales():
    year = datetime.now().year
    month = datetime.now().month
    products = Product.query.all()
    if request.method == 'POST':
        for p in products:
            qty = request.form.get(f'prod_{p.id}')
            if qty:
                existing = Sales.query.filter_by(year=year, month=month, product_id=p.id).first()
                if existing:
                    existing.quantity = float(qty)
                else:
                    db.session.add(Sales(year=year, month=month, product_id=p.id, quantity=float(qty)))
        db.session.commit()
        flash(f"Sales saved for {MONTHS[month-1]} {year}.")
        return redirect(url_for('enter_sales'))
    sales_data = {s.product_id: s.quantity for s in Sales.query.filter_by(year=year, month=month).all()}
    rows = f"<form method='post'><h3>Sales for {MONTHS[month-1]} {year}</h3><table class='table'><tr><th>Product</th><th>Sales Qty</th></tr>"
    for p in products:
        val = sales_data.get(p.id,"")
        rows += f"<tr><td>{p.name}</td><td><input name='prod_{p.id}' value='{val}'></td></tr>"
    rows += "</table><button class='btn btn-primary'>Save Sales</button></form>"
    return render_template_string(BASE_HTML, content=rows)

@app.route('/report')
def report():
    year = datetime.now().year
    products = Product.query.all()
    stocks = {s.product_id: s.quantity for s in Stock.query.filter_by(year=year).all()}
    sales_summary = db.session.query(
        Sales.product_id, func.sum(Sales.quantity)
    ).filter_by(year=year).group_by(Sales.product_id).all()
    sales_totals = {pid: total for pid,total in sales_summary}
    rows = f"<h3>Report for {year}</h3><table class='table'><tr><th>Product</th><th>Stock</th><th>Total Sales</th><th>Remaining</th></tr>"
    for p in products:
        stock_qty = stocks.get(p.id,0)
        sold = sales_totals.get(p.id,0) or 0
        remaining = stock_qty - sold
        rows += f"<tr><td>{p.name}</td><td>{stock_qty}</td><td>{sold}</td><td>{remaining}</td></tr>"
    rows += "</table><a href='" + url_for('export_excel') + "' class='btn btn-success'>Export to Excel</a>"
    return render_template_string(BASE_HTML, content=rows)

@app.route('/export_excel')
def export_excel():
    year = datetime.now().year
    products = Product.query.all()
    stocks = {s.product_id: s.quantity for s in Stock.query.filter_by(year=year).all()}
    sales_summary = db.session.query(
        Sales.product_id, func.sum(Sales.quantity)
    ).filter_by(year=year).group_by(Sales.product_id).all()
    sales_totals = {pid: total for pid,total in sales_summary}
    data = []
    for p in products:
        stock_qty = stocks.get(p.id,0)
        sold = sales_totals.get(p.id,0) or 0
        remaining = stock_qty - sold
        data.append({"Product": p.name, "Stock": stock_qty, "Total Sales": sold, "Remaining": remaining})
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"report_{year}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# --- Ensure DB exists & seed products ---
with app.app_context():
    db.create_all()
    if Product.query.count() == 0:
        for name in ['Product A', 'Product B', 'Product C', 'Product D']:
            db.session.add(Product(name=name))
        db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
