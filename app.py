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
import hashlib as _hashlib
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from collections import defaultdict
import time as _time
import urllib.request
import urllib.parse

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(32).hex())
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)

@app.after_request
def add_security_headers(resp):
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    resp.headers['X-XSS-Protection'] = '1; mode=block'
    resp.headers['Referrer-Policy'] = 'no-referrer'
    resp.headers['Permissions-Policy'] = 'geolocation=(), microphone=(self), camera=()'
    return resp

# ==================== CONFIG ====================
TARGET_BASE_URL = "https://dl.bs.freefiremobile.com/live/ABHotUpdates/"
VER_PHP_URL = "https://version.ggwhitehawk.com/live/ver.php"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get('PORT', 10000))
ADMIN_USER = "TIGRANMDZ"
ADMIN_PASS = "LEOMODZBRO"

_saved_pass = None
try:
    _pass_file_path = os.path.join(BASE_DIR, "admin_pass.txt")
    if os.path.exists(_pass_file_path):
        with open(_pass_file_path, 'r', encoding='utf-8') as _f:
            _saved_pass = _f.read().strip()
except Exception:
    pass
ADMIN_PASS_HASH = _saved_pass if _saved_pass else generate_password_hash(ADMIN_PASS)
TRUST_PROXY = os.environ.get("TRUST_PROXY", "1") == "1"
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 900
AI_RATE_LIMIT = 60

_login_attempts = defaultdict(list)
_ai_requests = defaultdict(list)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_ID", "")
_tg_last_update_id = 0

ADMINS_FILE = os.path.join(BASE_DIR, "admins.json")
PASS_FILE = os.path.join(BASE_DIR, "admin_pass.txt")
DATA_FILE = os.path.join(BASE_DIR, "crx_data.json")

user_configs = {}
registered_ips = {}
generated_keys = {}
key_expiry = {}

DEFAULT_CONFIG = {
    "HS_NECK": False, "HS_CHEST": False, "BYPASSV1": False,
    "BACKJUMPV1": False, "HIGH_SENSI": False, "ZIG_ZAG_MOVE": False
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

# Глобальные хранилища для новых функций
BANNED_IPS = {}
IP_BLACKLIST = set()
SCHEDULED_TASKS = []
DAILY_BONUS = {}
USER_REPUTATION = {}
USER_ACHIEVEMENTS = {}
QUIZ_ANSWERS = {}
GUESS_NUMBERS = {}
ADMIN_ACTIVITY = {}
ADMIN_GROUPS = {}


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


# ==================== HELPERS ====================
def load_admins_data():
    default = {"admins": [], "logs": []}
    try:
        if os.path.exists(ADMINS_FILE):
            with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                data = {"admins": [{"id": str(x), "name": "", "role": "admin"} for x in data], "logs": []}
            data.setdefault('admins', [])
            data.setdefault('logs', [])
            return data
    except Exception as e:
        print(f"[TG] load admins error: {e}")
    return default


def save_admins_data(data):
    try:
        with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[TG] save admins error: {e}")
        return False


def tg_log(action, by_id, target=""):
    try:
        data = load_admins_data()
        logs = data.get('logs', [])
        logs.append({
            'at': datetime.now().isoformat(),
            'by': str(by_id),
            'action': action,
            'target': str(target)
        })
        data['logs'] = logs[-200:]
        save_admins_data(data)
    except Exception as e:
        print(f"[TG] log error: {e}")


def get_user_role(chat_id):
    chat_id = str(chat_id)
    if chat_id == str(TELEGRAM_ADMIN_ID):
        return "owner"
    data = load_admins_data()
    for a in data.get('admins', []):
        if str(a.get('id')) == chat_id:
            return a.get('role', 'admin')
    return "guest"


def is_tg_admin(chat_id):
    return get_user_role(chat_id) in ("owner", "superadmin", "admin")


def is_super_or_owner(chat_id):
    return get_user_role(chat_id) in ("owner", "superadmin")


def is_main_admin(chat_id):
    return get_user_role(chat_id) == "owner"


def set_admin_pass_hash(new_hash):
    try:
        with open(PASS_FILE, 'w', encoding='utf-8') as f:
            f.write(new_hash)
        return True
    except Exception:
        return False


def role_emoji(role):
    return {"owner": "👑", "superadmin": "⭐", "admin": "🎖", "guest": "🚫"}.get(role, "🎖")


def normalize_key(value):
    return re.sub(r"\s+", "", str(value or "")).upper()


def generate_key(prefix="TIGRAN-MDZ-PROXY"):
    prefix = normalize_key(prefix) or "TIGRAN-MDZ-PROXY"
    alphabet = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(10))
    return f"{prefix}-{random_part}"


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


def get_client_ip():
    if TRUST_PROXY and request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if TRUST_PROXY and request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP').strip()
    return request.remote_addr or "0.0.0.0"


def check_rate_limit(store, ip, max_requests, window_seconds):
    now = _time.time()
    store[ip] = [t for t in store[ip] if now - t < window_seconds]
    if len(store[ip]) >= max_requests:
        return False
    store[ip].append(now)
    return True


def is_login_locked(ip):
    now = _time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < LOGIN_LOCKOUT_SECONDS]
    return len(_login_attempts[ip]) >= MAX_LOGIN_ATTEMPTS


def record_failed_login(ip):
    _login_attempts[ip].append(_time.time())


def clear_login_attempts(ip):
    _login_attempts.pop(ip, None)


def safe_join_cdn(path):
    if not path:
        return ""
    cleaned = path.replace("\\", "/").lstrip("/")
    parts = [p for p in cleaned.split("/") if p and p != ".." and p != "."]
    if any(".." in p for p in parts):
        return None
    return "/".join(parts)


def get_user_config(client_ip):
    if client_ip not in user_configs:
        user_configs[client_ip] = DEFAULT_CONFIG.copy()
        save_data()
    return user_configs[client_ip]


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


# ==================== TELEGRAM API ====================
def tg_api(method, params=None):
    if not TELEGRAM_BOT_TOKEN:
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    try:
        if params:
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(url, data=data)
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[TG] Error {method}: {e}")
        return None


def tg_send(chat_id, text):
    return tg_api("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})


def tg_send_buttons(chat_id, text, buttons):
    if not TELEGRAM_BOT_TOKEN:
        return None
    return tg_api("sendMessage", {
        "chat_id": chat_id, "text": text, "parse_mode": "HTML",
        "reply_markup": json.dumps({"inline_keyboard": buttons})
    })


def tg_answer_callback(callback_id, text="", alert=False):
    return tg_api("answerCallbackQuery", {
        "callback_query_id": callback_id, "text": text,
        "show_alert": "true" if alert else "false"
    })


def tg_edit_message(chat_id, message_id, text, buttons=None):
    params = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if buttons:
        params["reply_markup"] = json.dumps({"inline_keyboard": buttons})
    return tg_api("editMessageText", params)


def tg_notify_admin(text):
    if TELEGRAM_ADMIN_ID and TELEGRAM_BOT_TOKEN:
        tg_send(TELEGRAM_ADMIN_ID, text)


def tg_notify_all_admins(text):
    """Отправляет всем админам."""
    try:
        tg_send(TELEGRAM_ADMIN_ID, text)
    except:
        pass
    data = load_admins_data()
    for a in data.get('admins', []):
        try:
            tg_send(a['id'], text)
        except:
            pass


def tg_get_file(file_id):
    """Получить путь к файлу в Telegram."""
    res = tg_api("getFile", {"file_id": file_id})
    if res and res.get("ok"):
        return res["result"].get("file_path")
    return None


def tg_download_file(file_path, save_to):
    """Скачивает файл из Telegram."""
    try:
        url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        r = requests.get(url, timeout=60)
        if r.status_code == 200:
            with open(save_to, "wb") as f:
                f.write(r.content)
            return True
    except:
        pass
    return False


# ==================== UI: КНОПКИ ====================
PAGE_SIZE = 5


def tg_main_menu(chat_id):
    role = get_user_role(chat_id)
    if role == "guest":
        tg_send(chat_id, "⛔ Доступ запрещён.")
        return
    is_super = role in ("owner", "superadmin")
    is_owner = role == "owner"

    buttons = [
        [{"text": "🔑 Ключи", "callback_data": "menu_keys_0"},
         {"text": "🌐 Сессии", "callback_data": "menu_sessions"}],
        [{"text": "📊 Статистика", "callback_data": "menu_stats"},
         {"text": "👥 Админы", "callback_data": "menu_admins"}],
        [{"text": "🔍 Поиск ключа", "callback_data": "menu_search"},
         {"text": "🎯 Быстрые действия", "callback_data": "menu_quick"}],
        [{"text": "🛠 Утилиты", "callback_data": "menu_utils"},
         {"text": "📈 Отчёты", "callback_data": "menu_reports"}],
        [{"text": "🎮 Развлечения", "callback_data": "menu_fun"},
         {"text": "🔒 Безопасность", "callback_data": "menu_security"}],
    ]
    if is_super:
        buttons.append([{"text": "➕ Добавить админа", "callback_data": "menu_addadmin"}])
    if is_owner:
        buttons.append([{"text": "💾 Backup", "callback_data": "menu_backup"},
                        {"text": "📜 Логи", "callback_data": "menu_logs"}])
        buttons.append([{"text": "📢 Рассылка", "callback_data": "menu_broadcast"},
                        {"text": "🔑 Пароль", "callback_data": "menu_setpass"}])
        buttons.append([{"text": "⚙ Настройки", "callback_data": "menu_settings"},
                        {"text": "⏰ Задачи", "callback_data": "menu_tasks"}])

    tg_send_buttons(chat_id,
        f"{role_emoji(role)} <b>TIGRAN MODZ BOT</b>\n"
        f"Роль: <b>{role.upper()}</b>\n"
        f"ID: <code>{chat_id}</code>\n\n"
        f"👇 Выбери действие:",
        buttons)


def tg_menu_keys(chat_id, message_id, page=0):
    if not generated_keys:
        text = "📋 <b>Ключей нет</b>"
        buttons = [[{"text": "🔑 Создать ключ", "callback_data": "quick_genkey"}],
                   [{"text": "◀ Назад", "callback_data": "menu_back"}]]
        tg_edit_message(chat_id, message_id, text, buttons)
        return
    keys_list = list(generated_keys.items())
    total = len(keys_list)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    chunk = keys_list[start:end]
    lines = [f"📋 <b>Ключи</b> ({start+1}-{min(end, total)} из {total})\n"]
    for k, v in chunk:
        lines.append(f"<code>{k}</code>")
        lines.append(f"   └ {len(v['used_ips'])}/{v['limit']} IP · {v['days']}d")
    text = "\n".join(lines)
    nav = []
    if page > 0:
        nav.append({"text": "◀", "callback_data": f"menu_keys_{page-1}"})
    nav.append({"text": f"{page+1}/{total_pages}", "callback_data": "noop"})
    if page < total_pages - 1:
        nav.append({"text": "▶", "callback_data": f"menu_keys_{page+1}"})
    buttons = [nav,
               [{"text": "🔑 Создать ключ", "callback_data": "quick_genkey"}],
               [{"text": "◀ Назад", "callback_data": "menu_back"}]]
    tg_edit_message(chat_id, message_id, text, buttons)


def tg_menu_sessions(chat_id, message_id):
    if not registered_ips:
        text = "🌐 <b>Нет активных сессий</b>"
    else:
        lines = [f"🌐 <b>Активные сессии ({len(registered_ips)}):</b>\n"]
        for ip, key in list(registered_ips.items())[:15]:
            exp = key_expiry.get(ip)
            exp_str = exp.strftime('%d/%m/%Y') if exp else '-'
            lines.append(f"<code>{ip}</code>")
            lines.append(f"   └ {key} · до {exp_str}")
        text = "\n".join(lines)
    tg_edit_message(chat_id, message_id, text,
        [[{"text": "◀ Назад", "callback_data": "menu_back"}]])


def tg_menu_stats(chat_id, message_id):
    text = (
        f"📊 <b>Статистика сервера</b>\n\n"
        f"🔑 Всего ключей: <b>{len(generated_keys)}</b>\n"
        f"🌐 Активных IP: <b>{len(registered_ips)}</b>\n"
        f"🤖 AI-запросов: <b>{sum(len(v) for v in _ai_requests.values())}</b>\n"
        f"👥 Админов: <b>{1 + len(load_admins_data().get('admins', []))}</b>\n"
        f"🚫 Забанено IP: <b>{len(BANNED_IPS) + len(IP_BLACKLIST)}</b>\n"
        f"⏰ Задач в очереди: <b>{len(SCHEDULED_TASKS)}</b>\n"
        f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    tg_edit_message(chat_id, message_id, text,
        [[{"text": "◀ Назад", "callback_data": "menu_back"}]])


def tg_menu_admins(chat_id, message_id):
    adata = load_admins_data()
    admins = adata.get('admins', [])
    lines = [f"👑 <b>Owner:</b> <code>{TELEGRAM_ADMIN_ID}</code>\n"]
    if admins:
        lines.append(f"⭐🎖 <b>Админы ({len(admins)}):</b>")
        for a in admins:
            em = role_emoji(a.get('role', 'admin'))
            lines.append(f"{em} <code>{a.get('id')}</code> [{a.get('role','admin')}]")
    else:
        lines.append("(кроме owner никого)")
    tg_edit_message(chat_id, message_id, "\n".join(lines),
        [[{"text": "◀ Назад", "callback_data": "menu_back"}]])


def tg_menu_quick(chat_id, message_id):
    buttons = [
        [{"text": "🔑 Ключ (1 IP, 7д)", "callback_data": "quick_genkey"}],
        [{"text": "🔑 Ключ (5 IP, 30д)", "callback_data": "quick_genkey_big"}],
        [{"text": "📦 Массово 10 ключей", "callback_data": "quick_bulk10"}],
        [{"text": "📊 Обновить статистику", "callback_data": "menu_stats"}],
        [{"text": "◀ Назад", "callback_data": "menu_back"}]
    ]
    tg_edit_message(chat_id, message_id,
        "🎯 <b>Быстрые действия</b>\n\nВыбери готовый шаблон:", buttons)


def tg_menu_utils(chat_id, message_id):
    text = (
        "🛠 <b>Утилиты</b>\n\n"
        "• <code>/short URL</code> — сократить ссылку\n"
        "• <code>/hash текст</code> — SHA/MD5 хеш\n"
        "• <code>/hash md5 текст</code> — конкретный алгоритм\n"
        "• <code>/b64enc текст</code> — Base64 кодировать\n"
        "• <code>/b64dec строка</code> — Base64 декодировать\n"
        "• <code>/pass 20</code> — сгенерировать пароль\n"
        "• <code>/weather Moscow</code> — погода\n"
        "• <code>/currency 100 USD RUB</code> — курс валют\n"
        "• <code>/qr KEY</code> — QR-код ключа\n"
    )
    tg_edit_message(chat_id, message_id, text,
        [[{"text": "◀ Назад", "callback_data": "menu_back"}]])


def tg_menu_reports(chat_id, message_id):
    text = (
        "📈 <b>Отчёты и аналитика</b>\n\n"
        "• <code>/report</code> — полный отчёт сейчас\n"
        "• <code>/heatmap</code> — карта активных IP\n"
        "• <code>/activity</code> — топ админов по активности\n"
        "• <code>/export csv</code> — экспорт ключей\n"
        "• <code>/export json</code> — экспорт в JSON\n\n"
        "🌅 Автоотчёт отправляется каждый день в 09:00\n"
        "⏰ Напоминания об истечении — каждый час"
    )
    tg_edit_message(chat_id, message_id, text,
        [[{"text": "◀ Назад", "callback_data": "menu_back"}]])


def tg_menu_fun(chat_id, message_id):
    text = (
        "🎮 <b>Развлечения</b>\n\n"
        "• <code>/bonus</code> — ежедневный бонус\n"
        "• <code>/rep</code> — своя репутация\n"
        "• <code>/quiz</code> — квиз\n"
        "• <code>/guess</code> — угадай число\n"
        "• <code>/events</code> — календарь событий\n"
        "• <code>/poll Вопрос|A|B|C</code> — опрос\n"
    )
    tg_edit_message(chat_id, message_id, text,
        [[{"text": "◀ Назад", "callback_data": "menu_back"}]])


def tg_menu_security(chat_id, message_id):
    text = (
        "🔒 <b>Безопасность</b>\n\n"
        "• <code>/ban 1.2.3.4 24</code> — бан IP на 24ч\n"
        "• <code>/unban 1.2.3.4</code> — разбан\n"
        "• <code>/iplookup 8.8.8.8</code> — инфо об IP\n\n"
        f"🚫 Забанено сейчас: <b>{len(BANNED_IPS) + len(IP_BLACKLIST)}</b>"
    )
    tg_edit_message(chat_id, message_id, text,
        [[{"text": "◀ Назад", "callback_data": "menu_back"}]])


def tg_menu_tasks(chat_id, message_id):
    if not SCHEDULED_TASKS:
        text = "⏰ <b>Нет запланированных задач</b>\n\nИспользование:\n<code>/schedule broadcast 3600 Текст</code>"
    else:
        lines = [f"⏰ <b>Задачи ({len(SCHEDULED_TASKS)}):</b>\n"]
        for t in SCHEDULED_TASKS[:15]:
            left = int(t['when'] - time.time())
            lines.append(f"• <code>{t['id'][:12]}</code> · {t['action']} · через {left}с")
        text = "\n".join(lines)
    tg_edit_message(chat_id, message_id, text,
        [[{"text": "◀ Назад", "callback_data": "menu_back"}]])


# ==================== КАТЕГОРИЯ 2: КЛЮЧИ ПРОДВИНУТЫЕ ====================
def tg_bulk_create_keys(chat_id, count, prefix, limit, days):
    try:
        count = max(1, min(int(count), 50))
    except:
        count = 1
    try: limit = max(1, int(limit))
    except: limit = 1
    try: days = max(1, int(days))
    except: days = 7
    created = []
    for _ in range(count):
        k = generate_key(prefix)
        generated_keys[k] = {
            'prefix': normalize_key(prefix) or 'TIGRAN-MDZ-PROXY',
            'limit': limit, 'days': days,
            'created': datetime.now().isoformat(), 'used_ips': []
        }
        created.append(k)
    save_data()
    tg_log("bulk_genkey", chat_id, f"{count} keys")
    return created


def tg_export_keys(chat_id, format="csv"):
    if not generated_keys:
        tg_send(chat_id, "📦 Ключей нет.")
        return
    try:
        if format == "csv":
            lines = ["key,limit,days,used_ips,created"]
            for k, v in generated_keys.items():
                lines.append(f"{k},{v['limit']},{v['days']},{len(v['used_ips'])},{v.get('created','')}")
            content = "\n".join(lines)
            fname = f"keys_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        else:
            content = json.dumps(generated_keys, ensure_ascii=False, indent=2)
            fname = f"keys_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        path = os.path.join(BASE_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if TELEGRAM_BOT_TOKEN:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
            with open(path, "rb") as f:
                files = {"document": (fname, f)}
                data = {"chat_id": str(chat_id), "caption": f"📦 Экспорт: {len(generated_keys)} ключей"}
                requests.post(url, files=files, data=data, timeout=60)
        try: os.remove(path)
        except: pass
    except Exception as e:
        tg_send(chat_id, f"❌ Ошибка экспорта: {e}")


def tg_auto_delete_expired():
    while True:
        try:
            now = datetime.now()
            to_delete = []
            for k, v in list(generated_keys.items()):
                created = v.get('created')
                if not created: continue
                try:
                    dt = datetime.fromisoformat(created)
                    if (now - dt).days > v['days']:
                        to_delete.append(k)
                except: pass
            for k in to_delete:
                for ip in generated_keys[k].get('used_ips', []):
                    registered_ips.pop(ip, None)
                    key_expiry.pop(ip, None)
                del generated_keys[k]
            if to_delete:
                save_data()
                print(f"[TG] Auto-deleted {len(to_delete)} expired keys")
                tg_notify_all_admins(f"🧹 Авто-очистка: удалено {len(to_delete)} просроченных ключей")
        except Exception as e:
            print(f"[TG] auto-delete error: {e}")
        time.sleep(3600)


def tg_extend_key(key, extra_days):
    key = normalize_key(key)
    if key not in generated_keys:
        return False, "Ключ не найден"
    try: extra_days = max(1, int(extra_days))
    except: return False, "Неверное число дней"
    generated_keys[key]['days'] += extra_days
    save_data()
    return True, f"Продлён на {extra_days} дней. Всего: {generated_keys[key]['days']}d"


def tg_qr_for_key(chat_id, key):
    key = normalize_key(key)
    url = f"https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={key}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            path = os.path.join(BASE_DIR, f"qr_{key[:10]}.png")
            with open(path, "wb") as f:
                f.write(r.content)
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            with open(path, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": str(chat_id), "caption": f"🔗 QR для ключа:\n<code>{key}</code>", "parse_mode": "HTML"}
                requests.post(tg_url, files=files, data=data, timeout=60)
            try: os.remove(path)
            except: pass
    except Exception as e:
        tg_send(chat_id, f"❌ Ошибка QR: {e}")


# ==================== КАТЕГОРИЯ 3: БЕЗОПАСНОСТЬ ====================
def tg_ban_ip(ip, hours=24):
    try: hours = max(1, int(hours))
    except: hours = 24
    BANNED_IPS[ip] = time.time() + hours * 3600
    tg_log("ban_ip", "bot", f"{ip} for {hours}h")
    return f"IP {ip} забанен на {hours}ч"


def tg_unban_ip(ip):
    BANNED_IPS.pop(ip, None)
    IP_BLACKLIST.discard(ip)
    return f"IP {ip} разбанен"


def tg_is_ip_banned(ip):
    if ip in IP_BLACKLIST:
        return True
    if ip in BANNED_IPS:
        if time.time() < BANNED_IPS[ip]:
            return True
        else:
            del BANNED_IPS[ip]
    return False


def tg_get_ip_geo(ip):
    try:
        r = requests.get(
            f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,regionName,city,timezone,isp",
            timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('status') == 'success':
                return f"{d.get('country','?')} ({d.get('countryCode','?')}) · {d.get('city','?')} · {d.get('isp','?')}"
    except:
        pass
    return None


def tg_notify_login_all(client_ip, key, expiry_date):
    geo = tg_get_ip_geo(client_ip)
    geo_line = f"\n🌍 {geo}" if geo else ""
    text = (
        f"🔔 <b>НОВЫЙ ВХОД</b>\n\n"
        f"IP: <code>{client_ip}</code>{geo_line}\n"
        f"Ключ: <code>{key}</code>\n"
        f"До: {expiry_date.strftime('%d/%m/%Y')}"
    )
    tg_notify_all_admins(text)


# ==================== КАТЕГОРИЯ 4: AI ФУНКЦИИ ====================
def tg_ai_translate(text, target_lang="ru"):
    if not OPENAI_API_KEY: return None
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": f"Переведи текст на {target_lang}. Только перевод, без пояснений."},
                    {"role": "user", "content": text[:1500]}
                ],
                "max_tokens": 600, "temperature": 0.3
            }, timeout=25)
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content']
    except:
        pass
    return None


def tg_ai_summarize(text):
    if not OPENAI_API_KEY: return None
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Сделай краткое резюме текста в 3-5 предложениях."},
                    {"role": "user", "content": text[:3000]}
                ],
                "max_tokens": 400, "temperature": 0.5
            }, timeout=25)
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content']
    except:
        pass
    return None


