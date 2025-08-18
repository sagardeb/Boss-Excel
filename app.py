from flask import Flask, render_template_string, request, redirect, url_for
import sqlite3
import calendar

app = Flask(__name__)

# --- Database setup ---
DB_FILE = "sales.db"
PRODUCTS = ["Bikes", "Scooters", "Harleys", "ATV's", "PWC's", "Boats", "Snowmobiles"]
MONTHS = list(calendar.month_name)[1:]

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT,
    product TEXT,
    stock INTEGER,
    sales INTEGER
)
""")
conn.commit()

# --- Home ---
@app.route("/")
def home():
    return render_template_string("""
        <h1>Sales Entry</h1>
        <ul>
            {% for m in months %}
                <li><a href="{{ url_for('enter_sales', month=m) }}">{{ m }}</a></li>
            {% endfor %}
        </ul>
        <a href="{{ url_for('report') }}">📊 View Report</a>
    """, months=MONTHS)

# --- Sales entry ---
@app.route("/enter/<month>", methods=["GET", "POST"])
def enter_sales(month):
    # find month index
    month_index = MONTHS.index(month)

    # find current max entered month
    c.execute("SELECT DISTINCT month FROM sales")
    entered_months = [row[0] for row in c.fetchall()]
    entered_index = [MONTHS.index(m) for m in entered_months] if entered_months else []

    is_readonly = (month_index < max(entered_index, default=-1))

    if request.method == "POST" and not is_readonly:
        for p in PRODUCTS:
            stock = request.form.get(f"stock_{p}")
            sales = request.form.get(f"sales_{p}")

            # Stock only for January
            stock_val = int(stock) if (stock and month == "January") else None
            sales_val = int(sales) if sales else 0

            # check if exists
            c.execute("SELECT id FROM sales WHERE month=? AND product=?", (month, p))
            row = c.fetchone()
            if row:
                c.execute("UPDATE sales SET stock=?, sales=? WHERE id=?", (stock_val, sales_val, row[0]))
            else:
                c.execute("INSERT INTO sales (month, product, stock, sales) VALUES (?,?,?,?)",
                          (month, p, stock_val, sales_val))
        conn.commit()
        return redirect(url_for('home'))

    # fetch data
    c.execute("SELECT product, stock, sales FROM sales WHERE month=?", (month,))
    rows = {r[0]: (r[1], r[2]) for r in c.fetchall()}

    return render_template_string("""
        <h2>Enter Sales for {{ month }}</h2>
        <form method="post">
            <table border="1" cellpadding="5">
                <tr><th>Product</th>{% if month=='January' %}<th>Stock</th>{% endif %}<th>Sales</th></tr>
                {% for p in products %}
                <tr>
                    <td>{{ p }}</td>
                    {% if month=='January' %}
                        <td><input type="number" name="stock_{{p}}" value="{{ rows.get(p,(None,None))[0] or '' }}" {% if readonly %}readonly{% endif %}></td>
                    {% endif %}
                    <td><input type="number" name="sales_{{p}}" value="{{ rows.get(p,(None,None))[1] or '' }}" {% if readonly %}readonly{% endif %}></td>
                </tr>
                {% endfor %}
            </table>
            {% if not readonly %}<button type="submit">Save</button>{% endif %}
        </form>
        <a href="/">⬅ Back</a>
    """, month=month, products=PRODUCTS, rows=rows, readonly=is_readonly)

# --- Report ---
@app.route("/report")
def report():
    # fetch all
    c.execute("SELECT month, product, COALESCE(stock,0), sales FROM sales")
    data = c.fetchall()

    # reshape
    sales_data = {m: {p:0 for p in PRODUCTS} for m in MONTHS}
    for m,p,stock,sales in data:
        sales_data[m][p] = sales

    totals = {p: sum(sales_data[m][p] for m in MONTHS) for p in PRODUCTS}
    grand_total = sum(totals.values())

    apus = {p: (totals[p]/12 if totals[p]>0 else 0) for p in PRODUCTS}
    percents = {p: (totals[p]/grand_total*100 if grand_total>0 else 0) for p in PRODUCTS}

    return render_template_string("""
        <h1>📊 Sales Report</h1>

        <div style="display:flex; gap:20px;">
            <div style="flex:1;">
                <h3>Monthly Sales Trend</h3>
                <canvas id="lineChart"></canvas>
            </div>
            <div style="flex:1;">
                <h3>% Contribution by Product</h3>
                <canvas id="barChart"></canvas>
            </div>
        </div>

        <h3>Totals</h3>
        <table border="1" cellpadding="5">
            <tr><th>Product</th><th>Total</th><th>APUS</th><th>% of Sales</th></tr>
            {% for p in products %}
            <tr>
                <td>{{ p }}</td>
                <td>{{ totals[p] }}</td>
                <td>{{ '%.2f' % apus[p] }}</td>
                <td>{{ '%.1f' % percents[p] }}%</td>
            </tr>
            {% endfor %}
        </table>

        <a href="/">⬅ Back</a>

        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
        const lineCtx = document.getElementById('lineChart').getContext('2d');
        new Chart(lineCtx, {
            type: 'line',
            data: {
                labels: {{ months|tojson }},
                datasets: [
                    {% for p in products %}
                    {
                        label: '{{p}}',
                        data: {{ [sales_data[m][p] for m in months]|tojson }},
                        fill: false,
                        borderWidth: 2
                    },
                    {% endfor %}
                ]
            }
        });

        const barCtx = document.getElementById('barChart').getContext('2d');
        new Chart(barCtx, {
            type: 'bar',
            data: {
                labels: {{ products|tojson }},
                datasets: [{
                    label: '% of Sales',
                    data: {{ [percents[p] for p in products]|tojson }},
                    backgroundColor: 'rgba(75,192,192,0.6)'
                }]
            }
        });
        </script>
    """, products=PRODUCTS, months=MONTHS, sales_data=sales_data, totals=totals, apus=apus, percents=percents)

if __name__ == "__main__":
    app.run(debug=True)
