# app.py
import os
import psycopg2
import secrets
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import pandas as pd

# .envファイルから環境変数を読み込む
load_dotenv()

# --- アプリの初期設定 ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# --- ログインマネージャーの設定 ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "このページにアクセスするにはログインが必要です。"

# --- データベース接続 ---
def get_db_connection():
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    return conn

# --- Userモデルの定義 (api_keyプロパティを追加) ---
class User(UserMixin):
    def __init__(self, id, username, password_hash, api_key):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.api_key = api_key

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password_hash, api_key FROM users WHERE id = %s", (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    if user_data:
        return User(id=user_data[0], username=user_data[1], password_hash=user_data[2], api_key=user_data[3])
    return None

# --- テーブル作成 (usersテーブルにapi_keyカラムを追加) ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            api_key TEXT UNIQUE NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            activity_date DATE NOT NULL,
            activity_type TEXT NOT NULL,
            duration REAL NOT NULL,
            device TEXT NOT NULL,
            co2_emissions REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

# (CO2算出ロジックは変更なし)
COEFFICIENTS = {'data_center_kwh_per_gb': 0.07, 'network_kwh_per_gb': 0.05, 'co2_g_per_kwh_jp': 430}
DEVICE_POWER_KW = {'smartphone': 0.003, 'laptop': 0.04, 'desktop': 0.15}
ACTIVITY_GB_PER_HOUR = {'video_streaming_hd': 2.5, 'video_conference': 0.8, 'cloud_gaming': 4.0, 'music_streaming': 0.1, 'web_browse': 0.2}
def calculate_co2(activity, duration_hours, device):
    data_gb = ACTIVITY_GB_PER_HOUR.get(activity, 0) * duration_hours
    e_dc = data_gb * COEFFICIENTS['data_center_kwh_per_gb']
    e_net = data_gb * COEFFICIENTS['network_kwh_per_gb']
    e_dev = duration_hours * DEVICE_POWER_KW.get(device, 0)
    total_kwh = e_dc + e_net + e_dev
    total_co2_g = total_kwh * COEFFICIENTS['co2_g_per_kwh_jp']
    return round(total_co2_g, 2)

# --- 認証ルート ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, api_key FROM users WHERE username = %s", (username,))
        user_data = cursor.fetchone()
        conn.close()
        if user_data and check_password_hash(user_data[2], password):
            user = User(id=user_data[0], username=user_data[1], password_hash=user_data[2], api_key=user_data[3])
            login_user(user)
            return redirect(url_for('index'))
        flash('ユーザー名またはパスワードが正しくありません。')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        api_key = secrets.token_hex(16) # ★APIキーを生成
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password_hash, api_key) VALUES (%s, %s, %s)", (username, hashed_password, api_key))
            conn.commit()
            conn.close()
            flash('登録が完了しました。ログインしてください。')
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            flash('そのユーザー名は既に使用されています。')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ★新規追加：プロフィールページ (APIキー表示) ---
@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

# --- メイン機能ルート ---
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/api/activities', methods=['GET', 'POST'])
@login_required
def handle_activities():
    conn = get_db_connection()
    user_id = current_user.id
    if request.method == 'POST':
        data = request.json
        co2 = calculate_co2(data['activity_type'], data['duration'], data['device'])
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO activities (user_id, activity_date, activity_type, duration, device, co2_emissions) VALUES (%s, CURRENT_DATE, %s, %s, %s, %s)',
            (user_id, data['activity_type'], data['duration'], data['device'], co2)
        )
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'co2': co2})
    else: # GET
        query = "SELECT * FROM activities WHERE user_id = %s"
        df = pd.read_sql_query(query, conn, params=(user_id,))
        conn.close()
        if df.empty: return jsonify({'monthly_summary': {}, 'activity_summary': {}})
        df['activity_date'] = pd.to_datetime(df['activity_date'])
        df['month'] = df['activity_date'].dt.to_period('M').astype(str)
        monthly_summary = df.groupby('month')['co2_emissions'].sum().to_dict()
        activity_summary = df.groupby('activity_type')['co2_emissions'].sum().to_dict()
        return jsonify({'monthly_summary': monthly_summary, 'activity_summary': activity_summary})

# --- ★新規追加：拡張機能からのデータ受け入れ口 ---
DOMAIN_TO_ACTIVITY = {
    'www.youtube.com': 'video_streaming_hd', 'www.netflix.com': 'video_streaming_hd',
    'zoom.us': 'video_conference', 'meet.google.com': 'video_conference',
    'music.youtube.com': 'music_streaming', 'open.spotify.com': 'music_streaming'
}

@app.route('/api/log_from_extension', methods=['POST'])
def log_from_extension():
    api_key = request.headers.get('X-API-KEY')
    if not api_key: return jsonify({'error': 'API key is missing'}), 401

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE api_key = %s", (api_key,))
    user_data = cursor.fetchone()
    if not user_data:
        conn.close()
        return jsonify({'error': 'Invalid API key'}), 403

    user_id = user_data[0]
    data = request.json
    domain = data.get('domain')
    duration_minutes = data.get('duration_minutes')
    activity_type = DOMAIN_TO_ACTIVITY.get(domain, 'web_browse')
    
    # 拡張機能からの記録はデバイスを'laptop'と仮定
    co2 = calculate_co2(activity_type, duration_minutes / 60.0, 'laptop')

    cursor.execute(
        'INSERT INTO activities (user_id, activity_date, activity_type, duration, device, co2_emissions) VALUES (%s, CURRENT_DATE, %s, %s, %s, %s)',
        (user_id, activity_type, duration_minutes / 60.0, 'laptop', co2)
    )
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'}), 201

@app.cli.command("init-db")
def init_db_command():
    """Creates the database tables."""
    init_db()
    print("Initialized the database.")

if __name__ == '__main__':
    app.run(debug=True)