def tg_ai_describe_image(file_id, chat_id):
    if not OPENAI_API_KEY or not TELEGRAM_BOT_TOKEN:
        return None
    try:
        fp = tg_get_file(file_id)
        if not fp: return None
        path = os.path.join(BASE_DIR, f"ai_img_{file_id[:8]}.jpg")
        if not tg_download_file(fp, path): return None
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        try: os.remove(path)
        except: pass
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Опиши что на картинке, кратко и по делу."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                }],
                "max_tokens": 500
            }, timeout=40)
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"[TG] vision error: {e}")
    return None


def tg_ai_generate_image(chat_id, prompt):
    if not OPENAI_API_KEY:
        return False
    try:
        r = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={"model": "dall-e-3", "prompt": prompt[:800], "n": 1, "size": "1024x1024"},
            timeout=60)
        if r.status_code == 200:
            img_url = r.json()['data'][0]['url']
            tg_send(chat_id, f"🎨 <b>Готово!</b>\n\n🔗 <a href='{img_url}'>Скачать картинку</a>")
            return True
        else:
            tg_send(chat_id, f"❌ DALL-E: HTTP {r.status_code}")
    except Exception as e:
        tg_send(chat_id, f"❌ Ошибка: {e}")
    return False


# ==================== КАТЕГОРИЯ 5: УТИЛИТЫ ====================
def tg_url_shorten(url):
    try:
        r = requests.get(f"https://tinyurl.com/api-create.php?url={url}", timeout=10)
        if r.status_code == 200:
            return r.text.strip()
    except:
        pass
    return None


def tg_hash_text(text, algo="sha256"):
    try:
        if algo == "md5":
            return hashlib.md5(text.encode()).hexdigest()
        elif algo == "sha1":
            return hashlib.sha1(text.encode()).hexdigest()
        elif algo == "sha512":
            return hashlib.sha512(text.encode()).hexdigest()
        else:
            return hashlib.sha256(text.encode()).hexdigest()
    except:
        return None


def tg_b64_encode(text):
    return base64.b64encode(text.encode()).decode()


def tg_b64_decode(text):
    try:
        return base64.b64decode(text.encode()).decode()
    except:
        return None


def tg_password_gen(length=16):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
    try: length = max(8, min(int(length), 128))
    except: length = 16
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def tg_weather(city):
    try:
        r = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
        if r.status_code == 200:
            d = r.json()
            cur = d['current_condition'][0]
            return (f"🌤 <b>{city}</b>\n\n"
                    f"🌡 Температура: <b>{cur.get('temp_C')}°C</b> "
                    f"(ощущается {cur.get('FeelsLikeC')}°C)\n"
                    f"☁ {cur.get('weatherDesc',[{}])[0].get('value','?')}\n"
                    f"💧 Влажность: {cur.get('humidity')}%\n"
                    f"💨 Ветер: {cur.get('windspeedKmph')} км/ч")
    except:
        pass
    return None


def tg_currency_convert(amount, from_cur, to_cur):
    try: amount = float(amount)
    except: return None
    try:
        r = requests.get(
            f"https://api.exchangerate.host/convert?from={from_cur}&to={to_cur}&amount={amount}",
            timeout=10)
        if r.status_code == 200:
            d = r.json()
            if d.get('success'):
                res = d.get('result', 0)
                return f"{amount} {from_cur} = <b>{res:.2f} {to_cur}</b>"
    except:
        pass
    return None


# ==================== КАТЕГОРИЯ 6: ОТЧЁТЫ ====================
def tg_generate_stats_report():
    now = datetime.now()
    total_keys = len(generated_keys)
    active_ips = len(registered_ips)
    admin_count = 1 + len(load_admins_data().get('admins', []))
    ai_reqs = sum(len(v) for v in _ai_requests.values())
    soon_expiring = 0
    for ip, exp in key_expiry.items():
        if exp and (exp - now).days <= 3:
            soon_expiring += 1
    top_keys = sorted(generated_keys.items(),
                      key=lambda x: len(x[1].get('used_ips', [])),
                      reverse=True)[:5]
    return {
        "total_keys": total_keys, "active_ips": active_ips,
        "admin_count": admin_count, "ai_reqs": ai_reqs,
        "soon_expiring": soon_expiring, "top_keys": top_keys
    }


def tg_send_daily_report():
    s = tg_generate_stats_report()
    now = datetime.now()
    lines = [
        f"🌅 <b>ЕЖЕДНЕВНЫЙ ОТЧЁТ</b>",
        f"📅 {now.strftime('%d/%m/%Y %H:%M')}\n",
        f"🔑 Всего ключей: <b>{s['total_keys']}</b>",
        f"🌐 Активных IP: <b>{s['active_ips']}</b>",
        f"👥 Админов: <b>{s['admin_count']}</b>",
        f"🤖 AI-запросов: <b>{s['ai_reqs']}</b>",
        f"⚠ Истекают в 3 дня: <b>{s['soon_expiring']}</b>\n",
        f"🏆 <b>Топ-5 ключей:</b>"
    ]
    for k, v in s['top_keys']:
        lines.append(f"• <code>{k}</code> — {len(v.get('used_ips',[]))} IP")
    tg_notify_all_admins("\n".join(lines))


def tg_daily_report_scheduler():
    last_sent_day = None
    while True:
        try:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            if now.hour == 9 and now.minute < 5 and last_sent_day != today:
                last_sent_day = today
                tg_send_daily_report()
                print(f"[TG] Daily report sent")
        except Exception as e:
            print(f"[TG] report scheduler error: {e}")
        time.sleep(60)


def tg_ip_heatmap():
    if not registered_ips:
        return "Нет данных"
    lines = ["🗺 <b>Карта IP:</b>\n"]
    for ip, key in list(registered_ips.items())[:20]:
        exp = key_expiry.get(ip)
        exp_str = exp.strftime('%d/%m') if exp else '-'
        lines.append(f"📍 <code>{ip}</code> · {exp_str}")
    return "\n".join(lines)


# ==================== КАТЕГОРИЯ 7: АВТОМАТИЗАЦИЯ ====================
def tg_schedule_task(chat_id, when_seconds, action, params=None, recurring=None):
    task = {
        'id': f"task_{len(SCHEDULED_TASKS)}_{int(time.time())}",
        'when': time.time() + when_seconds,
        'action': action,
        'params': params or {},
        'chat_id': chat_id,
        'recurring': recurring
    }
    SCHEDULED_TASKS.append(task)
    return task


def tg_scheduler_loop():
    while True:
        try:
            now = time.time()
            done = []
            for task in SCHEDULED_TASKS:
                if now >= task['when']:
                    try:
                        act = task['action']
                        if act == 'broadcast':
                            tg_notify_all_admins(f"📢 <b>Авторассылка:</b>\n\n{task['params'].get('text','')}")
                        elif act == 'backup':
                            try:
                                payload = {
                                    "generated_keys": generated_keys,
                                    "registered_ips": registered_ips,
                                    "admins": load_admins_data(),
                                    "at": datetime.now().isoformat()
                                }
                                tb = json.dumps(payload, ensure_ascii=False, indent=2)
                                for i in range(0, len(tb), 3500):
                                    tg_send(task['chat_id'], f"<pre>{tb[i:i+3500]}</pre>")
                            except: pass
                        elif act == 'cleanup':
                            tg_notify_all_admins("🧹 Запущена авто-очистка ключей")
                    except Exception as e:
                        print(f"[TG] task error: {e}")
                    if task.get('recurring'):
                        task['when'] = now + task['recurring']
                    else:
                        done.append(task)
            for d in done:
                SCHEDULED_TASKS.remove(d)
        except Exception as e:
            print(f"[TG] scheduler loop error: {e}")
        time.sleep(10)


def tg_send_reminder_if_expiring():
    now = datetime.now()
    soon = []
    for ip, exp in key_expiry.items():
        if exp and 0 < (exp - now).days <= 1:
            soon.append((ip, registered_ips.get(ip, '?'), exp))
    if soon:
        lines = ["⏰ <b>Напоминание: ключи истекают завтра</b>\n"]
        for ip, key, exp in soon[:20]:
            lines.append(f"<code>{ip}</code> — {key} · до {exp.strftime('%d/%m')}")
        tg_notify_all_admins("\n".join(lines))
        return True
    return False


def tg_reminder_scheduler():
    last_hour = None
    while True:
        try:
            now = datetime.now()
            hour_key = now.strftime("%Y-%m-%d %H")
            if now.minute < 5 and last_hour != hour_key:
                last_hour = hour_key
                tg_send_reminder_if_expiring()
        except Exception as e:
            print(f"[TG] reminder error: {e}")
        time.sleep(60)


# ==================== КАТЕГОРИЯ 8: АДМИНЫ ====================
def tg_admin_register_activity(chat_id, action):
    cid = str(chat_id)
    if cid not in ADMIN_ACTIVITY:
        ADMIN_ACTIVITY[cid] = {'actions': 0, 'last': ''}
    ADMIN_ACTIVITY[cid]['actions'] += 1
    ADMIN_ACTIVITY[cid]['last'] = datetime.now().isoformat()


def tg_admins_activity_report():
    if not ADMIN_ACTIVITY:
        return "📊 Нет данных об активности."
    sorted_admins = sorted(ADMIN_ACTIVITY.items(), key=lambda x: x[1]['actions'], reverse=True)
    lines = ["📊 <b>Топ по активности:</b>\n"]
    for cid, data in sorted_admins[:15]:
        em = role_emoji(get_user_role(cid))
        lines.append(f"{em} <code>{cid}</code> — {data['actions']} действий · {data['last'][:16]}")
    return "\n".join(lines)


def tg_admin_dm(from_id, to_id, text):
    if get_user_role(from_id) == "guest":
        return "⛔ Нет прав."
    if get_user_role(to_id) == "guest":
        return "❌ Получатель не админ."
    try:
        tg_send(to_id, f"📩 <b>Сообщение от</b> <code>{from_id}</code>:\n\n{text}")
        return "✅ Отправлено."
    except Exception as e:
        return f"❌ Ошибка: {e}"


def tg_poll_create(chat_id, question, options):
    return tg_api("sendPoll", {
        "chat_id": chat_id, "question": question,
        "options": json.dumps(options), "is_anonymous": "true"
    })


# ==================== КАТЕГОРИЯ 9: РАЗВЛЕЧЕНИЯ ====================
def tg_daily_bonus(chat_id):
    cid = str(chat_id)
    today = datetime.now().strftime("%Y-%m-%d")
    if DAILY_BONUS.get(cid) == today:
        return f"⏰ Ты уже получил бонус сегодня! Возвращайся завтра."
    DAILY_BONUS[cid] = today
    USER_REPUTATION[cid] = USER_REPUTATION.get(cid, 0) + 1
    return f"🎁 Бонус получен! Твоя репутация: <b>{USER_REPUTATION[cid]}</b>"


def tg_add_achievement(chat_id, name):
    cid = str(chat_id)
    if cid not in USER_ACHIEVEMENTS:
        USER_ACHIEVEMENTS[cid] = []
    if name not in USER_ACHIEVEMENTS[cid]:
        USER_ACHIEVEMENTS[cid].append(name)
        tg_send(chat_id, f"🏅 <b>Новое достижение:</b> {name}")


def tg_quiz_start(chat_id):
    questions = [
        {"q": "Сколько будет 2+2*2?", "a": "6"},
        {"q": "Столица Армении?", "a": "ереван"},
        {"q": "Сколько дней в году?", "a": "365"},
        {"q": "Что больше: 100 или 99?", "a": "100"},
        {"q": "Какого цвета небо?", "a": "голубое"},
    ]
    q = random.choice(questions)
    tg_send(chat_id, f"🎮 <b>Квиз!</b>\n\n{q['q']}\n\n<i>Ответь в чат</i>")
    return q['a']


