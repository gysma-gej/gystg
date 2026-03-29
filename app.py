from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import hashlib
import uuid
import json
import os
from datetime import datetime

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
        inventory TEXT DEFAULT '{"Чёрный": 1}',
        selected_color TEXT DEFAULT 'Чёрный',
        hide_user_tag INTEGER DEFAULT 0,
        hide_last_seen INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_online INTEGER DEFAULT 0,
        verified INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        from_user TEXT,
        to_user TEXT,
        text TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_gift INTEGER DEFAULT 0,
        media_url TEXT,
        is_read INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS favorites (
        user_id TEXT,
        favorite_user_id TEXT,
        PRIMARY KEY (user_id, favorite_user_id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS blocked (
        user_id TEXT,
        blocked_user_id TEXT,
        PRIMARY KEY (user_id, blocked_user_id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS market_listings (
        id TEXT PRIMARY KEY,
        seller_id TEXT,
        seller_name TEXT,
        item_name TEXT,
        price INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS privacy_settings (
        user_id TEXT PRIMARY KEY,
        show_email INTEGER DEFAULT 1,
        show_username INTEGER DEFAULT 1,
        show_avatar INTEGER DEFAULT 1,
        show_bio INTEGER DEFAULT 1,
        show_user_tag INTEGER DEFAULT 1
    )''')
    
    conn.commit()
    conn.close()

init_db()

# ============ АВТОРИЗАЦИЯ ============
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
    
    c.execute('''INSERT INTO users (id, email, password, username, user_tag, balance, inventory) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (user_id, email, password_hash, username, user_tag, 100, json.dumps({'Чёрный': 1})))
    
    c.execute('INSERT INTO privacy_settings (user_id) VALUES (?)', (user_id,))
    
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
            'selected_color': user['selected_color'],
            'inventory': json.loads(user['inventory']) if user['inventory'] else {'Чёрный': 1},
            'verified': user['verified']
        })
    else:
        return jsonify({'error': 'Неверный email или пароль'}), 401

# ============ ПОЛЬЗОВАТЕЛИ ============
@app.route('/api/users', methods=['GET'])
def get_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, username, user_tag, bio, avatar, balance, selected_color, is_online, last_seen, verified FROM users')
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(users)

@app.route('/api/users/<user_id>', methods=['GET', 'PUT'])
def user(user_id):
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'GET':
        c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = c.fetchone()
        conn.close()
        if user:
            return jsonify(dict(user))
        return jsonify({'error': 'Not found'}), 404
    
    elif request.method == 'PUT':
        data = request.json
        updates = []
        values = []
        
        for key in ['username', 'user_tag', 'bio', 'avatar', 'selected_color', 'hide_user_tag', 'hide_last_seen']:
            if key in data:
                updates.append(f'{key} = ?')
                values.append(data[key])
        
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

@app.route('/api/users/<user_id>/inventory', methods=['PUT'])
def update_inventory(user_id):
    data = request.json
    inventory = data.get('inventory')
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET inventory = ? WHERE id = ?', (json.dumps(inventory), user_id))
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

# ============ СООБЩЕНИЯ ============
@app.route('/api/messages', methods=['POST'])
def send_message():
    data = request.json
    msg_id = str(uuid.uuid4())
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO messages (id, from_user, to_user, text, is_gift, media_url) 
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (msg_id, data['from_user'], data['to_user'], data['text'], 
               data.get('is_gift', 0), data.get('media_url', '')))
    conn.commit()
    conn.close()
    return jsonify({'id': msg_id})

@app.route('/api/messages/<user_id>', methods=['GET'])
def get_messages(user_id):
    other_user = request.args.get('with')
    conn = get_db()
    c = conn.cursor()
    
    if other_user:
        c.execute('''SELECT * FROM messages 
                     WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
                     ORDER BY timestamp''', 
                  (user_id, other_user, other_user, user_id))
    else:
        c.execute('SELECT * FROM messages WHERE from_user = ? OR to_user = ? ORDER BY timestamp', 
                  (user_id, user_id))
    
    messages = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(messages)

@app.route('/api/messages/read', methods=['POST'])
def mark_read():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE messages SET is_read = 1 WHERE from_user = ? AND to_user = ?', 
              (data['from_user'], data['to_user']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ============ ИЗБРАННОЕ ============
@app.route('/api/favorites/<user_id>', methods=['GET', 'POST', 'DELETE'])
def favorites(user_id):
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'GET':
        c.execute('SELECT favorite_user_id FROM favorites WHERE user_id = ?', (user_id,))
        favs = [row[0] for row in c.fetchall()]
        conn.close()
        return jsonify(favs)
    
    elif request.method == 'POST':
        fav_id = request.json.get('favorite_user_id')
        c.execute('INSERT OR IGNORE INTO favorites (user_id, favorite_user_id) VALUES (?, ?)', 
                  (user_id, fav_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        fav_id = request.json.get('favorite_user_id')
        c.execute('DELETE FROM favorites WHERE user_id = ? AND favorite_user_id = ?', 
                  (user_id, fav_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

# ============ БЛОКИРОВКА ============
@app.route('/api/blocked/<user_id>', methods=['GET', 'POST', 'DELETE'])
def blocked(user_id):
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'GET':
        c.execute('SELECT blocked_user_id FROM blocked WHERE user_id = ?', (user_id,))
        blocked_list = [row[0] for row in c.fetchall()]
        conn.close()
        return jsonify(blocked_list)
    
    elif request.method == 'POST':
        blocked_id = request.json.get('blocked_user_id')
        c.execute('INSERT OR IGNORE INTO blocked (user_id, blocked_user_id) VALUES (?, ?)', 
                  (user_id, blocked_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        blocked_id = request.json.get('blocked_user_id')
        c.execute('DELETE FROM blocked WHERE user_id = ? AND blocked_user_id = ?', 
                  (user_id, blocked_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

# ============ РЫНОК ============
@app.route('/api/market', methods=['GET', 'POST', 'DELETE'])
def market():
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'GET':
        c.execute('SELECT * FROM market_listings ORDER BY created_at DESC')
        listings = [dict(row) for row in c.fetchall()]
        conn.close()
        return jsonify(listings)
    
    elif request.method == 'POST':
        data = request.json
        listing_id = str(uuid.uuid4())
        c.execute('''INSERT INTO market_listings (id, seller_id, seller_name, item_name, price) 
                     VALUES (?, ?, ?, ?, ?)''',
                  (listing_id, data['seller_id'], data['seller_name'], data['item_name'], data['price']))
        conn.commit()
        conn.close()
        return jsonify({'id': listing_id})
    
    elif request.method == 'DELETE':
        listing_id = request.json.get('id')
        c.execute('DELETE FROM market_listings WHERE id = ?', (listing_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

# ============ НАСТРОЙКИ ПРИВАТНОСТИ ============
@app.route('/api/privacy/<user_id>', methods=['GET', 'PUT'])
def privacy(user_id):
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'GET':
        c.execute('SELECT * FROM privacy_settings WHERE user_id = ?', (user_id,))
        settings = c.fetchone()
        conn.close()
        if settings:
            return jsonify(dict(settings))
        return jsonify({})
    
    elif request.method == 'PUT':
        data = request.json
        updates = []
        values = []
        
        for key in ['show_email', 'show_username', 'show_avatar', 'show_bio', 'show_user_tag']:
            if key in data:
                updates.append(f'{key} = ?')
                values.append(1 if data[key] else 0)
        
        if updates:
            values.append(user_id)
            c.execute(f'UPDATE privacy_settings SET {", ".join(updates)} WHERE user_id = ?', values)
            conn.commit()
        
        conn.close()
        return jsonify({'success': True})

# ============ ФРОНТЕНД ============
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
