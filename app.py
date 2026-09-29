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

app = Flask(__name__)
# Используем стабильный ключ из env, чтобы сессии не терялись при рестарте
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(32).hex())
# ==== SECURE COOKIES ====
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,       # только по HTTPS
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # макс тело запроса 2MB
)

# ==== SECURITY HEADERS для ВСЕХ ответов ====
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

# ==================== SECURITY CONFIG ====================
# Хешируем пароль при старте (сам пароль больше в памяти в чистом виде не хранится)
_saved_pass = None
try:
    _pass_file_path = os.path.join(BASE_DIR, "admin_pass.txt")
    if os.path.exists(_pass_file_path):
        with open(_pass_file_path, 'r', encoding='utf-8') as _f:
            _saved_pass = _f.read().strip()
except Exception:
    pass
ADMIN_PASS_HASH = _saved_pass if _saved_pass else generate_password_hash(ADMIN_PASS)
# Доверять ли X-Forwarded-For (Railway ставит свой прокси → True)
TRUST_PROXY = os.environ.get("TRUST_PROXY", "1") == "1"
# Максимум попыток входа
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 900  # 15 минут
# Максимум запросов к AI на IP в час
AI_RATE_LIMIT = 60
# =========================================================

# In-memory хранилища (сбрасываются при рестарте — для Railway это ок)
_login_attempts = defaultdict(list)   # ip -> [timestamps]
_ai_requests = defaultdict(list)      # ip -> [timestamps]

# ==== AI CONFIG ====
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# ==== TELEGRAM BOT ====
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_ID", "")
_tg_last_update_id = 0

ADMINS_FILE = os.path.join(BASE_DIR, "admins.json")
PASS_FILE = os.path.join(BASE_DIR, "admin_pass.txt")


def load_admins_data():
    """Загружает данные: {'admins': [...], 'logs': [...]}."""
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
    """owner / superadmin / admin / guest."""
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


def get_admin_pass():
    try:
        if os.path.exists(PASS_FILE):
            with open(PASS_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception:
        pass
    return None


def set_admin_pass_hash(new_hash):
    try:
        with open(PASS_FILE, 'w', encoding='utf-8') as f:
            f.write(new_hash)
        return True
    except Exception:
        return False


def role_emoji(role):
    return {"owner": "👑", "superadmin": "⭐", "admin": "🎖", "guest": "🚫"}.get(role, "🎖")


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

# ==================== TELEGRAM BOT ====================
import urllib.request
import urllib.parse

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


def tg_notify_admin(text):
    if TELEGRAM_ADMIN_ID and TELEGRAM_BOT_TOKEN:
        tg_send(TELEGRAM_ADMIN_ID, text)

# ==================== UI: КНОПКИ И МЕНЮ ====================

def tg_send_buttons(chat_id, text, buttons):
    """Отправляет сообщение с inline-кнопками."""
    if not TELEGRAM_BOT_TOKEN:
        return None
    return tg_api("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps({"inline_keyboard": buttons})
    })


def tg_answer_callback(callback_id, text="", alert=False):
    """Отвечает на нажатие кнопки (убирает «часики»)."""
    return tg_api("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": text,
        "show_alert": "true" if alert else "false"
    })


def tg_edit_message(chat_id, message_id, text, buttons=None):
    """Редактирует уже отправленное сообщение."""
    params = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if buttons:
        params["reply_markup"] = json.dumps({"inline_keyboard": buttons})
    return tg_api("editMessageText", params)


def tg_reply_keyboard(chat_id, text, buttons):
    """Нижняя клавиатура (большие кнопки внизу экрана)."""
    if not TELEGRAM_BOT_TOKEN:
        return None
    return tg_api("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps({
            "keyboard": buttons,
            "resize_keyboard": True,
            "is_persistent": True
        })
    })


def tg_remove_keyboard(chat_id, text):
    """Убирает reply-клавиатуру."""
    return tg_api("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps({"remove_keyboard": True})
    })
    
    # ==================== UI: МЕНЮ БОТА ====================

PAGE_SIZE = 5  # ключей на странице


def tg_main_menu(chat_id):
    """Красивое главное меню."""
    role = get_user_role(chat_id)
    if role == "guest":
        tg_send(chat_id, "⛔ Доступ запрещён.")
        return

    is_super = role in ("owner", "superadmin")
    is_owner = role == "owner"

    buttons = [
        [
            {"text": "🔑 Ключи", "callback_data": "menu_keys_0"},
            {"text": "🌐 Сессии", "callback_data": "menu_sessions"}
        ],
        [
            {"text": "📊 Статистика", "callback_data": "menu_stats"},
            {"text": "👥 Админы", "callback_data": "menu_admins"}
        ],
        [
            {"text": "🔍 Поиск ключа", "callback_data": "menu_search"},
            {"text": "🎯 Быстрые действия", "callback_data": "menu_quick"}
        ],
    ]
    if is_super:
        buttons.append([
            {"text": "➕ Добавить админа", "callback_data": "menu_addadmin"}
        ])
    if is_owner:
        buttons.append([
            {"text": "💾 Backup", "callback_data": "menu_backup"},
            {"text": "📜 Логи", "callback_data": "menu_logs"}
        ])
        buttons.append([
            {"text": "📢 Рассылка", "callback_data": "menu_broadcast"},
            {"text": "🔑 Пароль", "callback_data": "menu_setpass"}
        ])
        buttons.append([
            {"text": "⚙ Настройки", "callback_data": "menu_settings"}
        ])

    tg_send_buttons(chat_id,
        f"{role_emoji(role)} <b>TIGRAN MODZ BOT</b>\n"
        f"Роль: <b>{role.upper()}</b>\n"
        f"ID: <code>{chat_id}</code>\n\n"
        f"👇 Выбери действие:",
        buttons
    )


def tg_menu_keys(chat_id, message_id, page=0):
    """Меню ключей с пагинацией."""
    if not generated_keys:
        text = "📋 <b>Ключей нет</b>"
        buttons = [
            [{"text": "🔑 Создать ключ", "callback_data": "quick_genkey"}],
            [{"text": "◀ Назад", "callback_data": "menu_back"}]
        ]
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

    # Кнопки навигации
    nav = []
    if page > 0:
        nav.append({"text": "◀", "callback_data": f"menu_keys_{page-1}"})
    nav.append({"text": f"{page+1}/{total_pages}", "callback_data": "noop"})
    if page < total_pages - 1:
        nav.append({"text": "▶", "callback_data": f"menu_keys_{page+1}"})

    buttons = [nav]
    buttons.append([{"text": "🔑 Создать ключ", "callback_data": "quick_genkey"}])
    buttons.append([{"text": "◀ Назад", "callback_data": "menu_back"}])

    tg_edit_message(chat_id, message_id, text, buttons)


def tg_menu_sessions(chat_id, message_id):
    """Меню активных сессий."""
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
    """Меню статистики."""
    text = (
        f"📊 <b>Статистика сервера</b>\n\n"
        f"🔑 Всего ключей: <b>{len(generated_keys)}</b>\n"
        f"🌐 Активных IP: <b>{len(registered_ips)}</b>\n"
        f"🤖 AI-запросов: <b>{sum(len(v) for v in _ai_requests.values())}</b>\n"
        f"👥 Админов: <b>{1 + len(load_admins_data().get('admins', []))}</b>\n"
        f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    tg_edit_message(chat_id, message_id, text,
        [[{"text": "◀ Назад", "callback_data": "menu_back"}]])


def tg_menu_admins(chat_id, message_id):
    """Меню списка админов."""
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
    """Меню быстрых действий."""
    buttons = [
        [{"text": "🔑 Ключ (1 IP, 7д)", "callback_data": "quick_genkey"}],
        [{"text": "🔑 Ключ (5 IP, 30д)", "callback_data": "quick_genkey_big"}],
        [{"text": "📊 Обновить статистику", "callback_data": "menu_stats"}],
        [{"text": "◀ Назад", "callback_data": "menu_back"}]
    ]
    tg_edit_message(chat_id, message_id,
        "🎯 <b>Быстрые действия</b>\n\nВыбери готовый шаблон:",
        buttons)


def tg_handle_callback(callback):
    """Обрабатывает нажатия inline-кнопок."""
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
        # ============ НАВИГАЦИЯ ============
        if data == "menu_back":
            tg_main_menu(chat_id)
            return

        if data == "noop":
            return

        # ============ МЕНЮ КЛЮЧЕЙ С ПАГИНАЦИЕЙ ============
        if data.startswith("menu_keys_"):
            try:
                page = int(data.split("_")[-1])
            except:
                page = 0
            tg_menu_keys(chat_id, msg_id, page)
            return

        if data == "menu_sessions":
            tg_menu_sessions(chat_id, msg_id)
            return

        if data == "menu_stats":
            tg_menu_stats(chat_id, msg_id)
            return

        if data == "menu_admins":
            tg_menu_admins(chat_id, msg_id)
            return

        if data == "menu_quick":
            tg_menu_quick(chat_id, msg_id)
            return

        if data == "menu_search":
            tg_edit_message(chat_id, msg_id,
                "🔍 <b>Поиск ключа</b>\n\n"
                "Напиши: <code>/find ЧАСТЬ_КЛЮЧА</code>\n"
                "Например: <code>/find MDZ</code>",
                [[{"text": "◀ Назад", "callback_data": "menu_back"}]])
            return

        # ============ БЫСТРЫЕ ДЕЙСТВИЯ ============
        if data == "quick_genkey":
            new_key = generate_key("TIGRAN-MDZ-PROXY")
            generated_keys[new_key] = {
                'prefix': 'TIGRAN-MDZ-PROXY',
                'limit': 1, 'days': 7,
                'created': datetime.now().isoformat(), 'used_ips': []
            }
            save_data()
            tg_log("genkey_btn", chat_id, new_key)
            tg_send(chat_id,
                f"✅ <b>Ключ создан</b>\n\n<code>{new_key}</code>\n\n"
                f"Лимит: 1 IP\nДней: 7")
            return

        if data == "quick_genkey_big":
            new_key = generate_key("TIGRAN-MDZ-PROXY")
            generated_keys[new_key] = {
                'prefix': 'TIGRAN-MDZ-PROXY',
                'limit': 5, 'days': 30,
                'created': datetime.now().isoformat(), 'used_ips': []
            }
            save_data()
            tg_log("genkey_btn", chat_id, new_key)
            tg_send(chat_id,
                f"✅ <b>Ключ создан</b>\n\n<code>{new_key}</code>\n\n"
                f"Лимит: 5 IP\nДней: 30")
            return

        # ============ УПРАВЛЕНИЕ АДМИНАМИ (SUPER+) ============
        if data == "menu_addadmin":
            if not is_super_or_owner(chat_id):
                tg_answer_callback(cb_id, "⛔ Нет прав", alert=True)
                return
            tg_send(chat_id,
                "➕ <b>Добавление админа</b>\n\n"
                "Напиши команду:\n"
                "<code>/addadmin 123456789 admin</code>\n"
                "или для супер-админа:\n"
                "<code>/addadmin 123456789 superadmin</code>")
            return

        # ============ ТОЛЬКО OWNER ============
        if data == "menu_backup":
            if not is_main_admin(chat_id):
                tg_answer_callback(cb_id, "⛔ Только owner", alert=True)
                return
            payload = {
                "generated_keys": generated_keys,
                "registered_ips": registered_ips,
                "key_expiry": {k: v.isoformat() for k, v in key_expiry.items()},
                "admins": load_admins_data(),
                "exported_at": datetime.now().isoformat()
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
                tg_answer_callback(cb_id, "⛔ Только owner", alert=True)
                return
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
                tg_answer_callback(cb_id, "⛔ Только owner", alert=True)
                return
            tg_send(chat_id, "📢 Напиши:\n<code>/broadcast Твой текст</code>")
            return

        if data == "menu_setpass":
            if not is_main_admin(chat_id):
                tg_answer_callback(cb_id, "⛔ Только owner", alert=True)
                return
            tg_send(chat_id, "🔑 Напиши:\n<code>/setpass НовыйПароль123</code>")
            return

        if data == "menu_settings":
            if not is_main_admin(chat_id):
                tg_answer_callback(cb_id, "⛔ Только owner", alert=True)
                return
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

        # ============ ЕСЛИ НЕИЗВЕСТНАЯ КНОПКА ============
        tg_answer_callback(cb_id, "⚠ Неизвестное действие", alert=False)

    except Exception as e:
        print(f"[TG] callback error: {e}")
        tg_send(chat_id, f"❌ Ошибка: {e}")

def tg_owner_ai_agent(chat_id, text):
    """AI-агент управления для Owner. Понимает команды на естественном языке."""
    if not OPENAI_API_KEY:
        return None
    system_prompt = (
        "Ты AI-агент управления Telegram-ботом TIGRAN MODZ для OWNER.\n"
        "Пользователь даёт команды на естественном языке (русский, английский, любой).\n"
        "Ты должен ВЕРНУТЬ ТОЛЬКО валидный JSON без markdown, без пояснений.\n\n"
        "Формат ответа:\n"
        '{"action": "ТИП", "params": {...}}\n\n'
        "Доступные action:\n"
        "- create_key: создать ключ. params: {\"custom_key\": \"если хотят точный ключ\", \"prefix\": \"TIGRAN-MDZ-PROXY\", \"limit\": 1, \"days\": 7}\n"
        "- revoke_key: удалить ключ. params: {\"key\": \"...\"}\n"
        "- list_keys: показать все ключи. params: {}\n"
        "- list_sessions: активные сессии. params: {}\n"
        "- list_admins: список админов. params: {}\n"
        "- add_admin: добавить админа. params: {\"id\": \"123456789\", \"role\": \"admin|superadmin\"}\n"
        "- del_admin: удалить админа. params: {\"id\": \"123456789\"}\n"
        "- set_role: сменить роль. params: {\"id\": \"123456789\", \"role\": \"admin|superadmin\"}\n"
        "- stats: статистика. params: {}\n"
        "- backup: экспорт данных. params: {}\n"
        "- help: справка. params: {}\n"
        "- chat: если это НЕ команда управления, а просто вопрос. params: {\"question\": \"текст вопроса\"}\n\n"
        "ВНИМАНИЕ: если пользователь просто спрашивает/общается — верни {\"action\":\"chat\",\"params\":{\"question\":\"<его вопрос>\"}}\n"
        "Примеры:\n"
        "'создай ключ TIGRAN-MDZ-PROXY-893YKP8S09' → {\"action\":\"create_key\",\"params\":{\"custom_key\":\"TIGRAN-MDZ-PROXY-893YKP8S09\"}}\n"
        "'создай ключ на 30 дней лимит 5' → {\"action\":\"create_key\",\"params\":{\"limit\":5,\"days\":30}}\n"
        "'удали ключ ABC-123' → {\"action\":\"revoke_key\",\"params\":{\"key\":\"ABC-123\"}}\n"
        "'сколько ключей?' → {\"action\":\"stats\",\"params\":{}}\n"
        "'как дела?' → {\"action\":\"chat\",\"params\":{\"question\":\"как дела?\"}}\n"
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
                "max_tokens": 300,
                "temperature": 0.1
            },
            timeout=25
        )
        if r.status_code != 200:
            print(f"[OwnerAI] HTTP {r.status_code}")
            return None
        content = r.json()['choices'][0]['message']['content'].strip()
        # Убираем ```json ... ```
        content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content, flags=re.MULTILINE).strip()
        # Иногда AI добавляет текст — берём первую {...}
        m = re.search(r'\{[\s\S]*\}', content)
        if m:
            content = m.group(0)
        return json.loads(content)
    except Exception as e:
        print(f"[OwnerAI] error: {e}")
        return None