def tg_check_quiz(chat_id, text):
    cid = str(chat_id)
    if cid in QUIZ_ANSWERS:
        expected = QUIZ_ANSWERS[cid]
        if text.strip().lower() == expected:
            del QUIZ_ANSWERS[cid]
            USER_REPUTATION[cid] = USER_REPUTATION.get(cid, 0) + 5
            tg_send(chat_id, f"✅ Правильно! +5 репутации\nВсего: {USER_REPUTATION[cid]}")
            return True
    return False


def tg_guess_number_start(chat_id):
    num = random.randint(1, 100)
    GUESS_NUMBERS[str(chat_id)] = num
    tg_send(chat_id, "🎲 <b>Угадай число</b>\n\nЯ загадал от 1 до 100. Напиши число.")
    return num


def tg_check_guess(chat_id, text):
    cid = str(chat_id)
    if cid not in GUESS_NUMBERS:
        return False
    try:
        guess = int(text.strip())
    except:
        return False
    target = GUESS_NUMBERS[cid]
    if guess == target:
        del GUESS_NUMBERS[cid]
        tg_send(chat_id, f"🎉 Угадал! Было число <b>{target}</b>")
        return True
    elif guess < target:
        tg_send(chat_id, "📈 Больше!")
    else:
        tg_send(chat_id, "📉 Меньше!")
    return True


def tg_events_calendar():
    now = datetime.now()
    return (
        f"📅 <b>Календарь событий</b>\n\n"
        f"🌅 Автоотчёт: каждый день в <b>09:00</b>\n"
        f"⏰ Напоминания: каждый час\n"
        f"🧹 Авто-очистка: каждый час\n"
        f"📅 Сегодня: {now.strftime('%d/%m/%Y %H:%M')}"
    )


# ==================== КАТЕГОРИЯ 10: ИНТЕГРАЦИИ ====================
def tg_google_sheets_sync():
    url = os.environ.get("GOOGLE_SHEETS_WEBHOOK", "")
    if not url:
        return False, "GOOGLE_SHEETS_WEBHOOK не настроен"
    try:
        data = {
            "keys": [{"key": k, "used": len(v['used_ips']), "days": v['days']} for k, v in generated_keys.items()],
            "ips": list(registered_ips.keys()),
            "at": datetime.now().isoformat()
        }
        r = requests.post(url, json=data, timeout=15)
        if r.status_code == 200:
            return True, "Синхронизировано"
    except Exception as e:
        return False, str(e)
    return False, "Не удалось"


def tg_send_email(to_email, subject, body):
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    if not all([smtp_host, smtp_user, smtp_pass]):
        return False, "SMTP не настроен (SMTP_HOST, SMTP_USER, SMTP_PASS)"
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = to_email
        with smtplib.SMTP_SSL(smtp_host, 465, timeout=15) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True, "Письмо отправлено"
    except Exception as e:
        return False, str(e)


def tg_send_youtube_info(url):
    try:
        r = requests.get(f"https://www.youtube.com/oembed?url={url}&format=json", timeout=10)
        if r.status_code == 200:
            d = r.json()
            return (f"🎬 <b>{d.get('title','?')}</b>\n\n"
                    f"👤 Автор: {d.get('author_name','?')}\n"
                    f"🌐 {d.get('provider_name','YouTube')}")
    except:
        pass
    return None


def tg_github_status():
    repo = os.environ.get("GITHUB_REPO", "")
    if not repo:
        return None
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}", timeout=10)
        if r.status_code == 200:
            d = r.json()
            return (f"🐙 <b>GitHub репозиторий</b>\n\n"
                    f"📦 {d.get('name')}\n"
                    f"⭐ Звёзд: {d.get('stargazers_count')}\n"
                    f"🍴 Форков: {d.get('forks_count')}\n"
                    f"📅 Обновлён: {d.get('updated_at','')[:10]}")
    except:
        pass
    return None


def tg_stripe_payment_link(amount, currency="usd"):
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not stripe_key:
        return None
    try:
        r = requests.post(
            "https://api.stripe.com/v1/payment_links",
            auth=(stripe_key, ""),
            data={
                "line_items[0][price_data][currency]": currency,
                "line_items[0][price_data][product_data][name]": "TIGRAN MODZ Подписка",
                "line_items[0][price_data][unit_amount]": int(amount * 100),
                "line_items[0][quantity]": 1,
            }, timeout=15)
        if r.status_code == 200:
            return r.json().get('url')
    except:
        pass
    return None


def tg_achievements_checker():
    while True:
        try:
            for cid, data in ADMIN_ACTIVITY.items():
                if data['actions'] >= 10:
                    tg_add_achievement(cid, "🔥 Активный админ (10+ действий)")
                if data['actions'] >= 50:
                    tg_add_achievement(cid, "🚀 Профи (50+ действий)")
            if len(generated_keys) >= 100:
                for cid in ADMIN_ACTIVITY.keys():
                    tg_add_achievement(cid, "💎 Ключник (100+ ключей)")
        except Exception as e:
            print(f"[TG] achievements error: {e}")
        time.sleep(3600)


# ==================== OWNER AI-АГЕНТ ====================
def tg_owner_ai_agent(chat_id, text):
    if not OPENAI_API_KEY:
        return None
    system_prompt = (
        "Ты AI-агент управления Telegram-ботом TIGRAN MODZ для OWNER.\n"
        "Пользователь даёт команды на естественном языке.\n"
        "Ты должен ВЕРНУТЬ ТОЛЬКО валидный JSON без markdown, без пояснений.\n\n"
        "Формат: {\"action\": \"ТИП\", \"params\": {...}}\n\n"
        "action: create_key, revoke_key, list_keys, list_sessions, list_admins, "
        "add_admin, del_admin, set_role, stats, backup, help, chat.\n"
        "Если это НЕ команда — верни {\"action\":\"chat\",\"params\":{\"question\":\"...\"}}\n"
    )
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text[:1500]}
                ],
                "max_tokens": 300, "temperature": 0.1
            }, timeout=25)
        if r.status_code != 200:
            return None
        content = r.json()['choices'][0]['message']['content'].strip()
        content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content, flags=re.MULTILINE).strip()
        m = re.search(r'\{[\s\S]*\}', content)
        if m:
            content = m.group(0)
        return json.loads(content)
    except Exception as e:
        print(f"[OwnerAI] error: {e}")
        return None


def tg_owner_execute_ai(chat_id, action_data):
    act = action_data.get('action', 'chat')
    params = action_data.get('params') or {}
    if act == 'chat':
        return False
    if act == 'create_key':
        custom = params.get('custom_key')
        if custom:
            new_key = normalize_key(custom)
            if new_key in generated_keys:
                tg_send(chat_id, f"⚠️ Ключ уже существует: <code>{new_key}</code>")
                return True
        else:
            new_key = generate_key(params.get('prefix', 'TIGRAN-MDZ-PROXY'))
        try: limit = max(1, int(params.get('limit', 1)))
        except: limit = 1
        try: days = max(1, int(params.get('days', 7)))
        except: days = 7
        generated_keys[new_key] = {
            'prefix': new_key.rsplit('-', 1)[0] if '-' in new_key else 'TIGRAN-MDZ-PROXY',
            'limit': limit, 'days': days,
            'created': datetime.now().isoformat(), 'used_ips': []
        }
        save_data()
        tg_log("ai_genkey", chat_id, new_key)
        tg_send(chat_id, f"🤖 <b>AI создал ключ</b>\n\n<code>{new_key}</code>\n\nЛимит IP: {limit}\nДней: {days}")
        return True
    if act == 'revoke_key':
        key = normalize_key(params.get('key', ''))
        if key in generated_keys:
            for ip in generated_keys[key]['used_ips']:
                registered_ips.pop(ip, None); key_expiry.pop(ip, None)
            del generated_keys[key]; save_data()
            tg_log("ai_revoke", chat_id, key)
            tg_send(chat_id, f"🤖 <b>AI удалил ключ:</b>\n<code>{key}</code>")
        else:
            tg_send(chat_id, f"🤖 Ключ <code>{key}</code> не найден.")
        return True
    if act == 'list_keys':
        if not generated_keys:
            tg_send(chat_id, "🤖 Ключей нет.")
            return True
        lines = ["🤖 <b>Ключи:</b>\n"]
        for k, v in list(generated_keys.items())[:30]:
            lines.append(f"<code>{k}</code> — {len(v['used_ips'])}/{v['limit']} · {v['days']}d")
        tg_send(chat_id, "\n".join(lines))
        return True
    if act == 'list_sessions':
        if not registered_ips:
            tg_send(chat_id, "🤖 Нет активных сессий.")
            return True
        lines = ["🤖 <b>Сессии:</b>\n"]
        for ip, key in list(registered_ips.items())[:30]:
            exp = key_expiry.get(ip)
            exp_str = exp.strftime('%d/%m/%Y') if exp else '-'
            lines.append(f"<code>{ip}</code> — {key} · до {exp_str}")
        tg_send(chat_id, "\n".join(lines))
        return True
    if act == 'list_admins':
        data = load_admins_data()
        admins = data.get('admins', [])
        lines = [f"🤖 👑 <b>Owner:</b> <code>{TELEGRAM_ADMIN_ID}</code>\n"]
        if admins:
            lines.append(f"⭐🎖 <b>Админы ({len(admins)}):</b>")
            for a in admins:
                em = role_emoji(a.get('role', 'admin'))
                lines.append(f"{em} <code>{a.get('id')}</code> [{a.get('role','admin')}]")
        else:
            lines.append("(кроме owner никого)")
        tg_send(chat_id, "\n".join(lines))
        return True
    if act == 'add_admin':
        new_id = str(params.get('id', '')).strip()
        new_role = (params.get('role') or 'admin').lower()
        if not new_id.isdigit():
            tg_send(chat_id, "🤖 ID должен быть числом.")
            return True
        if new_role not in ('admin', 'superadmin'):
            new_role = 'admin'
        if new_id == str(TELEGRAM_ADMIN_ID):
            tg_send(chat_id, "🤖 Это уже owner.")
            return True
        data = load_admins_data()
        if any(str(a.get('id')) == new_id for a in data['admins']):
            tg_send(chat_id, f"🤖 <code>{new_id}</code> уже админ.")
            return True
        data['admins'].append({
            "id": new_id, "name": "", "role": new_role,
            "added_by": str(chat_id), "added_at": datetime.now().isoformat()
        })
        save_admins_data(data)
        tg_log("ai_addadmin", chat_id, f"{new_id}:{new_role}")
        em = role_emoji(new_role)
        tg_send(chat_id, f"🤖 ✅ {em} Добавлен <code>{new_id}</code> [{new_role}]")
        try: tg_send(new_id, f"{em} Тебя назначили ({new_role})!\nНапиши /help")
        except: pass
        return True
    if act == 'del_admin':
        del_id = str(params.get('id', '')).strip()
        data = load_admins_data()
        if not any(str(a.get('id')) == del_id for a in data['admins']):
            tg_send(chat_id, f"🤖 <code>{del_id}</code> не найден.")
            return True
        data['admins'] = [a for a in data['admins'] if str(a.get('id')) != del_id]
        save_admins_data(data)
        tg_log("ai_deladmin", chat_id, del_id)
        tg_send(chat_id, f"🤖 🗑 Удалён <code>{del_id}</code>")
        return True
    if act == 'set_role':
        tgt_id = str(params.get('id', '')).strip()
        new_role = (params.get('role') or '').lower()
        if new_role not in ('admin', 'superadmin'):
            tg_send(chat_id, "🤖 Роль: admin или superadmin.")
            return True
        data = load_admins_data()
        found = False
        for a in data['admins']:
            if str(a.get('id')) == tgt_id:
                a['role'] = new_role; found = True; break
        if not found:
            tg_send(chat_id, f"🤖 <code>{tgt_id}</code> не найден.")
            return True
        save_admins_data(data)
        tg_send(chat_id, f"🤖 ✅ <code>{tgt_id}</code> → {role_emoji(new_role)} {new_role}")
        return True
    if act == 'stats':
        tg_send(chat_id,
            f"🤖 <b>Статистика</b>\n\n"
            f"Ключей: {len(generated_keys)}\n"
            f"Активных IP: {len(registered_ips)}\n"
            f"AI-запросов: {sum(len(v) for v in _ai_requests.values())}\n"
            f"Админов: {1 + len(load_admins_data().get('admins', []))}")
        return True
    if act == 'backup':
        try:
            payload = {
                "generated_keys": generated_keys, "registered_ips": registered_ips,
                "key_expiry": {k: v.isoformat() for k, v in key_expiry.items()},
                "admins": load_admins_data(),
                "exported_at": datetime.now().isoformat()
            }
            text_b = json.dumps(payload, ensure_ascii=False, indent=2)
            if len(text_b) < 3500:
                tg_send(chat_id, f"🤖 <b>Backup</b>\n\n<pre>{text_b}</pre>")
            else:
                for i in range(0, len(text_b), 3500):
                    tg_send(chat_id, f"<pre>{text_b[i:i+3500]}</pre>")
        except Exception as e:
            tg_send(chat_id, f"🤖 Ошибка: {e}")
        return True
    if act == 'help':
        return False
    return False


# ==================== CALLBACK HANDLER ====================
def tg_handle_callback(callback):
    chat_id = callback["message"]["chat"]["id"]
    msg_id = callback["message"]["message_id"]
    data = callback.get("data", "")
    cb_id = callback["id"]
    role = get_user_role(chat_id)
    if role == "guest":
        tg_answer_callback(cb_id, "⛔ Доступ запрещён", alert=True)
        return
    tg_answer_callback(cb_id, "")
    try:
        if data == "menu_back":
            tg_main_menu(chat_id); return
        if data == "noop":
            return
        if data.startswith("menu_keys_"):
            try: page = int(data.split("_")[-1])
            except: page = 0
            tg_menu_keys(chat_id, msg_id, page); return
        if data == "menu_sessions":
            tg_menu_sessions(chat_id, msg_id); return
        if data == "menu_stats":
            tg_menu_stats(chat_id, msg_id); return
        if data == "menu_admins":
            tg_menu_admins(chat_id, msg_id); return
        if data == "menu_quick":
            tg_menu_quick(chat_id, msg_id); return
        if data == "menu_utils":
            tg_menu_utils(chat_id, msg_id); return
        if data == "menu_reports":
            tg_menu_reports(chat_id, msg_id); return
        if data == "menu_fun":
            tg_menu_fun(chat_id, msg_id); return
        if data == "menu_security":
            tg_menu_security(chat_id, msg_id); return
        if data == "menu_tasks":
            if not is_main_admin(chat_id):
                tg_answer_callback(cb_id, "⛔ Только owner", alert=True); return
            tg_menu_tasks(chat_id, msg_id); return
        if data == "menu_search":
            tg_edit_message(chat_id, msg_id,
                "🔍 <b>Поиск ключа</b>\n\nНапиши: <code>/find ЧАСТЬ_КЛЮЧА</code>\nНапример: <code>/find MDZ</code>",
                [[{"text": "◀ Назад", "callback_data": "menu_back"}]])
            return
        if data == "quick_genkey":
            new_key = generate_key("TIGRAN-MDZ-PROXY")
            generated_keys[new_key] = {
                'prefix': 'TIGRAN-MDZ-PROXY', 'limit': 1, 'days': 7,
                'created': datetime.now().isoformat(), 'used_ips': []
            }
            save_data()
            tg_log("genkey_btn", chat_id, new_key)
            tg_send(chat_id, f"✅ <b>Ключ создан</b>\n\n<code>{new_key}</code>\n\nЛимит: 1 IP\nДней: 7")
            return
        if data == "quick_genkey_big":
            new_key = generate_key("TIGRAN-MDZ-PROXY")
            generated_keys[new_key] = {
                'prefix': 'TIGRAN-MDZ-PROXY', 'limit': 5, 'days': 30,
                'created': datetime.now().isoformat(), 'used_ips': []
            }
            save_data()
            tg_log("genkey_btn", chat_id, new_key)
            tg_send(chat_id, f"✅ <b>Ключ создан</b>\n\n<code>{new_key}</code>\n\nЛимит: 5 IP\nДней: 30")
            return
        if data == "quick_bulk10":
            if not is_super_or_owner(chat_id):
                tg_answer_callback(cb_id, "⛔ Нет прав", alert=True); return
            keys = tg_bulk_create_keys(chat_id, 10, "TIGRAN-MDZ-PROXY", 1, 7)
            lines = [f"✅ <b>Создано 10 ключей:</b>\n"]
            for k in keys:
                lines.append(f"<code>{k}</code>")
            tg_send(chat_id, "\n".join(lines))
            return
        if data == "menu_addadmin":
            if not is_super_or_owner(chat_id):
                tg_answer_callback(cb_id, "⛔ Нет прав", alert=True); return
            tg_send(chat_id,
                "➕ <b>Добавление админа</b>\n\n"
                "Напиши команду:\n<code>/addadmin 123456789 admin</code>\n"
                "или для супер-админа:\n<code>/addadmin 123456789 superadmin</code>")
            return
        if data == "menu_backup":
            if not is_main_admin(chat_id):
                tg_answer_callback(cb_id, "⛔ Только owner", alert=True); return
            payload = {
                "generated_keys": generated_keys, "registered_ips": registered_ips,
                "key_expiry": {k: v.isoformat() for k, v in key_expiry.items()},
                "admins": load_admins_data(), "exported_at": datetime.now().isoformat()
            }
            text_b = json.dumps(payload, ensure_ascii=False, indent=2)
            if len(text_b) < 3500:
                tg_send(chat_id, f"💾 <b>Backup</b>\n\n<pre>{text_b}</pre>")
            else:
                for i in range(0, len(text_b), 3500):
                    tg_send(chat_id, f"<pre>{text_b[i:i+3500]}</pre>")
            return
        if data == "menu_logs":
            if not is_main_admin(chat_id):
                tg_answer_callback(cb_id, "⛔ Только owner", alert=True); return
            adata = load_admins_data()
            logs = adata.get('logs', [])[-15:]
            if not logs:
                tg_edit_message(chat_id, msg_id, "Логов пока нет.",
                    [[{"text": "◀ Назад", "callback_data": "menu_back"}]])
                return
            lines = ["📜 <b>Последние действия:</b>\n"]
            for l in logs:
                t = l.get('at', '')[:16].replace('T', ' ')
                lines.append(f"<code>{t}</code> · {l.get('by')} · <b>{l.get('action')}</b> {l.get('target','')}")
            tg_edit_message(chat_id, msg_id, "\n".join(lines),
                [[{"text": "◀ Назад", "callback_data": "menu_back"}]])
            return
        if data == "menu_broadcast":
            if not is_main_admin(chat_id):
                tg_answer_callback(cb_id, "⛔ Только owner", alert=True); return
            tg_send(chat_id, "📢 Напиши:\n<code>/broadcast Твой текст</code>")
            return
        if data == "menu_setpass":
            if not is_main_admin(chat_id):
                tg_answer_callback(cb_id, "⛔ Только owner", alert=True); return
            tg_send(chat_id, "🔑 Напиши:\n<code>/setpass НовыйПароль123</code>")
            return
        if data == "menu_settings":
            if not is_main_admin(chat_id):
                tg_answer_callback(cb_id, "⛔ Только owner", alert=True); return
            settings_text = (
                f"⚙ <b>Настройки сервера</b>\n\n"
                f"🔒 Secure cookies: включены\n"
                f"🛡 Security headers: включены\n"
                f"⏱ Rate-limit AI: <b>{AI_RATE_LIMIT}/час</b>\n"
                f"🔐 Max login попыток: <b>{MAX_LOGIN_ATTEMPTS}</b>\n"
                f"🌍 Trust proxy: <b>{'Да' if TRUST_PROXY else 'Нет'}</b>"
            )
            tg_edit_message(chat_id, msg_id, settings_text,
                [[{"text": "◀ Назад", "callback_data": "menu_back"}]])
            return
        tg_answer_callback(cb_id, "⚠ Неизвестное действие", alert=False)
    except Exception as e:
        print(f"[TG] callback error: {e}")
        tg_send(chat_id, f"❌ Ошибка: {e}")


