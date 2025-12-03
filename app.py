from flask import Flask, request, render_template_string, jsonify
import sqlite3
import uuid
import datetime
import os

app = Flask(__name__)
DB_NAME = 'storage.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS secrets (
            id TEXT PRIMARY KEY, 
            ciphertext TEXT, 
            iv TEXT, 
            salt TEXT, 
            expire_at DATETIME
        )
    ''')
    conn.commit()
    conn.close()

init_db()

HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>端到端加密笔记</title>
    <style>
        :root { --bg: #0f172a; --panel: #1e293b; --text: #e2e8f0; --primary: #3b82f6; --danger: #ef4444; }
        body { background: var(--bg); color: var(--text); font-family: sans-serif; display: flex; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
        .container { background: var(--panel); padding: 2rem; border-radius: 16px; width: 100%; max-width: 500px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); height: fit-content; align-self: center; }
        h2 { margin-top: 0; text-align: center; color: #fff; font-weight: 600; }
        textarea, input, select { width: 100%; background: #334155; border: 1px solid #475569; color: white; padding: 12px; border-radius: 8px; margin: 10px 0; box-sizing: border-box; font-size: 16px; outline: none; }
        textarea { height: 150px; resize: none; }
        textarea:focus, input:focus, select:focus { border-color: var(--primary); }
        .btn { width: 100%; padding: 14px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 15px; transition: 0.2s; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: #2563eb; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-secondary { background: #334155; color: #cbd5e1; }
        .options { display: flex; gap: 10px; }
        .hidden { display: none; }
        .result-box { background: #0f172a; padding: 15px; border-radius: 8px; border: 1px dashed #475569; word-break: break-all; color: var(--primary); margin: 15px 0; font-family: monospace; }
        .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #64748b; }
        .footer a { color: #64748b; text-decoration: none; border-bottom: 1px dashed #64748b; }
        .loading { text-align: center; color: #94a3b8; font-style: italic; }
    </style>
</head>
<body>
    <div class="container">
        <div id="create-view">
            <h2>创建加密笔记</h2>
            <textarea id="content" placeholder="在此输入私密内容（将在您的设备上加密）..." required></textarea>
            
            <div class="options">
                <select id="expiration">
                    <option value="1">1 小时后过期</option>
                    <option value="24" selected>24 小时后过期</option>
                    <option value="168">7 天后过期</option>
                </select>
                <input type="text" id="password" placeholder="设置访问密码（可选）" autocomplete="off">
            </div>

            <button onclick="createNote()" class="btn btn-primary" id="create-btn">生成加密链接</button>
            <p style="font-size:12px; color:#94a3b8; text-align:center;">只有拥有链接（和密码）的人才能解密内容。<br>服务器无法查看您的原始内容。</p>
        </div>

        <div id="result-view" class="hidden">
            <h2>链接已生成</h2>
            <p style="font-size:14px; text-align:center; color:#cbd5e1;">请将下方链接发送给接收者：</p>
            <div class="result-box" id="share-link"></div>
            <p id="password-reminder" class="hidden" style="color:#f59e0b; font-size:13px; text-align:center;">⚠️ 此笔记已设置密码，请务必将密码单独告知对方！</p>
            <button onclick="location.reload()" class="btn btn-secondary">再写一条</button>
        </div>

        <div id="decrypt-view" class="hidden">
            <h2 style="color:var(--danger)">准备销毁</h2>
            <p style="text-align:center; margin-bottom:20px;">这是一条阅后即焚的加密笔记。<br>点击下方按钮后，内容将从服务器<strong>永久删除</strong>并尝试解密。</p>
            
            <div id="pass-input-area" class="hidden">
                <input type="text" id="decrypt-pass" placeholder="请输入对方设置的密码" autocomplete="off">
            </div>

            <button onclick="fetchAndDecrypt()" class="btn btn-danger" id="reveal-btn">立即查看并销毁</button>
        </div>

        <div id="content-view" class="hidden">
            <h2>笔记内容</h2>
            <textarea id="decrypted-content" readonly></textarea>
            <p style="text-align:center; color:#ef4444; font-size:13px;">笔记已销毁，无法再次访问。</p>
            <button onclick="location.href='/'" class="btn btn-secondary">我也要发笔记</button>
        </div>

        <div id="error-view" class="hidden">
            <h2>❌ 出错了</h2>
            <p id="error-msg" style="text-align:center; color:#94a3b8;">笔记不存在，或已过期销毁。</p>
            <button onclick="location.href='/'" class="btn btn-secondary">返回首页</button>
        </div>

        <div class="footer">
            &copy; 2025 <a href="https://github.com/sykin7/secret-note" target="_blank">加密传输系统</a> | 端到端加密保护
        </div>
    </div>

    <script>
        // 加密核心逻辑
        async function createNote() {
            const text = document.getElementById('content').value;
            if (!text) return alert('请输入内容');
            
            const btn = document.getElementById('create-btn');
            btn.innerText = '加密中...'; btn.disabled = true;

            try {
                const password = document.getElementById('password').value;
                const hours = document.getElementById('expiration').value;
                
                // 1. 生成密钥
                let key, salt = null;
                if (password) {
                    const enc = new TextEncoder();
                    salt = window.crypto.getRandomValues(new Uint8Array(16));
                    const keyMaterial = await window.crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]);
                    key = await window.crypto.subtle.deriveKey(
                        { name: "PBKDF2", salt: salt, iterations: 100000, hash: "SHA-256" },
                        keyMaterial, { name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]
                    );
                } else {
                    key = await window.crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
                }

                // 2. 加密
                const iv = window.crypto.getRandomValues(new Uint8Array(12));
                const encodedText = new TextEncoder().encode(text);
                const encrypted = await window.crypto.subtle.encrypt({ name: "AES-GCM", iv: iv }, key, encodedText);

                // 3. 准备发送数据
                const exportKey = password ? null : await window.crypto.subtle.exportKey("jwk", key);
                
                const response = await fetch('/api/create', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        ciphertext: arrayBufferToBase64(encrypted),
                        iv: arrayBufferToBase64(iv),
                        salt: salt ? arrayBufferToBase64(salt) : null,
                        expire_hours: hours
                    })
                });

                const data = await response.json();
                
                // 4. 生成链接
                let finalUrl = window.location.origin + '/note/' + data.id;
                if (!password) {
                    // 如果没密码，把密钥放在URL hash里 (服务器收不到 hash)
                    finalUrl += '#' + JSON.stringify(exportKey);
                } else {
                    document.getElementById('password-reminder').classList.remove('hidden');
                }

                document.getElementById('create-view').classList.add('hidden');
                document.getElementById('result-view').classList.remove('hidden');
                document.getElementById('share-link').innerText = finalUrl;
            
            } catch (e) {
                alert('加密失败，请使用现代浏览器');
                console.error(e);
                btn.innerText = '生成加密链接'; btn.disabled = false;
            }
        }

        async function fetchAndDecrypt() {
            const pathParts = window.location.pathname.split('/');
            const id = pathParts[pathParts.length - 1];
            const btn = document.getElementById('reveal-btn');
            btn.innerText = '正在解密...'; btn.disabled = true;

            try {
                const resp = await fetch('/api/read/' + id, { method: 'POST' });
                const data = await resp.json();

                if (data.error) {
                    showError(data.error);
                    return;
                }

                // 开始解密
                const iv = base64ToArrayBuffer(data.iv);
                const encryptedData = base64ToArrayBuffer(data.ciphertext);
                let key;

                if (data.salt) {
                    // 密码模式
                    const password = document.getElementById('decrypt-pass').value;
                    if (!password) return alert('请输入密码');
                    const salt = base64ToArrayBuffer(data.salt);
                    const enc = new TextEncoder();
                    const keyMaterial = await window.crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]);
                    key = await window.crypto.subtle.deriveKey(
                        { name: "PBKDF2", salt: salt, iterations: 100000, hash: "SHA-256" },
                        keyMaterial, { name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]
                    );
                } else {
                    // 链接密钥模式
                    if (!window.location.hash) throw new Error("缺少密钥");
                    const jwk = JSON.parse(decodeURIComponent(window.location.hash.substring(1)));
                    key = await window.crypto.subtle.importKey("jwk", jwk, { name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
                }

                const decrypted = await window.crypto.subtle.decrypt({ name: "AES-GCM", iv: iv }, key, encryptedData);
                
                document.getElementById('decrypt-view').classList.add('hidden');
                document.getElementById('content-view').classList.remove('hidden');
                document.getElementById('decrypted-content').value = new TextDecoder().decode(decrypted);

            } catch (e) {
                alert('解密失败！可能是密码错误或链接不完整。');
                btn.innerText = '立即查看并销毁'; btn.disabled = false;
            }
        }

        // 工具函数
        function arrayBufferToBase64(buffer) {
            let binary = '';
            const bytes = new Uint8Array(buffer);
            for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
            return window.btoa(binary);
        }
        function base64ToArrayBuffer(base64) {
            const binary_string = window.atob(base64);
            const len = binary_string.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) bytes[i] = binary_string.charCodeAt(i);
            return bytes.buffer;
        }
        function showError(msg) {
            document.getElementById('create-view').classList.add('hidden');
            document.getElementById('decrypt-view').classList.add('hidden');
            document.getElementById('error-view').classList.remove('hidden');
            document.getElementById('error-msg').innerText = msg;
        }

        // 初始化页面状态
        window.onload = function() {
            if (window.location.pathname.startsWith('/note/')) {
                document.getElementById('create-view').classList.add('hidden');
                document.getElementById('decrypt-view').classList.remove('hidden');
                
                // 检查是否需要密码输入框
                const isPasswordProtected = document.body.getAttribute('data-pass') === 'true';
                if (isPasswordProtected) {
                    document.getElementById('pass-input-area').classList.remove('hidden');
                }
            }
        };
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_LAYOUT)

@app.route('/api/create', methods=['POST'])
def create_api():
    data = request.json
    try:
        note_id = str(uuid.uuid4()).replace('-', '')
        hours = int(data.get('expire_hours', 24))
        expire_at = datetime.datetime.now() + datetime.timedelta(hours=hours)
        
        conn = get_db()
        conn.execute(
            'INSERT INTO secrets (id, ciphertext, iv, salt, expire_at) VALUES (?, ?, ?, ?, ?)',
            (note_id, data['ciphertext'], data['iv'], data['salt'], expire_at)
        )
        conn.commit()
        conn.close()
        return jsonify({'id': note_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/note/<note_id>')
def view_note_page(note_id):
    # 这里只检查是否存在和过期，不返回数据
    conn = get_db()
    row = conn.execute('SELECT salt, expire_at FROM secrets WHERE id = ?', (note_id,)).fetchone()
    conn.close()

    if not row:
        return render_template_string(HTML_LAYOUT.replace('<body>', '<body onload="showError(\'笔记不存在或已销毁\')">'))
    
    if datetime.datetime.strptime(row['expire_at'], '%Y-%m-%d %H:%M:%S.%f') < datetime.datetime.now():
        # 过期了，顺手删掉
        conn = get_db()
        conn.execute('DELETE FROM secrets WHERE id = ?', (note_id,))
        conn.commit()
        conn.close()
        return render_template_string(HTML_LAYOUT.replace('<body>', '<body onload="showError(\'笔记已过期\')">'))

    has_pass = 'true' if row['salt'] else 'false'
    # 注入一个标记告诉前端是否需要显示密码框
    return render_template_string(HTML_LAYOUT.replace('<body>', f'<body data-pass="{has_pass}">'))

@app.route('/api/read/<note_id>', methods=['POST'])
def read_api(note_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM secrets WHERE id = ?', (note_id,)).fetchone()
    
    if not row:
        conn.close()
        return jsonify({'error': 'Not found'}), 404

    # 阅后即焚：取出后立即物理删除
    conn.execute('DELETE FROM secrets WHERE id = ?', (note_id,))
    conn.commit()
    conn.close()

    # 如果已经过期
    if datetime.datetime.strptime(row['expire_at'], '%Y-%m-%d %H:%M:%S.%f') < datetime.datetime.now():
        return jsonify({'error': 'Expired'}), 410

    return jsonify({
        'ciphertext': row['ciphertext'],
        'iv': row['iv'],
        'salt': row['salt']
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8787)
