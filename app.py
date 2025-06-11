from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from flask_socketio import SocketIO, send, emit
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SESSION_TYPE'] = "filesystem"

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

# ----------------- User Model -----------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# ----------------- Message Model -----------------
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    content = db.Column(db.String(500), nullable=False)

# ----------------- Login Manager -----------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_request
def create_tables():
    db.create_all()

# ----------------- Routes -----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if not User.query.filter_by(username=username).first():
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        flash('Username already exists!', 'error')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        flash('Invalid credentials!', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('username', None)
    flash('Logged out!', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    messages = Message.query.order_by(Message.id.desc()).limit(10).all()  # Fetch last 10 messages
    return render_template('index.html', messages=messages, username=current_user.username)

@socketio.on('send_message')
def handle_message(data):
    username = data.get('username')
    msg = data.get('message')

    if username and msg:
        new_msg = Message(username=username, content=msg)
        db.session.add(new_msg)
        db.session.commit()
        emit('new_message', {'username': username, 'message': msg}, broadcast=True)

@app.route('/delete_message/<int:message_id>', methods=['DELETE'])
@login_required
def delete_message(message_id):
    message = Message.query.get(message_id)
    
    if message:
        if message.username == current_user.username:
            db.session.delete(message)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Deleted for everyone'}), 200
        return jsonify({'error': 'You can only delete your own messages'}), 403
    return jsonify({'error': 'Message not found'}), 404

if __name__ == '__main__':
    socketio.run(app, debug=True)
