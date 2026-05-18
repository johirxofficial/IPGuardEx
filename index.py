import socket
import time
import json
import os
import sys
import threading
import requests
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv, set_key

# ==============================================================================
# CLEAR COMMAND EXECUTION & ENVIRONMENT LOADER
# ==============================================================================
ENV_FILE = ".env"
STATE_FILE = "state.json"
TARGETS_FILE = "targets.json"
LOG_FILE = "ping_logger.log"

# ক্লিয়ার কমান্ড এক্সিকিউশন
if '--clear' in sys.argv:
    print("\n" + "="*50)
    print("🗑️  CLEARING ALL CONFIGURATIONS & DATA...")
    print("="*50)
    for f in [ENV_FILE, STATE_FILE, TARGETS_FILE, LOG_FILE]:
        if os.path.exists(f):
            os.remove(f)
            print(f"[-] Deleted: {f}")
    print("\n✅ Project reset to factory state! Run 'python index.py' to start fresh.\n")
    sys.exit(0)

def load_env_or_prompt():
    """ইউজারের কনফিগারেশন লোড বা ইনপুট নেওয়ার মেকানিজম"""
    load_dotenv(ENV_FILE)
    config = {
        'BOT_TOKEN': os.getenv('BOT_TOKEN', ''),
        'CHAT_ID': os.getenv('CHAT_ID', ''),
        'WEB_NAME': os.getenv('WEB_NAME', ''),
        'PORT': os.getenv('PORT', '')
    }
    
    required_keys = ['BOT_TOKEN', 'CHAT_ID', 'WEB_NAME', 'PORT']
    missing_or_empty = [k for k in required_keys if not config[k]]
    
    if missing_or_empty:
        print("\n" + "="*60)
        print("⚙️  IPGUARDEX INITIAL SETUP (FIRST TIME RUN) ⚙️")
        print("="*60)
        
        if 'BOT_TOKEN' in missing_or_empty:
            config['BOT_TOKEN'] = input("🔹 Enter Telegram Bot Token: ").strip()
        if 'CHAT_ID' in missing_or_empty:
            config['CHAT_ID'] = input("🔹 Enter Telegram Chat ID: ").strip()
        if 'WEB_NAME' in missing_or_empty:
            config['WEB_NAME'] = input("🔹 Enter Dashboard Title (Web Name): ").strip() or "IPGuardex Core"
        if 'PORT' in missing_or_empty:
            config['PORT'] = input("🔹 Enter Flask Web Port (Default 5000): ").strip() or "5000"
            
        # .env ফাইলে সেভ করা
        if not os.path.exists(ENV_FILE):
            with open(ENV_FILE, 'w') as f: pass
            
        for k, v in config.items():
            set_key(ENV_FILE, k, v)
        print("\n✅ Configuration saved securely! Next time it will auto-start.")
        print("="*60 + "\n")
        
    return config

# কনফিগারেশন সেটআপ
ENV_CONFIG = load_env_or_prompt()
BOT_TOKEN = ENV_CONFIG['BOT_TOKEN']
CHAT_ID = ENV_CONFIG['CHAT_ID']
WEB_NAME = ENV_CONFIG['WEB_NAME']
RUN_PORT = int(ENV_CONFIG['PORT'])
DOWN_ALERT_INTERVAL = 600  # ১০ মিনিট

LIVE_DOWNTIMES = {}
LIVE_UPTIMES = {}  
HISTORY_LOGS = []

app = Flask(__name__)

# ==============================================================================
# PERSISTENT STORAGE ENGINE (CRASH / RESTART PROOF)
# ==============================================================================
def init_storage():
    global HISTORY_LOGS
    if not os.path.exists(TARGETS_FILE) or os.path.getsize(TARGETS_FILE) == 0:
        with open(TARGETS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=4)
            
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                HISTORY_LOGS = data.get('history', [])
        except:
            HISTORY_LOGS = []

    # রিস্টার্টের পরেও লাইভ স্টেট ব্যাকআপ থেকে লোড করা
    load_state()

