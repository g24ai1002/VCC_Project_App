import logging
import os
import time
import pandas as pd
from datetime import datetime, date

import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for matplotlib

from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import yfinance as yf
from werkzeug.security import generate_password_hash, check_password_hash
import io
import matplotlib.pyplot as plt

# Set up error logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app and configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database/app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database and login manager
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Import models from models.py
from models import db as models_db, User, Favorite, Holding
models_db.init_app(app)

# Create tables if they don’t already exist
with app.app_context():
    models_db.create_all()

# -------------------------------
# In-memory cache for live price data (for detail view)
price_cache = {}
CACHE_DURATION = 300  # seconds

def get_price(symbol):
    """
    Retrieve the latest live price for a given symbol.
    Uses fast_info first, falls back to detailed info, and caches the result.
    (Used on the detail page only.)
    """
    now = time.time()
    if symbol in price_cache:
        cached_price, timestamp = price_cache[symbol]
        if now - timestamp < CACHE_DURATION:
            return cached_price

    try:
        ticker = yf.Ticker(symbol)
        fast_info = ticker.fast_info
        price = fast_info.get('last_price')
        if price is None:
            info = ticker.info
            price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('previousClose')
        if price is None:
            price = 'N/A'
    except Exception as e:
        logger.error(f"Error fetching live price for {symbol}: {e}")
        price = 'N/A'
    price_cache[symbol] = (price, now)
    return price

# -------------------------------
# Update Market Data Daily (CSV with columns: symbol, open, high, low, close, volume)
def update_market_data():
    """
    Downloads market data for a set of symbols and saves them to market_data.csv.
    If the CSV file exists and was updated today, it does not update again.
    """
    csv_file = "market_data.csv"
    if os.path.exists(csv_file):
        mod_time = datetime.fromtimestamp(os.path.getmtime(csv_file)).date()
        if mod_time == date.today():
            logger.info("Market data CSV is up-to-date.")
            return

    # Define symbol lists.
    top_shares = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"]
    currencies = ["USDINR=X", "EURINR=X", "GBPINR=X", "JPYINR=X", "AUDINR=X"]
    commodities = ["GOLDBEES.NS", "SILVERBEE.NS"]

    all_symbols = top_shares + currencies + commodities
    data_rows = []
    for symbol in all_symbols:
        try:
            ticker = yf.Ticker(symbol)
            time.sleep(1)  # Optional delay to help avoid rate limits
            hist = ticker.history(period="1d")
            if hist.empty:
                logger.error(f"No historical data for {symbol}")
                continue
            # Get the latest available row
            row = hist.iloc[-1]
            data_rows.append({
                "symbol": symbol,
                "open": row["Open"],
                "high": row["High"],
                "low": row["Low"],
                "close": row["Close"],
                "volume": row["Volume"]
            })
            logger.info(f"Fetched market data for {symbol}")
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")

    df = pd.DataFrame(data_rows)
    df.to_csv(csv_file, index=False)
    logger.info(f"Market data updated and saved to {csv_file}")

# Update market data at startup
update_market_data()

# -------------------------------
# User loader for flask-login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------------------
# Context processor to inject contact info from contact.txt
@app.context_processor
def inject_contact():
    try:
        with open('contact.txt', 'r') as f:
            contact = f.read()
    except Exception as e:
        logger.error(f"Error reading contact.txt: {e}")
        contact = "Contact us at support@example.com"
    return dict(contact_info=contact)

# -------------------------------
# Home: Redirect to menu (if logged in) or to login page
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('menu'))
    return redirect(url_for('login'))

# -------------------------------
# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('menu'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('menu'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html')

# -------------------------------
# Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('menu'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password, method='sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('menu'))
    return render_template('register.html')

# -------------------------------
# Main Menu Dashboard Route
@app.route('/menu')
@login_required
def menu():
    return render_template('menu.html')

# -------------------------------
# "My Favorite Shares" Route – using internal data only (price placeholder)
@app.route('/favorites', methods=['GET'])
@login_required
def favorites():
    search = request.args.get('search', '')
    favs = Favorite.query.filter_by(user_id=current_user.id).all()
    favorites_data = []
    for fav in favs:
        if search and search.lower() not in fav.stock_symbol.lower():
            continue
        favorites_data.append({
            'stock_symbol': fav.stock_symbol,
            'name': fav.stock_symbol,
            'price': "Click to view"
        })
    return render_template('favorites.html', favorites=favorites_data)

# -------------------------------
# Route to add a favorite via POST
@app.route('/add_favorite_post', methods=['POST'])
@login_required
def add_favorite_post():
    symbol = request.form.get('symbol')
    exists = Favorite.query.filter_by(stock_symbol=symbol, user_id=current_user.id).first()
    if not exists:
        new_fav = Favorite(stock_symbol=symbol, user_id=current_user.id)
        db.session.add(new_fav)
        db.session.commit()
        flash('Favorite added', 'success')
    else:
        flash('Favorite already exists', 'warning')
    return redirect(url_for('favorites'))

