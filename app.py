from flask import Flask, request, render_template_string, jsonify
import sqlite3
import uuid
import datetime
import time
import os
import json
import re
import random

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 

DB_NAME = 'storage.db'
ADMIN_CODE = os.environ.get('ADMIN_PASSWORD', 'admin888')

CREATION_LIMITS = {}
ADMIN_LIMITS = {}
MESSAGE_LIMITS = {}

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA auto_vacuum = FULL;')
    conn.execute('''CREATE TABLE IF NOT EXISTS secrets (id TEXT PRIMARY KEY, ciphertext TEXT, iv TEXT, salt TEXT, expire_at DATETIME, burn_mode INTEGER DEFAULT 1)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS chat_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT, ciphertext TEXT, iv TEXT, created_at REAL, sender_id TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS rooms (id TEXT PRIMARY KEY, name TEXT, is_public INTEGER, salt TEXT, created_at REAL, owner_token TEXT, last_active REAL)''')
    try: conn.execute('ALTER TABLE secrets ADD COLUMN burn_mode INTEGER DEFAULT 1')
    except: pass
    try: conn.execute('ALTER TABLE chat_messages ADD COLUMN sender_id TEXT')
    except: pass
    try: conn.execute('ALTER TABLE rooms ADD COLUMN owner_token TEXT')
    except: pass
    try: conn.execute('ALTER TABLE rooms ADD COLUMN last_active REAL')
    except: pass
    conn.commit()
    conn.close()

init_db()

def cleanup_memory_cache():
    now = time.time()
    for ip in list(CREATION_LIMITS.keys()):
        if now - CREATION_LIMITS[ip] > 60: del CREATION_LIMITS[ip]
    for ip in list(ADMIN_LIMITS.keys()):
        if now - ADMIN_LIMITS[ip] > 5: del ADMIN_LIMITS[ip]
    for ip in list(MESSAGE_LIMITS.keys()):
        if now - MESSAGE_LIMITS[ip] > 5: del MESSAGE_LIMITS[ip]

def clean_zombies():
    try:
        conn = get_db()
        now_dt = datetime.datetime.now()
        now_ts = time.time()
        conn.execute('DELETE FROM secrets WHERE expire_at < ?', (now_dt,))
        conn.execute('DELETE FROM chat_messages WHERE created_at < ?', (now_ts - 300,))
        conn.execute('DELETE FROM rooms WHERE is_public = 0 AND last_active < ?', (now_ts - 600,))
        cleanup_memory_cache()
        conn.commit()
        conn.close()
    except: pass

def random_clean():
    if random.random() < 0.01: clean_zombies()