# ==================== КОМАНДЫ БОТА ====================
def tg_handle_command(chat_id, text):
    role = get_user_role(chat_id)
    if role == "guest":
        tg_send(chat_id,
            f"⛔ <b>Доступ запрещён</b>\n\nТвой ID: <code>{chat_id}</code>\n\n"
            "Передай этот ID главному админу, чтобы получить доступ.")
        return

    tg_admin_register_activity(chat_id, "command")

    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower() if parts else ""
    args = parts[1].split() if len(parts) > 1 else []
    rest = parts[1] if len(parts) > 1 else ""

    # ===== /start /help =====
    if cmd in ("/start", "/help"):
        is_owner = role == "owner"
        is_super = role in ("owner", "superadmin")
        help_text = (
            f"{role_emoji(role)} <b>TIGRAN MODZ BOT</b>\n"
            f"Роль: <b>{role.upper()}</b> · ID: <code>{chat_id}</code>\n\n"
            "🔑 <b>Ключи:</b>\n"
            "/genkey [prefix] [limit] [days]\n"
            "/keys — список ключей\n"
            "/revoke KEY — отозвать\n"
            "/extend KEY 30 — продлить\n"
            "/qr KEY — QR-код\n"
            "/bulk 10 PREFIX 1 7 — массово\n"
            "/export csv|json — экспорт\n"
            "/sessions — активные сессии\n"
            "/stats — статистика\n"
            "/find ЧАСТЬ — поиск ключа\n\n"
            "🛠 <b>Утилиты:</b>\n"
            "/short URL · /hash · /b64enc · /b64dec\n"
            "/pass 20 · /weather · /currency\n\n"
            "🎮 <b>Развлечения:</b>\n"
            "/bonus · /rep · /quiz · /guess · /events\n\n"
        )
        if is_super:
            help_text += (
                "\n🎖 <b>Управление админами:</b>\n"
                "/admins — список\n"
                "/addadmin ID [role]\n"
                "/deladmin ID\n"
                "/setrole ID role\n"
                "/dm ID Текст — ЛС админу\n"
                "/poll Вопрос|A|B\n"
            )
        if is_owner:
            help_text += (
                "\n👑 <b>Только owner:</b>\n"
                "/setpass ПАРОЛЬ · /broadcast ТЕКСТ\n"
                "/backup · /logs · /report · /heatmap\n"
                "/activity · /ban IP · /unban IP\n"
                "/schedule broadcast 3600 Текст\n"
                "/tasks · /sheets · /email · /github · /stripe\n"
            )
        help_text += "\n🤖 <b>AI:</b> напиши без / — ответит AI\n🖼 <b>Фото:</b> отправь — распознает"
        tg_send(chat_id, help_text)
        tg_main_menu(chat_id)
        return

    # ===== КЛЮЧИ =====
    if cmd == "/genkey":
        prefix = args[0] if len(args) > 0 else "TIGRAN-MDZ-PROXY"
        try: limit = max(1, int(args[1])) if len(args) > 1 else 1
        except: limit = 1
        try: days = max(1, int(args[2])) if len(args) > 2 else 7
        except: days = 7
        new_key = generate_key(prefix)
        generated_keys[new_key] = {
            'prefix': normalize_key(prefix) or "TIGRAN-MDZ-PROXY",
            'limit': limit, 'days': days,
            'created': datetime.now().isoformat(), 'used_ips': []
        }
        save_data()
        tg_log("genkey", chat_id, new_key)
        tg_send(chat_id, f"✅ <b>Ключ создан</b>\n\n<code>{new_key}</code>\n\nЛимит IP: {limit}\nДней: {days}")
        return

    if cmd == "/keys":
        if not generated_keys:
            tg_send(chat_id, "Нет ключей."); return
        lines = ["📋 <b>Ключи:</b>\n"]
        for k, v in list(generated_keys.items())[:30]:
            lines.append(f"<code>{k}</code> — {len(v['used_ips'])}/{v['limit']} · {v['days']}d")
        tg_send(chat_id, "\n".join(lines))
        return

    if cmd == "/revoke":
        if not args: tg_send(chat_id, "Использование: /revoke KEY"); return
        key = normalize_key(args[0])
        if key in generated_keys:
            for ip in generated_keys[key]['used_ips']:
                registered_ips.pop(ip, None); key_expiry.pop(ip, None)
            del generated_keys[key]; save_data()
            tg_log("revoke", chat_id, key)
            tg_send(chat_id, f"🗑 Отозван: <code>{key}</code>")
        else:
            tg_send(chat_id, "❌ Ключ не найден.")
        return

    if cmd == "/bulk":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ Нет прав."); return
        if len(args) < 1:
            tg_send(chat_id, "Использование:\n<code>/bulk 10 TIGRAN-MDZ 1 7</code>\n(кол-во, префикс, лимит IP, дней)")
            return
        cnt = args[0]
        pf = args[1] if len(args) > 1 else "TIGRAN-MDZ-PROXY"
        lim = args[2] if len(args) > 2 else 1
        days_ = args[3] if len(args) > 3 else 7
        keys = tg_bulk_create_keys(chat_id, cnt, pf, lim, days_)
        lines = [f"✅ <b>Создано {len(keys)} ключей:</b>\n"]
        for k in keys[:30]:
            lines.append(f"<code>{k}</code>")
        tg_send(chat_id, "\n".join(lines))
        return

    if cmd == "/export":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ Нет прав."); return
        fmt = args[0].lower() if args else "csv"
        tg_send(chat_id, "📦 Готовлю файл...")
        tg_export_keys(chat_id, fmt)
        return

    if cmd == "/extend":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ Нет прав."); return
        if len(args) < 2:
            tg_send(chat_id, "Использование: <code>/extend KEY 30</code>"); return
        ok, msg = tg_extend_key(args[0], args[1])
        tg_send(chat_id, f"{'✅' if ok else '❌'} {msg}")
        return

    if cmd == "/qr":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ Нет прав."); return
        if not args:
            tg_send(chat_id, "Использование: <code>/qr КЛЮЧ</code>"); return
        tg_send(chat_id, "🔗 Генерирую QR...")
        tg_qr_for_key(chat_id, args[0])
        return

    if cmd == "/sessions":
        if not registered_ips:
            tg_send(chat_id, "Нет сессий."); return
        lines = ["🌐 <b>Сессии:</b>\n"]
        for ip, key in list(registered_ips.items())[:30]:
            exp = key_expiry.get(ip)
            exp_str = exp.strftime('%d/%m/%Y') if exp else '-'
            lines.append(f"<code>{ip}</code> — {key} · до {exp_str}")
        tg_send(chat_id, "\n".join(lines))
        return

    if cmd == "/stats":
        tg_send(chat_id,
            f"📊 <b>Статистика</b>\n\n"
            f"Ключей: {len(generated_keys)}\n"
            f"Активных IP: {len(registered_ips)}\n"
            f"AI-запросов: {sum(len(v) for v in _ai_requests.values())}\n"
            f"Админов: {1 + len(load_admins_data().get('admins', []))}\n"
            f"Забанено: {len(BANNED_IPS) + len(IP_BLACKLIST)}")
        return

    if cmd == "/find":
        if not args:
            tg_send(chat_id, "Использование: <code>/find ЧАСТЬ_КЛЮЧА</code>"); return
        query = normalize_key(" ".join(args))
        found = [(k, v) for k, v in generated_keys.items() if query in k]
        if not found:
            tg_send(chat_id, f"🔍 По запросу <code>{query}</code> ничего не найдено."); return
        lines = [f"🔍 <b>Найдено: {len(found)}</b>\n"]
        for k, v in found[:15]:
            lines.append(f"<code>{k}</code> — {len(v['used_ips'])}/{v['limit']} · {v['days']}d")
        tg_send(chat_id, "\n".join(lines))
        return

    # ===== УТИЛИТЫ =====
    if cmd == "/short":
        if not args:
            tg_send(chat_id, "Использование: <code>/short URL</code>"); return
        res = tg_url_shorten(args[0])
        tg_send(chat_id, f"🔗 <b>Короткая ссылка:</b>\n{res}" if res else "❌ Не удалось сократить.")
        return

    if cmd == "/hash":
        if not args:
            tg_send(chat_id, "Использование: <code>/hash текст</code>\nили <code>/hash md5 текст</code>"); return
        if args[0].lower() in ("md5", "sha1", "sha256", "sha512"):
            algo = args[0].lower(); txt = " ".join(args[1:])
        else:
            algo = "sha256"; txt = " ".join(args)
        h = tg_hash_text(txt, algo)
        tg_send(chat_id, f"🔐 <b>{algo.upper()}:</b>\n<code>{h}</code>")
        return

    if cmd == "/b64enc":
        if not args:
            tg_send(chat_id, "Использование: <code>/b64enc текст</code>"); return
        tg_send(chat_id, f"📦 <code>{tg_b64_encode(' '.join(args))}</code>")
        return

    if cmd == "/b64dec":
        if not args:
            tg_send(chat_id, "Использование: <code>/b64dec строка</code>"); return
        res = tg_b64_decode(args[0])
        tg_send(chat_id, f"📦 <code>{res}</code>" if res else "❌ Неверный Base64")
        return

    if cmd == "/pass":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ Нет прав."); return
        length = args[0] if args else 16
        pw = tg_password_gen(length)
        tg_send(chat_id, f"🔑 <b>Пароль:</b>\n<code>{pw}</code>")
        return

    if cmd == "/weather":
        if not args:
            tg_send(chat_id, "Использование: <code>/weather Moscow</code>"); return
        tg_send(chat_id, "🌤 Загружаю...")
        res = tg_weather(" ".join(args))
        tg_send(chat_id, res or "❌ Не нашёл город.")
        return

    if cmd == "/currency":
        if len(args) < 3:
            tg_send(chat_id, "Использование: <code>/currency 100 USD RUB</code>"); return
        res = tg_currency_convert(args[0], args[1].upper(), args[2].upper())
        tg_send(chat_id, res or "❌ Не удалось получить курс.")
        return

    # ===== ОТЧЁТЫ =====
    if cmd == "/report":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только owner."); return
        tg_send(chat_id, "📊 Собираю отчёт...")
        tg_send_daily_report()
        return

    if cmd == "/heatmap":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ Нет прав."); return
        tg_send(chat_id, tg_ip_heatmap())
        return

    if cmd == "/activity":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только owner."); return
        tg_send(chat_id, tg_admins_activity_report())
        return

    # ===== АВТОМАТИЗАЦИЯ =====
    if cmd == "/schedule":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только owner."); return
        if len(args) < 3:
            tg_send(chat_id, "Использование:\n<code>/schedule broadcast 3600 Текст</code>")
            return
        action = args[0]
        try: delay = int(args[1])
        except: tg_send(chat_id, "❌ Неверное число секунд"); return
        text_arg = " ".join(args[2:]) if len(args) > 2 else ""
        tg_schedule_task(chat_id, delay, action, {'text': text_arg})
        tg_send(chat_id, f"⏰ Запланировано <b>{action}</b> через {delay} секунд.")
        return

    if cmd == "/tasks":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только owner."); return
        if not SCHEDULED_TASKS:
            tg_send(chat_id, "📭 Нет запланированных задач."); return
        lines = [f"⏰ <b>Задачи ({len(SCHEDULED_TASKS)}):</b>\n"]
        for t in SCHEDULED_TASKS:
            left = int(t['when'] - time.time())
            lines.append(f"• <code>{t['id'][:12]}</code> · {t['action']} · через {left}с")
        tg_send(chat_id, "\n".join(lines))
        return

    # ===== БЕЗОПАСНОСТЬ =====
    if cmd == "/ban":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только owner."); return
        if not args:
            tg_send(chat_id, "Использование: <code>/ban 1.2.3.4 24</code>"); return
        ip = args[0]
        hours = args[1] if len(args) > 1 else 24
        msg = tg_ban_ip(ip, hours)
        tg_send(chat_id, f"🚫 {msg}")
        return

    if cmd == "/unban":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только owner."); return
        if not args:
            tg_send(chat_id, "Использование: <code>/unban 1.2.3.4</code>"); return
        msg = tg_unban_ip(args[0])
        tg_send(chat_id, f"✅ {msg}")
        return

    if cmd == "/iplookup":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ Нет прав."); return
        if not args:
            tg_send(chat_id, "Использование: <code>/iplookup 8.8.8.8</code>"); return
        geo = tg_get_ip_geo(args[0])
        tg_send(chat_id, f"🌍 <b>IP {args[0]}</b>\n\n{geo}" if geo else "❌ Не удалось определить.")
        return

    # ===== AI ДОП =====
    if cmd == "/translate":
        if not args:
            tg_send(chat_id, "Использование: <code>/translate hello world</code>"); return
        tg_send(chat_id, "🌐 Перевожу...")
        res = tg_ai_translate(" ".join(args))
        tg_send(chat_id, res or "❌ Не удалось.")
        return

    if cmd == "/image":
        if not args:
            tg_send(chat_id, "Использование: <code>/image кот в космосе</code>"); return
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ Нет прав."); return
        tg_send(chat_id, "🎨 Генерирую картинку... (30-60 сек)")
        tg_ai_generate_image(chat_id, " ".join(args))
        return

    # ===== АДМИНЫ =====
    if cmd == "/admins":
        data = load_admins_data()
        admins = data.get('admins', [])
        lines = [f"👑 <b>Owner:</b>\n<code>{TELEGRAM_ADMIN_ID}</code>\n"]
        if admins:
            lines.append(f"⭐🎖 <b>Админы ({len(admins)}):</b>")
            for a in admins:
                em = role_emoji(a.get('role', 'admin'))
                nm = f" — {a.get('name')}" if a.get('name') else ""
                lines.append(f"{em} <code>{a.get('id')}</code>{nm} [{a.get('role','admin')}]")
        else:
            lines.append("(кроме owner никого)")
        tg_send(chat_id, "\n".join(lines))
        return

    if cmd == "/addadmin":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ Только owner/superadmin."); return
        if not args:
            tg_send(chat_id, "Использование:\n<code>/addadmin 123456789 admin</code>"); return
        new_id = str(args[0]).strip()
        new_role = args[1].lower() if len(args) > 1 else "admin"
        if not new_id.isdigit():
            tg_send(chat_id, "❌ ID должен быть числом."); return
        if new_role not in ("admin", "superadmin"):
            tg_send(chat_id, "❌ Роль: admin или superadmin"); return
        if new_role == "superadmin" and not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только 👑 OWNER может назначать ⭐ superadmin."); return
        if new_id == str(TELEGRAM_ADMIN_ID):
            tg_send(chat_id, "⚠️ Это уже owner."); return
        data = load_admins_data()
        if any(str(a.get('id')) == new_id for a in data['admins']):
            tg_send(chat_id, f"⚠️ <code>{new_id}</code> уже в списке."); return
        data['admins'].append({
            "id": new_id, "name": "", "role": new_role,
            "added_by": str(chat_id), "added_at": datetime.now().isoformat()
        })
        save_admins_data(data)
        tg_log("addadmin", chat_id, f"{new_id}:{new_role}")
        em = role_emoji(new_role)
        tg_send(chat_id, f"✅ {em} <b>Добавлен:</b> <code>{new_id}</code> [{new_role}]")
        try: tg_send(new_id, f"{em} Тебя назначили ({new_role})!\nНапиши /help")
        except: pass
        return

    if cmd == "/deladmin":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ Нет прав."); return
        if not args:
            tg_send(chat_id, "Использование: /deladmin 123456789"); return
        del_id = str(args[0]).strip()
        data = load_admins_data()
        target = [a for a in data['admins'] if str(a.get('id')) == del_id]
        if not target:
            tg_send(chat_id, f"❌ <code>{del_id}</code> не найден."); return
        if target[0].get('role') == "superadmin" and not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только 👑 OWNER может удалять ⭐ superadmin."); return
        data['admins'] = [a for a in data['admins'] if str(a.get('id')) != del_id]
        save_admins_data(data)
        tg_log("deladmin", chat_id, del_id)
        tg_send(chat_id, f"🗑 Удалён: <code>{del_id}</code>")
        return

    if cmd == "/setrole":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ Нет прав."); return
        if len(args) < 2:
            tg_send(chat_id, "Использование: /setrole ID role"); return
        tgt_id, new_role = str(args[0]).strip(), args[1].lower()
        if new_role not in ("admin", "superadmin"):
            tg_send(chat_id, "❌ Роль: admin или superadmin"); return
        if new_role == "superadmin" and not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только 👑 OWNER может давать ⭐ superadmin."); return
        data = load_admins_data()
        found = False
        for a in data['admins']:
            if str(a.get('id')) == tgt_id:
                a['role'] = new_role; found = True; break
        if not found:
            tg_send(chat_id, "❌ Не найден."); return
        save_admins_data(data)
        tg_log("setrole", chat_id, f"{tgt_id}:{new_role}")
        tg_send(chat_id, f"✅ <code>{tgt_id}</code> → {role_emoji(new_role)} {new_role}")
        return

    if cmd == "/dm":
        if get_user_role(chat_id) == "guest":
            tg_send(chat_id, "⛔ Нет прав."); return
        if len(args) < 2:
            tg_send(chat_id, "Использование: <code>/dm 123456789 Текст</code>"); return
        to_id = args[0]
        text_msg = " ".join(args[1:])
        res = tg_admin_dm(chat_id, to_id, text_msg)
        tg_send(chat_id, res)
        return

    if cmd == "/poll":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ Нет прав."); return
        raw = " ".join(args)
        if "|" not in raw:
            tg_send(chat_id, "Использование: <code>/poll Вопрос|A|B|C</code>"); return
        parts_p = [p.strip() for p in raw.split("|") if p.strip()]
        if len(parts_p) < 3:
            tg_send(chat_id, "❌ Нужно минимум 3 части: Вопрос|A|B"); return
        tg_poll_create(chat_id, parts_p[0], parts_p[1:])
        return

    # ===== РАЗВЛЕЧЕНИЯ =====
    if cmd == "/bonus":
        tg_send(chat_id, tg_daily_bonus(chat_id))
        return

    if cmd == "/rep":
        cid = str(chat_id)
        tg_send(chat_id, f"⭐ Твоя репутация: <b>{USER_REPUTATION.get(cid, 0)}</b>")
        return

    if cmd == "/quiz":
        QUIZ_ANSWERS[str(chat_id)] = tg_quiz_start(chat_id)
        return

    if cmd == "/guess":
        tg_guess_number_start(chat_id)
        return

    if cmd == "/events":
        tg_send(chat_id, tg_events_calendar())
        return

    # ===== ИНТЕГРАЦИИ =====
    if cmd == "/sheets":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только owner."); return
        ok, msg = tg_google_sheets_sync()
        tg_send(chat_id, f"{'✅' if ok else '❌'} {msg}")
        return

    if cmd == "/email":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только owner."); return
        if len(args) < 2:
            tg_send(chat_id, "Использование: <code>/email a@b.com Тема|Текст</code>"); return
        to_email = args[0]
        raw = " ".join(args[1:])
        if "|" in raw:
            subj, body = raw.split("|", 1)
        else:
            subj, body = "TIGRAN MODZ", raw
        ok, msg = tg_send_email(to_email.strip(), subj.strip(), body.strip())
        tg_send(chat_id, f"{'✅' if ok else '❌'} {msg}")
        return

    if cmd == "/youtube":
        if not args:
            tg_send(chat_id, "Использование: <code>/youtube URL</code>"); return
        res = tg_send_youtube_info(args[0])
        tg_send(chat_id, res or "❌ Не нашёл видео.")
        return

    if cmd == "/github":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только owner."); return
        res = tg_github_status()
        tg_send(chat_id, res or "❌ GITHUB_REPO не настроен.")
        return

    if cmd == "/stripe":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только owner."); return
        if not args:
            tg_send(chat_id, "Использование: <code>/stripe 10</code> (USD)"); return
        try: amt = float(args[0])
        except: tg_send(chat_id, "❌ Неверная сумма."); return
        link = tg_stripe_payment_link(amt)
        tg_send(chat_id, f"💳 <b>Ссылка:</b>\n{link}" if link else "❌ Stripe не настроен.")
        return

    # ===== OWNER-ONLY =====
    if cmd == "/setpass":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только 👑 OWNER."); return
        if not rest.strip():
            tg_send(chat_id, "Использование: <code>/setpass НовыйПароль</code>"); return
        global ADMIN_PASS_HASH
        try:
            new_hash = generate_password_hash(rest.strip())
            set_admin_pass_hash(new_hash)
            ADMIN_PASS_HASH = new_hash
            tg_log("setpass", chat_id, "")
            tg_send(chat_id, "✅ <b>Пароль изменён!</b>")
        except Exception as e:
            tg_send(chat_id, f"❌ Ошибка: {e}")
        return

    if cmd == "/broadcast":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только 👑 OWNER."); return
        if not rest.strip():
            tg_send(chat_id, "Использование: /broadcast Текст"); return
        data = load_admins_data()
        ok = 0
        for a in data.get('admins', []):
            try: tg_send(a['id'], f"📢 <b>РАССЫЛКА:</b>\n\n{rest}"); ok += 1
            except: pass
        tg_send(chat_id, f"✅ Отправлено {ok} админам.")
        return

    if cmd == "/backup":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только 👑 OWNER."); return
        try:
            payload = {
                "generated_keys": generated_keys, "registered_ips": registered_ips,
                "key_expiry": {k: v.isoformat() for k, v in key_expiry.items()},
                "admins": load_admins_data(), "exported_at": datetime.now().isoformat()
            }
            text_b = json.dumps(payload, ensure_ascii=False, indent=2)
            if len(text_b) < 3500:
                tg_send(chat_id, f"🤖 <b>Backup</b>\n\n<pre>{text_b}</pre>")
            else:
                for i in range(0, len(text_b), 3500):
                    tg_send(chat_id, f"<pre>{text_b[i:i+3500]}</pre>")
        except Exception as e:
            tg_send(chat_id, f"🤖 Ошибка: {e}")
        return

    if cmd == "/logs":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только 👑 OWNER."); return
        data = load_admins_data()
        logs = data.get('logs', [])[-15:]
        if not logs:
            tg_send(chat_id, "Логов пока нет."); return
        lines = ["📜 <b>Последние действия:</b>\n"]
        for l in logs:
            t = l.get('at', '')[:16].replace('T', ' ')
            lines.append(f"<code>{t}</code> · {l.get('by')} · <b>{l.get('action')}</b> {l.get('target','')}")
        tg_send(chat_id, "\n".join(lines))
        return

    # ===== AI =====
    if cmd.startswith("/"):
        tg_send(chat_id, "❓ Неизвестная команда. /help")
        return

    if not OPENAI_API_KEY:
        tg_send(chat_id, "🤖 AI не настроен.")
        return

    user_msg = text.strip()
    if not user_msg:
        return

    if role == "owner":
        tg_send(chat_id, "🧠 <i>Анализирую...</i>")
        action_data = tg_owner_ai_agent(chat_id, user_msg)
        if action_data:
            executed = tg_owner_execute_ai(chat_id, action_data)
            if executed:
                return

    tg_send(chat_id, "🤖 <i>Думаю...</i>")
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": (
                        "Ты AI-ассистент в Telegram-боте TIGRAN MODZ. "
                        "Отвечай кратко (до 500 символов), на языке пользователя.")},
                    {"role": "user", "content": user_msg[:1500]}
                ],
                "max_tokens": 500, "temperature": 0.7
            }, timeout=25)
        if r.status_code == 200:
            tg_send(chat_id, r.json()['choices'][0]['message']['content'])
        else:
            tg_send(chat_id, f"❌ AI HTTP {r.status_code}")
    except Exception as e:
        tg_send(chat_id, f"❌ AI ошибка: {str(e)[:120]}")