def tg_owner_execute_ai(chat_id, action_data):
    """Выполняет действие от AI-агента. Возвращает True если выполнено, False — если это просто chat."""
    act = action_data.get('action', 'chat')
    params = action_data.get('params') or {}

    if act == 'chat':
        return False  # отдаём дальше обычному AI

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
        tg_send(chat_id,
            f"🤖 <b>AI создал ключ</b>\n\n<code>{new_key}</code>\n\n"
            f"Лимит IP: {limit}\nДней: {days}")
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
        try: tg_send(new_id, f"{em} Тебя назначили ({new_role}) в TIGRAN MODZ BOT!\nНапиши /help")
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
        try: tg_send(del_id, "⚠️ Твои права админа отозваны.")
        except: pass
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
        tg_log("ai_setrole", chat_id, f"{tgt_id}:{new_role}")
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
                "generated_keys": generated_keys,
                "registered_ips": registered_ips,
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
        return False  # пусть покажет стандартный /help

    return False

def tg_handle_command(chat_id, text):
    role = get_user_role(chat_id)
    if role == "guest":
        tg_send(chat_id,
            "⛔ <b>Доступ запрещён</b>\n\n"
            f"Твой ID: <code>{chat_id}</code>\n\n"
            "Передай этот ID главному админу, чтобы получить доступ."
        )
        return

    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower() if parts else ""
    args = parts[1].split() if len(parts) > 1 else []
    rest = parts[1] if len(parts) > 1 else ""

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
            "/sessions — активные сессии\n"
            "/stats — статистика\n"
        )
        if is_super:
             help_text += (
        "\n🎖 <b>Управление админами:</b>\n"
        "/admins — список всех\n"
        "/addadmin ID [role] — добавить (admin/superadmin)\n"
        "/deladmin ID — удалить\n"
        "/setrole ID role — изменить роль\n"
    )
if is_owner:
    help_text += (
        "\n👑 <b>Только owner:</b>\n"
        "/setpass НОВЫЙ_ПАРОЛЬ — сменить пароль админки\n"
        "/broadcast ТЕКСТ — рассылка всем админам\n"
        "/backup — выгрузить все данные\n"
        "/logs — последние действия\n"
    )
help_text += "\n🤖 <b>AI:</b> просто напиши любое сообщение без / — ответит AI"
tg_send(chat_id, help_text)
tg_main_menu(chat_id)
return

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
            f"Админов: {1 + len(load_admins_data().get('admins', []))}"
        )
        return
        
        if cmd == "/find":
    if not args:
        tg_send(chat_id, "Использование: <code>/find ЧАСТЬ_КЛЮЧА</code>")
        return
    query = normalize_key(" ".join(args))
    found = []
    for k, v in generated_keys.items():
        if query in k:
            found.append((k, v))
    if not found:
        tg_send(chat_id, f"🔍 По запросу <code>{query}</code> ничего не найдено.")
        return
    lines = [f"🔍 <b>Найдено: {len(found)}</b>\n"]
    for k, v in found[:15]:
        lines.append(f"<code>{k}</code> — {len(v['used_ips'])}/{v['limit']} · {v['days']}d")
    tg_send(chat_id, "\n".join(lines))
    return

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
            tg_send(chat_id, "⛔ Только owner/superadmin могут добавлять.")
            return
        if not args:
            tg_send(chat_id, "Использование:\n<code>/addadmin 123456789 admin</code>\nили\n<code>/addadmin 123456789 superadmin</code>")
            return
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
        try: tg_send(new_id, f"{em} Тебя назначили ({new_role}) в TIGRAN MODZ BOT!\nНапиши /help")
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
        try: tg_send(del_id, "⚠️ Твои права админа отозваны.")
        except: pass
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

    # ============ ТОЛЬКО OWNER ============
    if cmd == "/setpass":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только 👑 OWNER может менять пароль админки."); return
        if not rest.strip():
            tg_send(chat_id, "Использование: <code>/setpass НовыйПароль123</code>"); return
        global ADMIN_PASS_HASH
        try:
            new_hash = generate_password_hash(rest.strip())
            set_admin_pass_hash(new_hash)
            ADMIN_PASS_HASH = new_hash
            tg_log("setpass", chat_id, "")
            tg_send(chat_id, "✅ <b>Пароль админки изменён!</b>\n\n⚠️ Старый пароль больше не работает.")
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
            try: tg_send(a['id'], f"📢 <b>РАССЫЛКА ОТ OWNER:</b>\n\n{rest}"); ok += 1
            except: pass
        tg_send(chat_id, f"✅ Отправлено {ok} админам.")
        return

    if cmd == "/backup":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Только 👑 OWNER."); return
        try:
            payload = {
                "generated_keys": generated_keys,
                "registered_ips": registered_ips,
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

    # ============ AI ============
    if cmd.startswith("/"):
        tg_send(chat_id, "❓ Неизвестная команда. /help")
        return

    if not OPENAI_API_KEY:
        tg_send(chat_id, "🤖 AI не настроен (нет OPENAI_API_KEY).")
        return

    user_msg = text.strip()
    if not user_msg:
        return

    # ==== OWNER AI-АГЕНТ ====
    if role == "owner":
        tg_send(chat_id, "🧠 <i>Анализирую...</i>")
        action_data = tg_owner_ai_agent(chat_id, user_msg)
        if action_data:
            executed = tg_owner_execute_ai(chat_id, action_data)
            if executed:
                return

    # ==== ОБЫЧНЫЙ AI-ЧАТ ====
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
                        "Отвечай кратко (до 500 символов), по делу, на языке пользователя. "
                        "Ты можешь помочь с ключами, объяснить команды бота, ответить на любые вопросы."
                    )},
                    {"role": "user", "content": user_msg[:1500]}
                ],
                "max_tokens": 500,
                "temperature": 0.7
            },
            timeout=25
        )
        if r.status_code == 200:
            reply = r.json()['choices'][0]['message']['content']
            tg_send(chat_id, reply)
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

                    # ==== CALLBACK (нажатие кнопок) ====
                    if "callback_query" in upd:
                        try:
                            tg_handle_callback(upd["callback_query"])
                        except Exception as e:
                            print(f"[TG] callback error: {e}")
                        continue

                    # ==== MESSAGE ====
                    msg = upd.get("message") or upd.get("edited_message")
                    if msg and "text" in msg:
                        tg_handle_command(msg["chat"]["id"], msg["text"])
        except Exception as e:
            print(f"[TG] Polling error: {e}")
        time.sleep(1)


if TELEGRAM_BOT_TOKEN:
    threading.Thread(target=tg_polling, daemon=True).start()
# ========================================================


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
    """Возвращает IP клиента. Учитывает X-Forwarded-For только если включен TRUST_PROXY."""
    if TRUST_PROXY and request.headers.get('X-Forwarded-For'):
        # берем первый IP в цепочке
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if TRUST_PROXY and request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP').strip()
    return request.remote_addr or "0.0.0.0"