def validate_str(val, max_len=1000, default=""):
    if not isinstance(val, str): return default
    return val[:max_len]

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
        .container { padding: 20px; max-width: 600px; margin: auto; width: 100%; box-sizing: border-box; display: flex; flex-direction: column; max-height: 100vh; }
        .panel { background: var(--panel); padding: 2rem; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); margin-bottom: 20px; }
        h2 { margin-top: 0; text-align: center; color: #fff; font-size: 1.5rem; }
        h3 { color: #94a3b8; border-bottom: 1px solid #334155; padding-bottom: 10px; margin-top: 0; }
        textarea, input, select { width: 100%; background: #334155; border: 1px solid #475569; color: white; padding: 12px; border-radius: 8px; margin: 10px 0; box-sizing: border-box; font-size: 16px; outline: none; }
        .btn { width: 100%; padding: 14px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 10px; transition: 0.2s; text-align: center; display: inline-block; text-decoration: none; box-sizing: border-box; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-success { background: var(--success); color: white; }
        .btn-secondary { background: #334155; color: #cbd5e1; }
        .btn-sm { padding: 8px 15px; font-size: 14px; width: auto; margin-top: 0; }
        .options { display: flex; gap: 10px; align-items: center; }
        .hidden { display: none !important; }
        .result-box { background: #0f172a; padding: 15px; border-radius: 8px; border: 1px dashed #475569; word-break: break-all; color: var(--primary); margin: 15px 0; font-family: monospace; display: none; }
        .room-list { max-height: 300px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
        .room-item { background: #334155; padding: 15px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; }
        .room-info { display: flex; flex-direction: column; }
        .room-name { font-weight: bold; color: white; }
        .room-time { font-size: 12px; color: #94a3b8; margin-top: 4px; }
        .toggle-wrapper { display: flex; align-items: center; justify-content: space-between; background: #334155; padding: 10px; border-radius: 8px; margin-top: 10px; border: 1px solid #475569; }
        .switch { position: relative; display: inline-block; width: 50px; height: 24px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #64748b; transition: .4s; border-radius: 34px; }
        .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 4px; bottom: 4px; background-color: white; transition: .4s; border-radius: 50%; }
        input:checked + .slider { background-color: var(--success); }
        input:checked + .slider:before { transform: translateX(26px); }
        #chat-view { display: flex; flex-direction: column; height: 100%; max-width: 800px; margin: 0 auto; width: 100%; background: var(--bg); position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 100; }
        #chat-header { padding: 15px; background: var(--panel); border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; }
        #chat-title { font-weight: bold; color: white; }
        #chat-box { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
        .msg-row { display: flex; width: 100%; }
        .msg-row.me { justify-content: flex-end; }
        .msg-bubble { max-width: 70%; padding: 10px 15px; border-radius: 12px; font-size: 15px; line-height: 1.5; word-wrap: break-word; position: relative; }
        .me .msg-bubble { background: var(--msg-me); color: white; border-bottom-right-radius: 2px; }
        .other .msg-bubble { background: var(--msg-other); color: #e2e8f0; border-bottom-left-radius: 2px; }
        .media-placeholder { background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px; text-align: center; cursor: pointer; border: 1px dashed #64748b; transition: 0.2s; display: inline-block; width: 100%; box-sizing: border-box; }
        .media-placeholder:hover { background: rgba(0,0,0,0.4); border-color: var(--primary); }
        .msg-bubble img, .msg-bubble video { max-width: 100%; border-radius: 8px; margin-top: 5px; display: block; }
        .msg-bubble a { color: #60a5fa; text-decoration: underline; }
        .system-msg { text-align: center; color: #64748b; font-size: 12px; margin: 10px 0; }
        #chat-input-area { padding: 15px; background: var(--panel); border-top: 1px solid #334155; display: flex; gap: 10px; }
        #chat-msg-input { margin: 0; height: 50px; }
        .footer { text-align: center; margin-top: 20px; font-size: 12px; color: #64748b; padding-bottom: 20px; }
        .footer a { color: #64748b; text-decoration: none; border-bottom: 1px dashed #64748b; }
        .modal { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: flex; justify-content: center; align-items: center; z-index: 50; }
    </style>
</head>
<body>
    <div id="home-view" class="container">
        <div class="panel">
            <h2>加密传输系统</h2>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px;">
                <button onclick="showNoteCreate()" class="btn btn-primary">✉️ 发送私密笔记</button>
                <button onclick="createTempRoom()" class="btn btn-secondary">💬 临时私聊 (房主在线)</button>
            </div>
            <h3>🔴 公开聊天大厅</h3>
            <div id="room-list" class="room-list"><div style="text-align:center; color:#64748b; padding:20px;">加载中...</div></div>
            <button onclick="showCreateRoomModal()" class="btn btn-success" style="width:100%; margin-top:10px;">➕ 创建公开房间 (管理员)</button>
            <button onclick="loadRooms()" class="btn btn-secondary btn-sm" style="width:100%; margin-top:10px;">↻ 刷新列表</button>
        </div>
        <div class="footer">&copy; 2025 <a href="https://github.com/sykin7/secret-note" target="_blank">项目主页</a></div>
    </div>

    <div id="create-room-modal" class="modal hidden">
        <div class="panel" style="width: 90%; max-width: 400px;">
            <h3>创建公开聊天室</h3>
            <input type="text" id="new-room-name" placeholder="房间名称 (最多20字)" maxlength="20">
            <input type="text" id="new-room-pass" placeholder="进房密码 (必填)" autocomplete="off">
            <div style="border-top:1px dashed #475569; margin:10px 0;"></div>
            <input type="password" id="admin-code" placeholder="管理员口令" autocomplete="off">
            <div style="display:flex; gap:10px;">
                <button onclick="createPublicRoom()" class="btn btn-success">确认创建</button>
                <button onclick="closeModal('create-room-modal')" class="btn btn-secondary">取消</button>
            </div>
        </div>
    </div>

    <div id="note-wrapper" class="container hidden">
        <div class="panel">
            <div id="create-view">
                <h2>创建私密笔记</h2>
                <textarea id="content" placeholder="在此输入私密内容..." required style="height:120px"></textarea>
                <div class="options">
                    <select id="expiration" style="flex:1"><option value="1">1 小时后过期</option><option value="24" selected>24 小时后过期</option></select>
                </div>
                <div class="toggle-wrapper">
                    <span style="font-size:14px; color:#fff">🔥 阅后即焚</span>
                    <label class="switch"><input type="checkbox" id="burn-toggle" checked><span class="slider"></span></label>
                </div>
                <input type="text" id="password" placeholder="设置访问密码（可选）" autocomplete="off">
                <button onclick="createNote()" class="btn btn-primary" id="create-btn">生成加密链接</button>
                <button onclick="location.reload()" class="btn btn-secondary">返回大厅</button>
            </div>
            <div id="result-view" class="hidden">
                <h2>链接已生成</h2>
                <div class="result-box" id="share-link"></div>
                <div style="text-align:center; margin: 20px 0;">
                    <div style="margin-bottom:10px; color:#94a3b8; font-size:14px;">加密链接已就绪</div>
                    <button onclick="copyNoteLink()" class="btn btn-success" style="width: auto; padding: 10px 20px;">🔗 一键复制私密链接</button>
                </div>
                <p id="password-reminder" class="hidden" style="color:#f59e0b; font-size:13px; text-align:center;">⚠️ 已设置密码，请务必告知对方！</p>
                <button onclick="location.href='/'" class="btn btn-secondary">返回首页</button>
            </div>
            <div id="decrypt-view" class="hidden">
                <h2 id="view-title" style="color:var(--danger)">私密笔记</h2>
                <p id="view-desc" style="text-align:center;">正在请求解密...</p>
                <div id="pass-input-area" class="hidden"><input type="text" id="decrypt-pass" placeholder="输入密码" autocomplete="off"></div>
                <button onclick="fetchAndDecryptNote()" class="btn btn-danger" id="reveal-btn">立即查看</button>
                <button onclick="location.href='/'" class="btn btn-secondary">返回首页</button>
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
            <div id="chat-title" style="font-size:14px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:60%;">🔒 加密聊天室</div>
            <div style="display:flex; gap:10px;">
                <button id="copy-link-btn" onclick="copyRoomLink()" class="btn btn-success btn-sm" style="display:none;">🔗 复制链接</button>
                <button onclick="exitChat()" style="background:none; border:none; color:#ef4444; cursor:pointer; font-size:14px;">🚫 退出</button>
            </div>
        </div>
        <div id="chat-box"><div class="system-msg">正在连接...</div></div>
        <div id="chat-input-area">
            <button onclick="window.open('https://wj.iuiu.netlib.re/', '_blank')" class="btn btn-secondary" style="width:auto; padding:0 15px; margin:0; margin-right:8px;" title="传文件">📂</button>
            <input type="text" id="chat-msg-input" placeholder="输入消息..." onkeypress="if(event.keyCode==13) sendChatMsg()">
            <button onclick="sendChatMsg()" class="btn btn-primary" style="width:60px; margin:0;">发送</button>
        </div>
    </div>

    <script>
        const myClientId = Math.random().toString(36).substring(2);
        const path = window.location.pathname;

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

        window.onload = function() {
            if (path.startsWith('/note/')) {
                document.getElementById('home-view').classList.add('hidden');
                document.getElementById('note-wrapper').classList.remove('hidden');
                document.getElementById('create-view').classList.add('hidden');
                document.getElementById('decrypt-view').classList.remove('hidden');
                initNoteView();
            } else if (path.startsWith('/chat/')) {
                document.getElementById('home-view').classList.add('hidden');
                document.getElementById('chat-view').classList.remove('hidden');
                initChat();
            } else { loadRooms(); }
        };

        async function createTempRoom() {
            const key = await window.crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
            const exportedKey = await window.crypto.subtle.exportKey("jwk", key);
            const resp = await fetch('/api/room/create_temp', { method: 'POST' });
            const data = await resp.json();
            if(data.error) return alert(data.error);
            sessionStorage.setItem('owner_token_' + data.id, data.owner_token);
            window.location.href = '/chat/' + data.id + '#' + JSON.stringify(exportedKey);
        }

        let chatKey = null, lastMsgTime = 0, chatRoomId = null, heartbeatInterval = null;

        async function initChat() {
            chatRoomId = path.split('/').pop();
            const ownerToken = sessionStorage.getItem('owner_token_' + chatRoomId);
            if (ownerToken) {
                document.getElementById('copy-link-btn').style.display = 'block'; 
                heartbeatInterval = setInterval(() => {
                    fetch('/api/room/heartbeat', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ room_id: chatRoomId, owner_token: ownerToken }) });
                }, 3000);
            }
            if (!window.location.hash) {
                const pass = prompt("请输入密码:");
                if(pass) {
                    const resp = await fetch('/api/room/info/' + chatRoomId);
                    const data = await resp.json();
                    if(data.error) { alert('房间已销毁'); window.location.href='/'; return; }
                    chatKey = await getKey(pass, base64ToArrayBuffer(data.salt));
                } else { return appendChatMsg("缺少密钥", "system-msg"); }
            } else {
                try {
                    const jwk = JSON.parse(decodeURIComponent(window.location.hash.substring(1)));
                    chatKey = await window.crypto.subtle.importKey("jwk", jwk, { name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
                } catch(e) { return appendChatMsg("密钥错误", "system-msg"); }
            }
            appendChatMsg("已连接。消息5分钟销毁。", "system-msg");
            if(ownerToken) appendChatMsg("【房主】页面关闭后房间将销毁。", "system-msg");
            setInterval(pollMessages, 1500);
        }

        async function pollMessages() {
            if (!chatRoomId || !chatKey) return;
            try {
                const resp = await fetch(`/api/chat/poll/${chatRoomId}?last=${lastMsgTime}`);
                const data = await resp.json();
                if (data.status === 'room_gone') { alert('房间已销毁'); window.location.href = '/'; return; }
                for (const msg of data) {
                    if (msg.created_at > lastMsgTime) lastMsgTime = msg.created_at;
                    if (msg.sender_id === myClientId) continue; 
                    try { const text = await decryptData(msg.ciphertext, msg.iv, chatKey); appendChatMsg(text, 'other'); } catch (e) { }
                }
            } catch(e) {}
        }

        async function exitChat() {
            if(confirm("确定退出吗？")) {
                const ownerToken = sessionStorage.getItem('owner_token_' + chatRoomId);
                if(ownerToken) {
                    await fetch('/api/room/delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ room_id: chatRoomId, owner_token: ownerToken }) });
                }
                window.location.href = '/';
            }
        }

        function copyRoomLink() {
            navigator.clipboard.writeText(window.location.href).then(() => alert('邀请链接已复制'));
        }

        function copyNoteLink() {
            const link = document.getElementById('share-link').innerText;
            navigator.clipboard.writeText(link).then(() => alert('私密链接已复制，请发送给对方。'));
        }

        async function sendChatMsg() {
            const input = document.getElementById('chat-msg-input');
            const text = input.value.trim();
            if (!text || !chatKey) return;
            input.value = ''; appendChatMsg(text, 'me');
            try {
                const result = await encryptData(text, chatKey);
                await fetch('/api/chat/send', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ room_id: chatRoomId, ciphertext: result.ciphertext, iv: result.iv, sender_id: myClientId }) });
            } catch(e) {
                if(e.message && e.message.includes('413')) alert('内容太长');
                else if(e.message && e.message.includes('429')) alert('说话太快了，请慢一点');
            }
        }

        function appendChatMsg(text, type) {
            const box = document.getElementById('chat-box');
            if (type === 'system-msg') {
                const div = document.createElement('div'); div.className = 'system-msg'; div.innerText = text; box.appendChild(div);
            } else {
                const row = document.createElement('div'); row.className = 'msg-row ' + type;
                const bubble = document.createElement('div'); bubble.className = 'msg-bubble';
                
                let safeText = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                
                const imgRegex = /(https?:\/\/[^"'\s]+\.(?:png|jpg|jpeg|gif|webp))/i;
                const videoRegex = /(https?:\/\/[^"'\s]+\.(?:mp4|webm|ogg))/i;
                const urlRegex = /(https?:\/\/[^"'\s]+)/g;

                if (imgRegex.test(text)) {
                    bubble.innerHTML = safeText.replace(urlRegex, '<div class="media-placeholder" onclick="this.outerHTML=\'<img src=\\'$1\\'>\'">🖼️ 点击加载图片 (隐私保护)</div>');
                } else if (videoRegex.test(text)) {
                    bubble.innerHTML = safeText.replace(urlRegex, '<div class="media-placeholder" onclick="this.outerHTML=\'<video controls src=\\'$1\\'></video>\'">▶️ 点击播放视频 (隐私保护)</div>');
                } else {
                    bubble.innerHTML = safeText.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
                }
                
                row.appendChild(bubble); box.appendChild(row);
            }
            box.scrollTop = box.scrollHeight;
        }

        async function loadRooms() {
            try {
                const resp = await fetch('/api/rooms');
                const rooms = await resp.json();
                const listEl = document.getElementById('room-list');
                listEl.innerHTML = '';
                if (rooms.length === 0) { listEl.innerHTML = '<div style="text-align:center; color:#64748b; padding:20px;">暂无公开房间</div>'; return; }
                rooms.forEach(room => {
                    const div = document.createElement('div'); div.className = 'room-item';
                    div.innerHTML = `<div class="room-info"><span class="room-name">${escapeHtml(room.name)}</span><span class="room-time">${new Date(room.created_at * 1000).toLocaleString()}</span></div><div style="display:flex; gap:5px;"><button class="btn btn-primary btn-sm" onclick="joinRoom('${room.id}', '${room.name}', '${room.salt}')">加入</button><button class="btn btn-danger btn-sm" style="padding:8px 10px;" onclick="deleteRoom('${room.id}')">×</button></div>`;
                    listEl.appendChild(div);
                });
            } catch (e) {}
        }
        async function createPublicRoom() {
            const name = document.getElementById('new-room-name').value.trim();
            const pass = document.getElementById('new-room-pass').value;
            const adminCode = document.getElementById('admin-code').value;
            if (!name || !pass || !adminCode) return alert('请填写完整');
            const salt = window.crypto.getRandomValues(new Uint8Array(16));
            const saltBase64 = arrayBufferToBase64(salt);
            const key = await getKey(pass, salt);
            const exportedKey = await window.crypto.subtle.exportKey("jwk", key);
            const resp = await fetch('/api/room/create_public', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ name: name, salt: saltBase64, admin_code: adminCode }) });
            const data = await resp.json();
            if (data.error) return alert(data.error);
            window.location.href = '/chat/' + data.id + '#' + JSON.stringify(exportedKey);
        }
        async function joinRoom(id, name, saltBase64) {
            const pass = prompt(`请输入房间 "${name}" 的密码:`);
            if (!pass) return;
            try {
                const salt = base64ToArrayBuffer(saltBase64);
                const key = await getKey(pass, salt);
                const exportedKey = await window.crypto.subtle.exportKey("jwk", key);
                window.location.href = '/chat/' + id + '#' + JSON.stringify(exportedKey);
            } catch (e) { alert('错误'); }
        }
        async function deleteRoom(id) {
            const code = prompt("管理员口令:");
            if(!code) return;
            const resp = await fetch('/api/room/delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ room_id: id, admin_code: code }) });
            const data = await resp.json();
            if(data.error) alert(data.error); else loadRooms();
        }

        function showCreateRoomModal() { document.getElementById('create-room-modal').classList.remove('hidden'); }
        function closeModal(id) { document.getElementById(id).classList.add('hidden'); }
        function showNoteCreate() { document.getElementById('home-view').classList.add('hidden'); document.getElementById('note-wrapper').classList.remove('hidden'); }
        function escapeHtml(text) { const div = document.createElement('div'); div.innerText = text; return div.innerHTML; }
        
        function initNoteView() {
            const isBurn = document.body.getAttribute('data-burn') === '1';
            const title = document.getElementById('view-title');
            if (isBurn) { title.innerText = "🔥 阅后即焚"; document.getElementById('view-desc').innerText = "⚠️ 注意：此笔记阅读一次后将立即销毁！"; }
            else { title.innerText = "📅 限时笔记"; document.getElementById('view-desc').innerText = "此笔记在过期前可多次查看。"; }
            if (document.body.getAttribute('data-pass') === 'true') document.getElementById('pass-input-area').classList.remove('hidden');
        }
        async function createNote() {
            const text = document.getElementById('content').value;
            if (!text) return;
            const btn = document.getElementById('create-btn'); btn.innerText = '处理中...'; btn.disabled = true;
            try {
                const password = document.getElementById('password').value;
                let key, salt;
                if (password) { salt = window.crypto.getRandomValues(new Uint8Array(16)); key = await getKey(password, salt); }
                else { key = await window.crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]); salt = null; }
                const result = await encryptData(text, key);
                const exportKey = password ? null : await window.crypto.subtle.exportKey("jwk", key);
                const isBurn = document.getElementById('burn-toggle').checked;
                const resp = await fetch('/api/note/create', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ ciphertext: result.ciphertext, iv: result.iv, salt: salt ? arrayBufferToBase64(salt) : null, expire_hours: document.getElementById('expiration').value, burn_mode: isBurn ? 1 : 0 }) });
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
                } else { key = await window.crypto.subtle.importKey("jwk", JSON.parse(decodeURIComponent(window.location.hash.substring(1))), { name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]); }
                const text = await decryptData(data.ciphertext, data.iv, key);
                document.getElementById('decrypt-view').classList.add('hidden');
                document.getElementById('content-view').classList.remove('hidden');
                document.getElementById('decrypted-content').value = text;
                const status = document.getElementById('burn-status');
                if (document.body.getAttribute('data-burn') === '1') status.innerText = "🔥 笔记已销毁，无法再次访问。";
                else { status.innerText = "✅ 笔记暂未销毁，过期前可再次访问。"; status.style.color = "#10b981"; }
            } catch(e) { alert('解密失败，密码错误或链接无效'); }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index(): return render_template_string(HTML_LAYOUT)

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
def chat_page(room_id): return render_template_string(HTML_LAYOUT)

@app.route('/api/rooms')
def list_rooms():
    clean_zombies()
    conn = get_db()
    since = time.time() - 86400 
    rows = conn.execute('SELECT id, name, created_at, salt FROM rooms WHERE is_public = 1 AND created_at > ? ORDER BY created_at DESC', (since,)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route('/api/room/create_public', methods=['POST'])
def create_public_room():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    now = time.time()
    last = ADMIN_LIMITS.get(ip, 0)
    if now - last < 3: return jsonify({'error': '操作太快'}), 429
    ADMIN_LIMITS[ip] = now
    clean_zombies()
    data = request.json
    if data.get('admin_code') != ADMIN_CODE: return jsonify({'error': '管理员口令错误'}), 403
    name = validate_str(data.get('name'), 30, "Room")
    if not name: return jsonify({'error': '名称不能为空'}), 400
    uid = str(uuid.uuid4()).replace('-', '')
    conn = get_db()
    conn.execute('INSERT INTO rooms (id, name, is_public, salt, created_at, last_active) VALUES (?,?,?,?,?,?)', (uid, name, 1, data['salt'], time.time(), time.time()))
    conn.commit()
    conn.close()
    return jsonify({'id': uid})

@app.route('/api/room/create_temp', methods=['POST'])
def create_temp_room():
    clean_zombies()
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    now = time.time()
    last = CREATION_LIMITS.get(ip, 0)
    if now - last < 60: return jsonify({'error': '每分钟限建一个房间'}), 429
    CREATION_LIMITS[ip] = now
    uid = str(uuid.uuid4()).replace('-', '')
    owner_token = str(uuid.uuid4())
    conn = get_db()
    conn.execute('INSERT INTO rooms (id, name, is_public, salt, created_at, owner_token, last_active) VALUES (?,?,?,?,?,?,?)', 
                 (uid, '临时房间', 0, '', time.time(), owner_token, time.time()))
    conn.commit()
    conn.close()
    return jsonify({'id': uid, 'owner_token': owner_token})

@app.route('/api/room/heartbeat', methods=['POST'])
def room_heartbeat():
    data = request.json
    room_id = data.get('room_id')
    token = data.get('owner_token')
    conn = get_db()
    res = conn.execute('UPDATE rooms SET last_active = ? WHERE id = ? AND owner_token = ?', (time.time(), room_id, token))
    conn.commit()
    conn.close()
    if res.rowcount == 0: return jsonify({'status': 'failed'}), 403
    return jsonify({'status': 'ok'})

@app.route('/api/room/info/<id>')
def room_info(id):
    conn = get_db()
    row = conn.execute('SELECT salt FROM rooms WHERE id = ?', (id,)).fetchone()
    conn.close()
    if row: return jsonify(dict(row))
    return jsonify({'error': 'not found'})

@app.route('/api/room/delete', methods=['POST'])
def delete_room():
    data = request.json
    conn = get_db()
    can_delete = False
    if data.get('admin_code') == ADMIN_CODE: can_delete = True
    elif data.get('owner_token'):
        row = conn.execute('SELECT 1 FROM rooms WHERE id = ? AND owner_token = ?', (data['room_id'], data['owner_token'])).fetchone()
        if row: can_delete = True
    if can_delete:
        conn.execute('DELETE FROM rooms WHERE id = ?', (data['room_id'],))
        conn.execute('DELETE FROM chat_messages WHERE room_id = ?', (data['room_id'],))
        conn.commit()
        conn.close()
        return jsonify({'status': 'ok'})
    conn.close()
    return jsonify({'error': '无权删除'}), 403

@app.route('/api/chat/poll/<room_id>')
def poll_chat(room_id):
    random_clean()
    conn = get_db()
    room = conn.execute('SELECT is_public, last_active FROM rooms WHERE id = ?', (room_id,)).fetchone()
    if not room:
        conn.close()
        return jsonify({'status': 'room_gone'})
    if room['is_public'] == 0:
        if time.time() - room['last_active'] > 8:
            conn.execute('DELETE FROM rooms WHERE id = ?', (room_id,))
            conn.execute('DELETE FROM chat_messages WHERE room_id = ?', (room_id,))
            conn.commit()
            conn.close()
            return jsonify({'status': 'room_gone'})
    last_time = float(request.args.get('last', 0))
    now = time.time()
    rows = conn.execute('SELECT ciphertext, iv, created_at, sender_id FROM chat_messages WHERE room_id = ? AND created_at > ?', (room_id, last_time)).fetchall()
    conn.execute('DELETE FROM chat_messages WHERE created_at < ?', (now - 300,))
    conn.commit()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route('/api/note/create', methods=['POST'])
def create_note_api():
    clean_zombies()
    data = request.json
    if len(data.get('ciphertext', '')) > 20000: return jsonify({'error': '内容过长'}), 413
    uid = str(uuid.uuid4()).replace('-', '')
    expire = datetime.datetime.now() + datetime.timedelta(hours=int(data.get('expire_hours', 24)))
    burn_mode = int(data.get('burn_mode', 1))
    conn = get_db()
    conn.execute('INSERT INTO secrets (id, ciphertext, iv, salt, expire_at, burn_mode) VALUES (?,?,?,?,?,?)', (uid, data['ciphertext'], data['iv'], data['salt'], expire, burn_mode))
    conn.commit()
    conn.close()
    return jsonify({'id': uid})

@app.route('/api/note/read/<id>', methods=['POST'])
def read_note_api(id):
    conn = get_db()
    row = conn.execute('SELECT * FROM secrets WHERE id = ?', (id,)).fetchone()
    if row:
        if row['burn_mode'] == 1: conn.execute('DELETE FROM secrets WHERE id = ?', (id,))
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
    random_clean()
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    now = time.time()
    last = MESSAGE_LIMITS.get(ip, 0)
    if now - last < 1.0: return jsonify({'error': '发送太快'}), 429
    MESSAGE_LIMITS[ip] = now
    data = request.json
    if len(data.get('ciphertext', '')) > 20000: return jsonify({'error': '内容过长'}), 413
    sender_id = validate_str(data.get('sender_id'), 32, "anon")
    conn = get_db()
    conn.execute('INSERT INTO chat_messages (room_id, ciphertext, iv, created_at, sender_id) VALUES (?,?,?,?,?)', (data['room_id'], data['ciphertext'], data['iv'], time.time(), sender_id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8787)