def tg_polling():
    global _tg_last_update_id
    if not TELEGRAM_BOT_TOKEN:
        print("[TG] Bot token not set, skipping")
        return
    print("[TG] Bot started")
    while True:
        try:
            params = {
                "timeout": 25,
                "allowed_updates": json.dumps(["message", "edited_message", "callback_query"])
            }
            if _tg_last_update_id:
                params["offset"] = _tg_last_update_id + 1
            data = tg_api("getUpdates", params)
            if data and data.get("ok"):
                for upd in data.get("result", []):
                    _tg_last_update_id = upd["update_id"]

                    if "callback_query" in upd:
                        try:
                            tg_handle_callback(upd["callback_query"])
                        except Exception as e:
                            print(f"[TG] callback error: {e}")
                        continue

                    msg = upd.get("message") or upd.get("edited_message")
                    if msg and "text" in msg:
                        txt = msg["text"]
                        cid_quiz = msg["chat"]["id"]
                        if tg_check_quiz(cid_quiz, txt):
                            continue
                        if tg_check_guess(cid_quiz, txt):
                            continue
                        tg_handle_command(cid_quiz, txt)
                    elif msg and "photo" in msg:
                        try:
                            chat_id_ph = msg["chat"]["id"]
                            role_ph = get_user_role(chat_id_ph)
                            if role_ph in ("owner", "superadmin", "admin"):
                                photos = msg["photo"]
                                file_id_ph = photos[-1]["file_id"]
                                tg_send(chat_id_ph, "🖼 <i>Анализирую изображение...</i>")
                                desc = tg_ai_describe_image(file_id_ph, chat_id_ph)
                                if desc:
                                    tg_send(chat_id_ph, f"🖼 <b>Описание:</b>\n\n{desc}")
                                else:
                                    tg_send(chat_id_ph, "❌ Не смог распознать.")
                        except Exception as e:
                            print(f"[TG] photo AI error: {e}")
        except Exception as e:
            print(f"[TG] Polling error: {e}")
        time.sleep(1)


# ==================== FLASK ROUTES ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/Po7eO', methods=['GET', 'POST'])
def login():
    client_ip = get_client_ip()
    if request.method == 'POST':
        if is_login_locked(client_ip):
            return render_template_string(LOGIN_PAGE, error="СЛИШКОМ МНОГО ПОПЫТОК."), 429
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        user_ok = secrets.compare_digest(username.encode(), ADMIN_USER.encode())
        pass_ok = check_password_hash(ADMIN_PASS_HASH, password)
        if user_ok and pass_ok:
            clear_login_attempts(client_ip)
            session.clear()
            session['logged_in'] = True
            session.permanent = True
            return redirect(url_for('admin_dashboard'))
        record_failed_login(client_ip)
        return render_template_string(LOGIN_PAGE, error="CREDENCIAIS INVÁLIDAS")
    return render_template_string(LOGIN_PAGE, error=None)


@app.route('/admin')
def admin_index():
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    return render_template_string(ADMIN_DASHBOARD,
                                 keys=generated_keys, ips=registered_ips,
                                 key_expiry=key_expiry)


