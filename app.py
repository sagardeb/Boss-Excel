from flask import Flask, request, redirect, url_for, render_template_string, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import os
import random

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sales_stock.db'
db = SQLAlchemy(app)

# Database Models
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    stock = db.Column(db.Float, nullable=True)

class Sales(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

# Initialize DB
with app.app_context():
    db.create_all()
    if not Product.query.first():
        db.session.add_all([
            Product(name="Product A"),
            Product(name="Product B"),
            Product(name="Product C"),
        ])
        db.session.commit()

# ===== TEMP: Seed last 7 months random sales =====
with app.app_context():
    year = datetime.now().year
    products = Product.query.all()
    current_month = datetime.now().month
    for m in range(current_month-7, current_month):
        if m >= 1:
            for p in products:
                exists = Sales.query.filter_by(year=year, month=m, product_id=p.id).first()
                if not exists:
                    qty = random.randint(5, 50)
                    db.session.add(Sales(year=year, month=m, product_id=p.id, quantity=qty))
    db.session.commit()
# ===== END TEMP =====

# HTML Base Template
BASE = """
<!doctype html>
<html>
<head>
    <title>Sales & Stock App</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
</head>
<body class="p-4">
<div class="container">
    <h1>Sales & Stock App</h1>
    <nav>
        <a href="{{ url_for('sales') }}" class="btn btn-primary btn-sm">Sales Entry</a>
        <a href="{{ url_for('stock') }}" class="btn btn-secondary btn-sm">Stock Entry</a>
        <a href="{{ url_for('report') }}" class="btn btn-info btn-sm">Report</a>
    </nav>
    <hr>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <div class="alert alert-success">{{ messages[0] }}</div>
      {% endif %}
    {% endwith %}
    {{ content|safe }}
</div>
</body>
</html>
"""

@app.route("/")
def home():
    return redirect(url_for("sales"))

@app.route("/stock", methods=["GET","POST"])
def stock():
    products = Product.query.all()
    if request.method == "POST":
        for p in products:
            val = request.form.get(str(p.id))
            if val:
                p.stock = float(val)
        db.session.commit()
        flash("Stock updated successfully.")
        return redirect(url_for("stock"))

    form_html = "<form method='post'><table class='table'><tr><th>Product</th><th>Stock</th></tr>"
    for p in products:
        val = p.stock if p.stock is not None else ""
        form_html += f"<tr><td>{p.name}</td><td><input name='{p.id}' value='{val}'></td></tr>"
    form_html += "</table><button class='btn btn-success'>Save</button></form>"
    return render_template_string(BASE, content=form_html)

@app.route("/sales", methods=["GET","POST"])
def sales():
    year = datetime.now().year
    month = datetime.now().month
    products = Product.query.all()
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
    form_html += "</table><button class='btn btn-success'>Save</button></form>"

    # Read-only previous months in current year
    prev_months = Sales.query.filter(Sales.year == year, Sales.month < month).order_by(Sales.month).all()
    if prev_months:
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
    sales = Sales.query.all()
    data = [{"Year": s.year, "Month": s.month, "Product": s.product.name, "Quantity": s.quantity} for s in sales]
    df = pd.DataFrame(data)
    csv_path = "report.xlsx"
    df.to_excel(csv_path, index=False)
    return send_file(csv_path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
