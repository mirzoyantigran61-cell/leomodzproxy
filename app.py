import os
import re
import json
import gzip
import hashlib
import base64
import requests
import string
import random
import threading
import time
from flask import Flask, request, Response, jsonify, session, redirect, url_for, render_template_string
from datetime import datetime, timedelta
from functools import wraps
import socket

app = Flask(__name__)
app.secret_key = os.urandom(32).hex()

# ==================== CONFIG ====================
TARGET_BASE_URL = "https://dl.bs.freefiremobile.com/live/ABHotUpdates/"
VER_PHP_URL = "https://version.ggwhitehawk.com/live/ver.php"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get('PORT', 10000))

ADMIN_USER = "LEOMDZ"
ADMIN_PASS = "LARYMYBABY"

# Data file paths
DATA_FILE = os.path.join(BASE_DIR, "crx_data.json")

user_configs = {}
registered_ips = {}
generated_keys = {}
key_expiry = {}

DEFAULT_CONFIG = {
    "HS_NECK": False,
    "HS_CHEST": False,
    "BYPASSV1": False,
    "BACKJUMPV1": False,
    "HIGH_SENSI": False,
    "ZIG_ZAG_MOVE": False
}

ANTI_BAN_OVERRIDES = {
    "CleanFFAntiState": {"var_type": "bool", "var_value": "true"},
    "FFAntihackDefenceLevel": {"var_type": "string", "var_value": "0"},
    "FFAntihackLightInitOnThread": {"var_type": "bool", "var_value": "false"},
    "FFAntihackEmulatorCheckDisbaledClientVariant": {"var_type": "string", "var_value": ""},
    "FFAntihackSDKDetailEncryptBySHA1": {"var_type": "bool", "var_value": "false"},
    "EnableFFAntihackInfoExtra": {"var_type": "bool", "var_value": "false"},
    "CheckHacker": {"var_type": "bool", "var_value": "false"},
    "DebugHack": {"var_type": "bool", "var_value": "false"},
    "TestModeEnabled": {"var_type": "bool", "var_value": "true"},
    "EarlyInitGGP": {"var_type": "bool", "var_value": "false"},
    "DisableGinInfoSend": {"var_type": "int", "var_value": "1"},
    "GinInfoBRAliveThreshold": {"var_type": "int", "var_value": "0"},
    "AntiHackResetSubgameInterval": {"var_type": "int", "var_value": "0"},
    "FFANTIHACKEXT_SPLIT_THRESHOLD": {"var_type": "int", "var_value": "0"},
    "NeedProcessAH": {"var_type": "bool", "var_value": "true"},
    "EnablePlatformCheck": {"var_type": "bool", "var_value": "false"},
    "EnableSupCheck": {"var_type": "bool", "var_value": "false"},
    "EnableMMKPlatformCheck": {"var_type": "bool", "var_value": "false"},
    "ShowHighFrameRateSetting": {"var_type": "bool", "var_value": "true"},
    "Real60FrameSwitch": {"var_type": "bool", "var_value": "true"},
    "IsAlbumScreenShotNeedAntiMod": {"var_type": "bool", "var_value": "false"},
    "EnableIceWallHacker": {"var_type": "bool", "var_value": "false"},
    "EnableIceWallHackerKill": {"var_type": "bool", "var_value": "false"},
    "EnableHipHackerKill": {"var_type": "bool", "var_value": "false"},
    "EnableSendHackStoreLog": {"var_type": "bool", "var_value": "false"},
    "SystemAlbumImageAntiModStrategy": {"var_type": "int", "var_value": "0"},
    "AlbumImageAntiModSecs": {"var_type": "int", "var_value": "0"},
    "AlbumImageAntiMod_iOS": {"var_type": "bool", "var_value": "false"},
    "ReportInstantiateJank": {"var_type": "bool", "var_value": "false"},
    "InstantiateJankTimeLimit": {"var_type": "int", "var_value": "0"},
    "DisableKillRefreshGetTime": {"var_type": "int", "var_value": "0"},
    "BugReportIntervalOnLowMemory": {"var_type": "int", "var_value": "0"},
    "EnableIngameQuickReport": {"var_type": "bool", "var_value": "false"},
    "EnableBugReportTime": {"var_type": "bool", "var_value": "false"},
    "EnableBugReportEarly": {"var_type": "int", "var_value": "0"},
    "BugReportMaxCountPerSession": {"var_type": "int", "var_value": "0"},
    "KickUserInMatchGame": {"var_type": "bool", "var_value": "false"},
    "Reportee_Damager_RecentlyMaxCnt": {"var_type": "int", "var_value": "0"},
    "Reportee_Killer_RecentlyMaxCnt": {"var_type": "int", "var_value": "0"},
    "BlocklistMaxNum": {"var_type": "int", "var_value": "0"},
    "EnableCheckFileStates": {"var_type": "bool", "var_value": "false"},
    "OptionalDeepFileCheck": {"var_type": "bool", "var_value": "false"},
    "EnableFileCacherReadOpt": {"var_type": "bool", "var_value": "false"},
    "EnableFileCacherReadOpt_2022": {"var_type": "bool", "var_value": "false"},
    "EnableGGPDecryptFailureProtection": {"var_type": "bool", "var_value": "false"}
}

BACKJUMPV1_OVERRIDES = {
    "EnableAccelerationOnFalling": {"var_type": "bool", "var_value": "false"},
    "CanJumpFallingRunFast": {"var_type": "bool", "var_value": "false"},
    "CanCreepRunFast": {"var_type": "bool", "var_value": "false"},
    "CanCrouchingRunFast": {"var_type": "bool", "var_value": "false"},
    "StropFallingResetSpeed": {"var_type": "bool", "var_value": "true"}
}

HIGH_SENSI_OVERRIDES = {
    "SensitivityMaxSetting": {"var_type": "float", "var_value": "9.0"},
    "Sensitivity1PMaxSetting": {"var_type": "float", "var_value": "9.0"},
    "X1ScopeMaxSetting": {"var_type": "float", "var_value": "9.0"},
    "X2ScopeMaxSetting": {"var_type": "float", "var_value": "9.0"},
    "X4ScopeMaxSetting": {"var_type": "float", "var_value": "9.0"},
    "X8ScopeMaxSetting": {"var_type": "float", "var_value": "9.0"},
    "FreeLookMaxSetting": {"var_type": "float", "var_value": "9.0"}
}

