from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import subprocess
import psutil
import json
import os
import shutil
import threading
import time
from datetime import datetime
import sys

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "JAGWAR_HOSTING_SECRET_KEY_2024")

# ==================== إعدادات التخزين لـ Hugging Face ====================
# استخدام مجلد البيانات الدائم في Hugging Face
DATA_DIR = os.environ.get("DATA_DIR", "/data")
if not os.path.exists(DATA_DIR):
    # إذا لم يكن /data متاحاً (في Hugging Face المجاني)، استخدم مجلد محلي
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

USERS_FILE = os.path.join(DATA_DIR, "users.json")
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
LOGS_DIR = os.path.join(DATA_DIR, "logs")

# إنشاء المجلدات
for dir_path in [DATA_DIR, PROJECTS_DIR, LOGS_DIR]:
    os.makedirs(dir_path, exist_ok=True)
    print(f"✅ مجلد جاهز: {dir_path}")

# ==================== إدارة المستخدمين ====================
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    default_users = {
        "RAGNAR": {
            "password": "RAGNAR-HOST",
            "role": "admin",
            "created_at": str(datetime.now())
        }
    }
    save_users(default_users)
    return default_users

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

def add_user(username, password, role="user"):
    users = load_users()
    if username not in users:
        users[username] = {
            "password": password,
            "role": role,
            "created_at": str(datetime.now())
        }
        save_users(users)
        os.makedirs(os.path.join(PROJECTS_DIR, username), exist_ok=True)
        return True
    return False

def delete_user(username):
    users = load_users()
    if username in users and username != "RAGNAR":
        del users[username]
        save_users(users)
        shutil.rmtree(os.path.join(PROJECTS_DIR, username), ignore_errors=True)
        return True
    return False

# ==================== إدارة المشاريع ====================
def get_user_projects(username):
    user_dir = os.path.join(PROJECTS_DIR, username)
    if os.path.exists(user_dir):
        return [d for d in os.listdir(user_dir) if os.path.isdir(os.path.join(user_dir, d))]
    return []

def create_project(username, project_name):
    project_path = os.path.join(PROJECTS_DIR, username, project_name)
    os.makedirs(project_path, exist_ok=True)
    return project_path

def delete_project(username, project_name):
    project_path = os.path.join(PROJECTS_DIR, username, project_name)
    if os.path.exists(project_path):
        shutil.rmtree(project_path)
        return True
    return False

# ==================== تشغيل المشاريع ====================
running_processes = {}

def run_project(username, project_name, main_file, req_file):
    project_path = os.path.join(PROJECTS_DIR, username, project_name)
    process_id = f"{username}_{project_name}"
    
    try:
        if req_file and req_file != "":
            req_path = os.path.join(project_path, req_file)
            if os.path.exists(req_path):
                result = subprocess.run(
                    f"{sys.executable} -m pip install -r {req_path}",
                    shell=True,
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                print(f"PIP install: {result.stdout}")
        
        if main_file and main_file != "":
            main_path = os.path.join(project_path, main_file)
            if os.path.exists(main_path):
                log_file = os.path.join(LOGS_DIR, f"{process_id}.log")
                with open(log_file, 'w') as f:
                    process = subprocess.Popen(
                        f"{sys.executable} {main_file}",
                        shell=True,
                        cwd=project_path,
                        stdout=f,
                        stderr=subprocess.STDOUT,
                        text=True
                    )
                running_processes[process_id] = {
                    "process": process,
                    "log_file": log_file,
                    "start_time": str(datetime.now())
                }
                return True
    except Exception as e:
        print(f"Error: {e}")
    return False

def stop_project(username, project_name):
    process_id = f"{username}_{project_name}"
    if process_id in running_processes:
        try:
            running_processes[process_id]["process"].terminate()
            time.sleep(1)
            if running_processes[process_id]["process"].poll() is None:
                running_processes[process_id]["process"].kill()
        except:
            pass
        del running_processes[process_id]
        return True
    return False

def get_logs(username, project_name):
    process_id = f"{username}_{project_name}"
    log_file = os.path.join(LOGS_DIR, f"{process_id}.log")
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            return f.read()
    return ""

# ==================== إحصائيات النظام ====================
def get_system_stats():
    try:
        ram = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.5)
        return {
            "ram_used": round(ram.used / (1024**3), 1),
            "ram_total": round(ram.total / (1024**3), 1),
            "ram_percent": ram.percent,
            "cpu_percent": cpu_percent
        }
    except:
        return {
            "ram_used": 0,
            "ram_total": 4,
            "ram_percent": 0,
            "cpu_percent": 0
        }

