from flask import Flask, request, render_template_string, jsonify
import sqlite3
import uuid
import datetime
import time
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
            id TEXT PRIMARY KEY, ciphertext TEXT, iv TEXT, salt TEXT, expire_at DATETIME
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT, ciphertext TEXT, iv TEXT, created_at REAL
        )
    ''')
    try:
        conn.execute('ALTER TABLE secrets ADD COLUMN burn_mode INTEGER DEFAULT 1')
    except Exception:
        pass
    conn.commit()
    conn.close()

init_db()

HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>加密传输系统</title>
    <style>
        :root { --bg: #0f172a; --panel: #1e293b; --text: #e2e8f0; --primary: #3b82f6; --danger: #ef4444; --success: #10b981; --msg-me: #2563eb; --msg-other: #334155; }
        body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
        .container { padding: 20px; max-width: 500px; margin: auto; width: 100%; box-sizing: border-box; }
        .panel { background: var(--panel); padding: 2rem; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); }
        h2 { margin-top: 0; text-align: center; color: #fff; }
        textarea, input, select { width: 100%; background: #334155; border: 1px solid #475569; color: white; padding: 12px; border-radius: 8px; margin: 10px 0; box-sizing: border-box; font-size: 16px; outline: none; }
        .btn { width: 100%; padding: 14px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 10px; transition: 0.2s; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-success { background: var(--success); color: white; }
        .btn-secondary { background: #334155; color: #cbd5e1; }
        .options { display: flex; gap: 10px; align-items: center; }
        .hidden { display: none !important; }
        .result-box { background: #0f172a; padding: 15px; border-radius: 8px; border: 1px dashed #475569; word-break: break-all; color: var(--primary); margin: 15px 0; font-family: monospace; }
        .toggle-wrapper { display: flex; align-items: center; justify-content: space-between; background: #334155; padding: 10px; border-radius: 8px; margin-top: 10px; border: 1px solid #475569; }
        .switch { position: relative; display: inline-block; width: 50px; height: 24px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #64748b; transition: .4s; border-radius: 34px; }
        .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 4px; bottom: 4px; background-color: white; transition: .4s; border-radius: 50%; }
        input:checked + .slider { background-color: var(--success); }
        input:checked + .slider:before { transform: translateX(26px); }
        #chat-view { display: flex; flex-direction: column; height: 100%; max-width: 800px; margin: 0 auto; width: 100%; background: var(--bg); }
        #chat-header { padding: 15px; background: var(--panel); border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; }
        #chat-status { font-size: 12px; color: var(--success); display: flex; align-items: center; gap: 5px; }
        .dot { width: 8px; height: 8px; background: var(--success); border-radius: 50%; display: inline-block; animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        #chat-box { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
        .msg-row { display: flex; width: 100%; }
        .msg-row.me { justify-content: flex-end; }
        .msg-bubble { max-width: 70%; padding: 10px 15px; border-radius: 12px; font-size: 15px; line-height: 1.5; word-wrap: break-word; position: relative; }
        .me .msg-bubble { background: var(--msg-me); color: white; border-bottom-right-radius: 2px; }
        .other .msg-bubble { background: var(--msg-other); color: #e2e8f0; border-bottom-left-radius: 2px; }
        .system-msg { text-align: center; color: #64748b; font-size: 12px; margin: 10px 0; }
        #chat-input-area { padding: 15px; background: var(--panel); border-top: 1px solid #334155; display: flex; gap: 10px; }
        #chat-msg-input { margin: 0; height: 50px; }
        .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #64748b; }
        .footer a { color: #64748b; text-decoration: none; border-bottom: 1px dashed #64748b; }
    </style>
</head>
<body>
    <div id="home-view" class="container">
        <div class="panel" style="text-align: center;">
            <h2>请选择传输模式</h2>
            <p style="color:#94a3b8; font-size:14px; margin-bottom: 30px;">端到端加密保护 | 服务器不存原文</p>
            <button onclick="showNoteCreate()" class="btn btn-primary">✉️ 发送私密笔记</button>
            <button onclick="createChatRoom()" class="btn btn-success">💬 创建聊天室</button>
            <div class="footer">
                &copy; 2025 <a href="https://github.com/sykin7/secret-note" target="_blank">加密传输系统</a>
            </div>
        </div>
    </div>

    <div id="note-wrapper" class="container hidden">
        <div class="panel">
            <div id="create-view">
                <h2>创建私密笔记</h2>
                <textarea id="content" placeholder="在此输入私密内容..." required style="height:120px"></textarea>
                <div class="options">
                    <select id="expiration" style="flex:1">
                        <option value="1">1 小时后过期</option>
                        <option value="24" selected>24 小时后过期</option>
                        <option value="168">7 天后过期</option>
                    </select>
                </div>
                <div class="toggle-wrapper">
                    <span style="font-size:14px; color:#fff">🔥 阅后即焚 (阅读一次后立即删除)</span>
                    <label class="switch">
                        <input type="checkbox" id="burn-toggle" checked>
                        <span class="slider"></span>
                    </label>
                </div>
                <input type="text" id="password" placeholder="设置访问密码（可选）" autocomplete="off">
                <button onclick="createNote()" class="btn btn-primary" id="create-btn">生成加密链接</button>
                <button onclick="location.reload()" class="btn btn-secondary">返回</button>
            </div>

            <div id="result-view" class="hidden">
                <h2>链接已生成</h2>
                <div class="result-box" id="share-link"></div>
                <p id="password-reminder" class="hidden" style="color:#f59e0b; font-size:13px; text-align:center;">⚠️ 已设置密码，请务必告知对方！</p>
                <button onclick="location.href='/'" class="btn btn-secondary">返回首页</button>
            </div>

            <div id="decrypt-view" class="hidden">
                <h2 id="view-title" style="color:var(--danger)">私密笔记</h2>
                <p id="view-desc" style="text-align:center;">正在请求解密...</p>
                <div id="pass-input-area" class="hidden">
                    <input type="text" id="decrypt-pass" placeholder="输入密码" autocomplete="off">
                </div>
                <button onclick="fetchAndDecryptNote()" class="btn btn-danger" id="reveal-btn">立即查看</button>
            </div>

            <div id="content-view" class="hidden">
                <h2>笔记内容</h2>
                <textarea id="decrypted-content" readonly style="height:150px"></textarea>
                <p id="burn-status" style="text-align:center; color:#ef4444; font-size:13px;"></p>
                <button onclick="location.href='/'" class="btn btn-secondary">返回首页</button>
            </div>
        </div>
    </div>

    <div id="chat-view" class="hidden">
        <div id="chat-header">
            <div style="font-weight:bold; color:white;">🔒 加密聊天室</div>
            <div id="chat-status"><span class="dot"></span> 连接安全</div>
            <button onclick="location.href='/'" style="background:none; border:none; color:#94a3b8; cursor:pointer;">退出</button>
        </div>
        <div id="chat-box">
            <div class="system-msg">正在建立通道... 消息10秒自动销毁</div>
        </div>
        <div id="chat-input-area">
            <input type="text" id="chat-msg-input" placeholder="输入消息..." onkeypress="if(event.keyCode==13) sendChatMsg()">
            <button onclick="sendChatMsg()" class="btn btn-primary" style="width:80px; margin:0;">发送</button>
        </div>
    </div>

    <script>
        async function getKey(password, salt) {
            const enc = new TextEncoder();
            const keyMaterial = await window.crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]);
            return window.crypto.subtle.deriveKey({ name: "PBKDF2", salt: salt, iterations: 100000, hash: "SHA-256" }, keyMaterial, { name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
        }
        async function encryptData(text, key) {
            const iv = window.crypto.getRandomValues(new Uint8Array(12));
            const encoded = new TextEncoder().encode(text);
            const encrypted = await window.crypto.subtle.encrypt({ name: "AES-GCM", iv: iv }, key, encoded);
            return { ciphertext: arrayBufferToBase64(encrypted), iv: arrayBufferToBase64(iv) };
        }
        async function decryptData(encryptedBase64, ivBase64, key) {
            const data = base64ToArrayBuffer(encryptedBase64);
            const iv = base64ToArrayBuffer(ivBase64);
            const decrypted = await window.crypto.subtle.decrypt({ name: "AES-GCM", iv: iv }, key, data);
            return new TextDecoder().decode(decrypted);
        }
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

        const path = window.location.pathname;
        if (path.startsWith('/note/')) {
            document.getElementById('home-view').classList.add('hidden');
            document.getElementById('note-wrapper').classList.remove('hidden');
            document.getElementById('create-view').classList.add('hidden');
            document.getElementById('decrypt-view').classList.remove('hidden');
            
            const isBurn = document.body.getAttribute('data-burn') === '1';
            const desc = document.getElementById('view-desc');
            const title = document.getElementById('view-title');
            if (isBurn) {
                title.innerText = "🔥 阅后即焚";
                desc.innerText = "⚠️ 注意：此笔记阅读一次后将立即销毁！";
            } else {
                title.innerText = "📅 限时笔记";
                desc.innerText = "此笔记在过期前可多次查看。";
            }

            if (document.body.getAttribute('data-pass') === 'true') {
                document.getElementById('pass-input-area').classList.remove('hidden');
            }
        } else if (path.startsWith('/chat/')) {
            document.getElementById('home-view').classList.add('hidden');
            document.getElementById('chat-view').classList.remove('hidden');
            initChat();
        }

        function showNoteCreate() {
            document.getElementById('home-view').classList.add('hidden');
            document.getElementById('note-wrapper').classList.remove('hidden');
        }

        async function createNote() {
            const text = document.getElementById('content').value;
            if (!text) return;
            const btn = document.getElementById('create-btn'); btn.innerText = '处理中...'; btn.disabled = true;
            
            try {
                const password = document.getElementById('password').value;
                let key, salt;
                if (password) {
                    salt = window.crypto.getRandomValues(new Uint8Array(16));
                    key = await getKey(password, salt);
                } else {
                    key = await window.crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
                    salt = null;
                }
                
                const result = await encryptData(text, key);
                const exportKey = password ? null : await window.crypto.subtle.exportKey("jwk", key);
                const isBurn = document.getElementById('burn-toggle').checked;

                const resp = await fetch('/api/note/create', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        ciphertext: result.ciphertext, iv: result.iv,
                        salt: salt ? arrayBufferToBase64(salt) : null,
                        expire_hours: document.getElementById('expiration').value,
                        burn_mode: isBurn ? 1 : 0
                    })
                });
                const data = await resp.json();
                
                let link = window.location.origin + '/note/' + data.id;
                if (!password) link += '#' + JSON.stringify(exportKey);
                else document.getElementById('password-reminder').classList.remove('hidden');

                document.getElementById('create-view').classList.add('hidden');
                document.getElementById('result-view').classList.remove('hidden');
                document.getElementById('share-link').innerText = link;
            } catch(e) { alert('错误: ' + e); btn.disabled = false; }
        }

        async function fetchAndDecryptNote() {
            const id = path.split('/').pop();
            try {
                const resp = await fetch('/api/note/read/' + id, { method: 'POST' });
                const data = await resp.json();
                if (data.error) return alert(data.error);

                let key;
                if (data.salt) {
                    const pwd = document.getElementById('decrypt-pass').value;
                    if (!pwd) return alert('请输入密码');
                    key = await getKey(pwd, base64ToArrayBuffer(data.salt));
                } else {
                    key = await window.crypto.subtle.importKey("jwk", JSON.parse(decodeURIComponent(window.location.hash.substring(1))), { name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
                }

                const text = await decryptData(data.ciphertext, data.iv, key);
                document.getElementById('decrypt-view').classList.add('hidden');
                document.getElementById('content-view').classList.remove('hidden');
                document.getElementById('decrypted-content').value = text;
                
                const status = document.getElementById('burn-status');
                if (document.body.getAttribute('data-burn') === '1') {
                    status.innerText = "🔥 笔记已销毁，无法再次访问。";
                } else {
                    status.innerText = "✅ 笔记暂未销毁，过期前可再次访问。";
                    status.style.color = "#10b981";
                }
            } catch(e) { alert('解密失败，密码错误或链接无效'); }
        }

        let chatKey = null, lastMsgTime = 0, chatRoomId = null;
        async function createChatRoom() {
            const roomId = Math.random().toString(36).substring(2, 10);
            const key = await window.crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
            const exportedKey = await window.crypto.subtle.exportKey("jwk", key);
            window.location.href = window.location.origin + '/chat/' + roomId + '#' + JSON.stringify(exportedKey);
        }
        async function initChat() {
            chatRoomId = path.split('/').pop();
            if (!window.location.hash) return appendChatMsg("缺少密钥", "system-msg");
            try {
                const jwk = JSON.parse(decodeURIComponent(window.location.hash.substring(1)));
                chatKey = await window.crypto.subtle.importKey("jwk", jwk, { name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
                appendChatMsg("聊天室已就绪，链接即密钥。", "system-msg");
                setInterval(pollMessages, 1500);
            } catch (e) { appendChatMsg("密钥错误", "system-msg"); }
        }
        async function sendChatMsg() {
            const input = document.getElementById('chat-msg-input');
            const text = input.value.trim();
            if (!text || !chatKey) return;
            input.value = ''; appendChatMsg(text, 'me');
            try {
                const result = await encryptData(text, chatKey);
                await fetch('/api/chat/send', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ room_id: chatRoomId, ciphertext: result.ciphertext, iv: result.iv }) });
            } catch(e) {}
        }
        async function pollMessages() {
            if (!chatRoomId) return;
            try {
                const resp = await fetch(`/api/chat/poll/${chatRoomId}?last=${lastMsgTime}`);
                const msgs = await resp.json();
                for (const msg of msgs) {
                    if (msg.created_at > lastMsgTime) lastMsgTime = msg.created_at;
                    try { const text = await decryptData(msg.ciphertext, msg.iv, chatKey); appendChatMsg(text, 'other'); } catch (e) {}
                }
            } catch(e) {}
        }
        function appendChatMsg(text, type) {
            const box = document.getElementById('chat-box');
            if (type === 'system-msg') {
                const div = document.createElement('div'); div.className = 'system-msg'; div.innerText = text; box.appendChild(div);
            } else {
                const row = document.createElement('div'); row.className = 'msg-row ' + type;
                const bubble = document.createElement('div'); bubble.className = 'msg-bubble'; bubble.innerText = text; row.appendChild(bubble); box.appendChild(row);
            }
            box.scrollTop = box.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_LAYOUT)

@app.route('/note/<id>')
def note_page(id):
    conn = get_db()
    row = conn.execute('SELECT salt, expire_at, burn_mode FROM secrets WHERE id = ?', (id,)).fetchone()
    conn.close()
    if not row or datetime.datetime.strptime(row['expire_at'], '%Y-%m-%d %H:%M:%S.%f') < datetime.datetime.now():
        return render_template_string(HTML_LAYOUT.replace('<body>', '<body onload="alert(\'笔记不存在或已过期\');location.href=\'/\'">'))
    has_pass = 'true' if row['salt'] else 'false'
    is_burn = '1' if row['burn_mode'] is None or row['burn_mode'] == 1 else '0'
    return render_template_string(HTML_LAYOUT.replace('<body>', f'<body data-pass="{has_pass}" data-burn="{is_burn}">'))

@app.route('/chat/<room_id>')
def chat_page(room_id):
    return render_template_string(HTML_LAYOUT)

@app.route('/api/note/create', methods=['POST'])
def create_note_api():
    data = request.json
    uid = str(uuid.uuid4()).replace('-', '')
    expire = datetime.datetime.now() + datetime.timedelta(hours=int(data.get('expire_hours', 24)))
    burn_mode = int(data.get('burn_mode', 1))
    conn = get_db()
    conn.execute('INSERT INTO secrets (id, ciphertext, iv, salt, expire_at, burn_mode) VALUES (?,?,?,?,?,?)',
                 (uid, data['ciphertext'], data['iv'], data['salt'], expire, burn_mode))
    conn.commit()
    conn.close()
    return jsonify({'id': uid})

@app.route('/api/note/read/<id>', methods=['POST'])
def read_note_api(id):
    conn = get_db()
    row = conn.execute('SELECT * FROM secrets WHERE id = ?', (id,)).fetchone()
    if row:
        if row['burn_mode'] is None or row['burn_mode'] == 1:
            conn.execute('DELETE FROM secrets WHERE id = ?', (id,))
        else:
            if datetime.datetime.strptime(row['expire_at'], '%Y-%m-%d %H:%M:%S.%f') < datetime.datetime.now():
                conn.execute('DELETE FROM secrets WHERE id = ?', (id,))
                conn.commit()
                conn.close()
                return jsonify({'error': 'Expired'}), 410
        conn.commit()
    conn.close()
    if not row: return jsonify({'error': 'Not found'}), 404
    return jsonify({'ciphertext': row['ciphertext'], 'iv': row['iv'], 'salt': row['salt']})

@app.route('/api/chat/send', methods=['POST'])
def send_chat():
    data = request.json
    conn = get_db()
    conn.execute('INSERT INTO chat_messages (room_id, ciphertext, iv, created_at) VALUES (?,?,?,?)', (data['room_id'], data['ciphertext'], data['iv'], time.time()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/api/chat/poll/<room_id>')
def poll_chat(room_id):
    last_time = float(request.args.get('last', 0))
    now = time.time()
    conn = get_db()
    rows = conn.execute('SELECT ciphertext, iv, created_at FROM chat_messages WHERE room_id = ? AND created_at > ?', (room_id, last_time)).fetchall()
    conn.execute('DELETE FROM chat_messages WHERE created_at < ?', (now - 10,))
    conn.commit()
    conn.close()
    return jsonify([dict(row) for row in rows])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8787)
