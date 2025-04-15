from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import yfinance as yf
from werkzeug.security import generate_password_hash, check_password_hash
import io
import matplotlib.pyplot as plt

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
# User loader for flask-login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------------------
# Context processor to inject contact info from a text file
@app.context_processor
def inject_contact():
    try:
        with open('contact.txt', 'r') as f:
            contact = f.read()
    except Exception:
        contact = "Contact us at support@example.com"
    return dict(contact_info=contact)

# -------------------------------
# Home: redirect to menu (if logged in) or to login page
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
# Main Menu Dashboard Route (after login/register)
@app.route('/menu')
@login_required
def menu():
    return render_template('menu.html')

# -------------------------------
# "My Favorite Shares" Route with optional search
@app.route('/favorites', methods=['GET'])
@login_required
def favorites():
    search = request.args.get('search')
    favs = Favorite.query.filter_by(user_id=current_user.id).all()
    favorites_data = []
    for fav in favs:
        if search and search.lower() not in fav.stock_symbol.lower():
            continue
        try:
            ticker = yf.Ticker(fav.stock_symbol)
            info = ticker.info
            current_price = info.get('regularMarketPrice') or info.get('currentPrice', 'N/A')
            name = info.get('longName', fav.stock_symbol)
        except Exception:
            current_price = 'N/A'
            name = fav.stock_symbol
        favorites_data.append({'stock_symbol': fav.stock_symbol, 'price': current_price, 'name': name})
    return render_template('favorites.html', favorites=favorites_data)

# Route to add a favorite via POST (from form submission)
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
# "All Shares" Route
# Pre-defined list of top Indian shares.
indian_shares = [
    {'symbol': 'RELIANCE.NS', 'name': 'Reliance Industries'},
    {'symbol': 'TCS.NS', 'name': 'Tata Consultancy Services'},
    {'symbol': 'INFY.NS', 'name': 'Infosys'},
    {'symbol': 'HDFCBANK.NS', 'name': 'HDFC Bank'},
    {'symbol': 'ICICIBANK.NS', 'name': 'ICICI Bank'}
]

@app.route('/shares')
@login_required
def shares():
    search = request.args.get('search')
    shares_list = []
    for share in indian_shares:
        if search and search.lower() not in share['name'].lower() and search.lower() not in share['symbol'].lower():
            continue
        try:
            ticker = yf.Ticker(share['symbol'])
            info = ticker.info
            price = info.get('regularMarketPrice') or info.get('currentPrice', 'N/A')
        except Exception:
            price = 'N/A'
        shares_list.append({'symbol': share['symbol'], 'name': share['name'], 'price': price})
    return render_template('shares.html', shares=shares_list)

# -------------------------------
# "All Commodities" Route – show Gold and Silver ETFs
commodities_list = [
    {'symbol': 'GOLDBEES.NS', 'name': 'Gold ETF'},
    {'symbol': 'SILVERBEE.NS', 'name': 'Silver ETF'}
]

@app.route('/commodities')
@login_required
def commodities():
    commodity_data = []
    for com in commodities_list:
        try:
            ticker = yf.Ticker(com['symbol'])
            info = ticker.info
            price = info.get('regularMarketPrice') or info.get('currentPrice', 'N/A')
        except Exception:
            price = 'N/A'
        commodity_data.append({'symbol': com['symbol'], 'name': com['name'], 'price': price})
    return render_template('commodities.html', commodities=commodity_data)

# -------------------------------
# "All Currencies" Route – show Dollar and top currencies
currencies_list = [
    {'symbol': 'USDINR=X', 'name': 'US Dollar'},
    {'symbol': 'EURINR=X', 'name': 'Euro'},
    {'symbol': 'GBPINR=X', 'name': 'British Pound'},
    {'symbol': 'JPYINR=X', 'name': 'Japanese Yen'},
    {'symbol': 'AUDINR=X', 'name': 'Australian Dollar'},
    {'symbol': 'CADINR=X', 'name': 'Canadian Dollar'}
]

@app.route('/currencies')
@login_required
def currencies():
    currency_data = []
    for curr in currencies_list:
        try:
            ticker = yf.Ticker(curr['symbol'])
            info = ticker.info
            price = info.get('regularMarketPrice') or info.get('currentPrice', 'N/A')
        except Exception:
            price = 'N/A'
        currency_data.append({'symbol': curr['symbol'], 'name': curr['name'], 'price': price})
    return render_template('currencies.html', currencies=currency_data)

# -------------------------------
# "My Holdings" Route – display holdings and add new holding
@app.route('/holdings', methods=['GET'])
@login_required
def holdings():
    user_holdings = Holding.query.filter_by(user_id=current_user.id).all()
    holdings_data = []
    for h in user_holdings:
        try:
            ticker = yf.Ticker(h.asset_symbol)
            info = ticker.info
            current_price = info.get('regularMarketPrice') or info.get('currentPrice', None)
        except Exception:
            current_price = 0
        if current_price is None:
            current_price = 0
        profit_loss = (current_price - h.purchase_price) * h.quantity
        profit_loss_pct = ((current_price - h.purchase_price) / h.purchase_price * 100) if h.purchase_price != 0 else 0
        holdings_data.append({
            'asset_symbol': h.asset_symbol,
            'asset_type': h.asset_type,
            'quantity': h.quantity,
            'purchase_price': h.purchase_price,
            'current_price': current_price,
            'profit_loss': round(profit_loss, 2),
            'profit_loss_pct': round(profit_loss_pct, 2)
        })
    return render_template('holdings.html', holdings=holdings_data)

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
# "Share Page" Route – display detailed info and graph for an asset
@app.route('/share/<symbol>')
@login_required
def share(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        asset = {
            'symbol': symbol,
            'name': info.get('longName', symbol),
            'price': info.get('regularMarketPrice') or info.get('currentPrice', 'N/A')
        }
    except Exception:
        asset = {'symbol': symbol, 'name': symbol, 'price': 'N/A'}
    return render_template('share.html', asset=asset)

# -------------------------------
# Graph Route – generate and serve a PNG graph (last 1 month trend)
@app.route('/graph/<symbol>')
@login_required
def graph(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1mo")
        fig, ax = plt.subplots()
        ax.plot(hist.index, hist['Close'])
        ax.set_title('Price Trend (Last 1 Month)')
        ax.set_xlabel('Date')
        ax.set_ylabel('Price (Rs)')
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close(fig)
        return send_file(buf, mimetype='image/png')
    except Exception as e:
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
if _name_ == '_main_':
    app.run(host='0.0.0.0', port=5000)
