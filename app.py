from flask import Flask, request, render_template_string, redirect, url_for
import uuid
import sqlite3
import os

app = Flask(__name__)
DB_NAME = 'storage.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_app():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS secrets 
                 (id TEXT PRIMARY KEY, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_app()

PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Secure Note</title>
    <style>
        :root { --bg: #121212; --card: #1e1e1e; --text: #e0e0e0; --accent: #3b82f6; --danger: #ef4444; }
        body { background-color: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .wrapper { background: var(--card); padding: 2rem; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.2); width: 100%; max-width: 480px; box-sizing: border-box; }
        h2 { margin-top: 0; font-weight: 500; text-align: center; color: #fff; }
        textarea { width: 100%; height: 160px; background: #2d2d2d; color: #fff; border: 1px solid #404040; border-radius: 8px; padding: 12px; font-size: 16px; resize: none; outline: none; box-sizing: border-box; margin: 15px 0; }
        textarea:focus { border-color: var(--accent); }
        .btn { display: block; width: 100%; padding: 12px; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; transition: opacity 0.2s; text-decoration: none; text-align: center; box-sizing: border-box; }
        .btn-primary { background: var(--accent); color: white; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-secondary { background: #404040; color: #ccc; margin-top: 10px; }
        .btn:hover { opacity: 0.9; }
        .result-box { background: #2d2d2d; padding: 15px; border-radius: 8px; border: 1px dashed #555; word-break: break-all; font-family: monospace; color: var(--accent); margin-bottom: 20px; }
        .note { color: #888; font-size: 13px; text-align: center; margin-top: 15px; }
        footer { margin-top: 30px; text-align: center; font-size: 12px; color: #555; }
    </style>
</head>
<body>
    <div class="wrapper">
        {% if step == 'create' %}
            <h2>Create New Note</h2>
            <form method="POST">
                <textarea name="text" placeholder="Enter your private content here..." required></textarea>
                <button type="submit" class="btn btn-primary">Generate Link</button>
            </form>
            <div class="note">Content will be permanently deleted after reading.</div>
        
        {% elif step == 'link' %}
            <h2>Link Ready</h2>
            <div class="note">Share this link securely:</div>
            <div class="result-box">{{ url }}</div>
            <a href="/" class="btn btn-secondary">Create Another</a>

        {% elif step == 'confirm' %}
            <h2 style="color: var(--danger)">Warning</h2>
            <p style="text-align: center; line-height: 1.6;">You are about to view a secure note.<br>It will be <strong>permanently destroyed</strong> immediately after viewing.</p>
            <form method="POST" action="/read/{{ id }}">
                <button type="submit" class="btn btn-danger">Yes, Show Me</button>
            </form>

        {% elif step == 'view' %}
            <h2>Private Content</h2>
            <textarea readonly>{{ content }}</textarea>
            <div class="note">This note has been destroyed.</div>
            <a href="/" class="btn btn-secondary">Home</a>

        {% elif step == 'error' %}
            <h2>Not Found</h2>
            <p style="text-align: center; color: #888;">This note does not exist or has already been read.</p>
            <a href="/" class="btn btn-secondary">Home</a>
        {% endif %}

        <footer>
            &copy; 2025 kin. All rights reserved.
        </footer>
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        content = request.form.get('text')
        if not content:
            return redirect(url_for('index'))
        
        note_id = str(uuid.uuid4()).replace('-', '')
        conn = get_db()
        conn.execute('INSERT INTO secrets (id, content) VALUES (?, ?)', (note_id, content))
        conn.commit()
        conn.close()
        
        link = url_for('confirm_view', uid=note_id, _external=True)
        return render_template_string(PAGE_TEMPLATE, step='link', url=link)
    
    return render_template_string(PAGE_TEMPLATE, step='create')

@app.route('/note/<uid>', methods=['GET'])
def confirm_view(uid):
    conn = get_db()
    res = conn.execute('SELECT 1 FROM secrets WHERE id = ?', (uid,)).fetchone()
    conn.close()
    
    if not res:
        return render_template_string(PAGE_TEMPLATE, step='error')
    
    return render_template_string(PAGE_TEMPLATE, step='confirm', id=uid)

@app.route('/read/<uid>', methods=['POST'])
def read_note(uid):
    conn = get_db()
    res = conn.execute('SELECT content FROM secrets WHERE id = ?', (uid,)).fetchone()
    
    if res:
        conn.execute('DELETE FROM secrets WHERE id = ?', (uid,))
        conn.commit()
        conn.close()
        return render_template_string(PAGE_TEMPLATE, step='view', content=res['content'])
    
    conn.close()
    return render_template_string(PAGE_TEMPLATE, step='error')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8787)
