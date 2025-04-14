from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import yfinance as yf
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
import pandas as pd
import plotly
import plotly.graph_objs as go
import json

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database/app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    favorites = db.relationship('Favorite', backref='owner', lazy=True)
    holdings = db.relationship('Holding', backref='owner', lazy=True)

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    asset_type = db.Column(db.String(20), nullable=False)  # 'stock', 'commodity', 'currency'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Holding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    asset_type = db.Column(db.String(20), nullable=False)  # 'stock', 'commodity', 'currency'
    quantity = db.Column(db.Float, nullable=False)
    buy_price = db.Column(db.Float, nullable=False)
    buy_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Indian market constants
INDIAN_STOCKS = {
    'RELIANCE.NS': 'Reliance Industries',
    'TCS.NS': 'Tata Consultancy Services',
    'HDFCBANK.NS': 'HDFC Bank',
    'INFY.NS': 'Infosys',
    'HINDUNILVR.NS': 'Hindustan Unilever',
    'ICICIBANK.NS': 'ICICI Bank',
    'BHARTIARTL.NS': 'Bharti Airtel',
    'SBIN.NS': 'State Bank of India',
    'ASIANPAINT.NS': 'Asian Paints',
    'ADANIENT.NS': 'Adani Enterprises'
}

COMMODITIES = {
    'GC=F': 'Gold',
    'SI=F': 'Silver'
}

CURRENCIES = {
    'INR=X': 'USD/INR',
    'EURINR=X': 'EUR/INR',
    'GBPINR=X': 'GBP/INR',
    'JPYINR=X': 'JPY/INR',
    'CADINR=X': 'CAD/INR'
}