def check_rate_limit(store, ip, max_requests, window_seconds):
    """True = можно, False = превышен лимит."""
    now = _time.time()
    store[ip] = [t for t in store[ip] if now - t < window_seconds]
    if len(store[ip]) >= max_requests:
        return False
    store[ip].append(now)
    return True


def is_login_locked(ip):
    """Проверяет, заблокирован ли IP за много неудачных попыток."""
    now = _time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < LOGIN_LOCKOUT_SECONDS]
    return len(_login_attempts[ip]) >= MAX_LOGIN_ATTEMPTS


def record_failed_login(ip):
    _login_attempts[ip].append(_time.time())


def clear_login_attempts(ip):
    _login_attempts.pop(ip, None)


def safe_join_cdn(path):
    """Защита от path traversal. Возвращает безопасный путь или None."""
    if not path:
        return ""
    # убираем .. и абсолютные пути
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

def normalize_key(value):
    return re.sub(r"\s+", "", str(value or "")).upper()

def generate_key(prefix="TIGRAN-MDZ-PROXY"):
    prefix = normalize_key(prefix) or "TIGRAN-MDZ-PROXY"
    # 10 символов из букв+цифр — невозможно подобрать брутфорсом
    alphabet = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(10))
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
    client_ip = get_client_ip()
    if request.method == 'POST':
        if is_login_locked(client_ip):
            return render_template_string(LOGIN_PAGE, error="СЛИШКОМ МНОГО ПОПЫТОК. ПОДОЖДИ 15 МИНУТ."), 429
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        # защита от timing-attack: сравниваем и юзер и пароль через константное время
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
                                 keys=generated_keys,
                                 ips=registered_ips,
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

    tg_notify_admin(f"Новый вход\n\nIP: <code>{client_ip}</code>\nКлюч: <code>{key}</code>\nДо: {expiry_date.strftime('%d/%m/%Y')}")

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

    # защита от path traversal
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

# ==================== AI ASSISTANT ====================
@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    if not OPENAI_API_KEY:
        return jsonify({'error': 'AI nao configurado. Adicione OPENAI_API_KEY no Railway.'}), 503
    client_ip = get_client_ip()
    if not check_rate_limit(_ai_requests, client_ip, AI_RATE_LIMIT, 3600):
        return jsonify({'error': 'Лимит AI запросов исчерпан. Попробуй через час.'}), 429
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
                "You can answer ANY question on ANY topic: science, math, programming, history, "
                "languages, advice, creative writing, translations, code generation, etc. "
                "Do NOT restrict yourself to only the TIGRAN MODZ panel — you are a general-purpose AI. "
                "You also know about the TIGRAN MODZ PROXY panel (functions: HS_NECK, HS_CHEST, "
                "BACKJUMPV1, HIGH_SENSI, ZIG_ZAG_MOVE, keys, sessions), so if asked about it — help. "
                "IMPORTANT: Always detect the language of the user's message and reply in THAT EXACT language. "
                "Russian → Russian, English → English, Portuguese → Portuguese, Spanish → Spanish, "
                "Armenian → Armenian, Turkish → Turkish, Arabic → Arabic, Hindi → Hindi, "
                "Chinese → Chinese, Japanese → Japanese, and any other language. "
                "Match the user's language perfectly. Be accurate, helpful and thorough."
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
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model_choice,
                "messages": messages,
                "max_tokens": 600,
                "temperature": 0.7
            },
            timeout=30
        )
        if r.status_code != 200:
            return jsonify({'error': f'AI HTTP {r.status_code}'}), 502
        reply = r.json()['choices'][0]['message']['content']
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'error': f'Erro AI: {str(e)[:120]}'}), 500

