from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password = db.Column(db.String(150), nullable=False)
    favorites = db.relationship('Favorite', backref='owner', lazy=True)
    holdings = db.relationship('Holding', backref='owner', lazy=True)

    def _repr_(self):
        return f"<User {self.username}>"

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stock_symbol = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def _repr_(self):
        return f"<Favorite {self.stock_symbol} for user_id {self.user_id}>"

class Holding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_type = db.Column(db.String(50), nullable=False)  # share, commodity, or currency
    asset_symbol = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    purchase_price = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def _repr_(self):
        return (f"<Holding {self.asset_type}: {self.asset_symbol} x {self.quantity} "
                f"at Rs {self.purchase_price} for user_id {self.user_id}>")