def load_targets():
    try:
        with open(TARGETS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_targets(targets):
    try:
        with open(TARGETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(targets, f, indent=4)
    except Exception as e:
        print(f"[-] Error saving targets: {e}")

def save_history():
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'history': HISTORY_LOGS}, f, indent=4)
    except:
        pass

def load_state():
    """স্ক্রিপ্ট রিস্টার্ট হলে লাইভ ডাউন/আপ ডাটা লোড করবে"""
    global LIVE_DOWNTIMES, LIVE_UPTIMES
    if os.path.exists(STATE_FILE) and os.path.getsize(STATE_FILE) > 0:
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                LIVE_DOWNTIMES = data.get('downtimes', {})
                LIVE_UPTIMES = data.get('uptimes', {})
                print("[+] Restored live monitoring state from backup.")
        except:
            LIVE_DOWNTIMES, LIVE_UPTIMES = {}, {}

def save_state():
    """প্রতিবার স্টেট চেঞ্জ হলে ডিস্কে সেভ করবে (যেন রিস্টার্টে হারিয়ে না যায়)"""
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'downtimes': LIVE_DOWNTIMES, 'uptimes': LIVE_UPTIMES}, f, indent=4)
    except Exception as e:
        print(f"[-] State Save Error: {e}")

# ==============================================================================
# CORE MONITORING ENGINE
# ==============================================================================
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        print(f"[-] Telegram Send Error: {e}")