# Load user function for login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Home route (redirect to login)
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('menu'))
    return redirect(url_for('login'))

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('menu'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('menu'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    
    return render_template('login.html')

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('menu'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password, method='sha256')
        new_user = User(username=username, password=hashed_password)
        
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        flash('Registration successful!', 'success')
        return redirect(url_for('menu'))
    
    return render_template('register.html')

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Menu route
@app.route('/menu')
@login_required
def menu():
    return render_template('menu.html')

# Contact Us route
@app.route('/contact')
@login_required
def contact():
    contact_info = ""
    try:
        with open('contact.txt', 'r') as file:
            contact_info = file.read()
    except FileNotFoundError:
        contact_info = "Contact information not available at the moment."
    
    return render_template('contact.html', contact_info=contact_info)

# My Favorites route
@app.route('/favorites')
@login_required
def favorites():
    user = current_user
    favorites = Favorite.query.filter_by(user_id=user.id).all()
    
    stocks_data = []
    for fav in favorites:
        try:
            ticker = yf.Ticker(fav.symbol)
            info = ticker.info
            
            # Get current price
            current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            
            # Convert to INR if it's not an Indian stock
            if not fav.symbol.endswith('.NS') and fav.asset_type == 'stock':
                current_price = current_price * get_usd_to_inr_rate()
            
            stocks_data.append({
                'symbol': fav.symbol,
                'name': info.get('longName', fav.symbol),
                'price': current_price,
                'asset_type': fav.asset_type
            })
        except Exception as e:
            print(f"Error fetching data for {fav.symbol}: {e}")
            stocks_data.append({
                'symbol': fav.symbol,
                'name': 'Data unavailable',
                'price': 0,
                'asset_type': fav.asset_type
            })
    
    return render_template('favorites.html', stocks=stocks_data)

# All Stocks route
@app.route('/stocks')
@login_required
def stocks():
    top_stocks = {}
    
    for symbol, name in INDIAN_STOCKS.items():
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            
            top_stocks[symbol] = {
                'name': name,
                'price': current_price
            }
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
    
    return render_template('stocks.html', stocks=top_stocks)

# All Commodities route
@app.route('/commodities')
@login_required
def commodities():
    commodities_data = {}
    
    for symbol, name in COMMODITIES.items():
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Get price in USD
            price_usd = info.get('regularMarketPrice', 0)
            
            # Convert to INR
            price_inr = price_usd * get_usd_to_inr_rate()
            
            commodities_data[symbol] = {
                'name': name,
                'price': price_inr
            }
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
    
    return render_template('commodities.html', commodities=commodities_data)

# All Currencies route
@app.route('/currencies')
@login_required
def currencies():
    currencies_data = {}
    
    for symbol, name in CURRENCIES.items():
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            current_price = info.get('regularMarketPrice', 0)
            
            currencies_data[symbol] = {
                'name': name,
                'price': current_price
            }
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
    
    return render_template('currencies.html', currencies=currencies_data)

# My Holdings route
@app.route('/holdings')
@login_required
def holdings():
    user = current_user
    holdings = Holding.query.filter_by(user_id=user.id).all()
    
    holdings_data = []
    total_investment = 0
    total_current_value = 0
    
    for holding in holdings:
        try:
            ticker = yf.Ticker(holding.symbol)
            info = ticker.info
            
            # Get current price
            current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            
            # Convert to INR if it's not an Indian stock/commodity/currency
            if not holding.symbol.endswith('.NS') and holding.asset_type == 'stock':
                current_price = current_price * get_usd_to_inr_rate()
            
            # Calculate profit/loss
            investment = holding.quantity * holding.buy_price
            current_value = holding.quantity * current_price
            profit_loss = current_value - investment
            profit_loss_percent = (profit_loss / investment) * 100 if investment > 0 else 0
            
            total_investment += investment
            total_current_value += current_value
            
            holdings_data.append({
                'id': holding.id,
                'symbol': holding.symbol,
                'name': info.get('longName', holding.symbol),
                'asset_type': holding.asset_type,
                'quantity': holding.quantity,
                'buy_price': holding.buy_price,
                'current_price': current_price,
                'profit_loss': profit_loss,
                'profit_loss_percent': profit_loss_percent
            })
        except Exception as e:
            print(f"Error fetching data for {holding.symbol}: {e}")
    
    total_profit_loss = total_current_value - total_investment
    total_profit_loss_percent = (total_profit_loss / total_investment) * 100 if total_investment > 0 else 0
    
    return render_template(
        'holdings.html', 
        holdings=holdings_data, 
        total_investment=total_investment,
        total_current_value=total_current_value,
        total_profit_loss=total_profit_loss,
        total_profit_loss_percent=total_profit_loss_percent
    )

# Add Holding route
@app.route('/add_holding', methods=['GET', 'POST'])
@login_required
def add_holding():
    if request.method == 'POST':
        symbol = request.form['symbol']
        asset_type = request.form['asset_type']
        quantity = float(request.form['quantity'])
        buy_price = float(request.form['buy_price'])
        
        new_holding = Holding(
            symbol=symbol,
            asset_type=asset_type,
            quantity=quantity,
            buy_price=buy_price,
            user_id=current_user.id
        )
        
        db.session.add(new_holding)
        db.session.commit()
        
        flash(f'Added {symbol} to your holdings!', 'success')
        return redirect(url_for('holdings'))
    
    symbol = request.args.get('symbol', '')
    asset_type = request.args.get('asset_type', 'stock')
    
    return render_template('add_holding.html', symbol=symbol, asset_type=asset_type)

# Remove Holding route
@app.route('/remove_holding/<int:holding_id>')
@login_required
def remove_holding(holding_id):
    holding = Holding.query.filter_by(id=holding_id, user_id=current_user.id).first()
    
    if holding:
        db.session.delete(holding)
        db.session.commit()
        flash('Holding removed successfully!', 'success')
    else:
        flash('Holding not found.', 'danger')
    
    return redirect(url_for('holdings'))

# Add to favorites
@app.route('/add_favorite')
@login_required
def add_favorite():
    symbol = request.args.get('symbol', '')
    asset_type = request.args.get('asset_type', 'stock')
    
    # Check if already in favorites
    existing_favorite = Favorite.query.filter_by(
        symbol=symbol, 
        asset_type=asset_type,
        user_id=current_user.id
    ).first()
    
    if existing_favorite:
        flash('Already in favorites!', 'info')
    else:
        new_favorite = Favorite(
            symbol=symbol, 
            asset_type=asset_type,
            user_id=current_user.id
        )
        db.session.add(new_favorite)
        db.session.commit()
        flash('Added to favorites!', 'success')
    
    # Determine which page to return to
    if asset_type == 'stock':
        return redirect(url_for('stocks'))
    elif asset_type == 'commodity':
        return redirect(url_for('commodities'))
    elif asset_type == 'currency':
        return redirect(url_for('currencies'))
    else:
        return redirect(url_for('favorites'))

# Remove from favorites
@app.route('/remove_favorite')
@login_required
def remove_favorite():
    symbol = request.args.get('symbol', '')
    
    favorite = Favorite.query.filter_by(symbol=symbol, user_id=current_user.id).first()
    
    if favorite:
        db.session.delete(favorite)
        db.session.commit()
        flash('Removed from favorites!', 'success')
    else:
        flash('Not in favorites!', 'danger')
    
    return redirect(url_for('favorites'))

# Asset detail page (stock, commodity, currency)
@app.route('/asset/<symbol>')
@login_required
def asset_detail(symbol):
    try:
        # Determine asset type
        asset_type = 'stock'
        if symbol in COMMODITIES or symbol in COMMODITIES.values():
            asset_type = 'commodity'
        elif symbol in CURRENCIES or symbol in CURRENCIES.values():
            asset_type = 'currency'
        
        # Get ticker data
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Get price data for the past month
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        hist_data = ticker.history(start=start_date, end=end_date)
        
        # Create the price chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist_data.index, 
            y=hist_data['Close'],
            mode='lines',
            name='Price'
        ))
        
        # Customize chart layout
        fig.update_layout(
            title=f"{info.get('longName', symbol)} - Last 30 Days",
            xaxis_title="Date",
            yaxis_title="Price (₹)" if symbol.endswith('.NS') else "Price (converted to ₹)",
            template="plotly_white",
            height=500
        )
        
        # Convert to JSON for embedding in HTML
        graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Get current price
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
        
        # Convert to INR if needed
        if not symbol.endswith('.NS') and asset_type == 'stock':
            current_price = current_price * get_usd_to_inr_rate()
        
        # Check if in favorites
        is_favorite = Favorite.query.filter_by(
            symbol=symbol, 
            user_id=current_user.id
        ).first() is not None
        
        return render_template(
            'asset_detail.html',
            symbol=symbol,
            name=info.get('longName', symbol),
            price=current_price,
            asset_type=asset_type,
            graph_json=graph_json,
            info=info,
            is_favorite=is_favorite
        )
    
    except Exception as e:
        flash(f'Error fetching data: {e}', 'danger')
        return redirect(url_for('menu'))