@app.route('/admin/generate', methods=['POST'])
@login_required
def generate_new_key():
    data = request.get_json(silent=True) or {}
    key_prefix = normalize_key(data.get('prefix', 'TIGRAN-MDZ-PROXY')) or 'TIGRAN-MDZ-PROXY'
    ip_limit = max(1, int(data.get('limit', 1)))
    days_valid = max(1, int(data.get('days', 7)))
    new_key = generate_key(key_prefix)
    generated_keys[new_key] = {
        'prefix': key_prefix, 'limit': ip_limit, 'days': days_valid,
        'created': datetime.now().isoformat(), 'used_ips': []
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
    if tg_is_ip_banned(client_ip):
        return jsonify({'success': False, 'message': 'IP ЗАБАНЕН'}), 403
    data = request.get_json(silent=True) or {}
    key = normalize_key(data.get('key', ''))
    if client_ip in registered_ips:
        session['unlocked'] = True
        return jsonify({'success': True, 'message': 'JÁ REGISTRADO'})
    if key not in generated_keys:
        if not user_configs and not generated_keys:
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
    tg_notify_login_all(client_ip, key, expiry_date)
    return jsonify({
        'success': True, 'message': 'KEY VERIFICADA COM SUCESSO',
        'expires': expiry_date.isoformat()
    })


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
    safe_path = safe_join_cdn(path)
    if safe_path is None:
        return Response("Invalid path", status=400)
    path = safe_path
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


@app.route('/api/status', methods=['GET'])
def api_status():
    client_ip = get_client_ip()
    config = get_user_config(client_ip)
    return jsonify({
        "ip": client_ip, "config": config,
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
        'hs_neck': 'HS_NECK', 'hs_chest': 'HS_CHEST',
        'backjump_v1': 'BACKJUMPV1', 'high_sensi': 'HIGH_SENSI',
        'zig_zag_move': 'ZIG_ZAG_MOVE'
    }
    config_key = feature_map.get(feature)
    if not config_key:
        return jsonify({"error": "RECURSO INVÁLIDO"}), 400
    config = get_user_config(client_ip)
    config[config_key] = value
    save_data()
    return jsonify({"success": True, "ip": client_ip, "feature": feature, "value": value})


@app.route('/api/ip/check', methods=['GET'])
def api_ip_check():
    client_ip = get_client_ip()
    return jsonify({
        "ip": client_ip, "key": registered_ips.get(client_ip),
        "is_authorized": client_ip in registered_ips,
        "expires": key_expiry.get(client_ip, "").isoformat() if client_ip in key_expiry else None
    })


@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    if not OPENAI_API_KEY:
        return jsonify({'error': 'AI nao configurado.'}), 503
    client_ip = get_client_ip()
    if not check_rate_limit(_ai_requests, client_ip, AI_RATE_LIMIT, 3600):
        return jsonify({'error': 'Лимит AI запросов исчерпан.'}), 429
    data = request.get_json(silent=True) or {}
    message = str(data.get('message', ''))[:1500].strip()
    if not message:
        return jsonify({'error': 'Mensagem vazia'}), 400
    history = data.get('history', [])[-10:]
    model_choice = data.get('model', 'gpt-4o-mini')
    if model_choice not in ('gpt-4o-mini', 'gpt-4o', 'gpt-3.5-turbo'):
        model_choice = 'gpt-4o-mini'
    try:
        messages = [{
            "role": "system",
            "content": (
                "You are Tigran AI — a full-featured AI assistant, similar to ChatGPT. "
                "Answer ANY question on ANY topic. Detect language and reply in same language. "
                "You know about TIGRAN MODZ PROXY panel too."
            )
        }]
        for h in history:
            role = h.get('role', 'user')
            content = str(h.get('content', ''))[:800]
            if role in ('user', 'assistant') and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={"model": model_choice, "messages": messages, "max_tokens": 600, "temperature": 0.7},
            timeout=30)
        if r.status_code != 200:
            return jsonify({'error': f'AI HTTP {r.status_code}'}), 502
        return jsonify({'reply': r.json()['choices'][0]['message']['content']})
    except Exception as e:
        return jsonify({'error': f'Erro AI: {str(e)[:120]}'}), 500


@app.route('/api/user/info', methods=['GET'])
def user_info():
    client_ip = get_client_ip()
    info = {'ip': client_ip, 'country': None, 'country_code': None, 'city': None,
            'region': None, 'timezone': None, 'lat': None, 'lon': None, 'weather': None}
    try:
        r = requests.get(
            f"http://ip-api.com/json/{client_ip}?fields=status,country,countryCode,regionName,city,timezone,lat,lon",
            timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('status') == 'success':
                info['country'] = d.get('country')
                info['country_code'] = d.get('countryCode')
                info['city'] = d.get('city')
                info['region'] = d.get('regionName')
                info['timezone'] = d.get('timezone')
                info['lat'] = d.get('lat')
                info['lon'] = d.get('lon')
                if info['lat'] and info['lon']:
                    try:
                        w = requests.get(f"https://wttr.in/{info['lat']},{info['lon']}?format=j1", timeout=6)
                        if w.status_code == 200:
                            wd = w.json()
                            cur = wd['current_condition'][0]
                            info['weather'] = {
                                'temp': cur.get('temp_C'), 'feels': cur.get('FeelsLikeC'),
                                'desc': cur.get('weatherDesc', [{}])[0].get('value', ''),
                                'humidity': cur.get('humidity'), 'wind': cur.get('windspeedKmph'),
                                'icon': cur.get('weatherIconUrl', [{}])[0].get('value', ''),
                                'is_day': cur.get('isdaytime', 'yes') == 'yes'
                            }
                    except Exception:
                        pass
    except Exception:
        pass
    return jsonify(info)


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


@app.route('/ai')
def ai_page():
    return render_template_string(AI_PAGE)


@app.route('/unlock', methods=['POST'])
def unlock():
    return jsonify({'success': False, 'message': 'INFORME UMA KEY VÁLIDA'}), 400


@app.route('/tools')
def tools_page():
    if not session.get('unlocked'):
        return redirect(url_for('landing'))
    try:
        with open(os.path.join(BASE_DIR, 'tools.html'), 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "tools.html not found", 404


@app.route('/manifest.json')
def pwa_manifest():
    try:
        with open(os.path.join(BASE_DIR, 'manifest.json'), 'r', encoding='utf-8') as f:
            return Response(f.read(), mimetype='application/manifest+json')
    except FileNotFoundError:
        return Response('{}', mimetype='application/json')


@app.route('/service-worker.js')
def pwa_sw():
    try:
        with open(os.path.join(BASE_DIR, 'service-worker.js'), 'r', encoding='utf-8') as f:
            return Response(f.read(), mimetype='application/javascript')
    except FileNotFoundError:
        return Response('// not found', mimetype='application/javascript')


@app.route('/tools/<path:filename>')
def tools_assets(filename):
    try:
        with open(os.path.join(BASE_DIR, filename), 'rb') as f:
            return Response(f.read())
    except FileNotFoundError:
        return "Not found", 404


# ==================== NEON CSS/JS ====================
NEON_CSS = """
:root{--bg:#05030a;--panel:rgba(20,10,30,.6);--line:rgba(255,45,149,.25);--ink:#f5f3f7;--muted:#a08fa8;--p1:#ff2d95;--p2:#a855f7;--p3:#22d3ee}
*{box-sizing:border-box;margin:0;padding:0}
html,body{min-height:100vh;overflow-x:hidden}
body{background:var(--bg);color:var(--ink);font-family:'Inter','Segoe UI',Arial,sans-serif;position:relative;cursor:none}
#neonBg{position:fixed;inset:0;z-index:0;pointer-events:none}
#neonCursor{position:fixed;width:26px;height:26px;border-radius:50%;border:2px solid var(--p1);box-shadow:0 0 18px var(--p1),inset 0 0 12px var(--p1);pointer-events:none;z-index:9999;transition:transform .08s ease;transform:translate(-50%,-50%);mix-blend-mode:screen}
#neonCursor:after{content:"";position:absolute;top:50%;left:50%;width:4px;height:4px;border-radius:50%;background:var(--p3);box-shadow:0 0 10px var(--p3);transform:translate(-50%,-50%)}
.wrap{position:relative;z-index:2;min-height:100vh;display:grid;place-items:center;padding:24px}
.glass{background:var(--panel);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border:1px solid var(--line);border-radius:24px;box-shadow:0 0 60px rgba(255,45,149,.15),0 20px 60px rgba(0,0,0,.6);position:relative;overflow:hidden}
.glass:before{content:"";position:absolute;inset:0;border-radius:inherit;padding:1px;background:linear-gradient(135deg,rgba(255,45,149,.6),transparent 40%,transparent 60%,rgba(34,211,238,.5));-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none}
.neon-text{background:linear-gradient(90deg,var(--p1),var(--p2),var(--p3));-webkit-background-clip:text;background-clip:text;color:transparent;animation:neonHue 6s linear infinite}
@keyframes neonHue{0%{filter:hue-rotate(0)}100%{filter:hue-rotate(360deg)}}
.pulse{animation:pulse 2s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
.fade-in{animation:fadeIn .8s ease both}
@keyframes fadeIn{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
.glow-btn{position:relative;padding:16px 24px;border:0;border-radius:14px;background:linear-gradient(135deg,var(--p1),var(--p2));color:#fff;font-weight:900;letter-spacing:1.5px;text-transform:uppercase;cursor:none;overflow:hidden;transition:.25s;box-shadow:0 0 22px rgba(255,45,149,.5),0 8px 24px rgba(168,85,247,.35)}
.glow-btn:hover{transform:translateY(-2px) scale(1.02);box-shadow:0 0 40px rgba(255,45,149,.85),0 12px 30px rgba(168,85,247,.5)}
.field{position:relative;margin:18px 0}
.field label{display:block;font:700 10px monospace;letter-spacing:3px;color:var(--muted);margin-bottom:9px;text-transform:uppercase}
.field input{width:100%;padding:15px 16px;border-radius:12px;border:1px solid var(--line);background:rgba(5,3,10,.7);color:var(--ink);outline:none;font:inherit;transition:.25s}
.field input:focus{border-color:var(--p1);box-shadow:0 0 0 4px rgba(255,45,149,.15),0 0 25px rgba(255,45,149,.3)}
.scan{position:absolute;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--p3),transparent);animation:scan 4s linear infinite;opacity:.6}
@keyframes scan{0%{top:0}100%{top:100%}}
#aiBtn{position:fixed;bottom:22px;right:22px;width:62px;height:62px;border-radius:50%;background:linear-gradient(135deg,var(--p1),var(--p3));border:0;color:#fff;font-size:22px;cursor:none;z-index:9998;box-shadow:0 0 30px rgba(255,45,149,.7);animation:pulse 2.4s infinite}
#aiPanel{position:fixed;bottom:96px;right:22px;width:min(370px,92vw);max-height:70vh;background:rgba(15,8,22,.95);backdrop-filter:blur(16px);border:1px solid var(--line);border-radius:20px;z-index:9998;display:none;flex-direction:column;box-shadow:0 0 50px rgba(168,85,247,.5)}
#aiPanel.open{display:flex;animation:fadeIn .3s ease}
#aiHead{padding:14px 18px;border-bottom:1px solid var(--line);font:800 11px monospace;letter-spacing:2px;display:flex;justify-content:space-between;align-items:center;color:var(--p3)}
#aiLog{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;font-size:13px}
#aiLog .m{padding:9px 12px;border-radius:12px;max-width:85%;line-height:1.45;word-wrap:break-word}
#aiLog .u{align-self:flex-end;background:linear-gradient(135deg,var(--p1),var(--p2));color:#fff}
#aiLog .a{align-self:flex-start;background:rgba(34,211,238,.12);border:1px solid rgba(34,211,238,.3);color:#c8faff}
#aiForm{display:flex;border-top:1px solid var(--line)}
#aiInput{flex:1;padding:13px;background:transparent;border:0;color:#fff;outline:none;font:inherit}
#aiSend{padding:0 18px;background:linear-gradient(135deg,var(--p1),var(--p3));border:0;color:#fff;cursor:none;font-weight:900}
#muteBtn{position:fixed;top:18px;right:18px;z-index:9999;width:42px;height:42px;border-radius:50%;background:rgba(15,8,22,.85);border:1px solid var(--line);color:var(--p3);cursor:none;font-size:16px}
@media(max-width:720px){ #neonCursor{display:none}body{cursor:auto}}
"""

NEON_JS = """
(function(){
  const cur=document.getElementById('neonCursor');
  if(cur&&window.matchMedia('(pointer:fine)').matches){
    window.addEventListener('mousemove',e=>{cur.style.left=e.clientX+'px';cur.style.top=e.clientY+'px'});
    document.querySelectorAll('button,a,input').forEach(el=>{
      el.addEventListener('mouseenter',()=>cur.style.transform='translate(-50%,-50%) scale(1.6)');
      el.addEventListener('mouseleave',()=>cur.style.transform='translate(-50%,-50%) scale(1)');
    });
  } else if(cur){cur.style.display='none'}
  const c=document.getElementById('neonBg');
  if(c){
    const x=c.getContext('2d');let w,h,ps=[];
    function rs(){w=c.width=innerWidth;h=c.height=innerHeight;ps=[];const n=Math.min(70,Math.floor(w/22));for(let i=0;i<n;i++)ps.push({x:Math.random()*w,y:Math.random()*h,vx:(Math.random()-.5)*.4,vy:(Math.random()-.5)*.4,r:Math.random()*1.8+.4,c:['#ff2d95','#a855f7','#22d3ee'][Math.floor(Math.random()*3)]})}
    function lp(){x.clearRect(0,0,w,h);for(const p of ps){p.x+=p.vx;p.y+=p.vy;if(p.x<0||p.x>w)p.vx*=-1;if(p.y<0||p.y>h)p.vy*=-1;x.beginPath();x.arc(p.x,p.y,p.r,0,7);x.fillStyle=p.c;x.shadowBlur=12;x.shadowColor=p.c;x.fill()}for(let i=0;i<ps.length;i++)for(let j=i+1;j<ps.length;j++){const dx=ps[i].x-ps[j].x,dy=ps[i].y-ps[j].y,d=Math.hypot(dx,dy);if(d<130){x.beginPath();x.moveTo(ps[i].x,ps[i].y);x.lineTo(ps[j].x,ps[j].y);x.strokeStyle='rgba(168,85,247,'+(1-d/130)*.18+')';x.lineWidth=.6;x.stroke()}}requestAnimationFrame(lp)}
    addEventListener('resize',rs);rs();lp();
  }
  let ac=null,muted=localStorage.getItem('tnm_mute')==='1';
  function AC(){if(!ac){try{ac=new (window.AudioContext||window.webkitAudioContext)()}catch(e){}}return ac}
  function tone(f,d,type,vol){if(muted)return;const a=AC();if(!a)return;const o=a.createOscillator(),g=a.createGain();o.type=type||'sine';o.frequency.value=f;g.gain.value=vol||.05;o.connect(g);g.connect(a.destination);const t=a.currentTime;g.gain.setValueAtTime(0,t);g.gain.linearRampToValueAtTime(vol||.05,t+.01);g.gain.exponentialRampToValueAtTime(.0001,t+d);o.start(t);o.stop(t+d)}
  window.playHover=()=>tone(880,.05,'sine',.02);
  window.playClick=()=>tone(520,.12,'square',.04);
  window.playSuccess=()=>{tone(523,.15,'sine',.06);setTimeout(()=>tone(659,.15,'sine',.06),90);setTimeout(()=>tone(784,.3,'sine',.06),180)};
  window.playError=()=>{tone(180,.25,'sawtooth',.05);setTimeout(()=>tone(120,.35,'sawtooth',.05),120)};
  document.querySelectorAll('button,input,a').forEach(el=>{
    el.addEventListener('mouseenter',playHover);
    el.addEventListener('click',playClick);
  });
  const mb=document.getElementById('muteBtn');
  if(mb){mb.textContent=muted?'🔇':'🔊';mb.onclick=()=>{muted=!muted;localStorage.setItem('tnm_mute',muted?'1':'0');mb.textContent=muted?'🔇':'🔊';if(!muted)playClick()}}
  if(document.body.dataset.ai==='1'){
    const b=document.createElement('button');b.id='aiBtn';b.innerHTML='<i class="fa-solid fa-robot"></i>';document.body.appendChild(b);
    const p=document.createElement('div');p.id='aiPanel';p.innerHTML='<div id="aiHead"><span>◉ AI ASSISTANT</span><span style="cursor:pointer" id="aiX">✕</span></div><div id="aiLog"><div class="m a">Olá! Sou o assistente AI.</div></div><form id="aiForm"><input id="aiInput" placeholder="Pergunte algo..." autocomplete="off"><button id="aiSend" type="submit">▶</button></form>';
    document.body.appendChild(p);
    let hist=[];
    b.onclick=()=>{p.classList.toggle('open');playClick();document.getElementById('aiInput').focus()};
    document.getElementById('aiX').onclick=()=>p.classList.remove('open');
    document.getElementById('aiForm').onsubmit=async e=>{
      e.preventDefault();const inp=document.getElementById('aiInput'),log=document.getElementById('aiLog');
      const msg=inp.value.trim();if(!msg)return;inp.value='';
      log.insertAdjacentHTML('beforeend','<div class="m u"></div>');log.lastChild.textContent=msg;
      log.insertAdjacentHTML('beforeend','<div class="m a pulse">...</div>');log.scrollTop=log.scrollHeight;
      try{
        const r=await fetch('/api/ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,history:hist})});
        const d=await r.json();log.lastChild.remove();
        if(d.reply){log.insertAdjacentHTML('beforeend','<div class="m a"></div>');log.lastChild.textContent=d.reply;hist.push({role:'user',content:msg},{role:'assistant',content:d.reply});playSuccess()}
        else{log.insertAdjacentHTML('beforeend','<div class="m a" style="color:#ff8e8e"></div>');log.lastChild.textContent='⚠ '+(d.error||'Erro');playError()}
      }catch(err){log.lastChild.remove();log.insertAdjacentHTML('beforeend','<div class="m a" style="color:#ff8e8e">⚠ Falha</div>');playError()}
      log.scrollTop=log.scrollHeight;
    };
  }
})();
"""


# ==================== HTML: LOGIN ====================
LOGIN_PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TIGRAN MODZ · ADMIN</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>""" + NEON_CSS + """
.manifest{padding:52px 44px;display:flex;flex-direction:column;justify-content:space-between;border-right:1px solid var(--line)}
.form-panel{padding:52px 44px;display:flex;flex-direction:column;justify-content:center}
.login-shell{width:min(1000px,100%);display:grid;grid-template-columns:1.05fr .95fr;min-height:600px}
.mark{display:flex;align-items:center;gap:12px;font-weight:900;letter-spacing:3px;font-size:20px}
.mark i{display:grid;place-items:center;width:44px;height:44px;background:linear-gradient(135deg,var(--p1),var(--p3));color:#fff;border-radius:10px;box-shadow:0 0 20px var(--p1)}
.manifest h1{font-size:56px;line-height:.95;letter-spacing:-3px;margin:60px 0 0;max-width:420px}
.manifest p{color:var(--muted);line-height:1.75;max-width:380px;margin-top:16px}
.label{font:700 10px monospace;letter-spacing:3px;color:var(--p3);text-transform:uppercase}
.form-panel h2{font-size:32px;margin:12px 0 8px;letter-spacing:-1px}
.sub{color:var(--muted);margin-bottom:26px;font-size:14px}
.error{margin-top:14px;color:#ff8e8e;font:700 11px monospace;text-shadow:0 0 10px rgba(255,100,100,.6)}
.foot{margin-top:30px;color:#6b5a70;font:10px monospace;letter-spacing:1px}
@media(max-width:780px){.login-shell{grid-template-columns:1fr;min-height:0;border-radius:0}.manifest{padding:32px 22px;min-height:240px}.manifest h1{font-size:38px;margin-top:24px}.form-panel{padding:32px 22px}}
</style></head><body>
<canvas id="neonBg"></canvas><div id="neonCursor"></div><button id="muteBtn">🔊</button>
<div class="wrap"><main class="login-shell glass fade-in">
<section class="manifest"><div><div class="mark"><i class="fa-solid fa-bolt"></i> TIGRAN MODZ PROXY</div><div class="scan"></div><div style="margin-top:60px" class="label">PRIVATE CONTROL SYSTEM</div><h1>Enter the <span class="neon-text">operator</span> console.</h1><p>Área administrativa.</p></div><div style="font:11px monospace;color:#7a6578;letter-spacing:2px">NODE / 07 · AUTH REQUIRED</div></section>
<section class="form-panel"><div class="label">ADMIN AUTHENTICATION</div><h2>Entrar no painel</h2><p class="sub">Informe suas credenciais.</p>
<form method="POST"><div class="field"><label for="u">Usuário</label><input id="u" name="username" required></div><div class="field"><label for="p">Senha</label><input id="p" type="password" name="password" required></div><button class="glow-btn" type="submit">Acessar console <i class="fa-solid fa-arrow-right"></i></button>{% if error %}<div class="error">{{ error }}</div>{% endif %}</form>
<div class="foot"><i class="fa-solid fa-shield-halved"></i> SESSÃO PROTEGIDA</div></section>
</main></div>
<script>""" + NEON_JS + """</script></body></html>"""


# ==================== HTML: KEY PAGE ====================
KEY_PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TIGRAN MODZ · ACCESS</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>""" + NEON_CSS + """
.access{width:min(1000px,100%);display:grid;grid-template-columns:1.05fr .95fr;min-height:620px}
.visual{padding:48px;display:flex;flex-direction:column;justify-content:space-between;position:relative;overflow:hidden}
.brand{font-weight:900;letter-spacing:3px;font-size:18px}
.brand b{color:var(--p1);text-shadow:0 0 14px var(--p1)}
.visual h1{font-size:60px;line-height:.9;letter-spacing:-4px;margin:20px 0 0;max-width:400px}
.visual p{color:var(--muted);line-height:1.7;max-width:340px;margin-top:16px;font-size:14px}
.info-strip{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:24px}
.info-card{background:rgba(10,5,20,.6);border:1px solid var(--line);border-radius:12px;padding:11px 12px;font:11px monospace}
.info-card small{display:block;color:var(--muted);letter-spacing:1px;font-size:9px;margin-bottom:5px;text-transform:uppercase}
.info-card b{color:var(--p3);font-weight:800;font-size:13px}
.access-form{padding:48px 42px;display:flex;flex-direction:column;justify-content:center}
.access-form h2{font-size:30px;margin:12px 0 6px;letter-spacing:-1px}
#keyError{color:#ff8e8e;margin-top:14px;font:700 11px monospace}
.hint{margin-top:16px;color:#8a7a90;font:11px monospace;line-height:1.6}
@media(max-width:780px){.access{grid-template-columns:1fr;border-radius:0}.visual{padding:28px 20px}.visual h1{font-size:38px}.access-form{padding:28px 20px}}
</style></head><body>
<canvas id="neonBg"></canvas><div id="neonCursor"></div><button id="muteBtn">🔊</button>
<div class="wrap"><main class="access glass fade-in">
<section class="visual"><div><div class="brand"><i class="fa-solid fa-key"></i> TIGRAN MODZ <b>PROXY</b></div><div class="scan"></div><div style="margin-top:40px" class="label">ACCESS GATE / 01</div><h1>One key. <span class="neon-text">Full access.</span></h1><p>Use uma key.</p></div>
<div class="info-strip">
<div class="info-card"><small>País</small><b id="uCountry">—</b></div>
<div class="info-card"><small>Cidade</small><b id="uCity">—</b></div>
<div class="info-card"><small>Hora</small><b id="uTime">--:--:--</b></div>
<div class="info-card"><small>Clima</small><b id="uWeather">—</b></div>
</div></section>
<section class="access-form"><div class="label">USER ACCESS</div><h2>Validar acesso</h2><p class="sub">Cole sua key.</p>
<form id="keyForm"><div class="field"><label for="k">Access key</label><input id="k" required spellcheck="false" placeholder="TIGRAN-MDZ-PROXY-0000"></div><button class="glow-btn" type="submit">Abrir dashboard</button><div id="keyError"></div></form>
<div class="hint">Keys são geradas pelo administrador.</div></section>
</main></div>
<script>""" + NEON_JS + """
fetch('/api/user/info').then(r=>r.json()).then(d=>{
  document.getElementById('uCountry').textContent=(d.country||'—')+(d.country_code?' ('+d.country_code+')':'');
  document.getElementById('uCity').textContent=d.city||'—';
  if(d.timezone){
    function tick(){try{document.getElementById('uTime').textContent=new Date().toLocaleTimeString('ru-RU',{timeZone:d.timezone,hour12:false})}catch(e){}}
    tick();setInterval(tick,1000);
  }
  if(d.weather){const w=d.weather;document.getElementById('uWeather').textContent=(w.temp||'?')+'°C · '+(w.desc||'')}
}).catch(()=>{});
document.getElementById('keyForm').addEventListener('submit',async e=>{
  e.preventDefault();const b=e.target.querySelector('button'),m=document.getElementById('keyError');
  b.disabled=true;m.textContent='VALIDANDO...';
  try{
    const r=await fetch('/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:document.getElementById('k').value.trim()})});
    const d=await r.json();if(!r.ok||!d.success)throw Error(d.message||'KEY INVÁLIDA');
    playSuccess();m.style.color='#22d3ee';m.textContent='✓ ACESSO LIBERADO';
    setTimeout(()=>location.href='/dashboard',700);
  }catch(err){m.style.color='#ff8e8e';m.textContent=err.message;playError();b.disabled=false}
});
</script></body></html>"""


# ==================== HTML: ADMIN DASHBOARD ====================
ADMIN_DASHBOARD = """<!doctype html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TIGRAN MODZ · ADMIN</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>""" + NEON_CSS + """
.admin{min-height:100vh;display:grid;grid-template-columns:240px 1fr;position:relative;z-index:2}
.nav{padding:26px 18px;background:rgba(10,5,20,.7);backdrop-filter:blur(14px);border-right:1px solid var(--line);display:flex;flex-direction:column}
.brand{font-weight:900;letter-spacing:2px;font-size:15px}
.brand span{color:var(--p1);text-shadow:0 0 14px var(--p1)}
.nav-links{margin-top:40px;display:grid;gap:6px}
.nav-links a{padding:12px 14px;color:var(--muted);text-decoration:none;font:700 10px monospace;letter-spacing:1.5px;text-transform:uppercase;border-radius:12px;border:1px solid transparent;transition:.2s;cursor:none}
.nav-links a:hover,.nav-links a.active{background:linear-gradient(90deg,rgba(255,45,149,.15),transparent);border-color:rgba(255,45,149,.35);color:#fff}
.logout{display:block;margin-top:auto;padding:12px 14px;color:#ff9a9a;text-decoration:none;font:700 10px monospace;border-radius:12px;border:1px solid rgba(255,100,100,.25);text-align:center;cursor:none}
.workspace{padding:32px 40px;max-width:1300px;width:100%}
.bar{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid var(--line);padding-bottom:26px;flex-wrap:wrap;gap:14px}
.bar h1{font-size:38px;letter-spacing:-2px;margin:8px 0 0}
.eyebrow{font:700 10px monospace;letter-spacing:2px;color:var(--p3)}
.profile{color:var(--muted);font:11px monospace;padding:8px 14px;border-radius:999px;background:rgba(34,211,238,.1);border:1px solid rgba(34,211,238,.3)}
.cards{display:grid;grid-template-columns:1.2fr .8fr;gap:16px;margin-top:24px}
.card{background:rgba(20,10,30,.55);backdrop-filter:blur(14px);border:1px solid var(--line);border-radius:18px;padding:22px}
.card h2{font-size:13px;margin:0 0 18px;letter-spacing:1px;text-transform:uppercase;color:var(--p3)}
.field label{display:block;color:var(--muted);font:700 10px monospace;margin-bottom:7px}
.field input{width:100%;padding:12px 14px;border-radius:10px;border:1px solid var(--line);background:rgba(5,3,10,.7);color:#fff;outline:none}
.stats{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.stat{padding:18px;background:rgba(10,5,20,.6);border:1px solid var(--line);border-radius:14px}
.stat small{display:block;color:var(--muted);font:700 9px monospace}
.stat strong{display:block;font-size:34px;margin-top:10px;background:linear-gradient(135deg,var(--p1),var(--p3));-webkit-background-clip:text;background-clip:text;color:transparent}
.wide{margin-top:16px}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{text-align:left;padding:13px 10px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font:700 9px monospace;text-transform:uppercase}
td{color:#d8c9e0}
.badge{padding:5px 9px;border-radius:8px;background:rgba(255,45,149,.12);border:1px solid rgba(255,45,149,.35);color:#ff7ec0;font:700 10px monospace}
.danger{background:rgba(255,80,80,.15);border:1px solid rgba(255,80,80,.4);color:#ffaaaa;font:800 10px monospace;padding:8px 12px;border-radius:8px;cursor:none}
.generated{margin-top:14px;padding:12px;border-radius:10px;background:rgba(34,211,238,.08);border:1px solid rgba(34,211,238,.3);color:#8ff0ff;font:800 15px monospace;word-break:break-all}
@media(max-width:820px){.admin{grid-template-columns:1fr}.workspace{padding:20px 14px}.cards{grid-template-columns:1fr}}
</style></head><body data-ai="1">
<canvas id="neonBg"></canvas><div id="neonCursor"></div><button id="muteBtn">🔊</button>
<main class="admin">
<aside class="nav">
<div class="brand"><i class="fa-solid fa-bolt"></i> TIGRAN MODZ <span>PROXY</span></div>
<div class="nav-links"><a class="active" href="/admin/dashboard">Overview</a><a href="#keys">Keys</a><a href="#ips">Sessions</a></div>
<a class="logout" href="/admin/logout">Encerrar sessão</a>
</aside>
<section class="workspace">
<header class="bar fade-in"><div><div class="eyebrow">ADMIN CONTROL / 01</div><h1 class="neon-text">Operations</h1></div><div class="profile">● ADMIN ONLINE</div></header>
<div class="cards fade-in">
<section class="card"><h2>Emitir nova key</h2>
<div class="field"><label>Prefixo</label><input id="keyPrefix" value="TIGRAN-MDZ-PROXY"></div>
<div class="field"><label>Limite de IPs</label><input id="ipLimit" type="number" value="1" min="1"></div>
<div class="field"><label>Validade (dias)</label><input id="keyDays" type="number" value="7" min="1"></div>
<button class="glow-btn" style="width:100%" onclick="generateKey()">Gerar key</button>
<div id="generatedKey" class="generated" style="display:none"></div>
</section>
<section class="card"><h2>Resumo</h2>
<div class="stats"><div class="stat"><small>TOTAL KEYS</small><strong>{{ keys|length }}</strong></div><div class="stat"><small>IPS ATIVOS</small><strong>{{ ips|length }}</strong></div></div>
</section></div>
<section class="card wide fade-in"><h2>Keys emitidas</h2><table><thead><tr><th>KEY</th><th>LIMIT</th><th>USOS</th><th>VALIDADE</th><th>AÇÃO</th></tr></thead><tbody>{% for key, data in keys.items() %}<tr><td><span class="badge">{{ key }}</span></td><td>{{ data.limit }}</td><td>{{ data.used_ips|length }}</td><td>{{ data.days }} dias</td><td><button class="danger" onclick="revokeKey('{{ key }}')">REVOGAR</button></td></tr>{% else %}<tr><td colspan="5">Nenhuma key.</td></tr>{% endfor %}</tbody></table></section>
<section class="card wide fade-in"><h2>Sessões autorizadas</h2><table><thead><tr><th>IP</th><th>KEY</th><th>EXPIRA</th><th>STATUS</th></tr></thead><tbody>{% for ip, key in ips.items() %}<tr><td>{{ ip }}</td><td><span class="badge">{{ key }}</span></td><td>{% if key_expiry[ip] %}{{ key_expiry[ip].strftime('%d/%m/%Y') }}{% else %}-{% endif %}</td><td>● ATIVO</td></tr>{% else %}<tr><td colspan="4">Nenhuma sessão.</td></tr>{% endfor %}</tbody></table></section>
</section></main>
<script>""" + NEON_JS + """
async function generateKey(){const o=document.getElementById('generatedKey');o.style.display='block';o.textContent='GERANDO...';try{const r=await fetch('/admin/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prefix:document.getElementById('keyPrefix').value.trim()||'TIGRAN-MDZ-PROXY',limit:Math.max(1,parseInt(document.getElementById('ipLimit').value)||1),days:Math.max(1,parseInt(document.getElementById('keyDays').value)||7)})});const d=await r.json();if(!r.ok||!d.key)throw Error(d.error||'Erro');o.textContent='✓ '+d.key;playSuccess();setTimeout(()=>location.reload(),1400)}catch(e){o.textContent='ERRO: '+e.message;playError()}}
async function revokeKey(key){if(!confirm('Revogar '+key+'?'))return;const r=await fetch('/admin/revoke',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})});const d=await r.json();if(d.success){playSuccess();location.reload()}else{alert(d.error||'Erro');playError()}}
</script></body></html>"""


# ==================== HTML: USER DASHBOARD ====================
DASHBOARD_PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TIGRAN MODZ · DASHBOARD</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>""" + NEON_CSS + """
.app{min-height:100vh;display:grid;grid-template-columns:240px 1fr;position:relative;z-index:2}
.side{padding:26px 18px;background:rgba(10,5,20,.7);backdrop-filter:blur(14px);border-right:1px solid var(--line);display:flex;flex-direction:column}
.brand{font-weight:900;letter-spacing:2px;font-size:15px}
.brand span{color:var(--p1);text-shadow:0 0 14px var(--p1)}
.side nav{margin-top:40px;display:grid;gap:6px}
.side nav div{padding:12px 14px;color:var(--muted);font:700 10px monospace;text-transform:uppercase;border-radius:12px;border:1px solid transparent;cursor:none}
.side nav div.active{background:linear-gradient(90deg,rgba(255,45,149,.18),transparent);border-color:rgba(255,45,149,.4);color:#fff}
.side-foot{margin-top:auto;color:#6b5a70;font:10px monospace;line-height:1.7}
.main{padding:32px 40px;max-width:1250px;width:100%}
.top{display:flex;justify-content:space-between;align-items:flex-start;padding-bottom:26px;border-bottom:1px solid var(--line);flex-wrap:wrap;gap:14px}
.top h1{margin:8px 0 0;font-size:36px;letter-spacing:-1.5px}
.eyebrow{font:700 10px monospace;letter-spacing:2px;color:var(--p3)}
.status{display:flex;gap:8px;align-items:center;color:#ff7ec0;font:700 10px monospace;padding:8px 14px;border-radius:999px;background:rgba(255,45,149,.1);border:1px solid rgba(255,45,149,.3)}
.dot{width:8px;height:8px;background:var(--p1);border-radius:50%;box-shadow:0 0 14px var(--p1);animation:pulse 1.6s infinite}
.info-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:26px 0}
.info-card{background:rgba(20,10,30,.6);backdrop-filter:blur(12px);border:1px solid var(--line);border-radius:14px;padding:14px}
.info-card i{color:var(--p3);font-size:14px}
.info-card small{display:block;color:var(--muted);font:700 9px monospace;text-transform:uppercase;margin:6px 0 4px}
.info-card b{color:#fff;font-size:15px;font-weight:800;display:block;word-break:break-word}
.ip{margin:6px 0 22px;display:flex;align-items:center;gap:12px;padding:14px 18px;background:rgba(20,10,30,.6);border:1px solid var(--line);border-radius:14px;font:12px monospace;color:#c8b9d0}
.ip span:first-of-type{flex:1;word-break:break-all}
.tag{padding:5px 10px;border-radius:8px;background:linear-gradient(135deg,var(--p1),var(--p2));color:#fff;font:800 9px monospace}
.section-title{display:flex;align-items:center;gap:10px;margin:26px 0 12px;font:800 11px monospace;color:#c8b9d0;text-transform:uppercase}
.section-title:after{content:"";height:1px;background:linear-gradient(90deg,var(--line),transparent);flex:1}
.controls{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.control{display:flex;align-items:center;gap:14px;background:rgba(20,10,30,.55);border:1px solid var(--line);border-radius:16px;padding:16px;cursor:none;transition:.25s}
.control:hover{border-color:rgba(255,45,149,.5);transform:translateY(-3px)}
.control.visual-option.is-on{border-color:var(--p1);background:linear-gradient(135deg,rgba(255,45,149,.15),rgba(168,85,247,.08))}
.control.visual-option.is-on .icon{background:linear-gradient(135deg,var(--p1),var(--p3));color:#fff}
.icon{width:36px;height:36px;display:grid;place-items:center;background:rgba(255,45,149,.15);border-radius:10px;color:var(--p1);font-size:14px}
.info{flex:1;min-width:0}
.name{font-size:12px;font-weight:800}
.desc{color:var(--muted);font:10px monospace;margin-top:4px}
.sw{width:36px;height:20px;border-radius:20px;background:#322a38;padding:2px;transition:.25s;flex-shrink:0}
.sw .th{width:16px;height:16px;border-radius:50%;background:#8a7a90;transition:.25s}
.sw.on{background:linear-gradient(135deg,var(--p1),var(--p3));box-shadow:0 0 14px rgba(255,45,149,.6)}
.sw.on .th{margin-left:16px;background:#fff}
#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(80px);padding:13px 22px;background:linear-gradient(135deg,var(--p1),var(--p2));color:#fff;font:800 11px monospace;border-radius:12px;opacity:0;transition:.3s;z-index:9999}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
@media(max-width:820px){.app{grid-template-columns:1fr}.main{padding:20px 14px}.controls{grid-template-columns:1fr}}
</style></head><body data-ai="1">
<canvas id="neonBg"></canvas><div id="neonCursor"></div><button id="muteBtn">🔊</button>
<main class="app">
<aside class="side">
<div class="brand"><i class="fa-solid fa-bolt"></i> TIGRAN MODZ <span>PROXY</span></div>
<nav>
  <div class="active">Overview</div>
  <div onclick="location.href='/ai'">Tigran AI</div>
  <div onclick="location.href='/tools'">Tools</div>
</nav>
<div class="side-foot">SESSION ACTIVE</div>
</aside>
<section class="main">
<header class="top fade-in"><div><div class="eyebrow">USER CONSOLE</div><h1 class="neon-text">Dashboard</h1></div><div class="status"><i class="dot"></i> ONLINE</div></header>
<div class="info-grid">
<div class="info-card"><i class="fa-solid fa-globe"></i><small>País</small><b id="uCountry">—</b></div>
<div class="info-card"><i class="fa-solid fa-location-dot"></i><small>Cidade</small><b id="uCity">—</b></div>
<div class="info-card"><i class="fa-solid fa-clock"></i><small>Hora</small><b id="uTime">--:--:--</b></div>
<div class="info-card"><i class="fa-solid fa-calendar"></i><small>Data</small><b id="uDate">—</b></div>
<div class="info-card"><i class="fa-solid fa-cloud-sun"></i><small>Clima</small><b id="uWeather">—</b></div>
<div class="info-card"><i class="fa-solid fa-moon"></i><small>Período</small><b id="uDayNight">—</b></div>
<div class="info-card"><i class="fa-solid fa-mobile-screen"></i><small>Device</small><b id="uDevice">—</b></div>
<div class="info-card"><i class="fa-solid fa-battery-three-quarters"></i><small>Bateria</small><b id="uBattery">—</b></div>
</div>
<div class="ip"><span id="ipDisplay">CARREGANDO...</span><b class="tag">AUTHORIZED</b></div>
<div class="section-title">AIM MODULES</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('hs_neck')"><div class="icon"><i class="fa-solid fa-crosshairs"></i></div><div class="info"><div class="name">HS PESCOÇO</div><div class="desc">PRECISION TARGET</div></div><div class="sw" id="sw_hs_neck"><div class="th"></div></div></div>
<div class="control" onclick="toggle('hs_chest')"><div class="icon"><i class="fa-solid fa-bullseye"></i></div><div class="info"><div class="name">HS PEITO</div><div class="desc">PRECISION TARGET</div></div><div class="sw" id="sw_hs_chest"><div class="th"></div></div></div>
<div class="control visual-option" onclick="toggleVisual(this)"><div class="icon"><i class="fa-solid fa-crosshairs"></i></div><div class="info"><div class="name">PRECISÃO</div><div class="desc">PRECISION</div></div><div class="sw"><div class="th"></div></div></div>
<div class="control visual-option" onclick="toggleVisual(this)"><div class="icon"><i class="fa-solid fa-arrow-up"></i></div><div class="info"><div class="name">HS ALTO</div><div class="desc">PRECISION</div></div><div class="sw"><div class="th"></div></div></div>
</div>
<div class="section-title">MOVEMENT</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('backjump_v1')"><div class="icon"><i class="fa-solid fa-arrow-up"></i></div><div class="info"><div class="name">BACKJUMP</div><div class="desc">MOVEMENT</div></div><div class="sw" id="sw_backjump_v1"><div class="th"></div></div></div>
<div class="control" onclick="toggle('high_sensi')"><div class="icon"><i class="fa-solid fa-sliders"></i></div><div class="info"><div class="name">SENSI ALTA</div><div class="desc">CONTROL</div></div><div class="sw" id="sw_high_sensi"><div class="th"></div></div></div>
<div class="control" onclick="toggle('zig_zag_move')"><div class="icon"><i class="fa-solid fa-arrows-left-right"></i></div><div class="info"><div class="name">ZIG ZAG</div><div class="desc">MOVEMENT</div></div><div class="sw" id="sw_zig_zag_move"><div class="th"></div></div></div>
</div>
</section></main>
<div id="toast"></div>
<script>""" + NEON_JS + """
const names={hs_neck:'HS PESCOÇO',hs_chest:'HS PEITO',backjump_v1:'BACKJUMP',high_sensi:'SENSI ALTA',zig_zag_move:'ZIG ZAG'};
function toggleVisual(card){card.classList.toggle('is-on');toast(card.querySelector('.name').textContent+(card.classList.contains('is-on')?' ATIVO':' OFF'));if(card.classList.contains('is-on'))playSuccess()}
function toast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');clearTimeout(t._t);t._t=setTimeout(()=>t.classList.remove('show'),2000)}
fetch('/api/ip/check').then(r=>r.json()).then(d=>{document.getElementById('ipDisplay').textContent=d.ip||'N/A'});
fetch('/api/user/info').then(r=>r.json()).then(d=>{
  document.getElementById('uCountry').textContent=(d.country||'—')+(d.country_code?' ('+d.country_code+')':'');
  document.getElementById('uCity').textContent=d.city||'—';
  if(d.timezone){function tick(){try{const n=new Date();document.getElementById('uTime').textContent=n.toLocaleTimeString('ru-RU',{timeZone:d.timezone,hour12:false});document.getElementById('uDate').textContent=n.toLocaleDateString('ru-RU',{timeZone:d.timezone,day:'2-digit',month:'short'})}catch(e){}}tick();setInterval(tick,1000)}
  if(d.weather){document.getElementById('uWeather').textContent=(d.weather.temp||'?')+'°C · '+(d.weather.desc||'');document.getElementById('uDayNight').textContent=d.weather.is_day?'☀ DIA':'🌙 NOITE'}
});
(function(){const ua=navigator.userAgent;let os='';if(/Android/i.test(ua))os='Android';else if(/iPhone|iPad/i.test(ua))os='iOS';else if(/Windows/i.test(ua))os='Windows';else if(/Mac/i.test(ua))os='macOS';else if(/Linux/i.test(ua))os='Linux';let br='Browser';if(/Chrome/i.test(ua)&&!/Edg/i.test(ua))br='Chrome';else if(/Firefox/i.test(ua))br='Firefox';else if(/Safari/i.test(ua))br='Safari';document.getElementById('uDevice').textContent=os+' · '+br;if(navigator.getBattery){navigator.getBattery().then(b=>{function u(){document.getElementById('uBattery').textContent=Math.round(b.level*100)+'%'+(b.charging?' ⚡':'')}u();b.addEventListener('levelchange',u)})}})();
fetch('/api/status').then(r=>r.json()).then(d=>{const c=d.config;const m={hs_neck:'HS_NECK',hs_chest:'HS_CHEST',backjump_v1:'BACKJUMPV1',high_sensi:'HIGH_SENSI',zig_zag_move:'ZIG_ZAG_MOVE'};['hs_neck','hs_chest','backjump_v1','high_sensi','zig_zag_move'].forEach(f=>{const el=document.getElementById('sw_'+f);if(el)el.className='sw'+(c[m[f]]?' on':'')})});
function toggle(feature){const el=document.getElementById('sw_'+feature),val=!el.classList.contains('on');el.className='sw'+(val?' on':'');fetch('/api/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({feature,value:val})}).then(r=>r.json()).then(d=>{if(d.success){toast(names[feature]+' '+(val?'ON':'OFF'));if(val)playSuccess()}else throw Error()}).catch(()=>{el.className='sw'+(!val?' on':'');toast('ERRO');playError()})}
</script></body></html>"""


# ==================== HTML: AI PAGE ====================
AI_PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TIGRAN AI</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>""" + NEON_CSS + """
.aigrid{position:relative;z-index:2;display:grid;grid-template-columns:290px 1fr;height:100vh;overflow:hidden}
.aiside{background:rgba(10,5,20,.85);backdrop-filter:blur(16px);border-right:1px solid var(--line);display:flex;flex-direction:column;padding:14px;overflow:hidden}
.ailogo{display:flex;align-items:center;gap:10px;padding:8px 10px 14px;font-weight:900;letter-spacing:2px;font-size:15px;border-bottom:1px solid var(--line)}
.ailogo i{color:var(--p3)}
.actions{display:flex;gap:6px;margin-top:12px}
.actions button{flex:1;padding:11px 6px;border-radius:10px;border:1px solid var(--line);background:rgba(20,10,30,.6);color:#c8b9d0;cursor:none;font:700 9px monospace}
.actions button.primary{background:linear-gradient(135deg,var(--p1),var(--p3));color:#fff;border:0}
.chatlist{flex:1;overflow-y:auto;margin-top:12px;display:flex;flex-direction:column;gap:3px}
.chatitem{display:flex;align-items:center;gap:8px;padding:10px 11px;border-radius:10px;color:#c8b9d0;font-size:12px;cursor:none;border:1px solid transparent}
.chatitem.active{background:linear-gradient(90deg,rgba(255,45,149,.2),transparent);border-color:rgba(255,45,149,.4);color:#fff}
.chatitem .ttl{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chatitem .del{color:#ff8e8e;padding:2px}
.aibottom{padding-top:10px;border-top:1px solid var(--line);display:flex;gap:6px}
.aibottom a,.aibottom button{flex:1;text-align:center;padding:9px 6px;border-radius:10px;background:rgba(34,211,238,.1);border:1px solid rgba(34,211,238,.3);color:#8ff0ff;font:700 9px monospace;text-decoration:none;cursor:none}
.aimain{display:flex;flex-direction:column;height:100vh}
.aihead{padding:12px 20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.aihead .ttl{font:800 13px monospace;color:#fff;display:flex;align-items:center;gap:8px}
.aihead select,.aihead button{padding:7px 11px;border-radius:9px;border:1px solid var(--line);background:rgba(20,10,30,.7);color:#c8b9d0;font:700 10px monospace;cursor:none}
.msgs{flex:1;overflow-y:auto;padding:24px 5% 100px;display:flex;flex-direction:column;gap:16px}
.msg{display:flex;gap:12px;max-width:880px;width:100%;margin:0 auto}
.msg.u{flex-direction:row-reverse}
.msg .av{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font-size:12px;flex-shrink:0;font-weight:900}
.msg.u .av{background:linear-gradient(135deg,var(--p1),var(--p2));color:#fff}
.msg.a .av{background:linear-gradient(135deg,var(--p3),var(--p2));color:#fff}
.msg .bub{padding:12px 15px;border-radius:16px;line-height:1.6;font-size:14px;word-wrap:break-word;max-width:100%}
.msg.u .bub{background:linear-gradient(135deg,rgba(255,45,149,.18),rgba(168,85,247,.12));border:1px solid rgba(255,45,149,.4);color:#fff}
.msg.a .bub{background:rgba(20,10,30,.7);border:1px solid var(--line);color:#e8dff0}
.msg.a .bub code{background:rgba(34,211,238,.12);padding:2px 6px;border-radius:4px;font:12px monospace;color:#8ff0ff}
.typing i{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--p3);animation:blink 1.2s infinite;margin:0 2px}
.typing i:nth-child(2){animation-delay:.2s}.typing i:nth-child(3){animation-delay:.4s}
@keyframes blink{0%,60%,100%{opacity:.3}30%{opacity:1}}
.aiinput{padding:10px 16px 14px;border-top:1px solid var(--line)}
.aiinput .box{display:flex;gap:8px;max-width:880px;margin:0 auto;background:rgba(5,3,10,.8);border:1px solid var(--line);border-radius:16px;padding:6px}
.aiinput textarea{flex:1;background:transparent;border:0;color:#fff;outline:none;font:14px inherit;padding:10px;resize:none;max-height:180px}
.aiinput .btns{display:flex;gap:4px}
.aiinput .btns button{width:40px;height:40px;border-radius:11px;border:0;cursor:none;font-size:14px;color:#fff}
.aiinput .send{background:linear-gradient(135deg,var(--p1),var(--p3))}
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;text-align:center;color:var(--muted);gap:14px;padding:30px}
.empty h2{font-size:34px;background:linear-gradient(90deg,var(--p1),var(--p2),var(--p3));-webkit-background-clip:text;background-clip:text;color:transparent}
.empty .chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:14px}
.empty .chip{padding:9px 14px;border-radius:999px;background:rgba(20,10,30,.7);border:1px solid var(--line);color:#c8b9d0;cursor:none}
@media(max-width:820px){.aigrid{grid-template-columns:1fr}.aiside{position:fixed;left:0;top:0;bottom:0;width:290px;transform:translateX(-100%);z-index:999}.aiside.open{transform:translateX(0)}.msgs{padding:16px 12px 90px}}
</style></head><body>
<canvas id="neonBg"></canvas><div id="neonCursor"></div><button id="muteBtn">🔊</button>
<div class="aigrid">
<aside class="aiside" id="aiside">
  <div class="ailogo"><i class="fa-solid fa-robot"></i> TIGRAN AI</div>
  <div class="actions">
    <button class="primary" onclick="newChat()">+ НОВЫЙ</button>
    <button onclick="exportChats()">ЭКСПОРТ</button>
    <button onclick="document.getElementById('imp').click()">ИМПОРТ</button>
    <input type="file" id="imp" accept=".json" style="display:none" onchange="importChats(event)">
  </div>
  <div class="chatlist" id="chatlist"></div>
  <div class="aibottom">
    <a href="/dashboard">← К ПАНЕЛИ</a>
    <button onclick="clearAll()">ОЧИСТИТЬ</button>
  </div>
</aside>
<section class="aimain">
  <header class="aihead">
    <div class="ttl"><i class="fa-solid fa-comments"></i> Чат</div>
    <div style="display:flex;gap:6px">
      <select id="modelSel" onchange="save()">
        <option value="gpt-4o-mini">gpt-4o-mini</option>
        <option value="gpt-4o">gpt-4o</option>
        <option value="gpt-3.5-turbo">gpt-3.5-turbo</option>
      </select>
    </div>
  </header>
  <div class="msgs" id="msgs"></div>
  <div class="aiinput">
    <div class="box">
      <textarea id="ta" placeholder="Напиши сообщение..." rows="1"></textarea>
      <div class="btns"><button class="send" onclick="sendMsg()">▶</button></div>
    </div>
  </div>
</section>
</div>
<script>""" + NEON_JS + """
const LS='tigran_ai_v2';
let state=JSON.parse(localStorage.getItem(LS)||'null')||{chats:[],activeId:null,model:'gpt-4o-mini'};
function save(){state.model=document.getElementById('modelSel').value;localStorage.setItem(LS,JSON.stringify(state))}
function uid(){return Date.now().toString(36)+Math.random().toString(36).slice(2,6)}
function active(){return state.chats.find(c=>c.id===state.activeId)}
function escapeHtml(s){return String(s).replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]))}
function newChat(){const c={id:uid(),title:'Новый чат',msgs:[],created:Date.now()};state.chats.unshift(c);state.activeId=c.id;save();renderList();renderMsgs();document.getElementById('aiside')?.classList.remove('open')}
function selectChat(id){state.activeId=id;save();renderList();renderMsgs()}
function delChat(e,id){e.stopPropagation();if(!confirm('Удалить?'))return;state.chats=state.chats.filter(c=>c.id!==id);if(state.activeId===id){state.activeId=state.chats[0]?.id||null;if(!state.activeId)return newChat()}save();renderList();renderMsgs()}
function clearAll(){if(!confirm('Удалить ВСЕ?'))return;state.chats=[];state.activeId=null;save();newChat()}
function exportChats(){const blob=new Blob([JSON.stringify(state,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='tigran_chats.json';a.click()}
function importChats(e){const f=e.target.files[0];if(!f)return;const r=new FileReader();r.onload=()=>{try{const d=JSON.parse(r.result);if(d.chats){state.chats=[...d.chats,...state.chats];save();renderList();alert('OK')}}catch(err){alert('Err')}};r.readAsText(f);e.target.value=''}
function renderList(){const el=document.getElementById('chatlist');if(!state.chats.length){el.innerHTML='<div style="color:#6b5a70;font:11px monospace;padding:10px;text-align:center">Пусто</div>';return}el.innerHTML=state.chats.map(c=>'<div class="chatitem'+(c.id===state.activeId?' active':'')+'" onclick="selectChat(\\''+c.id+'\\')"><span class="ttl">'+escapeHtml(c.title)+'</span><i class="fa-solid fa-trash del" onclick="delChat(event,\\''+c.id+'\\')"></i></div>').join('')}
function fmt(t){let s=escapeHtml(t);s=s.replace(/```([\\s\\S]*?)```/g,(m,c)=>'<pre><code>'+c+'</code></pre>');s=s.replace(/`([^`]+)`/g,'<code>$1</code>');s=s.replace(/\\*\\*([^*]+)\\*\\*/g,'<b>$1</b>');s=s.replace(/\\n/g,'<br>');return s}
function renderMsgs(){const box=document.getElementById('msgs');const c=active();if(!c||!c.msgs.length){box.innerHTML='<div class="empty"><h2>TIGRAN AI</h2><p>Задай любой вопрос.</p><div class="chips"><button class="chip" onclick="quick(\\'Привет!\\')">Привет</button><button class="chip" onclick="quick(\\'Напиши функцию Python\\')">Код</button></div></div>';return}box.innerHTML=c.msgs.map(m=>{if(m.role==='user')return '<div class="msg u"><div class="av">Я</div><div class="bub">'+escapeHtml(m.content).replace(/\\n/g,'<br>')+'</div></div>';return '<div class="msg a"><div class="av">AI</div><div class="bub">'+fmt(m.content)+'</div></div>'}).join('');box.scrollTop=box.scrollHeight}
async function sendMsg(){const ta=document.getElementById('ta');const text=ta.value.trim();if(!text)return;if(!active())newChat();const c=active();c.msgs.push({role:'user',content:text});if(c.msgs.filter(m=>m.role==='user').length===1)c.title=text.slice(0,42);ta.value='';save();renderList();renderMsgs();await callAI(c)}
async function callAI(c){const box=document.getElementById('msgs');box.insertAdjacentHTML('beforeend','<div class="msg a" id="typing"><div class="av">AI</div><div class="bub"><span class="typing"><i></i><i></i><i></i></span></div></div>');box.scrollTop=box.scrollHeight;try{const r=await fetch('/api/ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:c.msgs[c.msgs.length-1].content,history:c.msgs.slice(0,-1),model:state.model})});const d=await r.json();document.getElementById('typing')?.remove();if(d.reply){c.msgs.push({role:'assistant',content:d.reply});save();renderMsgs();playSuccess()}else{c.msgs.push({role:'assistant',content:'⚠ '+(d.error||'Err')});save();renderMsgs()}}catch(e){document.getElementById('typing')?.remove();c.msgs.push({role:'assistant',content:'⚠ Ошибка'});save();renderMsgs()}}
function quick(t){document.getElementById('ta').value=t;sendMsg()}
document.getElementById('ta').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMsg()}});
document.getElementById('modelSel').value=state.model;
if(!state.chats.length)newChat();else{if(!state.activeId||!state.chats.find(c=>c.id===state.activeId))state.activeId=state.chats[0].id;renderList();renderMsgs()}
</script></body></html>"""


# ==================== MAIN ====================
def get_public_ip():
    try:
        return requests.get('https://api.ipify.org', timeout=5).text.strip()
    except:
        try:
            return requests.get('https://icanhazip.com', timeout=5).text.strip()
        except:
            return "N/A"


# Запуск фоновых задач
if TELEGRAM_BOT_TOKEN:
    threading.Thread(target=tg_polling, daemon=True).start()
    threading.Thread(target=tg_auto_delete_expired, daemon=True).start()
    threading.Thread(target=tg_daily_report_scheduler, daemon=True).start()
    threading.Thread(target=tg_scheduler_loop, daemon=True).start()
    threading.Thread(target=tg_reminder_scheduler, daemon=True).start()
    threading.Thread(target=tg_achievements_checker, daemon=True).start()


if __name__ == "__main__":
    if not user_configs and not generated_keys:
        load_data()
    port = int(os.environ.get('PORT', 10000))
    print("\n" + "="*50)
    print("  TIGRAN MODZ PROXY ADMIN PANEL")
    print("="*50)
    print(f"  Porta: {port}")
    print(f"  Admin: /Po7eO")
    print("="*50 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)