def check_network_state(ip, port=None):
    if not port:
        try:
            output = subprocess.run(["ping", "-c", "1", "-W", "1", ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return output.returncode == 0
        except:
            return False
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        try:
            s.connect((ip, int(port)))
            s.close()
            return True
        except:
            return False

def bg_monitoring_loop():
    global LIVE_DOWNTIMES, LIVE_UPTIMES, HISTORY_LOGS
    print(f"🚀 {WEB_NAME} Monitoring Engine Started...")
    
    while True:
        try:
            current_time = int(time.time())
            time_string = datetime.now().strftime("%I:%M:%S %p")
            TARGETS = load_targets()

            # ডাটাবেসে না থাকা টার্গেট মেমোরি থেকে ক্লিয়ার করা
            state_changed = False
            for name in list(LIVE_DOWNTIMES.keys()):
                if name not in TARGETS: 
                    del LIVE_DOWNTIMES[name]
                    state_changed = True
            for name in list(LIVE_UPTIMES.keys()):
                if name not in TARGETS: 
                    del LIVE_UPTIMES[name]
                    state_changed = True
            
            if state_changed: save_state() # ডিলিট হলে স্টেট আপডেট

            for name, target in TARGETS.items():
                ip = target['ip']
                port = target.get('port', None)
                
                is_online = check_network_state(ip, port)
                if not is_online:
                    time.sleep(1)
                    is_online = check_network_state(ip, port)
                    
                target_label = f"{ip}:{port}" if port else f"{ip} (Ping)"

                if not is_online:
                    if name in LIVE_UPTIMES:
                        del LIVE_UPTIMES[name]
                        save_state()

                    if name not in LIVE_DOWNTIMES:
                        LIVE_DOWNTIMES[name] = {
                            'ip': ip, 'port': port, 'down_since': current_time,
                            'down_time_str': time_string, 'last_alert_sent': current_time
                        }
                        save_state() # নতুন ডাউন স্টেট সেভ
                        send_telegram_message(f"🚨 *SERVER DOWN ALERT!*\n\n🖥️ *Host:* {name}\n🌐 *Target:* {target_label}\n⏰ *সময়:* {time_string}\n⚠️ *Status:* CRITICAL / OFFLINE")
                    else:
                        down_since = LIVE_DOWNTIMES[name]['down_since']
                        last_alert = LIVE_DOWNTIMES[name].get('last_alert_sent', down_since)
                        if current_time - last_alert >= DOWN_ALERT_INTERVAL:
                            down_duration = current_time - down_since
                            m, s = divmod(down_duration, 60)
                            duration_text = f"{m}m {s}s" if m > 0 else f"{s}s"
                            send_telegram_message(f"⚠️ *REMINDER: SERVER STILL DOWN!*\n\n🖥️ *Host:* {name}\n🌐 *Target:* {target_label}\n⏳ *মোট ডাউন টাইম:* {duration_text}")
                            LIVE_DOWNTIMES[name]['last_alert_sent'] = current_time
                            save_state() # রিমাইন্ডার টাইম আপডেট সেভ
                else:
                    if name not in LIVE_UPTIMES:
                        LIVE_UPTIMES[name] = current_time
                        save_state() # নতুন আপ স্টেট সেভ

                    if name in LIVE_DOWNTIMES:
                        down_since = LIVE_DOWNTIMES[name]['down_since']
                        total_down_time = current_time - down_since
                        m, s = divmod(total_down_time, 60)
                        res_text = f"{m} মিনিট {s} সেকেন্ড" if m > 0 else f"{s} সেকেন্ড"
                        
                        send_telegram_message(f"✅ *SERVER UP ALERT!*\n\n🖥️ *Host:* {name}\n🌐 *Target:* {target_label}\n🎉 *স্ট্যাটাস:* আপ হইছে\n⏳ *রিকভারি টাইম:* {res_text} পর অনলাইন")
                        
                        HISTORY_LOGS.append({
                            'name': name, 'ip': ip, 'port': port,
                            'timestamp': time_string, 'details': f"Recovered after {res_text}"
                        })
                        if len(HISTORY_LOGS) > 100: HISTORY_LOGS.pop(0)
                        save_history()
                        
                        del LIVE_DOWNTIMES[name]
                        save_state() # ডাউন থেকে আপে এসে স্টেট সেভ

        except Exception as loop_err:
            print(f"[-] Loop Warning: {loop_err}")
            
        time.sleep(10)

# ==============================================================================
# FLASK WEB SERVER API & AURORA INTERFACE
# ==============================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ web_name }} Aurora Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {
            background: linear-gradient(135deg, #020617 0%, #0f172a 50%, #1e1b4b 100%);
            min-height: 100vh; color: #f8fafc; font-family: 'Segoe UI', system-ui, sans-serif;
            position: relative; overflow-x: hidden;
        }
        body::before, body::after {
            content: ""; position: absolute; width: 600px; height: 600px; border-radius: 50%;
            filter: blur(150px); opacity: 0.15; z-index: -1; pointer-events: none;
        }
        body::before { top: -20%; left: -10%; background: #8b5cf6; }
        body::after { bottom: -10%; right: -10%; background: #06b6d4; }
        
        .glass-panel {
            background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 16px; box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        }
        .server-card {
            background: linear-gradient(180deg, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 0.4) 100%);
            border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); backdrop-filter: blur(10px);
        }
        .server-card:hover {
            transform: translateY(-4px); border-color: rgba(139, 92, 246, 0.4);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(139, 92, 246, 0.2);
        }
        @keyframes customPulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.1); }
        }
        .live-dot { animation: customPulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
    </style>
</head>
<body class="p-3 md:p-6 lg:p-8">
    <div class="max-w-[1600px] mx-auto space-y-6">
        <div class="glass-panel p-5 flex flex-col sm:flex-row justify-between items-center gap-4">
            <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 flex items-center justify-center border border-indigo-500/30 text-indigo-400 text-2xl">
                    <i class="fa-solid fa-network-wired"></i>
                </div>
                <div>
                    <h1 class="text-xl md:text-2xl font-bold tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-indigo-400 to-purple-400 uppercase">{{ web_name }}</h1>
                    <p class="text-[11px] md:text-xs text-slate-400 font-mono">Live Grid Engine • Crash-Proof Persistence Active</p>
                </div>
            </div>
            <button onclick="openModal()" class="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 rounded-xl font-bold text-xs md:text-sm transition-all shadow-[0_0_15px_rgba(79,70,229,0.3)] flex items-center gap-2 text-white">
                <i class="fa-solid fa-server"></i> ADD SERVER
            </button>
        </div>

        <div class="grid grid-cols-3 gap-4">
            <div class="glass-panel p-4 flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400"><i class="fa-solid fa-server"></i></div>
                <div><p class="text-[10px] text-slate-500 uppercase font-bold">Total Nodes</p><h2 id="stat-total" class="text-xl font-bold text-white">0</h2></div>
            </div>
            <div class="glass-panel p-4 flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400"><i class="fa-solid fa-circle-check"></i></div>
                <div><p class="text-[10px] text-slate-500 uppercase font-bold">Online</p><h2 id="stat-online" class="text-xl font-bold text-emerald-400">0</h2></div>
            </div>
            <div class="glass-panel p-4 flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center text-red-400"><i class="fa-solid fa-triangle-exclamation"></i></div>
                <div><p class="text-[10px] text-slate-500 uppercase font-bold">Offline</p><h2 id="stat-offline" class="text-xl font-bold text-red-400">0</h2></div>
            </div>
        </div>

        <div class="glass-panel p-5 md:p-6">
            <h2 class="text-sm md:text-base font-bold mb-5 flex items-center gap-2 text-slate-300 uppercase tracking-widest">
                <i class="fa-solid fa-border-all text-indigo-400"></i> Active Monitor Nodes
            </h2>
            <div id="hosts-grid" class="grid grid-cols-2 min-[480px]:grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8 gap-3 md:gap-4"></div>
        </div>

        <div class="glass-panel p-5">
            <h2 class="text-sm font-bold mb-4 flex items-center gap-2 text-slate-300 uppercase tracking-widest"><i class="fa-solid fa-clock-rotate-left text-cyan-400"></i> Recovery Intelligence</h2>
            <div id="history-box" class="max-h-[300px] overflow-y-auto space-y-2 pr-2"></div>
        </div>
    </div>

    <div id="hostModal" class="fixed inset-0 bg-slate-900/80 backdrop-blur-sm hidden flex items-center justify-center p-4 z-50">
        <div class="glass-panel w-full max-w-md p-6 relative border-indigo-500/20 shadow-2xl">
            <h3 id="modalTitle" class="text-lg font-bold mb-5 text-indigo-300 uppercase tracking-wider">Deploy Monitor Target</h3>
            <form id="hostForm" onsubmit="saveHost(event)">
                <input type="hidden" id="old_name">
                <div class="space-y-4">
                    <div>
                        <label class="block text-[10px] text-slate-400 mb-1 font-bold uppercase tracking-wider">Node Alias</label>
                        <input type="text" id="host_name" required class="w-full bg-slate-900/80 border border-slate-700/50 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 text-white font-medium">
                    </div>
                    <div>
                        <label class="block text-[10px] text-slate-400 mb-1 font-bold uppercase tracking-wider">IPv4 / FQDN</label>
                        <input type="text" id="host_ip" required class="w-full bg-slate-900/80 border border-slate-700/50 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 text-white font-mono">
                    </div>
                    <div>
                        <label class="block text-[10px] text-slate-400 mb-1 font-bold uppercase tracking-wider">TCP Port (Blank for Ping)</label>
                        <input type="number" id="host_port" class="w-full bg-slate-900/80 border border-slate-700/50 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 text-white font-mono">
                    </div>
                </div>
                <div class="mt-6 flex justify-end gap-3">
                    <button type="button" onclick="closeModal()" class="px-5 py-2.5 bg-slate-800/80 hover:bg-slate-700 rounded-xl text-xs font-bold uppercase tracking-wider transition-all">Abort</button>
                    <button type="submit" class="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 rounded-xl text-xs font-bold uppercase tracking-wider transition-all shadow-lg text-white">Initialize</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        let backendTimeOffset = 0;
        function formatDuration(seconds) {
            if (seconds < 60) return `${Math.floor(seconds)}s`;
            const m = Math.floor(seconds / 60);
            const s = Math.floor(seconds % 60);
            if (m < 60) return `${m}m ${s}s`;
            const h = Math.floor(m / 60);
            return `${h}h ${m % 60}m`;
        }

        function openModal(name='', ip='', port='') {
            document.getElementById('old_name').value = name;
            document.getElementById('host_name').value = name;
            document.getElementById('host_ip').value = ip;
            document.getElementById('host_port').value = port;
            document.getElementById('modalTitle').innerText = name ? 'EDIT MONITOR TARGET' : 'DEPLOY MONITOR TARGET';
            document.getElementById('hostModal').classList.remove('hidden');
        }
        function closeModal() { document.getElementById('hostModal').classList.add('hidden'); }

        function saveHost(e) {
            e.preventDefault();
            const name = document.getElementById('host_name').value.trim();
            const ip = document.getElementById('host_ip').value.trim();
            const port = document.getElementById('host_port').value.trim();
            const old_name = document.getElementById('old_name').value;

            fetch('/api/targets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, ip, port, old_name })
            }).then(res => res.json()).then(res => { if(res.status === 'success') { closeModal(); loadData(); } });
        }

        function deleteHost(name) {
            if(confirm(`WARNING: Remove Node [${name}]?`)) {
                fetch(`/api/targets?name=${encodeURIComponent(name)}`, { method: 'DELETE' })
                .then(res => res.json()).then(res => { if(res.status === 'success') loadData(); });
            }
        }

        function loadData() {
            fetch('/api/live_data')
            .then(res => res.json())
            .then(data => {
                const now = Math.floor(Date.now() / 1000);
                backendTimeOffset = now - data.server_time;
                
                let totalNodes = Object.keys(data.targets).length;
                let onlineNodes = 0;
                let offlineNodes = Object.keys(data.downtimes).length;
                
                const gridBody = document.getElementById('hosts-grid');
                gridBody.innerHTML = '';
                
                Object.keys(data.targets).forEach(name => {
                    const target = data.targets[name];
                    const downData = data.downtimes[name];
                    const upSince = data.uptimes[name];
                    const label = target.port ? `${target.ip}:${target.port}` : `${target.ip}`;
                    const protocol = target.port ? 'TCP' : 'ICMP';
                    
                    let statusHtml = '', borderClass = '', timerHtml = '';
                    const currentTimeServer = Math.floor(Date.now() / 1000) - backendTimeOffset;

                    if (downData) {
                        const downDuration = currentTimeServer - downData.down_since;
                        borderClass = 'border-red-500/40 bg-red-500/5';
                        statusHtml = `<div class="flex items-center gap-1.5 text-red-400 text-xs font-bold tracking-wider"><div class="w-2 h-2 rounded-full bg-red-500 live-dot"></div> OFFLINE</div>`;
                        timerHtml = `<div class="text-[11px] text-red-300/80 font-mono mt-1"><i class="fa-solid fa-caret-down text-red-500"></i> Down: ${formatDuration(downDuration)}</div>`;
                    } else if (upSince) {
                        onlineNodes++;
                        const upDuration = currentTimeServer - upSince;
                        borderClass = 'border-emerald-500/20 bg-emerald-500/5 hover:border-emerald-500/40';
                        statusHtml = `<div class="flex items-center gap-1.5 text-emerald-400 text-xs font-bold tracking-wider"><div class="w-2 h-2 rounded-full bg-emerald-400"></div> ONLINE</div>`;
                        timerHtml = `<div class="text-[11px] text-emerald-300/70 font-mono mt-1"><i class="fa-solid fa-caret-up text-emerald-500"></i> Alive: ${formatDuration(upDuration)}</div>`;
                    }

                    gridBody.innerHTML += `
                        <div class="server-card p-4 relative flex flex-col justify-between h-full min-h-[130px]">
                            <div class="absolute top-2 right-2 flex gap-1 opacity-20 hover:opacity-100 transition-opacity">
                                <button onclick="openModal('${name}', '${target.ip}', '${target.port || ''}')" class="text-cyan-400 p-1 rounded text-xs"><i class="fa-solid fa-pen"></i></button>
                                <button onclick="deleteHost('${name}')" class="text-red-400 p-1 rounded text-xs"><i class="fa-solid fa-xmark"></i></button>
                            </div>
                            <div>
                                <h3 class="font-bold text-xs sm:text-sm text-slate-200 truncate pr-8">${name}</h3>
                                <p class="text-[10px] text-indigo-300/70 font-mono truncate border-b border-white/5 pb-2 mb-2">${label} [${protocol}]</p>
                            </div>
                            <div class="mt-auto">${statusHtml}${timerHtml}</div>
                        </div>
                    `;
                });

                document.getElementById('stat-total').innerText = totalNodes;
                document.getElementById('stat-online').innerText = onlineNodes;
                document.getElementById('stat-offline').innerText = offlineNodes;

                const historyBox = document.getElementById('history-box');
                historyBox.innerHTML = '';
                if(data.history.length === 0) historyBox.innerHTML = `<p class="text-xs text-slate-600 text-center py-4">No events logged.</p>`;
                data.history.forEach(log => {
                    historyBox.innerHTML += `
                        <div class="px-4 py-2 bg-slate-900/40 rounded-lg border border-emerald-500/10 flex justify-between items-center text-xs">
                            <span class="font-bold text-slate-300">${log.name} <span class="text-[10px] px-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded ml-1">UP</span></span>
                            <div class="flex gap-3 text-slate-400 font-mono text-[11px]"><span>${log.details}</span><span class="text-slate-500">${log.timestamp}</span></div>
                        </div>
                    `;
                });
            });
        }
        setInterval(loadData, 2500);
        window.onload = loadData;
    </script>
