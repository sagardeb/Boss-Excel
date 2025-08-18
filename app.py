from flask import Flask, render_template_string, request, redirect, url_for
import sqlite3
import random

app = Flask(__name__)

DB_NAME = "sales.db"

PRODUCTS = [
    "Bikes",
    "Scooters",
    "Harleys",
    "ATVs",
    "PWCs",
    "Boats",
    "Snowmobiles",
    "All Used Units"
]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Base January sales from your Excel
BASE_SALES = {
    "Bikes": 10,
    "Scooters": 10,
    "Harleys": 4,
    "ATVs": 45,
    "PWCs": 4,
    "Boats": 2,
    "Snowmobiles": 3,
    "All Used Units": 45
}

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    month TEXT,
                    product TEXT,
                    units INTEGER,
                    stock INTEGER
                )""")
    conn.commit()

    # Seed only if empty
    c.execute("SELECT COUNT(*) FROM sales")
    if c.fetchone()[0] == 0:
        for i, month in enumerate(MONTHS):
            for product in PRODUCTS:
                units = None
                if i < 7:  # Jan–Jul with ±20% variation
                    base = BASE_SALES[product]
                    units = max(0, int(base * random.uniform(0.8, 1.2)))
                c.execute("INSERT INTO sales (month, product, units, stock) VALUES (?,?,?,?)",
                          (month, product, units, None))
    conn.commit()
    conn.close()

@app.route("/")
def index():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT DISTINCT month FROM sales")
    months = [row[0] for row in c.fetchall()]
    conn.close()
    return render_template_string("""
        <h1>Sales Entry</h1>
        <ul>
        {% for m in months %}
            <li><a href="{{ url_for('enter_sales', month=m) }}">{{ m }}</a></li>
        {% endfor %}
        </ul>
        <a href="{{ url_for('report') }}">View Report</a>
    """, months=months)

@app.route("/enter/<month>", methods=[GET, POST])
def enter_sales(month):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if request.method == "POST":
        for product in PRODUCTS:
            units = request.form.get(f"units_{product}")
            stock = request.form.get(f"stock_{product}")
            c.execute("UPDATE sales SET units=?, stock=? WHERE month=? AND product=?",
                      (units if units else None,
                       stock if stock else None,
                       month, product))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    c.execute("SELECT product, units, stock FROM sales WHERE month=?", (month,))
    rows = c.fetchall()
    conn.close()

    return render_template_string("""
        <h2>Enter Sales for {{ month }}</h2>
        <form method="post">
        <table border="1">
            <tr><th>Product</th><th>Units Sold</th><th>Stock</th></tr>
            {% for product, units, stock in rows %}
            <tr>
                <td>{{ product }}</td>
                <td><input type="number" name="units_{{ product }}" value="{{ units or '' }}"></td>
                <td><input type="number" name="stock_{{ product }}" value="{{ stock or '' }}"></td>
            </tr>
            {% endfor %}
        </table>
        <input type="submit" value="Save">
        </form>
        <a href="{{ url_for('index') }}">Back</a>
    """, month=month, rows=rows)

@app.route("/report")
def report():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT month, product, units FROM sales")
    rows = c.fetchall()
    conn.close()

    # Organize by month
    data = {m: {p: 0 for p in PRODUCTS} for m in MONTHS}
    for month, product, units in rows:
        if units:
            data[month][product] = units

    # Totals and APUS
    totals = {m: sum(data[m].values()) for m in MONTHS}
    apus = {m: (sum(data[m].values())/len(PRODUCTS) if totals[m] > 0 else 0) for m in MONTHS}
    grand_total = sum(totals.values())
    percent_sales = {m: (totals[m]/grand_total*100 if grand_total>0 else 0) for m in MONTHS}

    return render_template_string("""
        <h1>Yearly Sales Report</h1>
        <table border="1">
            <tr>
                <th>Month</th>
                {% for p in products %}<th>{{p}}</th>{% endfor %}
                <th>Total</th><th>APUS</th><th>% of Sales</th>
            </tr>
            {% for m in months %}
            <tr>
                <td>{{ m }}</td>
                {% for p in products %}<td>{{ data[m][p] }}</td>{% endfor %}
                <td>{{ totals[m] }}</td>
                <td>{{ '%.2f' % apus[m] }}</td>
                <td>{{ '%.2f' % percent_sales[m] }}%</td>
            </tr>
            {% endfor %}
        </table>
        <a href="/">Back</a>

        <h2>Charts</h2>
        <div id="chart_div" style="width: 900px; height: 500px;"></div>
        <script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
        <script type="text/javascript">
          google.charts.load('current', {'packages':['corechart']});
          google.charts.setOnLoadCallback(drawChart);
          function drawChart() {
            var data = google.visualization.arrayToDataTable([
              ['Month', {% for p in products %}'{{p}}',{% endfor %} 'Total'],
              {% for m in months %}
                ['{{m}}', {% for p in products %} {{ data[m][p] }}, {% endfor %} {{ totals[m] }}],
              {% endfor %}
            ]);

            var options = { title: 'Monthly Sales by Product', curveType: 'function', legend: { position: 'bottom' } };
            var chart = new google.visualization.LineChart(document.getElementById('chart_div'));
            chart.draw(data, options);
          }
        </script>
    """, products=PRODUCTS, months=MONTHS, data=data, totals=totals, apus=apus, percent_sales=percent_sales) 

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0")
