from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from . import db, bcrypt
from .models import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        login_id = request.form.get('login_id')
        password = request.form.get('password')
        
        # Check by email or phone
        user = User.query.filter((User.email == login_id) | (User.phone == login_id)).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash('Login Unsuccessful. Please check your credentials.', 'danger')
            
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        # Simple validation
        if User.query.filter_by(email=email).first():
            flash('Email is already registered. Please login.', 'warning')
            return redirect(url_for('auth.login'))
            
        if phone and User.query.filter_by(phone=phone).first():
            flash('Phone number is already registered. Please login.', 'warning')
            return redirect(url_for('auth.login'))
            
        if User.query.filter_by(username=username).first():
            flash('Username is already taken.', 'warning')
            return redirect(url_for('auth.register'))
            
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, email=email, phone=phone, password_hash=hashed_password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html')

@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))