</body>
</html>
"""

@app.route('/')
def index_route():
    return render_template_string(HTML_TEMPLATE, web_name=WEB_NAME)

@app.route('/api/live_data', methods=['GET'])
def get_live_data():
    return jsonify({
        "server_time": int(time.time()),  
        "targets": load_targets(),
        "downtimes": LIVE_DOWNTIMES,
        "uptimes": LIVE_UPTIMES,
        "history": list(reversed(HISTORY_LOGS))
    })

@app.route('/api/targets', methods=['POST'])
def save_or_update_target():
    data = request.json
    name = data.get('name')
    ip = data.get('ip')
    port = data.get('port')
    old_name = data.get('old_name')
    
    if not name or not ip: return jsonify({"status": "error", "message": "Missing Data"}), 400
    targets = load_targets()
    if old_name and old_name in targets: del targets[old_name]
    targets[name] = {"ip": ip, "port": int(port) if (port and str(port).strip() != '') else None}
    save_targets(targets)
    return jsonify({"status": "success"})

@app.route('/api/targets', methods=['DELETE'])
def delete_target():
    name = request.args.get('name')
    targets = load_targets()
    if name in targets:
        del targets[name]
        save_targets(targets)
        # টার্গেট ডিলিট হলে স্টেট থেকেও মুছে ফেলা হচ্ছে (লুপের কাজ এড়াতে এখানেও দিলাম)
        if name in LIVE_DOWNTIMES: del LIVE_DOWNTIMES[name]
        if name in LIVE_UPTIMES: del LIVE_UPTIMES[name]
        save_state()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404

if __name__ == "__main__":
    init_storage()
    monitor_thread = threading.Thread(target=bg_monitoring_loop, daemon=True)
    monitor_thread.start()
    print(f"🌍 Web Dashboard UI serving at http://localhost:{RUN_PORT}")
    app.run(host='0.0.0.0', port=RUN_PORT, debug=False, use_reloader=False)
