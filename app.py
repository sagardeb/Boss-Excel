from flask import Flask, request, redirect, url_for, render_template_string, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
import pandas as pd
import io
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sales_stock.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ====== MODELS ======
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    __table_args__ = (db.UniqueConstraint('year', 'product_id', name='uniq_stock'),)

class Sales(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    __table_args__ = (db.UniqueConstraint('year', 'month', 'product_id', name='uniq_sales'),)

# ====== BASIC TEMPLATE ======
BASE = """
<!doctype html>
<html>
<head>
<title>Sales & Stock</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
</head>
<body class="p-4">
<div class="container">
<h1>Sales & Stock</h1>
<nav>
<a href="/">Home</a> | 
<a href="/products">Products</a> | 
<a href="/stock">Annual Stock</a> | 
<a href="/sales">Monthly Sales</a> | 
<a href="/report">Reports</a>
</nav>
<hr>
{% with msgs = get_flashed_messages() %}
{% if msgs %}<div class="alert alert-info">{{ msgs[0] }}</div>{% endif %}
{% endwith %}
{{ content|safe }}
</div>
</body>
</html>
"""

# ====== ROUTES ======
@app.route("/")
def home():
    return render_template_string(BASE, content="<p>Welcome! Use the menu above.</p>")

@app.route("/products", methods=["GET","POST"])
def products():
    if request.method == "POST":
        name = request.form.get("name")
        if name:
            db.session.add(Product(name=name))
            db.session.commit()
            flash("Product added.")
        return redirect(url_for("products"))
    rows = "".join(f"<li>{p.name}</li>" for p in Product.query.all())
    form = '<form method="post"><input name="name" required> <button>Add</button></form>'
    return render_template_string(BASE, content=f"<ul>{rows}</ul>{form}")

@app.route("/stock", methods=["GET","POST"])
def stock():
    year = datetime.now().year
    products = Product.query.all()
    existing = {s.product_id: s.quantity for s in Stock.query.filter_by(year=year).all()}
    if request.method == "POST" and not existing:
        for p in products:
            qty = request.form.get(str(p.id))
            if qty:
                db.session.add(Stock(year=year, product_id=p.id, quantity=float(qty)))
        db.session.commit()
        flash("Stock saved for this year.")
        return redirect(url_for("stock"))
    table = '<form method="post"><table class="table">'
    for p in products:
        val = existing.get(p.id, "")
        dis = "disabled" if existing else ""
        table += f"<tr><td>{p.name}</td><td><input name='{p.id}' value='{val}' {dis}></td></tr>"
    table += "</table>"
    if not existing:
        table += "<button>Save</button>"
    table += "</form>"
    return render_template_string(BASE, content=table)

@app.route("/sales", methods=["GET","POST"])
def sales():
    year = datetime.now().year
    month = datetime.now().month
    products = Product.query.all()

    # Existing sales for current month
    existing = {s.product_id: s.quantity for s in Sales.query.filter_by(year=year, month=month).all()}

    if request.method == "POST":
        for p in products:
            qty = request.form.get(str(p.id))
            if qty:
                if p.id in existing:
                    rec = Sales.query.filter_by(year=year, month=month, product_id=p.id).first()
                    rec.quantity = float(qty)
                else:
                    db.session.add(Sales(year=year, month=month, product_id=p.id, quantity=float(qty)))
        db.session.commit()
        flash("Sales saved.")
        return redirect(url_for("sales"))

    # Editable form for current month
    form_html = f"<form method='post'><h3>{year} - {month}</h3><table class='table'>"
    for p in products:
        val = existing.get(p.id, "")
        form_html += f"<tr><td>{p.name}</td><td><input name='{p.id}' value='{val}'></td></tr>"
    form_html += "</table><button>Save</button></form>"

    # Read-only previous months of the year
    prev_months = Sales.query.filter(Sales.year == year, Sales.month < month).order_by(Sales.month).all()
    if prev_months:
        # Group sales by month
        month_data = {}
        for s in prev_months:
            month_data.setdefault(s.month, {})[s.product_id] = s.quantity

        table_html = "<h3>Previous Months</h3>"
        for m in sorted(month_data.keys()):
            table_html += f"<h5>{year} - {m}</h5><table class='table'>"
            for p in products:
                qty = month_data[m].get(p.id, "")
                table_html += f"<tr><td>{p.name}</td><td>{qty}</td></tr>"
            table_html += "</table>"
    else:
        table_html = "<p>No previous month data.</p>"

    return render_template_string(BASE, content=form_html + "<hr>" + table_html)


@app.route("/report")
def report():
    year = datetime.now().year
    products = Product.query.all()
    stocks = {s.product_id: s.quantity for s in Stock.query.filter_by(year=year).all()}
    sales_sum = {pid: total for pid, total in db.session.query(Sales.product_id, func.sum(Sales.quantity)).filter_by(year=year).group_by(Sales.product_id).all()}
    rows = "<table class='table'><tr><th>Product</th><th>Stock</th><th>Sales</th><th>Remaining</th></tr>"
    for p in products:
        st = stocks.get(p.id, 0)
        sl = sales_sum.get(p.id, 0)
        rows += f"<tr><td>{p.name}</td><td>{st}</td><td>{sl}</td><td>{st - sl}</td></tr>"
    rows += "</table><a href='/export'>Export to Excel</a>"
    return render_template_string(BASE, content=rows)

@app.route("/export")
def export():
    year = datetime.now().year
    products = Product.query.all()
    stocks = {s.product_id: s.quantity for s in Stock.query.filter_by(year=year).all()}
    sales_sum = {pid: total for pid, total in db.session.query(Sales.product_id, func.sum(Sales.quantity)).filter_by(year=year).group_by(Sales.product_id).all()}
    data = []
    for p in products:
        st = stocks.get(p.id, 0)
        sl = sales_sum.get(p.id, 0)
        data.append({"Product": p.name, "Stock": st, "Sales": sl, "Remaining": st - sl})
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"report_{year}.xlsx")

# ====== INIT DB ======
with app.app_context():
    db.create_all()
    if Product.query.count() == 0:
        db.session.add_all([Product(name=f"Product {x}") for x in ["A","B","C","D"]])
        db.session.commit()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
