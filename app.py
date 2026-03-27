from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import hashlib
import uuid
import os

app = Flask(__name__, static_folder='.')
CORS(app)

DB_PATH = '/opt/render/project/src/gystg.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE,
        password TEXT,
        username TEXT UNIQUE,
        user_tag TEXT UNIQUE,
        bio TEXT,
        avatar TEXT,
        balance INTEGER DEFAULT 100,
        selected_color TEXT DEFAULT 'Чёрный',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_online INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

init_db()

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    username = data.get('username')
    user_tag = data.get('user_tag')
    
    if not email or not password or not username or not user_tag:
        return jsonify({'error': 'Все поля обязательны'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM users WHERE email = ? OR username = ? OR user_tag = ?', 
              (email, username, user_tag))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Email, имя или @юзернейм уже заняты'}), 400
    
    user_id = str(uuid.uuid4())
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    c.execute('''INSERT INTO users (id, email, password, username, user_tag, balance) 
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user_id, email, password_hash, username, user_tag, 100))
    conn.commit()
    conn.close()
    
    return jsonify({'id': user_id, 'username': username, 'user_tag': user_tag, 'balance': 100})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    conn = get_db()
    c = conn.cursor()
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    c.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password_hash))
    user = c.fetchone()
    conn.close()
    
    if user:
        return jsonify({
            'id': user['id'],
            'email': user['email'],
            'username': user['username'],
            'user_tag': user['user_tag'],
            'bio': user['bio'] or '',
            'avatar': user['avatar'] or '',
            'balance': user['balance'],
            'selected_color': user['selected_color']
        })
    else:
        return jsonify({'error': 'Неверный email или пароль'}), 401

@app.route('/api/users', methods=['GET'])
def get_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, username, user_tag, bio, avatar, balance, selected_color, is_online FROM users')
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(users)

@app.route('/api/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.json
    conn = get_db()
    c = conn.cursor()
    
    updates = []
    values = []
    
    if 'username' in data:
        updates.append('username = ?')
        values.append(data['username'])
    if 'user_tag' in data:
        updates.append('user_tag = ?')
        values.append(data['user_tag'])
    if 'bio' in data:
        updates.append('bio = ?')
        values.append(data['bio'])
    if 'avatar' in data:
        updates.append('avatar = ?')
        values.append(data['avatar'])
    
    if updates:
        values.append(user_id)
        c.execute(f'UPDATE users SET {", ".join(updates)} WHERE id = ?', values)
        conn.commit()
    
    conn.close()
    return jsonify({'success': True})

@app.route('/api/users/<user_id>/balance', methods=['POST'])
def update_balance(user_id):
    data = request.json
    amount = data.get('amount')
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET balance = balance + ? WHERE id = ?', (amount, user_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/users/<user_id>/online', methods=['POST'])
def set_online(user_id):
    data = request.json
    is_online = 1 if data.get('is_online') else 0
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET is_online = ?, last_seen = CURRENT_TIMESTAMP WHERE id = ?', (is_online, user_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