ZIG_ZAG_MOVE_OVERRIDES = {
    "FreeMoveAngularSpeed": {"var_type": "float", "var_value": "9999.0"},
    "FreeMoveAngularSpeedStand": {"var_type": "float", "var_value": "9999.0"},
    "FreeMoveAngularSpeedCrouch": {"var_type": "float", "var_value": "9999.0"},
    "FreeMoveAngularSpeedCreep": {"var_type": "float", "var_value": "9999.0"},
    "ResetRotationSpeed": {"var_type": "float", "var_value": "9999.0"},
}

# ==================== KEEP ALIVE ====================
def keep_alive():
    while True:
        try:
            requests.get(f"http://localhost:{PORT}/api/ping", timeout=5)
            print(f"[{datetime.now()}] Keep-alive ping sent")
        except:
            pass
        time.sleep(240)

@app.route('/api/ping')
def ping():
    return jsonify({'status': 'alive', 'time': datetime.now().isoformat()})

threading.Thread(target=keep_alive, daemon=True).start()

# ==================== DATA PERSISTENCE ====================

def save_data():
    data = {
        'user_configs': user_configs,
        'registered_ips': registered_ips,
        'generated_keys': generated_keys,
        'key_expiry': {ip: exp.isoformat() for ip, exp in key_expiry.items()}
    }
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")

def load_data():
    global user_configs, registered_ips, generated_keys, key_expiry
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            user_configs = data.get('user_configs', {})
            registered_ips = data.get('registered_ips', {})
            generated_keys = data.get('generated_keys', {})
            key_expiry = {}
            for ip, exp_str in data.get('key_expiry', {}).items():
                try:
                    key_expiry[ip] = datetime.fromisoformat(exp_str)
                except:
                    pass
            print(f"Loaded data: {len(generated_keys)} keys, {len(registered_ips)} IPs")
        except Exception as e:
            print(f"Error loading data: {e}")
            user_configs = {}
            registered_ips = {}
            generated_keys = {}
            key_expiry = {}
    else:
        print("No existing data file found. Starting fresh.")
        user_configs = {}
        registered_ips = {}
        generated_keys = {}
        key_expiry = {}
        save_data()

# Também carrega o estado quando a aplicação é iniciada por Gunicorn/Railway.
load_data()

# ========================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def get_user_config(client_ip):
    if client_ip not in user_configs:
        user_configs[client_ip] = DEFAULT_CONFIG.copy()
        save_data()
    return user_configs[client_ip]

def normalize_key(value):
    return re.sub(r"\s+", "", str(value or "")).upper()

def generate_key(prefix="LEO-MDZ-PROXY"):
    prefix = normalize_key(prefix) or "LEO-MDZ-PROXY"
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"{prefix}-{random_part}"

def get_overrides_for_ip(client_ip):
    config = get_user_config(client_ip)
    overrides = {}
    if config.get("BYPASSV1", False):
        overrides.update(ANTI_BAN_OVERRIDES)
    if config.get("BACKJUMPV1", False):
        overrides.update(BACKJUMPV1_OVERRIDES)
    if config.get("HIGH_SENSI", False):
        overrides.update(HIGH_SENSI_OVERRIDES)
    if config.get("ZIG_ZAG_MOVE", False):
        overrides.update(ZIG_ZAG_MOVE_OVERRIDES)
    return overrides

def sha1_b64(data):
    return base64.b64encode(hashlib.sha1(data).digest()).decode()

def patch_fileinfo(original_text, config):
    if not config.get("HS_NECK", False) and not config.get("HS_CHEST", False):
        return original_text
    lines = original_text.splitlines()
    new_lines = []
    cache_res_file = os.path.join(BASE_DIR, "cache_res")
    cache_res2_file = os.path.join(BASE_DIR, "cache_res2")
    for line in lines:
        if line.startswith("cache_res,"):
            if config.get("HS_NECK", False) and os.path.exists(cache_res_file):
                try:
                    with open(cache_res_file, "rb") as f:
                        gz_data = f.read()
                    raw_data = gzip.decompress(gz_data)
                    new_line = f"cache_res,{sha1_b64(raw_data)},{len(raw_data)},0,{sha1_b64(gz_data)},{len(gz_data)},True,0"
                    new_lines.append(new_line)
                except:
                    new_lines.append(line)
            elif config.get("HS_CHEST", False) and os.path.exists(cache_res2_file):
                try:
                    with open(cache_res2_file, "rb") as f:
                        gz_data = f.read()
                    raw_data = gzip.decompress(gz_data)
                    new_line = f"cache_res,{sha1_b64(raw_data)},{len(raw_data)},0,{sha1_b64(gz_data)},{len(gz_data)},True,0"
                    new_lines.append(new_line)
                except:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    return "\n".join(new_lines)

def modify_ver_response(response_text, client_ip):
    try:
        data = json.loads(response_text)
        cdn_url = f"https://{request.host}/cdn/live/ABHotUpdates/"
        data["cdn_url"] = cdn_url
        data["backup_cdn_url"] = cdn_url
        data["abhotupdate_cdn_url"] = cdn_url
        overrides = get_overrides_for_ip(client_ip)
        if overrides:
            gamevar = data.get("gamevar", "")
            for var_name, override in overrides.items():
                gamevar += f"\n{var_name},{var_name},{override['var_type']},{override['var_value']},,"
            data["gamevar"] = gamevar
        return json.dumps(data)
    except:
        return response_text

# ==================== ROUTES ====================