# ==================== USER INFO ====================
@app.route('/api/user/info', methods=['GET'])
def user_info():
    client_ip = get_client_ip()
    info = {
        'ip': client_ip, 'country': None, 'country_code': None, 'city': None,
        'region': None, 'timezone': None, 'lat': None, 'lon': None, 'weather': None
    }
    try:
        r = requests.get(
            f"http://ip-api.com/json/{client_ip}?fields=status,country,countryCode,regionName,city,timezone,lat,lon",
            timeout=5
        )
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
                        w = requests.get(
                            f"https://wttr.in/{info['lat']},{info['lon']}?format=j1",
                            timeout=6
                        )
                        if w.status_code == 200:
                            wd = w.json()
                            cur = wd['current_condition'][0]
                            info['weather'] = {
                                'temp': cur.get('temp_C'),
                                'feels': cur.get('FeelsLikeC'),
                                'desc': cur.get('weatherDesc', [{}])[0].get('value', ''),
                                'humidity': cur.get('humidity'),
                                'wind': cur.get('windspeedKmph'),
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
    return jsonify({'success': False, 'message': 'INFORME UMA KEY VÁLIDA NA PÁGINA DE ACESSO'}), 400
    
# ==================== TOOLS PAGE ====================
@app.route('/tools')
def tools_page():
    """Отдаёт HTML-файл с инструментами"""
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
# =====================================================


# ==================== NEON DESIGN SYSTEM (общий CSS) ====================
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
.glow-btn:before{content:"";position:absolute;top:0;left:-100%;width:100%;height:100%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.4),transparent);transition:.6s}
.glow-btn:hover:before{left:100%}
.field{position:relative;margin:18px 0}
.field label{display:block;font:700 10px monospace;letter-spacing:3px;color:var(--muted);margin-bottom:9px;text-transform:uppercase}
.field input{width:100%;padding:15px 16px;border-radius:12px;border:1px solid var(--line);background:rgba(5,3,10,.7);color:var(--ink);outline:none;font:inherit;transition:.25s}
.field input:focus{border-color:var(--p1);box-shadow:0 0 0 4px rgba(255,45,149,.15),0 0 25px rgba(255,45,149,.3)}
.spinner{width:34px;height:34px;border-radius:50%;border:3px solid transparent;border-top-color:var(--p1);border-right-color:var(--p2);animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
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

# ==================== NEON JS (общий скрипт: частицы, звук, AI, курсор) ====================
NEON_JS = """
(function(){
  // ==== ПЕРСОНАЛЬНЫЙ КУРСОР ====
  const cur=document.getElementById('neonCursor');
  if(cur&&window.matchMedia('(pointer:fine)').matches){
    window.addEventListener('mousemove',e=>{cur.style.left=e.clientX+'px';cur.style.top=e.clientY+'px'});
    document.querySelectorAll('button,a,input').forEach(el=>{
      el.addEventListener('mouseenter',()=>cur.style.transform='translate(-50%,-50%) scale(1.6)');
      el.addEventListener('mouseleave',()=>cur.style.transform='translate(-50%,-50%) scale(1)');
    });
  } else if(cur){cur.style.display='none'}

  // ==== КАНВАС-ЧАСТИЦЫ ====
  const c=document.getElementById('neonBg');
  if(c){
    const x=c.getContext('2d');let w,h,ps=[];
    function rs(){w=c.width=innerWidth;h=c.height=innerHeight;ps=[];const n=Math.min(70,Math.floor(w/22));for(let i=0;i<n;i++)ps.push({x:Math.random()*w,y:Math.random()*h,vx:(Math.random()-.5)*.4,vy:(Math.random()-.5)*.4,r:Math.random()*1.8+.4,c:['#ff2d95','#a855f7','#22d3ee'][Math.floor(Math.random()*3)]})}
    function lp(){x.clearRect(0,0,w,h);for(const p of ps){p.x+=p.vx;p.y+=p.vy;if(p.x<0||p.x>w)p.vx*=-1;if(p.y<0||p.y>h)p.vy*=-1;x.beginPath();x.arc(p.x,p.y,p.r,0,7);x.fillStyle=p.c;x.shadowBlur=12;x.shadowColor=p.c;x.fill()}for(let i=0;i<ps.length;i++)for(let j=i+1;j<ps.length;j++){const dx=ps[i].x-ps[j].x,dy=ps[i].y-ps[j].y,d=Math.hypot(dx,dy);if(d<130){x.beginPath();x.moveTo(ps[i].x,ps[i].y);x.lineTo(ps[j].x,ps[j].y);x.strokeStyle='rgba(168,85,247,'+(1-d/130)*.18+')';x.lineWidth=.6;x.stroke()}}requestAnimationFrame(lp)}
    addEventListener('resize',rs);rs();lp();
  }

  // ==== ЗВУКИ (Web Audio) ====
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

  // ==== AI ВИДЖЕТ ====
  if(document.body.dataset.ai==='1'){
    const b=document.createElement('button');b.id='aiBtn';b.innerHTML='<i class="fa-solid fa-robot"></i>';document.body.appendChild(b);
    const p=document.createElement('div');p.id='aiPanel';p.innerHTML='<div id="aiHead"><span>◉ AI ASSISTANT</span><span style="cursor:pointer" id="aiX">✕</span></div><div id="aiLog"><div class="m a">Olá! Sou o assistente AI do TIGRAN MODZ. Pergunte sobre funções, keys ou configuração.</div></div><form id="aiForm"><input id="aiInput" placeholder="Pergunte algo..." autocomplete="off"><button id="aiSend" type="submit">▶</button></form>';
    document.body.appendChild(p);
    let hist=[];
    b.onclick=()=>{p.classList.toggle('open');playClick();document.getElementById('aiInput').focus()};
    document.getElementById('aiX').onclick=()=>p.classList.remove('open');
    document.getElementById('aiForm').onsubmit=async e=>{
      e.preventDefault();const inp=document.getElementById('aiInput'),log=document.getElementById('aiLog');
      const msg=inp.value.trim();if(!msg)return;inp.value='';
      log.insertAdjacentHTML('beforeend','<div class="m u"></div>');log.lastChild.textContent=msg;
      log.insertAdjacentHTML('beforeend','<div class="m a pulse">digitando...</div>');log.scrollTop=log.scrollHeight;
      try{
        const r=await fetch('/api/ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,history:hist})});
        const d=await r.json();log.lastChild.remove();
        if(d.reply){log.insertAdjacentHTML('beforeend','<div class="m a"></div>');log.lastChild.textContent=d.reply;hist.push({role:'user',content:msg},{role:'assistant',content:d.reply});playSuccess()}
        else{log.insertAdjacentHTML('beforeend','<div class="m a" style="color:#ff8e8e"></div>');log.lastChild.textContent='⚠ '+(d.error||'Erro');playError()}
      }catch(err){log.lastChild.remove();log.insertAdjacentHTML('beforeend','<div class="m a" style="color:#ff8e8e">⚠ Falha de conexão</div>');playError()}
      log.scrollTop=log.scrollHeight;
    };
  }
})();
"""

# ==================== LOGIN_PAGE (неоновая) ====================
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
<section class="manifest"><div><div class="mark"><i class="fa-solid fa-bolt"></i> TIGRAN MODZ PROXY</div><div class="scan"></div><div style="margin-top:60px" class="label">PRIVATE CONTROL SYSTEM</div><h1>Enter the <span class="neon-text">operator</span> console.</h1><p>Área administrativa para controle de acessos, keys e sessões ativas.</p></div><div style="font:11px monospace;color:#7a6578;letter-spacing:2px">NODE / 07 · AUTH REQUIRED</div></section>
<section class="form-panel"><div class="label">ADMIN AUTHENTICATION</div><h2>Entrar no painel</h2><p class="sub">Informe suas credenciais para continuar.</p>
<form method="POST" autocomplete="on"><div class="field"><label for="u">Usuário</label><input id="u" name="username" required placeholder="seu usuário"></div><div class="field"><label for="p">Senha</label><input id="p" type="password" name="password" required placeholder="sua senha"></div><button class="glow-btn" type="submit">Acessar console <i class="fa-solid fa-arrow-right"></i></button>{% if error %}<div class="error">{{ error }}</div>{% endif %}</form>
<div class="foot"><i class="fa-solid fa-shield-halved"></i> SESSÃO PROTEGIDA · TIGRAN MODZ PROXY</div></section>
</main></div>
<script>""" + NEON_JS + """</script></body></html>"""

# ==================== KEY_PAGE (неоновая, с данными о пользователе) ====================
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
@media(max-width:780px){.access{grid-template-columns:1fr;border-radius:0}.visual{padding:28px 20px}.visual h1{font-size:38px;letter-spacing:-2px}.access-form{padding:28px 20px}.info-strip{grid-template-columns:1fr 1fr}}
</style></head><body>
<canvas id="neonBg"></canvas><div id="neonCursor"></div><button id="muteBtn">🔊</button>
<div class="wrap"><main class="access glass fade-in">
<section class="visual"><div><div class="brand"><i class="fa-solid fa-key"></i> TIGRAN MODZ <b>PROXY</b></div><div class="scan"></div><div style="margin-top:40px" class="label">ACCESS GATE / 01</div><h1>One key. <span class="neon-text">Full access.</span></h1><p>Use uma key emitida pelo administrador para abrir seu painel de controle.</p></div>
<div class="info-strip">
<div class="info-card"><small><i class="fa-solid fa-globe"></i> País</small><b id="uCountry">—</b></div>
<div class="info-card"><small><i class="fa-solid fa-location-dot"></i> Cidade</small><b id="uCity">—</b></div>
<div class="info-card"><small><i class="fa-solid fa-clock"></i> Hora local</small><b id="uTime">--:--:--</b></div>
<div class="info-card"><small><i class="fa-solid fa-cloud-sun"></i> Clima</small><b id="uWeather">—</b></div>
</div></section>
<section class="access-form"><div class="label">USER ACCESS</div><h2>Validar acesso</h2><p class="sub">Cole sua key para continuar.</p>
<form id="keyForm"><div class="field"><label for="k">Access key</label><input id="k" required spellcheck="false" placeholder="TIGRAN-MDZ-PROXY-0000"></div><button class="glow-btn" type="submit">Abrir dashboard <i class="fa-solid fa-arrow-up-right-from-square"></i></button><div id="keyError"></div></form>
<div class="hint">Keys são geradas exclusivamente pelo administrador.</div>
<div class="foot"><i class="fa-solid fa-lock"></i> ENCRYPTED SESSION</div></section>
</main></div>
<script>""" + NEON_JS + """
// ==== ЖИВЫЕ ДАННЫЕ О ПОЛЬЗОВАТЕЛЕ ====
fetch('/api/user/info').then(r=>r.json()).then(d=>{
  document.getElementById('uCountry').textContent=(d.country||'—')+(d.country_code?' ('+d.country_code+')':'');
  document.getElementById('uCity').textContent=d.city||'—';
  if(d.timezone){
    function tick(){
      try{
        const t=new Date().toLocaleTimeString('ru-RU',{timeZone:d.timezone,hour12:false});
        document.getElementById('uTime').textContent=t;
      }catch(e){document.getElementById('uTime').textContent=new Date().toLocaleTimeString('ru-RU')}
    }
    tick();setInterval(tick,1000);
  }
  if(d.weather){
    const w=d.weather;
    document.getElementById('uWeather').textContent=(w.is_day?'☀ ':'🌙 ')+(w.temp||'?')+'°C · '+(w.desc||'');
  }
}).catch(()=>{});
document.getElementById('keyForm').addEventListener('submit',async e=>{
  e.preventDefault();const b=e.target.querySelector('button'),m=document.getElementById('keyError');
  b.disabled=true;m.textContent='VALIDANDO KEY...';
  try{
    const r=await fetch('/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:document.getElementById('k').value.trim()})});
    const d=await r.json();if(!r.ok||!d.success)throw Error(d.message||'KEY INVÁLIDA');
    playSuccess();m.style.color='#22d3ee';m.textContent='✓ ACESSO LIBERADO';
    setTimeout(()=>location.href='/dashboard',700);
  }catch(err){m.style.color='#ff8e8e';m.textContent=err.message;playError();b.disabled=false}
});
</script></body></html>"""

# ==================== ADMIN_DASHBOARD (неоновая) ====================
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
.nav-links a:hover,.nav-links a.active{background:linear-gradient(90deg,rgba(255,45,149,.15),transparent);border-color:rgba(255,45,149,.35);color:#fff;transform:translateX(3px)}
.logout{display:block;margin-top:auto;padding:12px 14px;color:#ff9a9a;text-decoration:none;font:700 10px monospace;letter-spacing:1px;border-radius:12px;border:1px solid rgba(255,100,100,.25);text-align:center;transition:.2s;cursor:none}
.logout:hover{background:rgba(255,100,100,.1)}
.workspace{padding:32px 40px;max-width:1300px;width:100%}
.bar{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid var(--line);padding-bottom:26px;flex-wrap:wrap;gap:14px}
.bar h1{font-size:38px;letter-spacing:-2px;margin:8px 0 0}
.eyebrow{font:700 10px monospace;letter-spacing:2px;color:var(--p3)}
.profile{color:var(--muted);font:11px monospace;padding:8px 14px;border-radius:999px;background:rgba(34,211,238,.1);border:1px solid rgba(34,211,238,.3)}
.profile i{color:var(--p1);text-shadow:0 0 10px var(--p1)}
.cards{display:grid;grid-template-columns:1.2fr .8fr;gap:16px;margin-top:24px}
.card{background:rgba(20,10,30,.55);backdrop-filter:blur(14px);border:1px solid var(--line);border-radius:18px;padding:22px;transition:.25s;position:relative;overflow:hidden}
.card:hover{border-color:rgba(255,45,149,.5);box-shadow:0 0 30px rgba(255,45,149,.15)}
.card h2{font-size:13px;margin:0 0 18px;letter-spacing:1px;text-transform:uppercase;color:var(--p3)}
.field label{display:block;color:var(--muted);font:700 10px monospace;letter-spacing:1px;margin-bottom:7px}
.field input{width:100%;padding:12px 14px;border-radius:10px;border:1px solid var(--line);background:rgba(5,3,10,.7);color:#fff;outline:none;font:inherit;transition:.2s}
.field input:focus{border-color:var(--p1);box-shadow:0 0 0 3px rgba(255,45,149,.15)}
.stats{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.stat{padding:18px;background:rgba(10,5,20,.6);border:1px solid var(--line);border-radius:14px;position:relative;overflow:hidden}
.stat:before{content:"";position:absolute;top:-20px;right:-20px;width:80px;height:80px;background:radial-gradient(circle,var(--p1),transparent 70%);opacity:.25}
.stat small{display:block;color:var(--muted);font:700 9px monospace;letter-spacing:1.5px}
.stat strong{display:block;font-size:34px;margin-top:10px;background:linear-gradient(135deg,var(--p1),var(--p3));-webkit-background-clip:text;background-clip:text;color:transparent}
.wide{margin-top:16px}
.table-wrap{overflow-x:auto;border-radius:12px}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{text-align:left;padding:13px 10px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font:700 9px monospace;letter-spacing:1.5px;text-transform:uppercase}
td{color:#d8c9e0}
.badge{padding:5px 9px;border-radius:8px;background:rgba(255,45,149,.12);border:1px solid rgba(255,45,149,.35);color:#ff7ec0;font:700 10px monospace}
.danger{background:rgba(255,80,80,.15);border:1px solid rgba(255,80,80,.4);color:#ffaaaa;font:800 10px monospace;padding:8px 12px;border-radius:8px;cursor:none;transition:.2s}
.danger:hover{background:rgba(255,80,80,.3)}
.generated{margin-top:14px;padding:12px;border-radius:10px;background:rgba(34,211,238,.08);border:1px solid rgba(34,211,238,.3);color:#8ff0ff;font:800 15px monospace;word-break:break-all}
@media(max-width:820px){.admin{grid-template-columns:1fr}.nav{border-right:0;border-bottom:1px solid var(--line);padding:16px}.nav-links{margin-top:16px;grid-template-columns:repeat(3,1fr);gap:5px;display:grid}.nav-links a{padding:10px 6px;text-align:center;font-size:9px}.logout{margin-top:14px}.workspace{padding:20px 14px}.cards{grid-template-columns:1fr}.bar h1{font-size:28px}table{min-width:560px}}
</style></head><body data-ai="1">
<canvas id="neonBg"></canvas><div id="neonCursor"></div><button id="muteBtn">🔊</button>
<main class="admin">
<aside class="nav">
<div class="brand"><i class="fa-solid fa-bolt"></i> TIGRAN MODZ <span>PROXY</span></div>
<div class="nav-links"><a class="active" href="/admin/dashboard"><i class="fa-solid fa-chart-simple"></i> Overview</a><a href="#keys"><i class="fa-solid fa-key"></i> Keys</a><a href="#ips"><i class="fa-solid fa-users"></i> Sessions</a></div>
<a class="logout" href="/admin/logout"><i class="fa-solid fa-arrow-right-from-bracket"></i> Encerrar sessão</a>
</aside>
<section class="workspace">
<header class="bar fade-in"><div><div class="eyebrow">ADMIN CONTROL / 01</div><h1 class="neon-text">Operations</h1></div><div class="profile"><i class="fa-solid fa-circle pulse"></i> ADMIN ONLINE</div></header>
<div class="cards fade-in">
<section class="card"><h2><i class="fa-solid fa-key"></i> Emitir nova key</h2>
<div class="field"><label>Prefixo</label><input id="keyPrefix" value="TIGRAN-MDZ-PROXY"></div>
<div class="field"><label>Limite de IPs</label><input id="ipLimit" type="number" value="1" min="1"></div>
<div class="field"><label>Validade em dias</label><input id="keyDays" type="number" value="7" min="1"></div>
<button class="glow-btn" style="width:100%" onclick="generateKey()">Gerar key <i class="fa-solid fa-arrow-right"></i></button>
<div id="generatedKey" class="generated" style="display:none"></div>
</section>
<section class="card"><h2><i class="fa-solid fa-chart-line"></i> Resumo</h2>
<div class="stats"><div class="stat"><small>TOTAL KEYS</small><strong>{{ keys|length }}</strong></div><div class="stat"><small>IPS ATIVOS</small><strong>{{ ips|length }}</strong></div></div>
</section></div>
<section id="keys" class="card wide fade-in"><h2>Keys emitidas</h2><div class="table-wrap"><table><thead><tr><th>KEY</th><th>LIMIT</th><th>USOS</th><th>VALIDADE</th><th>AÇÃO</th></tr></thead><tbody>{% for key, data in keys.items() %}<tr><td><span class="badge">{{ key }}</span></td><td>{{ data.limit }}</td><td>{{ data.used_ips|length }}</td><td>{{ data.days }} dias</td><td><button class="danger" onclick="revokeKey('{{ key }}')">REVOGAR</button></td></tr>{% else %}<tr><td colspan="5" style="color:var(--muted)">Nenhuma key emitida.</td></tr>{% endfor %}</tbody></table></div></section>
<section id="ips" class="card wide fade-in"><h2>Sessões autorizadas</h2><div class="table-wrap"><table><thead><tr><th>IP</th><th>KEY</th><th>EXPIRA</th><th>STATUS</th></tr></thead><tbody>{% for ip, key in ips.items() %}<tr><td>{{ ip }}</td><td><span class="badge">{{ key }}</span></td><td>{% if key_expiry[ip] %}{{ key_expiry[ip].strftime('%d/%m/%Y') }}{% else %}-{% endif %}</td><td style="color:#7fffd4">● ATIVO</td></tr>{% else %}<tr><td colspan="4" style="color:var(--muted)">Nenhuma sessão autorizada.</td></tr>{% endfor %}</tbody></table></div></section>
</section></main>
<script>""" + NEON_JS + """
async function generateKey(){const o=document.getElementById('generatedKey');o.style.display='block';o.textContent='GERANDO...';try{const r=await fetch('/admin/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prefix:document.getElementById('keyPrefix').value.trim()||'TIGRAN-MDZ-PROXY',limit:Math.max(1,parseInt(document.getElementById('ipLimit').value)||1),days:Math.max(1,parseInt(document.getElementById('keyDays').value)||7)})});const d=await r.json();if(!r.ok||!d.key)throw Error(d.error||'Erro');o.textContent='✓ '+d.key;playSuccess();setTimeout(()=>location.reload(),1400)}catch(e){o.textContent='ERRO: '+e.message;playError()}}
async function revokeKey(key){if(!confirm('Revogar '+key+'?'))return;const r=await fetch('/admin/revoke',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})});const d=await r.json();if(d.success){playSuccess();location.reload()}else{alert(d.error||'Erro');playError()}}
</script></body></html>"""

# ==================== DASHBOARD_PAGE (неоновая, с AI и данными) ====================
DASHBOARD_PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TIGRAN MODZ · DASHBOARD</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>""" + NEON_CSS + """
.app{min-height:100vh;display:grid;grid-template-columns:240px 1fr;position:relative;z-index:2}
.side{padding:26px 18px;background:rgba(10,5,20,.7);backdrop-filter:blur(14px);border-right:1px solid var(--line);display:flex;flex-direction:column}
.brand{font-weight:900;letter-spacing:2px;font-size:15px}
.brand span{color:var(--p1);text-shadow:0 0 14px var(--p1)}
.side nav{margin-top:40px;display:grid;gap:6px}
.side nav div{padding:12px 14px;color:var(--muted);font:700 10px monospace;letter-spacing:1.5px;text-transform:uppercase;border-radius:12px;border:1px solid transparent;transition:.2s}
.side nav div.active{background:linear-gradient(90deg,rgba(255,45,149,.18),transparent);border-color:rgba(255,45,149,.4);color:#fff}
.side-foot{margin-top:auto;color:#6b5a70;font:10px monospace;line-height:1.7}
.main{padding:32px 40px;max-width:1250px;width:100%}
.top{display:flex;justify-content:space-between;align-items:flex-start;padding-bottom:26px;border-bottom:1px solid var(--line);flex-wrap:wrap;gap:14px}
.top h1{margin:8px 0 0;font-size:36px;letter-spacing:-1.5px}
.eyebrow{font:700 10px monospace;letter-spacing:2px;color:var(--p3)}
.status{display:flex;gap:8px;align-items:center;color:#ff7ec0;font:700 10px monospace;padding:8px 14px;border-radius:999px;background:rgba(255,45,149,.1);border:1px solid rgba(255,45,149,.3)}
.dot{width:8px;height:8px;background:var(--p1);border-radius:50%;box-shadow:0 0 14px var(--p1);animation:pulse 1.6s infinite}
.info-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:26px 0}
.info-card{background:rgba(20,10,30,.6);backdrop-filter:blur(12px);border:1px solid var(--line);border-radius:14px;padding:14px;transition:.25s;position:relative;overflow:hidden}
.info-card:hover{border-color:rgba(34,211,238,.5);transform:translateY(-3px);box-shadow:0 0 24px rgba(34,211,238,.15)}
.info-card i{color:var(--p3);font-size:14px;text-shadow:0 0 12px var(--p3)}
.info-card small{display:block;color:var(--muted);font:700 9px monospace;letter-spacing:1.2px;text-transform:uppercase;margin:6px 0 4px}
.info-card b{color:#fff;font-size:15px;font-weight:800;display:block;word-break:break-word}
.ip{margin:6px 0 22px;display:flex;align-items:center;gap:12px;padding:14px 18px;background:rgba(20,10,30,.6);border:1px solid var(--line);border-radius:14px;font:12px monospace;color:#c8b9d0}
.ip span:first-of-type{flex:1;word-break:break-all}
.eye{border:0;background:none;color:var(--muted);cursor:none;font-size:14px}
.tag{padding:5px 10px;border-radius:8px;background:linear-gradient(135deg,var(--p1),var(--p2));color:#fff;font:800 9px monospace;letter-spacing:1px}
.section-title{display:flex;align-items:center;gap:10px;margin:26px 0 12px;font:800 11px monospace;letter-spacing:2px;color:#c8b9d0;text-transform:uppercase}
.section-title:after{content:"";height:1px;background:linear-gradient(90deg,var(--line),transparent);flex:1}
.controls{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.control{display:flex;align-items:center;gap:14px;background:rgba(20,10,30,.55);backdrop-filter:blur(12px);border:1px solid var(--line);border-radius:16px;padding:16px;cursor:none;transition:.25s;position:relative;overflow:hidden}
.control:hover{border-color:rgba(255,45,149,.5);transform:translateY(-3px);box-shadow:0 0 26px rgba(255,45,149,.18)}
.control.visual-option.is-on{border-color:var(--p1);background:linear-gradient(135deg,rgba(255,45,149,.15),rgba(168,85,247,.08))}
.control.visual-option.is-on .icon{background:linear-gradient(135deg,var(--p1),var(--p3));color:#fff;box-shadow:0 0 16px var(--p1)}
.control.visual-option.is-on .sw{background:linear-gradient(135deg,var(--p1),var(--p3))}
.control.visual-option.is-on .sw .th{margin-left:16px;background:#fff}
.icon{width:36px;height:36px;display:grid;place-items:center;background:rgba(255,45,149,.15);border-radius:10px;color:var(--p1);font-size:14px;transition:.25s}
.info{flex:1;min-width:0}
.name{font-size:12px;font-weight:800;letter-spacing:.5px}
.desc{color:var(--muted);font:10px monospace;margin-top:4px;letter-spacing:.5px}
.sw{width:36px;height:20px;border-radius:20px;background:#322a38;padding:2px;transition:.25s;flex-shrink:0}
.sw .th{width:16px;height:16px;border-radius:50%;background:#8a7a90;transition:.25s}
.sw.on{background:linear-gradient(135deg,var(--p1),var(--p3));box-shadow:0 0 14px rgba(255,45,149,.6)}
.sw.on .th{margin-left:16px;background:#fff}
.bottom{margin-top:30px;padding-top:18px;border-top:1px solid var(--line);color:#6b5a70;font:10px monospace;letter-spacing:1px}
#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(80px);padding:13px 22px;background:linear-gradient(135deg,var(--p1),var(--p2));color:#fff;font:800 11px monospace;border-radius:12px;opacity:0;transition:.3s;z-index:9999;box-shadow:0 0 30px rgba(255,45,149,.6);letter-spacing:1px}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
@media(max-width:820px){.app{grid-template-columns:1fr}.side{border-right:0;border-bottom:1px solid var(--line);padding:16px}.side nav{margin-top:16px;grid-template-columns:repeat(3,1fr);gap:5px;display:grid}.side nav div{padding:10px 6px;text-align:center;font-size:9px}.side-foot{display:none}.main{padding:20px 14px}.top h1{font-size:28px}.controls{grid-template-columns:1fr}.ip{padding:12px 14px}}
</style></head><body data-ai="1">
<canvas id="neonBg"></canvas><div id="neonCursor"></div><button id="muteBtn">🔊</button>
<main class="app">
<aside class="side">
<div class="brand"><i class="fa-solid fa-bolt"></i> TIGRAN MODZ <span>PROXY</span></div>
<nav>
  <div class="active"><i class="fa-solid fa-grid-2"></i> Overview</div>
  <div onclick="location.href='/ai'"><i class="fa-solid fa-robot"></i> Tigran AI</div>
  <div onclick="location.href='/tools'"><i class="fa-solid fa-toolbox"></i> Tools</div>
  <div><i class="fa-solid fa-crosshairs"></i> Aim</div>
  <div><i class="fa-solid fa-sliders"></i> Modules</div>
</nav>
<div class="side-foot">SESSION ACTIVE<br>CONTROL NODE / 01</div>
</aside>
<section class="main">
<header class="top fade-in"><div><div class="eyebrow">USER CONSOLE</div><h1 class="neon-text">Dashboard</h1></div><div class="status"><i class="dot"></i> ONLINE</div></header>
<div class="info-grid" id="infoGrid">
<div class="info-card"><i class="fa-solid fa-globe"></i><small>País</small><b id="uCountry">—</b></div>
<div class="info-card"><i class="fa-solid fa-location-dot"></i><small>Cidade</small><b id="uCity">—</b></div>
<div class="info-card"><i class="fa-solid fa-clock"></i><small>Hora local</small><b id="uTime">--:--:--</b></div>
<div class="info-card"><i class="fa-solid fa-calendar"></i><small>Data</small><b id="uDate">—</b></div>
<div class="info-card"><i class="fa-solid fa-cloud-sun"></i><small>Clima</small><b id="uWeather">—</b></div>
<div class="info-card"><i class="fa-solid fa-moon"></i><small>Período</small><b id="uDayNight">—</b></div>
<div class="info-card"><i class="fa-solid fa-mobile-screen"></i><small>Dispositivo</small><b id="uDevice">—</b></div>
<div class="info-card"><i class="fa-solid fa-battery-three-quarters"></i><small>Bateria</small><b id="uBattery">—</b></div>
</div>
<div class="ip"><i class="fa-solid fa-network-wired" style="color:var(--p3)"></i><span id="ipDisplay">CARREGANDO...</span><button class="eye" id="ipToggle" onclick="toggleIpVisibility()"><i class="fa-solid fa-eye"></i></button><b class="tag">AUTHORIZED</b></div>
<div class="section-title">AIM MODULES</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('hs_neck')"><div class="icon"><i class="fa-solid fa-crosshairs"></i></div><div class="info"><div class="name">HS PESCOÇO</div><div class="desc">PRECISION TARGET</div></div><div class="sw" id="sw_hs_neck"><div class="th"></div></div></div>
<div class="control" onclick="toggle('hs_chest')"><div class="icon"><i class="fa-solid fa-bullseye"></i></div><div class="info"><div class="name">HS PEITO</div><div class="desc">PRECISION TARGET</div></div><div class="sw" id="sw_hs_chest"><div class="th"></div></div></div>
<div class="control visual-option" onclick="toggleVisual(this)"><div class="icon"><i class="fa-solid fa-crosshairs"></i></div><div class="info"><div class="name">PRECISÃO</div><div class="desc">PRECISION TARGET</div></div><div class="sw"><div class="th"></div></div></div>
<div class="control visual-option" onclick="toggleVisual(this)"><div class="icon"><i class="fa-solid fa-arrow-up"></i></div><div class="info"><div class="name">HS ALTO</div><div class="desc">PRECISION TARGET</div></div><div class="sw"><div class="th"></div></div></div>
<div class="control visual-option" onclick="toggleVisual(this)"><div class="icon"><i class="fa-solid fa-bullseye"></i></div><div class="info"><div class="name">HS ALTO + NECK</div><div class="desc">PRECISION TARGET</div></div><div class="sw"><div class="th"></div></div></div>
<div class="control visual-option" onclick="toggleVisual(this)"><div class="icon"><i class="fa-solid fa-expand"></i></div><div class="info"><div class="name">ESP ACTIVATED</div><div class="desc">PRECISION TARGET</div></div><div class="sw"><div class="th"></div></div></div>
</div>
<div class="section-title">MOVEMENT & CONFIG</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('backjump_v1')"><div class="icon"><i class="fa-solid fa-arrow-up"></i></div><div class="info"><div class="name">BACKJUMP</div><div class="desc">MOVEMENT MODULE</div></div><div class="sw" id="sw_backjump_v1"><div class="th"></div></div></div>
<div class="control" onclick="toggle('high_sensi')"><div class="icon"><i class="fa-solid fa-sliders"></i></div><div class="info"><div class="name">SENSI ALTA</div><div class="desc">CONTROL PROFILE</div></div><div class="sw" id="sw_high_sensi"><div class="th"></div></div></div>
<div class="control" onclick="toggle('zig_zag_move')"><div class="icon"><i class="fa-solid fa-arrows-left-right"></i></div><div class="info"><div class="name">ZIG ZAG</div><div class="desc">MOVEMENT MODULE</div></div><div class="sw" id="sw_zig_zag_move"><div class="th"></div></div></div>
</div>
<div class="bottom">LEAKS BYPASS · CONTROLLED SESSION</div>
</section></main>
<div id="toast"></div>
<script>""" + NEON_JS + """
const names={hs_neck:'HS PESCOÇO',hs_chest:'HS PEITO',backjump_v1:'BACKJUMP',high_sensi:'SENSI ALTA',zig_zag_move:'ZIG ZAG'};
function toggleVisual(card){card.classList.toggle('is-on');const name=card.querySelector('.name').textContent;toast(name+(card.classList.contains('is-on')?' ATIVO':' DESATIVADO'));if(card.classList.contains('is-on'))playSuccess()}
function toast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');clearTimeout(t._t);t._t=setTimeout(()=>t.classList.remove('show'),2000)}

// ==== ДАННЫЕ О ПОЛЬЗОВАТЕЛЕ ====
let actualIp='',ipVisible=true,userTZ=null;
fetch('/api/ip/check').then(r=>r.json()).then(d=>{actualIp=d.ip||'DESCONHECIDO';document.getElementById('ipDisplay').textContent=actualIp});
function toggleIpVisibility(){ipVisible=!ipVisible;document.getElementById('ipDisplay').textContent=ipVisible?actualIp:'•••.•••.•••.•••';document.getElementById('ipToggle').innerHTML=ipVisible?'<i class="fa-solid fa-eye"></i>':'<i class="fa-solid fa-eye-slash"></i>'}

fetch('/api/user/info').then(r=>r.json()).then(d=>{
  document.getElementById('uCountry').textContent=(d.country||'—')+(d.country_code?' ('+d.country_code+')':'');
  document.getElementById('uCity').textContent=d.city||'—';
  userTZ=d.timezone;
  if(d.timezone){
    function tick(){
      try{
        const now=new Date();
        document.getElementById('uTime').textContent=now.toLocaleTimeString('ru-RU',{timeZone:d.timezone,hour12:false});
        document.getElementById('uDate').textContent=now.toLocaleDateString('ru-RU',{timeZone:d.timezone,weekday:'short',day:'2-digit',month:'short'});
      }catch(e){}
    }
    tick();setInterval(tick,1000);
  }
  if(d.weather){
    const w=d.weather;
    document.getElementById('uWeather').textContent=(w.temp||'?')+'°C · '+(w.desc||'');
    document.getElementById('uDayNight').textContent=w.is_day?'☀ DIA':'🌙 NOITE';
  }
}).catch(()=>{});

// ==== ДАННЫЕ УСТРОЙСТВА ====
(function(){
  const ua=navigator.userAgent;
  let dev='Desconhecido',os='';
  if(/Android/i.test(ua))os='Android';
  else if(/iPhone|iPad|iPod/i.test(ua))os='iOS';
  else if(/Windows/i.test(ua))os='Windows';
  else if(/Mac/i.test(ua))os='macOS';
  else if(/Linux/i.test(ua))os='Linux';
  let br='Navegador';
  if(/Chrome/i.test(ua)&&!/Edg/i.test(ua))br='Chrome';
  else if(/Firefox/i.test(ua))br='Firefox';
  else if(/Safari/i.test(ua))br='Safari';
  else if(/Edg/i.test(ua))br='Edge';
  dev=os+' · '+br;
  document.getElementById('uDevice').textContent=dev||'—';
  if(navigator.getBattery){
    navigator.getBattery().then(b=>{
      function upd(){document.getElementById('uBattery').textContent=Math.round(b.level*100)+'%'+(b.charging?' ⚡':'')}
      upd();b.addEventListener('levelchange',upd);b.addEventListener('chargingchange',upd);
    });
  } else {document.getElementById('uBattery').textContent='—'}
})();

// ==== ТУМБЛЕРЫ ====
fetch('/api/status').then(r=>r.json()).then(d=>{const c=d.config;['hs_neck','hs_chest','backjump_v1','high_sensi','zig_zag_move'].forEach(f=>{const map={hs_neck:'HS_NECK',hs_chest:'HS_CHEST',backjump_v1:'BACKJUMPV1',high_sensi:'HIGH_SENSI',zig_zag_move:'ZIG_ZAG_MOVE'};const el=document.getElementById('sw_'+f);if(el)el.className='sw'+(c[map[f]]?' on':'')})});
function toggle(feature){const el=document.getElementById('sw_'+feature),val=!el.classList.contains('on');el.className='sw'+(val?' on':'');fetch('/api/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({feature,value:val})}).then(r=>r.json()).then(d=>{if(d.success){toast(names[feature]+' '+(val?'ON':'OFF'));if(val)playSuccess()}else throw Error()}).catch(()=>{el.className='sw'+(!val?' on':'');toast('ERRO: '+names[feature]);playError()})}
</script></body></html>"""

# ==================== AI_PAGE (полноценный ChatGPT) ====================
# ==================== AI_PAGE (полноценный ChatGPT PRO) ====================
AI_PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>TIGRAN AI</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>""" + NEON_CSS + """
*{scrollbar-width:thin;scrollbar-color:rgba(255,45,149,.4) transparent}
*::-webkit-scrollbar{width:6px;height:6px}
*::-webkit-scrollbar-thumb{background:rgba(255,45,149,.4);border-radius:6px}
body.light{--bg:#f0eef5;--panel:rgba(255,255,255,.7);--line:rgba(168,85,247,.2);--ink:#1a0f26;--muted:#5a4a66}
body.light .msg.a .bub{background:rgba(255,255,255,.85);color:#1a0f26}
body.light .aiside{background:rgba(255,255,255,.75)}
body.light .aiinput .box{background:rgba(255,255,255,.8)}
body.light textarea{color:#1a0f26}
body.light .chatitem{color:#3a2a44}
body.light .chatitem.active{color:#1a0f26}
.aigrid{position:relative;z-index:2;display:grid;grid-template-columns:290px 1fr;height:100vh;overflow:hidden}
.aiside{background:rgba(10,5,20,.85);backdrop-filter:blur(16px);border-right:1px solid var(--line);display:flex;flex-direction:column;padding:14px;overflow:hidden}
.ailogo{display:flex;align-items:center;gap:10px;padding:8px 10px 14px;font-weight:900;letter-spacing:2px;font-size:15px;border-bottom:1px solid var(--line)}
.ailogo i{color:var(--p3);text-shadow:0 0 14px var(--p3)}
.actions{display:flex;gap:6px;margin-top:12px}
.actions button{flex:1;padding:11px 6px;border-radius:10px;border:1px solid var(--line);background:rgba(20,10,30,.6);color:#c8b9d0;cursor:none;font:700 9px monospace;letter-spacing:1px;transition:.2s}
.actions button:hover{border-color:var(--p1);color:#fff;background:rgba(255,45,149,.12)}
.actions button.primary{background:linear-gradient(135deg,var(--p1),var(--p3));color:#fff;border:0}
.actions button.primary:hover{filter:brightness(1.15)}
.search{margin-top:10px;position:relative}
.search input{width:100%;padding:10px 12px 10px 34px;border-radius:10px;border:1px solid var(--line);background:rgba(5,3,10,.7);color:#fff;outline:none;font:12px inherit}
.search i{position:absolute;left:11px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:12px}
body.light .search input{color:#1a0f26;background:rgba(255,255,255,.7)}
.folders{display:flex;flex-wrap:wrap;gap:4px;margin-top:10px}
.folders button{padding:5px 9px;border-radius:999px;border:1px solid var(--line);background:transparent;color:var(--muted);font:700 9px monospace;cursor:none;letter-spacing:1px}
.folders button.active{background:rgba(255,45,149,.15);border-color:var(--p1);color:#fff}
.chatlist{flex:1;overflow-y:auto;margin-top:12px;display:flex;flex-direction:column;gap:3px;padding-right:2px}
.chatitem{display:flex;align-items:center;gap:8px;padding:10px 11px;border-radius:10px;color:#c8b9d0;font-size:12px;cursor:none;border:1px solid transparent;transition:.2s}
.chatitem:hover{background:rgba(255,45,149,.1);border-color:rgba(255,45,149,.3)}
.chatitem.active{background:linear-gradient(90deg,rgba(255,45,149,.2),transparent);border-color:rgba(255,45,149,.4);color:#fff}
.chatitem.pinned{border-color:rgba(34,211,238,.4)}
.chatitem .ttl{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chatitem .badge{font-size:9px;color:var(--p3)}
.chatitem .del,.chatitem .pin{opacity:.4;font-size:10px;color:#ff8e8e;padding:2px}
.chatitem .pin{color:var(--p3)}
.chatitem .del:hover,.chatitem .pin:hover{opacity:1}
.folder-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.aibottom{padding-top:10px;border-top:1px solid var(--line);display:flex;gap:6px;flex-wrap:wrap}
.aibottom a,.aibottom button{flex:1;text-align:center;padding:9px 6px;border-radius:10px;background:rgba(34,211,238,.1);border:1px solid rgba(34,211,238,.3);color:#8ff0ff;font:700 9px monospace;text-decoration:none;letter-spacing:1px;cursor:none;min-width:0}
.aibottom a:hover,.aibottom button:hover{background:rgba(34,211,238,.2)}
.aimain{display:flex;flex-direction:column;height:100vh;overflow:hidden}
.aihead{padding:12px 20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.aihead .ttl{font:800 13px monospace;letter-spacing:2px;color:#fff;display:flex;align-items:center;gap:8px}
.aihead .ttl i{color:var(--p1);text-shadow:0 0 12px var(--p1)}
.aihead .tools{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.aihead select,.aihead button{padding:7px 11px;border-radius:9px;border:1px solid var(--line);background:rgba(20,10,30,.7);color:#c8b9d0;font:700 10px monospace;cursor:none;outline:none}
.aihead select:hover,.aihead button:hover{border-color:var(--p1);color:#fff}
.msgs{flex:1;overflow-y:auto;padding:24px 5% 100px;display:flex;flex-direction:column;gap:16px}
.msg{display:flex;gap:12px;max-width:880px;width:100%;margin:0 auto;animation:fadeIn .35s ease;position:relative;group:msg}
.msg.u{flex-direction:row-reverse}
.msg .av{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font-size:12px;flex-shrink:0;font-weight:900}
.msg.u .av{background:linear-gradient(135deg,var(--p1),var(--p2));color:#fff;box-shadow:0 0 14px rgba(255,45,149,.5)}
.msg.a .av{background:linear-gradient(135deg,var(--p3),var(--p2));color:#fff;box-shadow:0 0 14px rgba(34,211,238,.5)}
.msg .bub{padding:12px 15px;border-radius:16px;line-height:1.6;font-size:14px;word-wrap:break-word;overflow-wrap:anywhere;max-width:100%}
.msg.u .bub{background:linear-gradient(135deg,rgba(255,45,149,.18),rgba(168,85,247,.12));border:1px solid rgba(255,45,149,.4);color:#fff;border-top-right-radius:4px}
.msg.a .bub{background:rgba(20,10,30,.7);border:1px solid var(--line);color:#e8dff0;border-top-left-radius:4px}
.msg.a .bub pre{background:rgba(5,3,10,.95);padding:12px;border-radius:10px;overflow-x:auto;font:12px monospace;border:1px solid var(--line);margin:8px 0;white-space:pre}
.msg.a .bub code{background:rgba(34,211,238,.12);padding:2px 6px;border-radius:4px;font:12px monospace;color:#8ff0ff}
.msg .row-act{display:flex;gap:6px;margin-top:6px;opacity:0;transition:.2s}
.msg:hover .row-act{opacity:1}
.msg .row-act button{padding:4px 8px;border-radius:6px;border:1px solid var(--line);background:rgba(5,3,10,.6);color:var(--muted);font:9px monospace;cursor:none}
.msg .row-act button:hover{color:#fff;border-color:var(--p1)}
.typing{display:inline-flex;gap:4px}
.typing i{width:7px;height:7px;border-radius:50%;background:var(--p3);animation:blink 1.2s infinite}
.typing i:nth-child(2){animation-delay:.2s}.typing i:nth-child(3){animation-delay:.4s}
@keyframes blink{0%,60%,100%{opacity:.3;transform:translateY(0)}30%{opacity:1;transform:translateY(-4px)}}
.aiinput{padding:10px 16px 14px;border-top:1px solid var(--line);background:rgba(10,5,20,.6)}
.aiinput .info{display:flex;justify-content:space-between;font:9px monospace;color:var(--muted);max-width:880px;margin:0 auto 6px;padding:0 4px}
.aiinput .box{display:flex;gap:8px;max-width:880px;margin:0 auto;background:rgba(5,3,10,.8);border:1px solid var(--line);border-radius:16px;padding:6px;transition:.25s;align-items:flex-end}
.aiinput .box:focus-within{border-color:var(--p1);box-shadow:0 0 0 4px rgba(255,45,149,.12),0 0 25px rgba(255,45,149,.25)}
.aiinput textarea{flex:1;background:transparent;border:0;color:#fff;outline:none;font:14px inherit;padding:10px;resize:none;max-height:180px;min-height:24px;font-family:inherit;line-height:1.5}
.aiinput .btns{display:flex;gap:4px}
.aiinput .btns button{width:40px;height:40px;border-radius:11px;border:0;cursor:none;font-size:14px;color:#fff;flex-shrink:0}
.aiinput .mic{background:rgba(255,45,149,.15);border:1px solid rgba(255,45,149,.3)!important;color:var(--p1)!important}
.aiinput .mic.rec{background:var(--p1)!important;color:#fff!important;animation:pulse 1s infinite}
.aiinput .send{background:linear-gradient(135deg,var(--p1),var(--p3))}
.aiinput .send:hover{filter:brightness(1.15)}
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;text-align:center;color:var(--muted);gap:14px;padding:30px}
.empty h2{font-size:34px;background:linear-gradient(90deg,var(--p1),var(--p2),var(--p3));-webkit-background-clip:text;background-clip:text;color:transparent;letter-spacing:-1px}
.empty p{max-width:460px;line-height:1.6;font-size:14px}
.empty .chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:14px;max-width:600px}
.empty .chip{padding:9px 14px;border-radius:999px;background:rgba(20,10,30,.7);border:1px solid var(--line);color:#c8b9d0;font:12px inherit;cursor:none;transition:.2s}
.empty .chip:hover{border-color:var(--p1);color:#fff;background:rgba(255,45,149,.12)}
.menuBtn{display:none;width:36px;height:36px;border-radius:10px;border:1px solid var(--line);background:rgba(20,10,30,.7);color:#fff;cursor:none;align-items:center;justify-content:center;font-size:14px}
@media(max-width:820px){
  .aigrid{grid-template-columns:1fr}
  .aiside{position:fixed;left:0;top:0;bottom:0;width:290px;transform:translateX(-100%);transition:.3s;z-index:999;box-shadow:20px 0 60px #000}
  .aiside.open{transform:translateX(0)}
  .menuBtn{display:flex}
  .msgs{padding:16px 12px 90px}
  .msg .row-act{opacity:1}
}
</style></head><body>
<canvas id="neonBg"></canvas><div id="neonCursor"></div><button id="muteBtn">🔊</button>
<div class="aigrid">
<aside class="aiside" id="aiside">
  <div class="ailogo"><i class="fa-solid fa-robot"></i> TIGRAN AI</div>
  <div class="actions">
    <button class="primary" onclick="newChat()"><i class="fa-solid fa-plus"></i> НОВЫЙ</button>
    <button onclick="exportChats()"><i class="fa-solid fa-download"></i> ЭКСПОРТ</button>
    <button onclick="document.getElementById('imp').click()"><i class="fa-solid fa-upload"></i> ИМПОРТ</button>
    <input type="file" id="imp" accept=".json" style="display:none" onchange="importChats(event)">
  </div>
  <div class="search"><i class="fa-solid fa-magnifying-glass"></i><input id="searchInp" placeholder="Поиск по чатам..." oninput="renderList()"></div>
  <div class="folders" id="folders"></div>
  <div class="chatlist" id="chatlist"></div>
  <div class="aibottom">
    <a href="/dashboard"><i class="fa-solid fa-arrow-left"></i> К ПАНЕЛИ</a>
    <button onclick="clearAll()"><i class="fa-solid fa-trash"></i> ОЧИСТИТЬ</button>
  </div>
</aside>
<section class="aimain">
  <header class="aihead">
    <div style="display:flex;align-items:center;gap:8px">
      <button class="menuBtn" onclick="document.getElementById('aiside').classList.toggle('open')"><i class="fa-solid fa-bars"></i></button>
      <div class="ttl"><i class="fa-solid fa-comments"></i> Чат</div>
    </div>
    <div class="tools">
      <select id="modelSel" onchange="save();renderMsgs()">
        <option value="gpt-4o-mini">gpt-4o-mini ⚡</option>
        <option value="gpt-4o">gpt-4o 🧠</option>
        <option value="gpt-3.5-turbo">gpt-3.5-turbo 💨</option>
      </select>
      <button onclick="toggleTheme()" id="themeBtn" title="Тема">🌙</button>
      <button onclick="ttsToggle()" id="ttsBtn" title="Озвучка">🔇</button>
    </div>
  </header>
  <div class="msgs" id="msgs"></div>
  <div class="aiinput">
    <div class="info"><span id="charCount">0 символов</span><span id="statInfo"></span></div>
    <div class="box">
      <textarea id="ta" placeholder="Напиши сообщение... (Enter — отправить, Shift+Enter — новая строка)" rows="1"></textarea>
      <div class="btns">
        <button class="mic" id="micBtn" onclick="toggleMic()" title="Голосовой ввод"><i class="fa-solid fa-microphone"></i></button>
        <button class="send" onclick="sendMsg()"><i class="fa-solid fa-paper-plane"></i></button>
      </div>
    </div>
  </div>
</section>
</div>
<script>""" + NEON_JS + """
// ===== СОСТОЯНИЕ =====
const LS='tigran_ai_v2';
let state=JSON.parse(localStorage.getItem(LS)||'null')||{chats:[],activeId:null,folder:'all',model:'gpt-4o-mini',theme:'dark',tts:false};
function save(){state.model=document.getElementById('modelSel').value;localStorage.setItem(LS,JSON.stringify(state))}
function uid(){return Date.now().toString(36)+Math.random().toString(36).slice(2,6)}
function active(){return state.chats.find(c=>c.id===state.activeId)}
function escapeHtml(s){return String(s).replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]))}
const FOLDERS=[{id:'all',name:'Все',color:'#ff2d95'},{id:'work',name:'Работа',color:'#22d3ee'},{id:'personal',name:'Личное',color:'#a855f7'},{id:'study',name:'Учёба',color:'#fbbf24'},{id:'other',name:'Другое',color:'#94a3b8'}];

// ===== ФАЙЛЫ =====
function exportChats(){
  const data=JSON.stringify(state,null,2);
  const blob=new Blob([data],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;a.download='tigran_ai_chats_'+new Date().toISOString().slice(0,10)+'.json';
  a.click();URL.revokeObjectURL(url);playSuccess();
}
function importChats(e){
  const f=e.target.files[0];if(!f)return;
  const r=new FileReader();
  r.onload=()=>{try{const d=JSON.parse(r.result);if(d.chats&&Array.isArray(d.chats)){state.chats=[...d.chats,...state.chats];save();renderList();playSuccess();alert('Импортировано чатов: '+d.chats.length)}else alert('Неверный формат')}catch(err){alert('Ошибка чтения файла')}};
  r.readAsText(f);e.target.value='';
}
function clearAll(){if(!confirm('Удалить ВСЕ чаты? Это действие необратимо!'))return;state.chats=[];state.activeId=null;save();newChat()}

// ===== ЧАТЫ =====
function newChat(){
  const c={id:uid(),title:'Новый чат',msgs:[],created:Date.now(),folder:'other',pinned:false};
  state.chats.unshift(c);state.activeId=c.id;save();renderList();renderMsgs();
  document.getElementById('ta').focus();document.getElementById('aiside')?.classList.remove('open');
}
function selectChat(id){state.activeId=id;save();renderList();renderMsgs();document.getElementById('aiside')?.classList.remove('open')}
function delChat(e,id){e.stopPropagation();if(!confirm('Удалить чат?'))return;state.chats=state.chats.filter(c=>c.id!==id);if(state.activeId===id){state.activeId=state.chats[0]?.id||null;if(!state.activeId)return newChat()}save();renderList();renderMsgs()}
function pinChat(e,id){e.stopPropagation();const c=state.chats.find(x=>x.id===id);c.pinned=!c.pinned;save();renderList()}
function setFolder(e,id,f){e.stopPropagation();const c=state.chats.find(x=>x.id===id);c.folder=f;save();renderList()}
function setFilter(f){state.folder=f;save();renderList()}

// ===== РЕНДЕР СПИСКА =====
function renderList(){
  const el=document.getElementById('chatlist');
  const q=(document.getElementById('searchInp').value||'').toLowerCase();
  const filtered=state.chats.filter(c=>{
    if(state.folder!=='all'&&c.folder!==state.folder)return false;
    if(q&&!c.title.toLowerCase().includes(q)&&!c.msgs.some(m=>m.content.toLowerCase().includes(q)))return false;
    return true;
  }).sort((a,b)=>(b.pinned?1:0)-(a.pinned?1:0)||b.created-a.created);
  // папки
  document.getElementById('folders').innerHTML=FOLDERS.map(f=>'<button class="'+(state.folder===f.id?'active':'')+'" onclick="setFilter(\\''+f.id+'\\')">'+f.name+'</button>').join('');
  if(!filtered.length){el.innerHTML='<div style="color:#6b5a70;font:11px monospace;padding:10px;text-align:center">Пусто</div>';return}
  el.innerHTML=filtered.map(c=>{
    const fo=FOLDERS.find(f=>f.id===c.folder)||FOLDERS[4];
    return '<div class="chatitem'+(c.id===state.activeId?' active':'')+(c.pinned?' pinned':'')+'" onclick="selectChat(\\''+c.id+'\\')">'+
      '<span class="folder-dot" style="background:'+fo.color+'"></span>'+
      '<span class="ttl">'+escapeHtml(c.title)+'</span>'+
      (c.pinned?'<i class="fa-solid fa-thumbtack pin"></i>':'')+
      '<i class="fa-solid fa-trash del" onclick="delChat(event,\\''+c.id+'\\')"></i>'+
    '</div>';
  }).join('');
}

// ===== MARKDOWN =====
function fmt(t){
  let s=escapeHtml(t);
  s=s.replace(/```([a-z]*)([\\s\\S]*?)```/g,(m,l,c)=>'<pre><code>'+c+'</code></pre>');
  s=s.replace(/`([^`]+)`/g,'<code>$1</code>');
  s=s.replace(/\\*\\*([^*]+)\\*\\*/g,'<b>$1</b>');
  s=s.replace(/\\*([^*]+)\\*/g,'<i>$1</i>');
  s=s.replace(/\\n/g,'<br>');
  return s;
}

// ===== РЕНДЕР СООБЩЕНИЙ =====
function renderMsgs(){
  const box=document.getElementById('msgs');
  const c=active();
  if(!c||!c.msgs.length){
    box.innerHTML='<div class="empty"><h2>TIGRAN AI</h2><p>Задай любой вопрос — отвечу на том же языке. Программирование, перевод, тексты, анализ, советы, математика — всё умею.</p><div class="chips"><button class="chip" onclick="quick(\\'Привет! Что ты умеешь?\\')">Что умеешь?</button><button class="chip" onclick="quick(\\'Напиши функцию Python для сортировки списка\\')">Пример кода</button><button class="chip" onclick="quick(\\'Translate to English: привет, как дела?\\')">Перевод</button><button class="chip" onclick="quick(\\'Расскажи интересный факт о космосе\\')">Факт</button><button class="chip" onclick="quick(\\'Составь план на день продуктивности\\')">План дня</button></div></div>';
    return;
  }
  box.innerHTML=c.msgs.map((m,i)=>{
    if(m.role==='user')return '<div class="msg u"><div class="av">Я</div><div><div class="bub">'+escapeHtml(m.content).replace(/\\n/g,'<br>')+'</div><div class="row-act"><button onclick="editMsg('+i+')"><i class="fa-solid fa-pen"></i> Изменить</button><button onclick="delMsg('+i+')"><i class="fa-solid fa-trash"></i></button></div></div></div>';
    return '<div class="msg a"><div class="av">AI</div><div><div class="bub">'+fmt(m.content)+'</div><div class="row-act"><button onclick="copyMsg('+i+')"><i class="fa-solid fa-copy"></i></button><button onclick="regen()"><i class="fa-solid fa-rotate"></i> Заново</button><button onclick="speak('+i+')"><i class="fa-solid fa-volume-high"></i></button><button onclick="delMsg('+i+')"><i class="fa-solid fa-trash"></i></button></div></div></div>';
  }).join('');
  box.scrollTop=box.scrollHeight;
  updateStat();
}
function updateStat(){
  const c=active();if(!c)return;
  document.getElementById('statInfo').textContent='Сообщений: '+c.msgs.length+' · Модель: '+state.model;
}
function copyMsg(i){const c=active();navigator.clipboard.writeText(c.msgs[i].content);playClick();toastMini('Скопировано')}
function delMsg(i){const c=active();c.msgs.splice(i,1);save();renderMsgs()}
function editMsg(i){const c=active();const v=prompt('Редактировать:',c.msgs[i].content);if(v===null)return;c.msgs[i].content=v;save();renderMsgs()}
function speak(i){const c=active();const u=new SpeechSynthesisUtterance(c.msgs[i].content);u.lang=navigator.language||'ru-RU';speechSynthesis.cancel();speechSynthesis.speak(u)}
function toastMini(t){const d=document.createElement('div');d.textContent=t;d.style.cssText='position:fixed;bottom:80px;left:50%;transform:translateX(-50%);padding:8px 14px;background:rgba(34,211,238,.9);color:#000;border-radius:8px;font:700 11px monospace;z-index:9999';document.body.appendChild(d);setTimeout(()=>d.remove(),1500)}

// ===== ОТПРАВКА =====
async function sendMsg(){
  const ta=document.getElementById('ta');
  const text=ta.value.trim();if(!text)return;
  if(!active())newChat();
  const c=active();
  c.msgs.push({role:'user',content:text});
  if(c.msgs.filter(m=>m.role==='user').length===1){c.title=text.slice(0,42)+(text.length>42?'…':'')}
  ta.value='';ta.style.height='auto';save();renderList();renderMsgs();
  playClick();
  await callAI(c);
}
async function callAI(c){
  const box=document.getElementById('msgs');
  box.insertAdjacentHTML('beforeend','<div class="msg a" id="typing"><div class="av">AI</div><div class="bub"><span class="typing"><i></i><i></i><i></i></span></div></div>');
  box.scrollTop=box.scrollHeight;
  try{
    const r=await fetch('/api/ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:c.msgs[c.msgs.length-1].content,history:c.msgs.slice(0,-1),model:state.model})});
    const d=await r.json();
    document.getElementById('typing')?.remove();
    if(d.reply){c.msgs.push({role:'assistant',content:d.reply});save();renderMsgs();playSuccess();if(state.tts)speak(c.msgs.length-1)}
    else{c.msgs.push({role:'assistant',content:'⚠ Ошибка: '+(d.error||'пустой ответ')});save();renderMsgs();playError()}
  }catch(e){document.getElementById('typing')?.remove();c.msgs.push({role:'assistant',content:'⚠ Ошибка соединения.'});save();renderMsgs();playError()}
}
function regen(){const c=active();if(!c||!c.msgs.length)return;if(c.msgs[c.msgs.length-1].role==='assistant')c.msgs.pop();save();renderMsgs();callAI(c)}
function quick(t){document.getElementById('ta').value=t;sendMsg()}

// ===== ГОЛОСОВОЙ ВВОД =====
let recog=null,recording=false;
function toggleMic(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){alert('Голосовой ввод не поддерживается браузером');return}
  const btn=document.getElementById('micBtn');
  if(recording){recog.stop();return}
  recog=new SR();recog.lang=navigator.language||'ru-RU';recog.interimResults=false;recog.continuous=false;
  recog.onstart=()=>{recording=true;btn.classList.add('rec');playClick()};
  recog.onend=()=>{recording=false;btn.classList.remove('rec')};
  recog.onerror=()=>{recording=false;btn.classList.remove('rec')};
  recog.onresult=e=>{const t=e.results[0][0].transcript;document.getElementById('ta').value=t;sendMsg()};
  recog.start();
}

// ===== ОЗВУЧКА =====
function ttsToggle(){state.tts=!state.tts;save();document.getElementById('ttsBtn').textContent=state.tts?'🔊':'🔇';playClick()}

// ===== ТЕМА =====
function toggleTheme(){state.theme=state.theme==='dark'?'light':'dark';applyTheme();save();playClick()}
function applyTheme(){document.body.classList.toggle('light',state.theme==='light');document.getElementById('themeBtn').textContent=state.theme==='light'?'☀':'🌙'}

// ===== TEXTAREA =====
const ta=document.getElementById('ta');
ta.addEventListener('input',()=>{ta.style.height='auto';ta.style.height=Math.min(ta.scrollHeight,180)+'px';document.getElementById('charCount').textContent=ta.value.length+' символов'});
ta.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMsg()}});

// ===== INIT =====
document.getElementById('modelSel').value=state.model;
document.getElementById('ttsBtn').textContent=state.tts?'🔊':'🔇';
applyTheme();

// ==== FIX: явная привязка функций и кнопок ====
try{
  window.sendMsg=sendMsg; window.toggleMic=toggleMic;
  window.newChat=newChat; window.selectChat=selectChat;
  window.quick=quick; window.exportChats=exportChats;
  window.importChats=importChats; window.clearAll=clearAll;
  window.toggleTheme=toggleTheme; window.ttsToggle=ttsToggle;
  window.setFilter=setFilter; window.delChat=delChat;

  function bindSafe(el,fn){
    if(!el)return;
    el.addEventListener('click',function(e){
      e.preventDefault();
      try{fn(e)}catch(err){console.error(err);alert('Ошибка: '+err.message)}
    },{passive:false});
  }

  var taEl=document.getElementById('ta');
  bindSafe(document.querySelector('.aiinput .send'), sendMsg);
  bindSafe(document.getElementById('micBtn'), toggleMic);

  if(taEl){
    taEl.addEventListener('keydown',function(e){
      if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMsg()}
    });
  }

  // защита от битых данных
  if(!Array.isArray(state.chats)) state.chats=[];
  state.chats=state.chats.filter(function(c){return c&&c.id&&Array.isArray(c.msgs)});

  if(!state.chats.length){ newChat() }
  else{
    if(!state.activeId||!state.chats.find(function(c){return c.id===state.activeId}))
      state.activeId=state.chats[0].id;
    renderList(); renderMsgs();
  }
}catch(err){
  console.error('INIT error:',err);
  alert('INIT error: '+err.message);
}
</script></body></html>"""


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
            return "Nao foi possivel obter o IP publico"

if __name__ == "__main__":
    if not user_configs and not generated_keys:
        load_data()
    port = int(os.environ.get('PORT', 10000))

    print("\n" + "="*50)
    print("  TIGRAN MODZ PROXY ADMIN PANEL")
    print("="*50)
    print(f"  Porta do servidor: {port}")
    print(f"  Admin     : /Po7eO")
    print(f"  Status    : Rodando")
    print("="*50 + "\n")

    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