# -------------------------------
# Remove favorite route
@app.route('/remove_favorite/<symbol>')
@login_required
def remove_favorite(symbol):
    fav = Favorite.query.filter_by(stock_symbol=symbol, user_id=current_user.id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        flash('Favorite removed', 'success')
    return redirect(url_for('favorites'))

# -------------------------------
# "All Shares" Route – read details from CSV and use the "close" column as price
@app.route('/shares')
@login_required
def shares():
    search = request.args.get('search', '').lower()
    try:
        df = pd.read_csv("market_data.csv")
    except Exception as e:
        logger.error(f"Error reading market_data.csv: {e}")
        df = pd.DataFrame(columns=["symbol", "open", "high", "low", "close", "volume"])

    # Define your top shares list (adjust/extend as needed)
    top_shares = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"]
    df_shares = df[df["symbol"].isin(top_shares)]
    if search:
        df_shares = df_shares[
            df_shares["symbol"].str.lower().str.contains(search)
        ]
    shares_list = df_shares.to_dict(orient="records")
    for share in shares_list:
        share["price"] = share.get("close", "N/A")
        share["name"] = share.get("symbol", "N/A")
    return render_template("shares.html", shares=shares_list)

# -------------------------------
# "All Commodities" Route – read details from CSV
@app.route('/commodities')
@login_required
def commodities():
    try:
        df = pd.read_csv("market_data.csv")
    except Exception as e:
        logger.error(f"Error reading market_data.csv: {e}")
        df = pd.DataFrame(columns=["symbol", "open", "high", "low", "close", "volume"])

    commodities_list = ["GOLDBEES.NS", "SILVERBEE.NS"]
    df_comm = df[df["symbol"].isin(commodities_list)]
    comm_data = df_comm.to_dict(orient="records")
    for row in comm_data:
        row["price"] = row.get("close", "N/A")
        row["name"] = row.get("symbol", "N/A")
    return render_template("commodities.html", commodities=comm_data)

# -------------------------------
# "All Currencies" Route – read details from CSV
@app.route('/currencies')
@login_required
def currencies():
    try:
        df = pd.read_csv("market_data.csv")
    except Exception as e:
        logger.error(f"Error reading market_data.csv: {e}")
        df = pd.DataFrame(columns=["symbol", "open", "high", "low", "close", "volume"])

    currencies_list = ["USDINR=X", "EURINR=X", "GBPINR=X", "JPYINR=X", "AUDINR=X"]
    df_curr = df[df["symbol"].isin(currencies_list)]
    curr_data = df_curr.to_dict(orient="records")
    for row in curr_data:
        row["price"] = row.get("close", "N/A")
        row["name"] = row.get("symbol", "N/A")
    return render_template("currencies.html", currencies=curr_data)

# -------------------------------
# "My Holdings" Route – live price fetch (for calculations)
@app.route('/holdings', methods=['GET'])
@login_required
def holdings():
    user_holdings = Holding.query.filter_by(user_id=current_user.id).all()
    holdings_data = []
    for h in user_holdings:
        current_price = get_price(h.asset_symbol)
        calc_price = current_price if isinstance(current_price, (int, float)) else 0
        profit_loss = (calc_price - h.purchase_price) * h.quantity
        profit_loss_pct = ((calc_price - h.purchase_price) / h.purchase_price * 100) if h.purchase_price != 0 else 0
        holdings_data.append({
            'asset_symbol': h.asset_symbol,
            'asset_type': h.asset_type,
            'quantity': h.quantity,
            'purchase_price': h.purchase_price,
            'current_price': current_price,
            'profit_loss': round(profit_loss, 2),
            'profit_loss_pct': round(profit_loss_pct, 2)
        })
    return render_template("holdings.html", holdings=holdings_data)

@app.route('/holdings', methods=['POST'])
@login_required
def add_holding():
    asset_type = request.form.get('asset_type')
    asset_symbol = request.form.get('asset_symbol')
    quantity = float(request.form.get('quantity'))
    purchase_price = float(request.form.get('purchase_price'))
    new_holding = Holding(
        asset_type=asset_type,
        asset_symbol=asset_symbol,
        quantity=quantity,
        purchase_price=purchase_price,
        user_id=current_user.id
    )
    db.session.add(new_holding)
    db.session.commit()
    flash('Holding added', 'success')
    return redirect(url_for('holdings'))

# -------------------------------
# "Share Page" Route – live price fetch on detail view
@app.route('/share/<symbol>')
@login_required
def share(symbol):
    try:
        ticker = yf.Ticker(symbol)
        fast_info = ticker.fast_info
        price = fast_info.get('last_price')
        if price is None:
            info = ticker.info
            price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('previousClose', 'N/A')
        asset = {
            'symbol': symbol,
            'name': ticker.info.get('longName', symbol),
            'price': price if price is not None else 'N/A'
        }
    except Exception as e:
        logger.error(f"Error in share route for {symbol}: {e}")
        asset = {'symbol': symbol, 'name': symbol, 'price': 'N/A'}
    return render_template("share.html", asset=asset)

# -------------------------------
# Graph Route – generate and serve a PNG graph (last 1 month trend)
@app.route('/graph/<symbol>')
@login_required
def graph(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1mo")
        if hist.empty:
            logger.error(f"No historical data available for {symbol}")
            return "No historical data available for graph."
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(hist.index, hist['Close'], marker='o', linestyle='-')
        ax.set_title(f'{symbol} Price Trend (Last 1 Month)')
        ax.set_xlabel('Date')
        ax.set_ylabel('Price (Rs)')
        ax.grid(True)
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close(fig)
        return send_file(buf, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error generating graph for {symbol}: {e}")
        return "Error generating graph"

# -------------------------------
# Logout Route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out', 'success')
    return redirect(url_for('login'))

# -------------------------------
# Test Route – quick verification (no login required)
@app.route('/test/<symbol>')
def test(symbol):
    price = get_price(symbol)
    return render_template("test.html", symbol=symbol, price=price)

# -------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)