# ==================== Routes ====================

@app.route('/')
def root():
    if 'username' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_panel'))
        return redirect(url_for('index'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_users()
        
        if username in users and users[username]['password'] == password:
            session['username'] = username
            session['role'] = users[username]['role']
            if users[username]['role'] == 'admin':
                return redirect(url_for('admin_panel'))
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="اسم المستخدم أو كلمة السر غير صحيحة")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/index')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    if session.get('role') == 'admin':
        return redirect(url_for('admin_panel'))
    
    projects = get_user_projects(session['username'])
    stats = get_system_stats()
    return render_template('index.html', 
                         username=session['username'], 
                         projects=projects,
                         stats=stats)

@app.route('/admin_panel')
def admin_panel():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    users = load_users()
    stats = get_system_stats()
    all_projects = {}
    for user in users:
        all_projects[user] = get_user_projects(user)
    
    return render_template('admin_panel.html', 
                         users=users,
                         stats=stats,
                         projects=all_projects,
                         running_processes=running_processes)

@app.route('/add_user', methods=['POST'])
def add_user_route():
    if 'username' not in session or session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')
    
    if add_user(username, password, role):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "User exists"})

@app.route('/delete_user', methods=['POST'])
def delete_user_route():
    if 'username' not in session or session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    username = data.get('username')
    if delete_user(username):
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/create_project', methods=['POST'])
def create_project_route():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    project_name = data.get('project_name')
    create_project(session['username'], project_name)
    return jsonify({"success": True})

@app.route('/delete_project', methods=['POST'])
def delete_project_route():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    project_name = data.get('project_name')
    delete_project(session['username'], project_name)
    return jsonify({"success": True})

@app.route('/get_files')
def get_files():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    project_name = request.args.get('project')
    project_path = os.path.join(PROJECTS_DIR, session['username'], project_name)
    
    files = []
    if os.path.exists(project_path):
        files = os.listdir(project_path)
    return jsonify({"files": files})

@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    project_name = request.form.get('project')
    file = request.files.get('file')
    
    if file and project_name:
        project_path = os.path.join(PROJECTS_DIR, session['username'], project_name)
        file.save(os.path.join(project_path, file.filename))
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/create_file', methods=['POST'])
def create_file():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    project_name = data.get('project')
    filename = data.get('filename')
    content = data.get('content', '')
    
    project_path = os.path.join(PROJECTS_DIR, session['username'], project_name)
    file_path = os.path.join(project_path, filename)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return jsonify({"success": True})

@app.route('/delete_file', methods=['POST'])
def delete_file():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    project_name = data.get('project')
    filename = data.get('filename')
    
    project_path = os.path.join(PROJECTS_DIR, session['username'], project_name)
    file_path = os.path.join(project_path, filename)
    
    if os.path.exists(file_path):
        os.remove(file_path)
    
    return jsonify({"success": True})

@app.route('/run_project', methods=['POST'])
def run_project_route():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    project_name = data.get('project')
    main_file = data.get('main_file')
    req_file = data.get('req_file')
    
    success = run_project(session['username'], project_name, main_file, req_file)
    return jsonify({"success": success})

@app.route('/stop_project', methods=['POST'])
def stop_project_route():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    project_name = data.get('project')
    
    success = stop_project(session['username'], project_name)
    return jsonify({"success": success})

@app.route('/get_logs')
def get_logs_route():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    project_name = request.args.get('project')
    logs = get_logs(session['username'], project_name)
    return jsonify({"logs": logs})

@app.route('/get_stats')
def get_stats_route():
    stats = get_system_stats()
    return jsonify(stats)

# ==================== تشغيل التطبيق ====================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7860))
    print("\n" + "="*50)
    print("🐺 JAGWAR HOSTING - تم التشغيل بنجاح!")
    print("="*50)
    print(f"📍 المنفذ: {port}")
    print(f"🔑 بيانات الدخول: RAGNAR / RAGNAR-HOST")
    print(f"💾 مجلد البيانات: {DATA_DIR}")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)