# Search functionality
@app.route('/search')
@login_required
def search():
    query = request.args.get('query', '').strip().lower()
    asset_type = request.args.get('asset_type', 'all')
    
    results = []
    
    if not query:
        return jsonify(results)
    
    # Search in stocks
    if asset_type in ['all', 'stock']:
        for symbol, name in INDIAN_STOCKS.items():
            if query in symbol.lower() or query in name.lower():
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'asset_type': 'stock'
                })
    
    # Search in commodities
    if asset_type in ['all', 'commodity']:
        for symbol, name in COMMODITIES.items():
            if query in symbol.lower() or query in name.lower():
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'asset_type': 'commodity'
                })
    
    # Search in currencies
    if asset_type in ['all', 'currency']:
        for symbol, name in CURRENCIES.items():
            if query in symbol.lower() or query in name.lower():
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'asset_type': 'currency'
                })
    
    return jsonify(results)

# Helper function to get USD to INR conversion rate
def get_usd_to_inr_rate():
    try:
        usd_inr = yf.Ticker("INR=X")
        return usd_inr.info.get('regularMarketPrice', 75.0)  # Default to 75 if unable to fetch
    except:
        return 75.0  # Default fallback rate

# Initialize the database
@app.before_first_request
def create_tables():
    db.create_all()

if __name__ == '__main__':
    # Ensure database directory exists
    os.makedirs('database', exist_ok=True)
    
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