@app.route('/Po7eO', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template_string(LOGIN_PAGE, error="CREDENCIAIS INVÁLIDAS")
    return render_template_string(LOGIN_PAGE, error=None)

@app.route('/admin')
def admin_index():
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    return render_template_string(ADMIN_DASHBOARD,
                                 keys=generated_keys,
                                 ips=registered_ips,
                                 key_expiry=key_expiry)

@app.route('/admin/generate', methods=['POST'])
@login_required
def generate_new_key():
    data = request.get_json(silent=True) or {}
    key_prefix = normalize_key(data.get('prefix', 'LEO-MDZ-PROXY')) or 'LEO-MDZ-PROXY'
    ip_limit = max(1, int(data.get('limit', 1)))
    days_valid = max(1, int(data.get('days', 7)))
    new_key = generate_key(key_prefix)
    generated_keys[new_key] = {
        'prefix': key_prefix,
        'limit': ip_limit,
        'days': days_valid,
        'created': datetime.now().isoformat(),
        'used_ips': []
    }
    save_data()
    return jsonify({'key': new_key, 'limit': ip_limit, 'days': days_valid})

@app.route('/admin/revoke', methods=['POST'])
@login_required
def revoke_key():
    data = request.get_json(silent=True) or {}
    key = normalize_key(data.get('key', ''))
    if key in generated_keys:
        for ip in generated_keys[key]['used_ips']:
            if ip in registered_ips:
                del registered_ips[ip]
            if ip in key_expiry:
                del key_expiry[ip]
        del generated_keys[key]
        save_data()
        return jsonify({'success': True})
    return jsonify({'error': 'KEY NÃO ENCONTRADA'}), 400

@app.route('/admin/logout')
@login_required
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/verify', methods=['POST'])
def verify_key():
    client_ip = get_client_ip()
    data = request.get_json(silent=True) or {}
    key = normalize_key(data.get('key', ''))

    if client_ip in registered_ips:
        session['unlocked'] = True
        return jsonify({'success': True, 'message': 'JÁ REGISTRADO'})

    if key not in generated_keys:
        # Recarrega o estado caso a key tenha sido criada por outro worker/processo.
        load_data()
    if key not in generated_keys:
        return jsonify({'success': False, 'message': 'KEY INVÁLIDA'}), 401

    key_data = generated_keys[key]
    if len(key_data['used_ips']) >= key_data['limit']:
        return jsonify({'success': False, 'message': 'LIMITE DA KEY ATINGIDO'}), 401

    registered_ips[client_ip] = key
    key_data['used_ips'].append(client_ip)
    expiry_date = datetime.now() + timedelta(days=key_data['days'])
    key_expiry[client_ip] = expiry_date
    session['unlocked'] = True
    save_data()

    return jsonify({
        'success': True,
        'message': 'KEY VERIFICADA COM SUCESSO',
        'expires': expiry_date.isoformat()
    })

# ============ PROXY ROUTES - NO KEY REQUIRED ============

@app.route('/ver.php', methods=['GET'])
@app.route('/live/ver.php', methods=['GET'])
def handle_ver_php():
    client_ip = get_client_ip()
    params = dict(request.args)
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length", "connection", "accept-encoding")}
    try:
        response = requests.get(VER_PHP_URL, params=params, headers=headers, timeout=60)
        modified = modify_ver_response(response.text, client_ip)
        return Response(modified, status=200, content_type="application/json")
    except Exception as e:
        return Response(f"Error: {e}", status=502)

@app.route('/cdn/live/ABHotUpdates/', methods=['GET'])
@app.route('/cdn/live/ABHotUpdates/<path:path>', methods=['GET'])
def handle_cdn(path=""):
    client_ip = get_client_ip()
    config = get_user_config(client_ip)
    cache_file = os.path.join(BASE_DIR, "cache_res")
    cache_res2_file = os.path.join(BASE_DIR, "cache_res2")
    assetindexer_file = os.path.join(BASE_DIR, "cache_res3")

    if re.compile(r"android_astc/1\.123\.[^/]*/gameassetbundles/avatar/assetindexer").match(path) and os.path.exists(assetindexer_file):
        with open(assetindexer_file, "rb") as f:
            return Response(f.read(), status=200, content_type="application/octet-stream")

    if "cache_res" in path:
        if config.get("HS_NECK", False) and os.path.exists(cache_file):
            with open(cache_file, "rb") as f:
                return Response(f.read(), status=200, content_type="application/octet-stream")
        elif config.get("HS_CHEST", False) and os.path.exists(cache_res2_file):
            with open(cache_res2_file, "rb") as f:
                return Response(f.read(), status=200, content_type="application/octet-stream")

    if "fileinfo" in path:
        target_url = TARGET_BASE_URL + path
        try:
            resp = requests.get(target_url, timeout=60)
            if config.get("HS_NECK", False) or config.get("HS_CHEST", False):
                patched = patch_fileinfo(resp.text, config)
                return Response(patched.encode(), status=200, content_type="binary/octet-stream")
            return Response(resp.content, status=200, content_type="binary/octet-stream")
        except Exception as e:
            return Response(f"Error: {e}", status=502)

    target_url = TARGET_BASE_URL + path
    try:
        resp = requests.get(target_url, timeout=60)
        return Response(resp.content, status=resp.status_code, content_type=resp.headers.get('content-type', 'application/octet-stream'))
    except Exception as e:
        return Response(f"Error: {e}", status=502)

# ============ API ROUTES ============

@app.route('/api/status', methods=['GET'])
def api_status():
    client_ip = get_client_ip()
    config = get_user_config(client_ip)
    return jsonify({
        "ip": client_ip,
        "config": config,
        "key": registered_ips.get(client_ip),
        "expires": key_expiry.get(client_ip, "").isoformat() if client_ip in key_expiry else None
    })

@app.route('/api/toggle', methods=['POST'])
def api_toggle():
    client_ip = get_client_ip()
    data = request.json
    feature = data.get('feature')
    value = data.get('value')

    feature_map = {
        'hs_neck': 'HS_NECK',
        'hs_chest': 'HS_CHEST',
        'backjump_v1': 'BACKJUMPV1',
        'high_sensi': 'HIGH_SENSI',
        'zig_zag_move': 'ZIG_ZAG_MOVE'
    }

    config_key = feature_map.get(feature)
    if not config_key:
        return jsonify({"error": "RECURSO INVÁLIDO"}), 400

    config = get_user_config(client_ip)
    config[config_key] = value
    save_data()

    return jsonify({
        "success": True,
        "ip": client_ip,
        "feature": feature,
        "value": value
    })

@app.route('/api/ip/check', methods=['GET'])
def api_ip_check():
    client_ip = get_client_ip()
    return jsonify({
        "ip": client_ip,
        "key": registered_ips.get(client_ip),
        "is_authorized": client_ip in registered_ips,
        "expires": key_expiry.get(client_ip, "").isoformat() if client_ip in key_expiry else None
    })

@app.route('/')
def landing():
    if session.get('unlocked'):
        return redirect(url_for('dashboard'))
    return render_template_string(KEY_PAGE, error=None)

@app.route('/dashboard')
def dashboard():
    if not session.get('unlocked'):
        return redirect(url_for('landing'))
    return render_template_string(DASHBOARD_PAGE)

@app.route('/unlock', methods=['POST'])
def unlock():
    return jsonify({'success': False, 'message': 'INFORME UMA KEY VÁLIDA NA PÁGINA DE ACESSO'}), 400

# ==================== HTML TEMPLATES ====================

LOGIN_PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LARY MODZ PROXY · ADMIN</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"><style>
:root{--bg:#0b0a0f;--panel:#14121a;--line:#2e2535;--muted:#a08fa8;--ink:#f8f5fb;--accent:#ff2d95;--accent2:#ff5eb3}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at 80% 10%,#3a1530 0,transparent 32%),var(--bg);color:var(--ink);font-family:Inter,Arial,sans-serif;display:grid;place-items:center;padding:24px}.login-shell{width:min(980px,100%);min-height:560px;display:grid;grid-template-columns:1.05fr .95fr;border:1px solid var(--line);background:rgba(20,18,26,.94);box-shadow:0 32px 90px #0008}.manifest{padding:58px;display:flex;flex-direction:column;justify-content:space-between;border-right:1px solid var(--line);background:linear-gradient(150deg,#24151f,#121018 55%)}.label{font:700 10px monospace;letter-spacing:3px;color:var(--accent);text-transform:uppercase}.mark{display:flex;align-items:center;gap:12px;font-weight:900;letter-spacing:3px;font-size:20px}.mark i{display:grid;place-items:center;width:42px;height:42px;background:var(--accent);color:#1a0a12;border-radius:8px}.manifest h1{font-size:58px;line-height:.95;letter-spacing:-4px;margin:0;max-width:400px}.manifest h1 span{color:var(--accent)}.manifest p{color:var(--muted);line-height:1.7;max-width:360px}.serial{font:11px monospace;color:#7a6578;letter-spacing:2px}.form-panel{padding:58px 52px;display:flex;flex-direction:column;justify-content:center}.form-panel h2{font-size:30px;margin:10px 0 8px}.sub{color:var(--muted);margin:0 0 30px}.field{margin:18px 0}.field label{display:block;color:#b9a8c0;font:700 10px monospace;letter-spacing:2px;text-transform:uppercase;margin-bottom:9px}.field input{width:100%;padding:15px 14px;background:#0d0b12;border:1px solid var(--line);color:var(--ink);outline:none;font:inherit}.field input:focus{border-color:var(--accent)}button{width:100%;padding:15px;border:0;background:var(--accent);color:#1a0a12;font-weight:900;letter-spacing:1px;text-transform:uppercase;cursor:pointer}button:hover{background:#ff5eb3}.error{margin-top:14px;color:#ff8e8e;font:700 11px monospace}.foot{margin-top:34px;color:#6b5a70;font:10px monospace;letter-spacing:1px}@media(max-width:720px){body{padding:12px;display:block}.login-shell{grid-template-columns:1fr;min-height:0;border:0}.manifest{padding:30px 22px;min-height:245px}.manifest h1{font-size:40px;letter-spacing:-3px}.manifest p{font-size:13px}.form-panel{padding:30px 22px}.field input{min-height:52px}.form-panel button{min-height:52px}}
/* visual refresh */ body{background-image:radial-gradient(circle at 82% 8%,#3b1735 0,transparent 32%),radial-gradient(circle at 12% 90%,#152744 0,transparent 28%)} .login-shell,.access{border-radius:28px;overflow:hidden;border-color:#3a4b68;box-shadow:0 30px 100px #0009} .card,.control,.ip{border-radius:18px;box-shadow:0 14px 34px #0003} .card:hover,.control:hover{border-color:#ff2d9580} .field input{border-radius:12px;background:#0b101a} .field input:focus{box-shadow:0 0 0 4px #ff2d9522} button,.access-btn{border-radius:12px;background:linear-gradient(135deg,#ff2d95,#ff78bc);box-shadow:0 10px 24px #ff2d9525;transition:.2s} button:hover,.access-btn:hover{transform:translateY(-1px);filter:brightness(1.08)} .badge{border-radius:8px;border:1px solid #ff2d9544} .profile,.status{border-radius:999px} .nav-links a,.side nav div{border-radius:12px} .nav-links a:hover,.nav-links a.active,.side nav div:hover,.side nav div.active{background:#ff2d951c;border-color:#ff2d9555;transform:translateX(3px)} .stat{border-radius:14px;background:#0f1624} .generated{border-radius:10px;background:#ff2d950d;padding:10px}
</style></head><body><main class="login-shell"><section class="manifest"><div><div class="mark"><i class="fa-solid fa-bolt"></i> LARY MODZ PROXY</div><div style="margin-top:64px" class="label">PRIVATE CONTROL SYSTEM</div><h1>Enter the<br><span>operator</span><br>console.</h1><p>Área administrativa para controle de acessos, keys e sessões ativas.</p></div><div class="serial">NODE / 07 · AUTH REQUIRED</div></section><section class="form-panel"><div class="label">ADMIN AUTHENTICATION</div><h2>Entrar no painel</h2><p class="sub">Informe suas credenciais para continuar.</p><form method="POST" autocomplete="on"><div class="field"><label for="username">Usuário</label><input id="username" name="username" required autocomplete="username" placeholder="seu usuário"></div><div class="field"><label for="password">Senha</label><input id="password" type="password" name="password" required autocomplete="current-password" placeholder="sua senha"></div><button type="submit">Acessar console <i class="fa-solid fa-arrow-right"></i></button>{% if error %}<div class="error">{{ error }}</div>{% endif %}</form><div class="foot"><i class="fa-solid fa-shield-halved"></i> SESSÃO PROTEGIDA · LARY MODZ PROXY</div></section></main></body></html>"""

ADMIN_DASHBOARD = """<!doctype html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LARY MODZ PROXY · ADMIN</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"><style>
:root{--bg:#0b0a0f;--panel:#16131c;--line:#2e2535;--muted:#a08fa8;--ink:#f5f3f7;--lime:#ff2d95}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,Arial,sans-serif}.admin{min-height:100vh;display:grid;grid-template-columns:230px 1fr}.nav{padding:28px 20px;background:#121018;border-right:1px solid var(--line)}.brand{font-weight:900;letter-spacing:2px}.brand span{color:var(--lime)}.nav-links{margin-top:58px;display:grid;gap:7px}.nav-links a{padding:13px;color:var(--muted);text-decoration:none;font:700 10px monospace;letter-spacing:1px;text-transform:uppercase}.nav-links a.active,.nav-links a:hover{background:var(--lime);color:#1a0a12}.logout{display:block;margin-top:60px;color:#ff9a9a;text-decoration:none;font:700 10px monospace;letter-spacing:1px}.workspace{padding:34px 42px;max-width:1250px;width:100%}.bar{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid var(--line);padding-bottom:28px}.bar h1{font-size:38px;letter-spacing:-2px;margin:8px 0 0}.eyebrow{font:700 10px monospace;letter-spacing:2px;color:var(--lime)}.profile{color:var(--muted);font:11px monospace}.cards{display:grid;grid-template-columns:1.2fr .8fr;gap:16px;margin-top:24px}.card{background:var(--panel);border:1px solid var(--line);padding:24px}.card h2{font-size:14px;margin:0 0 20px}.field{margin:14px 0}.field label{display:block;color:var(--muted);font:700 10px monospace;letter-spacing:1px;margin-bottom:7px}.field input{width:100%;padding:13px;background:#0d0b12;border:1px solid var(--line);color:#fff;font:inherit;outline:none}.field input:focus{border-color:var(--lime)}button{padding:13px 18px;border:0;background:var(--lime);color:#1a0a12;font-weight:900;letter-spacing:1px;cursor:pointer}.stats{display:grid;grid-template-columns:1fr 1fr;gap:10px}.stat{padding:18px;background:#121018;border:1px solid var(--line)}.stat small{display:block;color:var(--muted);font:700 9px monospace;letter-spacing:1px}.stat strong{display:block;font-size:32px;margin-top:12px}.wide{margin-top:16px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:12px}th,td{text-align:left;padding:14px 10px;border-bottom:1px solid var(--line)}th{color:var(--muted);font:700 9px monospace;letter-spacing:1px}td{color:#c8b9d0}.badge{padding:5px 8px;background:#3a1a2e;color:var(--lime);font:700 10px monospace}.danger{background:#492326;color:#ffaaaa;font-size:10px;padding:8px 10px}.generated{margin-top:15px;color:var(--lime);font:800 16px monospace;word-break:break-all}@media(max-width:780px){.admin{grid-template-columns:1fr}.nav{border-right:0;border-bottom:1px solid var(--line);padding:18px 14px}.nav-links{margin-top:20px;grid-template-columns:repeat(3,1fr);gap:5px}.nav-links a{min-height:44px;display:flex;align-items:center;justify-content:center;padding:8px 4px;text-align:center;font-size:9px}.logout{margin-top:18px;padding:10px 0}.workspace{padding:22px 14px}.cards{grid-template-columns:1fr}.bar{align-items:center}.bar h1{font-size:29px}.profile{font-size:9px}.card{padding:18px 15px}.field input{min-height:50px}.card button{min-height:48px}.table-wrap{margin:0 -4px;overflow-x:auto}table{min-width:560px}}
/* visual refresh */ body{background-image:radial-gradient(circle at 82% 8%,#3b1735 0,transparent 32%),radial-gradient(circle at 12% 90%,#152744 0,transparent 28%)} .login-shell,.access{border-radius:28px;overflow:hidden;border-color:#3a4b68;box-shadow:0 30px 100px #0009} .card,.control,.ip{border-radius:18px;box-shadow:0 14px 34px #0003} .card:hover,.control:hover{border-color:#ff2d9580} .field input{border-radius:12px;background:#0b101a} .field input:focus{box-shadow:0 0 0 4px #ff2d9522} button,.access-btn{border-radius:12px;background:linear-gradient(135deg,#ff2d95,#ff78bc);box-shadow:0 10px 24px #ff2d9525;transition:.2s} button:hover,.access-btn:hover{transform:translateY(-1px);filter:brightness(1.08)} .badge{border-radius:8px;border:1px solid #ff2d9544} .profile,.status{border-radius:999px} .nav-links a,.side nav div{border-radius:12px} .nav-links a:hover,.nav-links a.active,.side nav div:hover,.side nav div.active{background:#ff2d951c;border-color:#ff2d9555;transform:translateX(3px)} .stat{border-radius:14px;background:#0f1624} .generated{border-radius:10px;background:#ff2d950d;padding:10px}
</style></head><body><main class="admin"><aside class="nav"><div class="brand"><i class="fa-solid fa-bolt"></i> LARY MODZ<span>PROXY</span></div><div class="nav-links"><a class="active" href="/admin/dashboard"><i class="fa-solid fa-chart-simple"></i> Overview</a><a href="#keys"><i class="fa-solid fa-key"></i> Keys</a><a href="#ips"><i class="fa-solid fa-users"></i> Sessions</a></div><a class="logout" href="/admin/logout"><i class="fa-solid fa-arrow-right-from-bracket"></i> Encerrar sessão</a></aside><section class="workspace"><header class="bar"><div><div class="eyebrow">ADMIN CONTROL / 01</div><h1>Operations</h1></div><div class="profile"><i class="fa-solid fa-circle" style="color:#ff2d95"></i> ADMIN ONLINE</div></header><div class="cards"><section class="card"><h2><i class="fa-solid fa-key"></i> Emitir nova key</h2><div class="field"><label>Prefixo</label><input id="keyPrefix" value="LEO-MDZ-PROXY"></div><div class="field"><label>Limite de IPs</label><input id="ipLimit" type="number" value="1" min="1"></div><div class="field"><label>Validade em dias</label><input id="keyDays" type="number" value="7" min="1"></div><button onclick="generateKey()">Gerar key <i class="fa-solid fa-arrow-right"></i></button><div id="generatedKey" class="generated"></div></section><section class="card"><h2><i class="fa-solid fa-chart-line"></i> Resumo</h2><div class="stats"><div class="stat"><small>TOTAL KEYS</small><strong>{{ keys|length }}</strong></div><div class="stat"><small>IPS ATIVOS</small><strong>{{ ips|length }}</strong></div></div></section></div><section id="keys" class="card wide"><h2>Keys emitidas</h2><div class="table-wrap"><table><thead><tr><th>KEY</th><th>LIMIT</th><th>USOS</th><th>VALIDADE</th><th>AÇÃO</th></tr></thead><tbody>{% for key, data in keys.items() %}<tr><td><span class="badge">{{ key }}</span></td><td>{{ data.limit }}</td><td>{{ data.used_ips|length }}</td><td>{{ data.days }} dias</td><td><button class="danger" onclick="revokeKey('{{ key }}')">REVOGAR</button></td></tr>{% else %}<tr><td colspan="5">Nenhuma key emitida.</td></tr>{% endfor %}</tbody></table></div></section><section id="ips" class="card wide"><h2>Sessões autorizadas</h2><div class="table-wrap"><table><thead><tr><th>IP</th><th>KEY</th><th>EXPIRA</th><th>STATUS</th></tr></thead><tbody>{% for ip, key in ips.items() %}<tr><td>{{ ip }}</td><td><span class="badge">{{ key }}</span></td><td>{% if key_expiry[ip] %}{{ key_expiry[ip].strftime('%d/%m/%Y') }}{% else %}-{% endif %}</td><td>ATIVO</td></tr>{% else %}<tr><td colspan="4">Nenhuma sessão autorizada.</td></tr>{% endfor %}</tbody></table></div></section></section></main><script>async function generateKey(){const o=document.getElementById('generatedKey');o.textContent='GERANDO...';try{const r=await fetch('/admin/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prefix:document.getElementById('keyPrefix').value.trim()||'LEO-MDZ-PROXY',limit:Math.max(1,parseInt(document.getElementById('ipLimit').value)||1),days:Math.max(1,parseInt(document.getElementById('keyDays').value)||7)})});const d=await r.json();if(!r.ok||!d.key)throw Error(d.error||'Erro');o.textContent='✓ '+d.key;setTimeout(()=>location.reload(),1200)}catch(e){o.textContent='ERRO: '+e.message}}async function revokeKey(key){if(!confirm('Revogar '+key+'?'))return;const r=await fetch('/admin/revoke',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})});const d=await r.json();if(d.success)location.reload();else alert(d.error||'Erro ao revogar')}</script></body></html>"""

KEY_PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LARY MODZ PROXY · ACCESS</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"><style>
:root{--bg:#0a080d;--ink:#f5f3f7;--muted:#a08fa8;--lime:#ff2d95;--line:#2e2535}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:var(--bg);color:var(--ink);font-family:Inter,Arial,sans-serif;display:grid;place-items:center;padding:24px}.access{width:min(920px,100%);display:grid;grid-template-columns:1.1fr .9fr;background:#14121a;border:1px solid var(--line);box-shadow:0 28px 80px #0009}.visual{min-height:560px;padding:46px;background:#100e14;color:#fff;display:flex;flex-direction:column;justify-content:space-between;position:relative;overflow:hidden}.visual:after{content:"";position:absolute;width:280px;height:280px;border:1px solid #ff2d9555;border-radius:50%;right:-90px;bottom:-100px;box-shadow:0 0 0 34px #ff2d9512,0 0 0 68px #ff2d9508}.brand{font-weight:900;letter-spacing:3px}.brand b{color:var(--lime)}.visual h1{position:relative;z-index:1;font-size:64px;line-height:.9;letter-spacing:-5px;margin:0;max-width:390px}.visual h1 span{color:var(--lime)}.visual p{position:relative;z-index:1;color:#b9a8c0;line-height:1.7;max-width:330px}.code{font:11px monospace;color:#7a6578;letter-spacing:2px}.access-form{padding:58px 48px;display:flex;flex-direction:column;justify-content:center;background:#14121a}.eyebrow{font:700 10px monospace;letter-spacing:2px;color:#c2186b}.access-form h2{font-size:32px;margin:12px 0 8px}.access-form .sub{color:var(--muted);margin:0 0 28px}.field{margin:18px 0}.field label{display:block;font:700 10px monospace;letter-spacing:2px;color:var(--muted);margin-bottom:8px}.field input{width:100%;padding:16px;border:1px solid var(--line);background:#0d0b12;color:var(--ink);font:inherit;outline:none}.field input:focus{border-color:#ff5eb3;box-shadow:0 0 0 4px #ff2d9533}.access-btn{width:100%;padding:16px;background:#0d0b12;color:#ffffff;border:1px solid #3d2e42;font-weight:900;letter-spacing:1px;cursor:pointer;box-shadow:0 8px 20px #0006}.access-btn:disabled{opacity:.65;cursor:wait}.access-btn:hover{background:#24151f;border-color:#ff2d95}.hint{margin-top:18px;color:#8a7a90;font:11px monospace;line-height:1.6}.foot{margin-top:38px;color:#a08fa8;font:10px monospace;letter-spacing:1px}#keyError{color:#b74747;margin-top:14px;font:700 11px monospace}@media(max-width:720px){body{padding:12px;display:block}.access{grid-template-columns:1fr;width:100%;box-shadow:0 18px 45px #20242d22}.visual{min-height:245px;padding:28px 22px}.visual h1{font-size:42px;letter-spacing:-3px}.visual p{font-size:13px}.access-form{padding:30px 22px}.field input{min-height:52px}.access-btn{min-height:52px}}
/* visual refresh */ body{background-image:radial-gradient(circle at 82% 8%,#3b1735 0,transparent 32%),radial-gradient(circle at 12% 90%,#152744 0,transparent 28%)} .login-shell,.access{border-radius:28px;overflow:hidden;border-color:#3a4b68;box-shadow:0 30px 100px #0009} .card,.control,.ip{border-radius:18px;box-shadow:0 14px 34px #0003} .card:hover,.control:hover{border-color:#ff2d9580} .field input{border-radius:12px;background:#0b101a} .field input:focus{box-shadow:0 0 0 4px #ff2d9522} button,.access-btn{border-radius:12px;background:linear-gradient(135deg,#ff2d95,#ff78bc);box-shadow:0 10px 24px #ff2d9525;transition:.2s} button:hover,.access-btn:hover{transform:translateY(-1px);filter:brightness(1.08)} .badge{border-radius:8px;border:1px solid #ff2d9544} .profile,.status{border-radius:999px} .nav-links a,.side nav div{border-radius:12px} .nav-links a:hover,.nav-links a.active,.side nav div:hover,.side nav div.active{background:#ff2d951c;border-color:#ff2d9555;transform:translateX(3px)} .stat{border-radius:14px;background:#0f1624} .generated{border-radius:10px;background:#ff2d950d;padding:10px}
</style></head><body><main class="access"><section class="visual"><div class="brand"><i class="fa-solid fa-key"></i> LARY MODZ<b>PROXY</b></div><div><div class="eyebrow" style="color:var(--lime)">ACCESS GATE / 01</div><h1>One key.<br><span>Full access.</span></h1><p>Use a key issued by the administrator to open your control dashboard.</p></div><div class="code">SECURE CHANNEL · READY</div></section><section class="access-form"><div class="eyebrow">USER ACCESS</div><h2>Validar acesso</h2><p class="sub">Cole sua key para continuar.</p><form id="keyForm"><div class="field"><label for="accessKey">Access key</label><input id="accessKey" required spellcheck="false" placeholder="LEO-MDZ-PROXY-0000"></div><button class="access-btn" type="submit">Abrir dashboard <i class="fa-solid fa-arrow-up-right-from-square"></i></button><div id="keyError" role="alert"></div></form><div class="hint">Keys são geradas exclusivamente pelo administrador.</div><div class="foot"><i class="fa-solid fa-lock"></i> ENCRYPTED SESSION</div></section></main><script>document.getElementById('keyForm').addEventListener('submit',async e=>{e.preventDefault();const b=e.target.querySelector('button'),m=document.getElementById('keyError');b.disabled=true;m.textContent='VALIDANDO KEY...';try{const r=await fetch('/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:document.getElementById('accessKey').value.trim()})});const d=await r.json();if(!r.ok||!d.success)throw Error(d.message||'KEY INVÁLIDA');location.href='/dashboard'}catch(err){m.textContent=err.message;b.disabled=false}});</script></body></html>"""

DASHBOARD_PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LARY MODZ PROXY · DASHBOARD</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"><style>
:root{--bg:#0f0d12;--panel:#18151e;--line:#2e2535;--muted:#a08fa8;--ink:#f5f3f7;--lime:#ff2d95}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:var(--bg);color:var(--ink);font-family:Inter,Arial,sans-serif}.app{min-height:100vh;display:grid;grid-template-columns:230px 1fr}.side{padding:28px 20px;border-right:1px solid var(--line);background:#131018;display:flex;flex-direction:column}.brand{font-weight:900;letter-spacing:2px}.brand span{color:var(--lime)}.side nav{margin-top:64px;display:grid;gap:8px}.side nav div{padding:12px;color:var(--muted);font:700 10px monospace;letter-spacing:1.5px;text-transform:uppercase}.side nav div.active{background:var(--lime);color:#1a0a12}.side-foot{margin-top:auto;color:#6b5a70;font:10px monospace;line-height:1.7}.main{padding:34px 42px;max-width:1180px;width:100%}.top{display:flex;justify-content:space-between;align-items:flex-start;padding-bottom:30px;border-bottom:1px solid var(--line)}.top h1{margin:8px 0 0;font-size:36px;letter-spacing:-1.5px}.eyebrow{font:700 10px monospace;letter-spacing:2px;color:var(--lime)}.status{display:flex;gap:8px;align-items:center;color:#ff7ec0;font:700 10px monospace}.dot{width:7px;height:7px;background:#ff2d95;border-radius:50%;box-shadow:0 0 14px #ff2d95}.ip{margin:28px 0;display:flex;align-items:center;gap:12px;padding:15px 18px;background:#16131c;border:1px solid var(--line);font:12px monospace;color:#c8b9d0}.ip span:first-of-type{flex:1}.eye{border:0;background:none;color:var(--muted);cursor:pointer}.tag{padding:5px 8px;color:#1a0a12;background:var(--lime);font:800 9px monospace}.section-title{display:flex;align-items:center;gap:10px;margin:28px 0 12px;font:800 11px monospace;letter-spacing:2px;color:#b9a8c0}.section-title:after{content:"";height:1px;background:var(--line);flex:1}.controls{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.control{display:flex;align-items:center;gap:14px;background:var(--panel);border:1px solid var(--line);padding:17px;cursor:pointer;transition:.2s}.control:hover{border-color:#c2186b;transform:translateY(-2px)}.control.disabled{cursor:pointer}.control.disabled:hover{border-color:#c2186b;transform:translateY(-2px)}.control.visual-option.is-on{border-color:var(--lime);background:#2a1525}.control.visual-option.is-on .icon{background:var(--lime);color:#1a0a12}.control.visual-option.is-on .sw{background:var(--lime)}.control.visual-option.is-on .sw .th{margin-left:16px;background:#1a0a12}.icon{width:34px;height:34px;display:grid;place-items:center;background:#2a1a28;color:var(--lime)}.info{flex:1}.name{font-size:12px;font-weight:800}.desc{color:var(--muted);font:10px monospace;margin-top:5px}.sw{width:34px;height:18px;border-radius:20px;background:#322a38;padding:2px}.sw .th{width:14px;height:14px;border-radius:50%;background:#8a7a90;transition:.2s}.sw.on{background:var(--lime)}.sw.on .th{margin-left:16px;background:#1a0a12}.bottom{margin-top:30px;padding-top:18px;border-top:1px solid var(--line);color:#6b5a70;font:10px monospace}@media(max-width:760px){body{overflow-x:hidden}.app{grid-template-columns:1fr}.side{border-right:0;border-bottom:1px solid var(--line);padding:18px 14px}.side nav{margin-top:18px;grid-template-columns:repeat(3,1fr);gap:5px}.side nav div{min-height:44px;display:flex;align-items:center;justify-content:center;padding:8px 4px;text-align:center;font-size:9px}.side-foot{display:none}.main{padding:22px 14px}.top h1{font-size:28px}.top{align-items:center}.status{font-size:9px}.ip{padding:14px 12px;min-height:24px}.controls{grid-template-columns:1fr;gap:10px}.control{min-height:64px;padding:14px}.name{font-size:12px}}
/* visual refresh */ body{background-image:radial-gradient(circle at 82% 8%,#3b1735 0,transparent 32%),radial-gradient(circle at 12% 90%,#152744 0,transparent 28%)} .login-shell,.access{border-radius:28px;overflow:hidden;border-color:#3a4b68;box-shadow:0 30px 100px #0009} .card,.control,.ip{border-radius:18px;box-shadow:0 14px 34px #0003} .card:hover,.control:hover{border-color:#ff2d9580} .field input{border-radius:12px;background:#0b101a} .field input:focus{box-shadow:0 0 0 4px #ff2d9522} button,.access-btn{border-radius:12px;background:linear-gradient(135deg,#ff2d95,#ff78bc);box-shadow:0 10px 24px #ff2d9525;transition:.2s} button:hover,.access-btn:hover{transform:translateY(-1px);filter:brightness(1.08)} .badge{border-radius:8px;border:1px solid #ff2d9544} .profile,.status{border-radius:999px} .nav-links a,.side nav div{border-radius:12px} .nav-links a:hover,.nav-links a.active,.side nav div:hover,.side nav div.active{background:#ff2d951c;border-color:#ff2d9555;transform:translateX(3px)} .stat{border-radius:14px;background:#0f1624} .generated{border-radius:10px;background:#ff2d950d;padding:10px}
</style></head><body><main class="app"><aside class="side"><div class="brand"><i class="fa-solid fa-bolt"></i> LARY MODZ<span>PROXY</span></div><nav><div class="active"><i class="fa-solid fa-grid-2"></i> Overview</div><div><i class="fa-solid fa-crosshairs"></i> Aim</div><div><i class="fa-solid fa-sliders"></i> Modules</div></nav><div class="side-foot">SESSION ACTIVE<br>CONTROL NODE / 01</div></aside><section class="main"><header class="top"><div><div class="eyebrow">USER CONSOLE</div><h1>Dashboard</h1></div><div class="status"><i class="dot"></i> ONLINE</div></header><div class="ip"><i class="fa-solid fa-network-wired"></i><span id="ipDisplay">CARREGANDO...</span><button class="eye" id="ipToggle" onclick="toggleIpVisibility()" title="Ocultar IP"><i class="fa-solid fa-eye"></i></button><b class="tag">AUTHORIZED</b></div><div class="section-title">AIM MODULES</div><div class="controls"><div class="control" onclick="toggle('hs_neck')"><div class="icon"><i class="fa-solid fa-crosshairs"></i></div><div class="info"><div class="name">HS PESCOÇO</div><div class="desc">PRECISION TARGET</div></div><div class="sw" id="sw_hs_neck"><div class="th"></div></div></div><div class="control" onclick="toggle('hs_chest')"><div class="icon"><i class="fa-solid fa-bullseye"></i></div><div class="info"><div class="name">HS PEITO</div><div class="desc">PRECISION TARGET</div></div><div class="sw" id="sw_hs_chest"><div class="th"></div></div></div><div class="control visual-option" onclick="toggleVisual(this)"><div class="icon"><i class="fa-solid fa-crosshairs"></i></div><div class="info"><div class="name">PRECISÃO</div><div class="desc">PRECISION TARGET</div></div><div class="sw"><div class="th"></div></div></div><div class="control visual-option" onclick="toggleVisual(this)"><div class="icon"><i class="fa-solid fa-arrow-up"></i></div><div class="info"><div class="name">HS ALTO</div><div class="desc">PRECISION TARGET</div></div><div class="sw"><div class="th"></div></div></div><div class="control visual-option" onclick="toggleVisual(this)"><div class="icon"><i class="fa-solid fa-bullseye"></i></div><div class="info"><div class="name">
HS ALTO + NECK</div><div class="desc">PRECISION TARGET</div></div><div class="sw"><div class="th"></div></div></div><div class="control visual-option" onclick="toggleVisual(this)"><div class="icon"><i class="fa-solid fa-expand"></i></div><div class="info"><div class="name">HOLOGRAMA</div><div class="desc">PRECISION TARGET</div></div><div class="sw"><div class="th"></div></div></div></div><div class="section-title">MOVEMENT & CONFIG</div><div class="controls"><div class="control" onclick="toggle('backjump_v1')"><div class="icon"><i class="fa-solid fa-arrow-up"></i></div><div class="info"><div class="name">BACKJUMP</div><div class="desc">MOVEMENT MODULE</div></div><div class="sw" id="sw_backjump_v1"><div class="th"></div></div></div><div class="control" onclick="toggle('high_sensi')"><div class="icon"><i class="fa-solid fa-sliders"></i></div><div class="info"><div class="name">SENSI ALTA</div><div class="desc">CONTROL PROFILE</div></div><div class="sw" id="sw_high_sensi"><div class="th"></div></div></div><div class="control" onclick="toggle('zig_zag_move')"><div class="icon"><i class="fa-solid fa-arrows-left-right"></i></div><div class="info"><div class="name">ZIG ZAG</div><div class="desc">MOVEMENT MODULE</div></div><div class="sw" id="sw_zig_zag_move"><div class="th"></div></div></div></div><div class="bottom">LEAKS BYPASS · CONTROLLED SESSION</div></section></main><div id="toast" style="position:fixed;bottom:24px;right:24px;padding:12px 16px;background:#ff2d95;color:#1a0a12;font:800 11px monospace;opacity:0;transition:.2s"></div><script>const names={hs_neck:'HS PESCOÇO',hs_chest:'HS PEITO',backjump_v1:'BACKJUMP',high_sensi:'SENSI ALTA',zig_zag_move:'ZIG ZAG'};function toggleVisual(card){card.classList.toggle('is-on');const name=card.querySelector('.name').textContent;toast(name+(card.classList.contains('is-on')?' ATIVO':' DESATIVADO'))}function toast(m){const t=document.getElementById('toast');t.textContent=m;t.style.opacity=1;clearTimeout(t._t);t._t=setTimeout(()=>t.style.opacity=0,1800)}let actualIp='',ipVisible=true;fetch('/api/ip/check').then(r=>r.json()).then(d=>{actualIp=d.ip||'DESCONHECIDO';document.getElementById('ipDisplay').textContent=actualIp});function toggleIpVisibility(){ipVisible=!ipVisible;document.getElementById('ipDisplay').textContent=ipVisible?actualIp:'•••.•••.•••.•••';document.getElementById('ipToggle').innerHTML=ipVisible?'<i class="fa-solid fa-eye"></i>':'<i class="fa-solid fa-eye-slash"></i>'}fetch('/api/status').then(r=>r.json()).then(d=>{const c=d.config;['hs_neck','hs_chest','backjump_v1','high_sensi','zig_zag_move'].forEach(f=>{const map={hs_neck:'HS_NECK',hs_chest:'HS_CHEST',backjump_v1:'BACKJUMPV1',high_sensi:'HIGH_SENSI',zig_zag_move:'ZIG_ZAG_MOVE'};document.getElementById('sw_'+f).className='sw'+(c[map[f]]?' on':'')})});function toggle(feature){const el=document.getElementById('sw_'+feature),val=!el.classList.contains('on');el.className='sw'+(val?' on':'');fetch('/api/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({feature,value:val})}).then(r=>r.json()).then(d=>{if(d.success)toast(names[feature]+' '+(val?'ON':'OFF'));else throw Error()}).catch(()=>{el.className='sw'+(!val?' on':'');toast('ERRO AO ALTERAR '+names[feature])})}</script></body></html>"""
# ==================== MAIN ====================
def get_public_ip():
    try:
        response = requests.get('https://api.ipify.org', timeout=5)
        return response.text.strip()
    except:
        try:
            response = requests.get('https://icanhazip.com', timeout=5)
            return response.text.strip()
        except:
            return "Não foi possível obter o IP público"

if __name__ == "__main__":
    load_data()
    port = int(os.environ.get('PORT', 10000))

    print("\n" + "="*50)
    print("  LEO MDZ PROXY ADMIN PANEL")
    print("="*50)
    print(f"  Porta do servidor: {port}")
    print(f"  URL pública: https://leomdzproxy-production.up.railway.app")
    print(f"  Admin     : /Po7eO")
    print(f"  Status    : Rodando")
    print("="*50 + "\n")

    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
