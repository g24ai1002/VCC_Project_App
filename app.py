from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import yfinance as yf
from werkzeug.security import generate_password_hash, check_password_hash

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

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    favorites = db.relationship('Favorite', backref='owner', lazy=True)

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stock_symbol = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Load user function for login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Home route (show stock list)
@app.route('/')
def index():
    return render_template('index.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html')

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('dashboard'))
    return render_template('register.html')

# Dashboard route (favorites, stock data)
@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user
    favorites = Favorite.query.filter_by(user_id=user.id).all()
    stocks = []
    for fav in favorites:
        stock = yf.Ticker(fav.stock_symbol).info
        stocks.append({
            'symbol': fav.stock_symbol,
            'price': stock.get('currentPrice'),
            'name': stock.get('longName')
        })
    return render_template('dashboard.html', stocks=stocks)

# Add to favorites
@app.route('/add_favorite/<symbol>')
@login_required
def add_favorite(symbol):
    new_favorite = Favorite(stock_symbol=symbol, user_id=current_user.id)
    db.session.add(new_favorite)
    db.session.commit()
    return redirect(url_for('dashboard'))

# Remove from favorites
@app.route('/remove_favorite/<symbol>')
@login_required
def remove_favorite(symbol):
    favorite = Favorite.query.filter_by(stock_symbol=symbol, user_id=current_user.id).first()
    db.session.delete(favorite)
    db.session.commit()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(host='104.198.24.232', port=5000)
