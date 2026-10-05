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
_ai_memory = defaultdict(list)
AI_MEMORY_LIMIT = 50

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_ID", "")
_tg_last_update_id = 0

ADMINS_FILE = os.path.join(BASE_DIR, "admins.json")
PASS_FILE = os.path.join(BASE_DIR, "admin_pass.txt")
DATA_FILE = os.path.join(BASE_DIR, "crx_data.json")
PROFILES_FILE = os.path.join(BASE_DIR, "user_profiles.json")

# ==================== I18N (МУЛЬТИЯЗЫЧНОСТЬ) ====================
LANG_FILE = os.path.join(BASE_DIR, "bot_lang.json")
_current_lang = "ru"

TRANSLATIONS = {
    "ru": {
        "menu.title": "TIGRAN MODZ BOT",
        "menu.role": "Роль",
        "menu.id": "ID",
        "menu.choose": "👇 Выбери действие:",
        "btn.keys": "🔑 Ключи",
        "btn.sessions": "🌐 Сессии",
        "btn.stats": "📊 Статистика",
        "btn.admins": "👥 Админы",
        "btn.search": "🔍 Поиск ключа",
        "btn.quick": "🎯 Быстрые действия",
        "btn.utils": "🛠 Утилиты",
        "btn.reports": "📈 Отчёты",
        "btn.fun": "🎮 Развлечения",
        "btn.security": "🔒 Безопасность",
        "btn.addadmin": "➕ Добавить админа",
        "btn.backup": "💾 Backup",
        "btn.logs": "📜 Логи",
        "btn.broadcast": "📢 Рассылка",
        "btn.pass": "🔑 Пароль",
        "btn.settings": "⚙ Настройки",
        "btn.tasks": "⏰ Задачи",
        "btn.create_key": "🔑 Создать ключ",
        "btn.back": "◀ Назад",
        "keys.title": "Ключи",
        "keys.none": "Ключей нет",
        "keys.created": "Ключ создан",
        "keys.not_found": "Не найдено",
        "sessions.title": "Активные сессии",
        "sessions.none": "Нет активных сессий",
        "stats.title": "Статистика",
        "stats.keys": "Всего ключей",
        "stats.ips": "Активных IP",
        "stats.ai": "AI-запросов",
        "stats.admins": "Админов",
        "access.denied": "⛔ Доступ запрещён",
        "access.your_id": "Твой ID",
        "access.ask_admin": "Передай этот ID главному админу.",
        "role.owner": "owner",
        "role.superadmin": "superadmin",
        "role.admin": "admin",
        "role.guest": "guest",
        "lang.changed": "Язык бота изменён на",
        "lang.current": "Текущий язык",
    },
    "en": {
        "menu.title": "TIGRAN MODZ BOT",
        "menu.role": "Role",
        "menu.id": "ID",
        "menu.choose": "👇 Choose action:",
        "btn.keys": "🔑 Keys",
        "btn.sessions": "🌐 Sessions",
        "btn.stats": "📊 Stats",
        "btn.admins": "👥 Admins",
        "btn.search": "🔍 Search key",
        "btn.quick": "🎯 Quick actions",
        "btn.utils": "🛠 Utilities",
        "btn.reports": "📈 Reports",
        "btn.fun": "🎮 Fun",
        "btn.security": "🔒 Security",
        "btn.addadmin": "➕ Add admin",
        "btn.backup": "💾 Backup",
        "btn.logs": "📜 Logs",
        "btn.broadcast": "📢 Broadcast",
        "btn.pass": "🔑 Password",
        "btn.settings": "⚙ Settings",
        "btn.tasks": "⏰ Tasks",
        "btn.create_key": "🔑 Create key",
        "btn.back": "◀ Back",
        "keys.title": "Keys",
        "keys.none": "No keys",
        "keys.created": "Key created",
        "keys.not_found": "Not found",
        "sessions.title": "Active sessions",
        "sessions.none": "No active sessions",
        "stats.title": "Statistics",
        "stats.keys": "Total keys",
        "stats.ips": "Active IPs",
        "stats.ai": "AI requests",
        "stats.admins": "Admins",
        "access.denied": "⛔ Access denied",
        "access.your_id": "Your ID",
        "access.ask_admin": "Send this ID to the main admin.",
        "role.owner": "owner",
        "role.superadmin": "superadmin",
        "role.admin": "admin",
        "role.guest": "guest",
        "lang.changed": "Bot language changed to",
        "lang.current": "Current language",
    },
    "vi": {
        "menu.title": "TIGRAN MODZ BOT", "menu.role": "Vai trò", "menu.id": "ID",
        "menu.choose": "👇 Chọn hành động:", "btn.keys": "🔑 Khóa", "btn.sessions": "🌐 Phiên",
        "btn.stats": "📊 Thống kê", "btn.admins": "👥 Quản trị", "btn.search": "🔍 Tìm khóa",
        "btn.quick": "🎯 Hành động nhanh", "btn.utils": "🛠 Tiện ích", "btn.reports": "📈 Báo cáo",
        "btn.fun": "🎮 Giải trí", "btn.security": "🔒 Bảo mật", "btn.addadmin": "➕ Thêm quản trị",
        "btn.backup": "💾 Sao lưu", "btn.logs": "📜 Nhật ký", "btn.broadcast": "📢 Phát sóng",
        "btn.pass": "🔑 Mật khẩu", "btn.settings": "⚙ Cài đặt", "btn.tasks": "⏰ Nhiệm vụ",
        "btn.create_key": "🔑 Tạo khóa", "btn.back": "◀ Quay lại",
        "keys.title": "Khóa", "keys.none": "Không có khóa", "keys.created": "Đã tạo khóa",
        "keys.not_found": "Không tìm thấy", "sessions.title": "Phiên hoạt động",
        "sessions.none": "Không có phiên", "stats.title": "Thống kê", "stats.keys": "Tổng số khóa",
        "stats.ips": "IP hoạt động", "stats.ai": "Yêu cầu AI", "stats.admins": "Quản trị viên",
        "access.denied": "⛔ Từ chối truy cập", "access.your_id": "ID của bạn",
        "access.ask_admin": "Gửi ID này cho quản trị viên chính.", "role.owner": "chủ sở hữu",
        "role.superadmin": "siêu quản trị", "role.admin": "quản trị", "role.guest": "khách",
        "lang.changed": "Đã đổi ngôn ngữ bot thành", "lang.current": "Ngôn ngữ hiện tại",
    },
    "hy": {
        "menu.title": "TIGRAN MODZ BOT", "menu.role": "Դեր", "menu.id": "ID",
        "menu.choose": "👇 Ընտրիր գործողություն:", "btn.keys": "🔑 Բանալիներ",
        "btn.sessions": "🌐 Սեսիաներ", "btn.stats": "📊 Վիճակագրություն",
        "btn.admins": "👥 Ադմիններ", "btn.search": "🔍 Փնտրել բանալի",
        "btn.quick": "🎯 Արագ գործողություններ", "btn.utils": "🛠 Գործիքներ",
        "btn.reports": "📈 Հաշվետվություններ", "btn.fun": "🎮 Ժամանց",
        "btn.security": "🔒 Անվտանգություն", "btn.addadmin": "➕ Ավելացնել ադմին",
        "btn.backup": "💾 Պահուստ", "btn.logs": "📜 Մատյան",
        "btn.broadcast": "📢 Հեռարձակում", "btn.pass": "🔑 Գաղտնաբառ",
        "btn.settings": "⚙ Կարգավորումներ", "btn.tasks": "⏰ Առաջադրանքներ",
        "btn.create_key": "🔑 Ստեղծել բանալի", "btn.back": "◀ Հետ",
        "keys.title": "Բանալիներ", "keys.none": "Բանալիներ չկան",
        "keys.created": "Բանալին ստեղծված է", "keys.not_found": "Չի գտնվել",
        "sessions.title": "Ակտիվ սեսիաներ", "sessions.none": "Ակտիվ սեսիաներ չկան",
        "stats.title": "Վիճակագրություն", "stats.keys": "Ընդհանուր բանալիներ",
        "stats.ips": "Ակտիվ IP-ներ", "stats.ai": "AI հարցումներ",
        "stats.admins": "Ադմիններ", "access.denied": "⛔ Մուտքն արգելված է",
        "access.your_id": "Ձեր ID-ն", "access.ask_admin": "Ուղարկեք այս ID-ն գլխավոր ադմինին:",
        "role.owner": "սեփականատեր", "role.superadmin": "սուպեր ադմին",
        "role.admin": "ադմին", "role.guest": "հյուր",
        "lang.changed": "Բոտի լեզուն փոխված է", "lang.current": "Ընթացիկ լեզու",
    },
    "pt": {
        "menu.title": "TIGRAN MODZ BOT", "menu.role": "Função", "menu.id": "ID",
        "menu.choose": "👇 Escolha ação:", "btn.keys": "🔑 Chaves", "btn.sessions": "🌐 Sessões",
        "btn.stats": "📊 Estatísticas", "btn.admins": "👥 Admins", "btn.search": "🔍 Buscar chave",
        "btn.quick": "🎯 Ações rápidas", "btn.utils": "🛠 Utilitários", "btn.reports": "📈 Relatórios",
        "btn.fun": "🎮 Diversão", "btn.security": "🔒 Segurança", "btn.addadmin": "➕ Adicionar admin",
        "btn.backup": "💾 Backup", "btn.logs": "📜 Logs", "btn.broadcast": "📢 Transmitir",
        "btn.pass": "🔑 Senha", "btn.settings": "⚙ Configurações", "btn.tasks": "⏰ Tarefas",
        "btn.create_key": "🔑 Criar chave", "btn.back": "◀ Voltar",
        "keys.title": "Chaves", "keys.none": "Sem chaves", "keys.created": "Chave criada",
        "keys.not_found": "Não encontrado", "sessions.title": "Sessões ativas",
        "sessions.none": "Sem sessões ativas", "stats.title": "Estatísticas",
        "stats.keys": "Total de chaves", "stats.ips": "IPs ativos",
        "stats.ai": "Requisições AI", "stats.admins": "Admins",
        "access.denied": "⛔ Acesso negado", "access.your_id": "Seu ID",
        "access.ask_admin": "Envie este ID ao admin principal.", "role.owner": "dono",
        "role.superadmin": "superadmin", "role.admin": "admin", "role.guest": "convidado",
        "lang.changed": "Idioma do bot alterado para", "lang.current": "Idioma atual",
    },
    "es": {
        "menu.title": "TIGRAN MODZ BOT", "menu.role": "Rol", "menu.id": "ID",
        "menu.choose": "👇 Elige acción:", "btn.keys": "🔑 Claves", "btn.sessions": "🌐 Sesiones",
        "btn.stats": "📊 Estadísticas", "btn.admins": "👥 Admins", "btn.search": "🔍 Buscar clave",
        "btn.quick": "🎯 Acciones rápidas", "btn.utils": "🛠 Utilidades", "btn.reports": "📈 Informes",
        "btn.fun": "🎮 Diversión", "btn.security": "🔒 Seguridad", "btn.addadmin": "➕ Añadir admin",
        "btn.backup": "💾 Copia", "btn.logs": "📜 Registros", "btn.broadcast": "📢 Difusión",
        "btn.pass": "🔑 Contraseña", "btn.settings": "⚙ Ajustes", "btn.tasks": "⏰ Tareas",
        "btn.create_key": "🔑 Crear clave", "btn.back": "◀ Atrás",
        "keys.title": "Claves", "keys.none": "Sin claves", "keys.created": "Clave creada",
        "keys.not_found": "No encontrado", "sessions.title": "Sesiones activas",
        "sessions.none": "Sin sesiones", "stats.title": "Estadísticas",
        "stats.keys": "Claves totales", "stats.ips": "IPs activas",
        "stats.ai": "Peticiones AI", "stats.admins": "Admins",
        "access.denied": "⛔ Acceso denegado", "access.your_id": "Tu ID",
        "access.ask_admin": "Envía este ID al admin principal.", "role.owner": "propietario",
        "role.superadmin": "superadmin", "role.admin": "admin", "role.guest": "invitado",
        "lang.changed": "Idioma del bot cambiado a", "lang.current": "Idioma actual",
    },
    "tr": {
        "menu.title": "TIGRAN MODZ BOT", "menu.role": "Rol", "menu.id": "ID",
        "menu.choose": "👇 Eylem seç:", "btn.keys": "🔑 Anahtarlar", "btn.sessions": "🌐 Oturumlar",
        "btn.stats": "📊 İstatistikler", "btn.admins": "👥 Yöneticiler", "btn.search": "🔍 Anahtar ara",
        "btn.quick": "🎯 Hızlı işlemler", "btn.utils": "🛠 Araçlar", "btn.reports": "📈 Raporlar",
        "btn.fun": "🎮 Eğlence", "btn.security": "🔒 Güvenlik", "btn.addadmin": "➕ Yönetici ekle",
        "btn.backup": "💾 Yedek", "btn.logs": "📜 Kayıtlar", "btn.broadcast": "📢 Yayın",
        "btn.pass": "🔑 Şifre", "btn.settings": "⚙ Ayarlar", "btn.tasks": "⏰ Görevler",
        "btn.create_key": "🔑 Anahtar oluştur", "btn.back": "◀ Geri",
        "keys.title": "Anahtarlar", "keys.none": "Anahtar yok", "keys.created": "Anahtar oluşturuldu",
        "keys.not_found": "Bulunamadı", "sessions.title": "Aktif oturumlar",
        "sessions.none": "Oturum yok", "stats.title": "İstatistikler",
        "stats.keys": "Toplam anahtar", "stats.ips": "Aktif IP'ler",
        "stats.ai": "AI istekleri", "stats.admins": "Yöneticiler",
        "access.denied": "⛔ Erişim reddedildi", "access.your_id": "ID'niz",
        "access.ask_admin": "Bu ID'yi ana yöneticiye gönderin.", "role.owner": "sahip",
        "role.superadmin": "süperadmin", "role.admin": "yönetici", "role.guest": "misafir",
        "lang.changed": "Bot dili değiştirildi:", "lang.current": "Mevcut dil",
    },
}

LANG_NAMES = {
    "ru": "Русский", "en": "English", "vi": "Tiếng Việt", "hy": "Հայերեն",
    "pt": "Português", "es": "Español", "tr": "Türkçe", "de": "Deutsch",
    "fr": "Français", "it": "Italiano", "zh": "中文", "ja": "日本語",
    "ko": "한국어", "ar": "العربية", "fa": "فارسی", "he": "עברית",
    "hi": "हिन्दी", "bn": "বাংলা", "ur": "اردو", "th": "ไทย",
    "id": "Bahasa Indonesia", "ms": "Bahasa Melayu", "tl": "Filipino",
    "kk": "Қазақша", "uz": "O'zbek", "az": "Azərbaycan", "ka": "ქართული",
    "uk": "Українська", "be": "Беларуская", "bg": "Български", "sr": "Српски",
    "hr": "Hrvatski", "sl": "Slovenščina", "sk": "Slovenčina", "cs": "Čeština",
    "pl": "Polski", "lt": "Lietuvių", "lv": "Latviešu", "et": "Eesti",
    "fi": "Suomi", "sv": "Svenska", "no": "Norsk", "da": "Dansk",
    "nl": "Nederlands", "el": "Ελληνικά", "ro": "Română", "hu": "Magyar",
    "sq": "Shqip", "mk": "Македонски", "is": "Íslenska", "ga": "Gaeilge",
    "mt": "Malti", "ca": "Català", "gl": "Galego", "eu": "Euskara",
    "af": "Afrikaans", "sw": "Kiswahili", "am": "አማርኛ", "yo": "Yorùbá",
    "ig": "Igbo", "ha": "Hausa", "zu": "Zulu", "xh": "isiXhosa",
    "st": "Sesotho", "sn": "Shona", "so": "Soomaali", "mg": "Malagasy",
    "ne": "नेपाली", "si": "සිංහල", "ta": "தமிழ்", "te": "తెలుగు",
    "kn": "ಕನ್ನಡ", "ml": "മലയാളം", "mr": "मराठी", "gu": "ગુજરાતી",
    "pa": "ਪੰਜਾਬੀ", "or": "ଓଡ଼ିଆ", "as": "অসমীয়া", "my": "မြန်မာ",
    "km": "ខ្មែរ", "lo": "ລາວ", "mn": "Монгол", "bo": "བོད་སྐད",
    "ug": "ئۇيغۇرچە", "ky": "Кыргызча", "tg": "Тоҷикӣ", "tk": "Türkmençe",
    "ps": "پښتو", "ku": "Kurdî", "sd": "سنڌي", "yue": "粵語",
    "ceb": "Cebuano", "jv": "Basa Jawa", "su": "Basa Sunda", "hmn": "Hmoob",
    "haw": "ʻŌlelo Hawaiʻi", "mi": "Te Reo Māori", "sm": "Gagana Samoa",
    "to": "Lea Faka-Tonga", "fj": "Vosa Vakaviti", "qu": "Runa Simi",
    "ay": "Aymar", "gn": "Avañe'ẽ", "nah": "Nāhuatl", "eo": "Esperanto",
    "la": "Latina", "yi": "ייִדיש", "lb": "Lëtzebuergesch", "fo": "Føroyskt",
    "cy": "Cymraeg", "gd": "Gàidhlig", "br": "Brezhoneg", "oc": "Occitan",
    "co": "Corsu", "sc": "Sardu", "rm": "Rumantsch", "fy": "Frysk",
    "li": "Limburgs", "nds": "Plattdüütsch", "hsb": "Hornjoserbsce",
    "csb": "Kaszëbsczi", "szl": "Ślōnski", "bar": "Boarisch", "ksh": "Kölsch",
    "vo": "Volapük", "io": "Ido", "ia": "Interlingua", "ie": "Interlingue",
    "an": "Aragonés", "ast": "Asturianu", "ext": "Estremeñu", "mwl": "Mirandés",
    "lad": "Ladino", "grc": "Ἀρχαία Ἑλληνικὴ", "syc": "ܣܘܪܝܝܐ",
    "cop": "ⲘⲉⲧⲢⲉⲙⲛ̀ⲭⲏⲙⲓ", "chr": "ᏣᎳᎩ", "iu": "ᐃᓄᒃᑎᑐᑦ",
    "oj": "ᐊᓂᔑᓈᐯᒧᐎᓐ", "cr": "ᓀᐦᐃᔭᐍᐏᐣ", "nv": "Diné bizaad",
    "quc": "K'iche'", "yua": "Maaya t'aan", "ht": "Kreyòl ayisyen",
    "pap": "Papiamentu", "srn": "Sranantongo", "jam": "Jamaican",
}

LANG_ALIASES = {
    "русский": "ru", "russian": "ru", "ru": "ru", "rus": "ru", "ро": "ru",
    "английский": "en", "english": "en", "en": "en", "eng": "en", "engleza": "en",
    "вьетнамский": "vi", "vietnamese": "vi", "vi": "vi", "viet": "vi", "tiếng việt": "vi", "vietnam": "vi",
    "армянский": "hy", "armenian": "hy", "hy": "hy", "հայերեն": "hy", "arm": "hy",
    "португальский": "pt", "portuguese": "pt", "pt": "pt", "português": "pt", "portugues": "pt",
    "испанский": "es", "spanish": "es", "es": "es", "español": "es", "espanol": "es", "castellano": "es",
    "турецкий": "tr", "turkish": "tr", "tr": "tr", "türkçe": "tr", "turkce": "tr", "türk": "tr",
    "немецкий": "de", "german": "de", "de": "de", "deutsch": "de",
    "французский": "fr", "french": "fr", "fr": "fr", "français": "fr", "francais": "fr",
    "итальянский": "it", "italian": "it", "it": "it", "italiano": "it",
    "китайский": "zh", "chinese": "zh", "zh": "zh", "中文": "zh", "mandarin": "zh", "普通话": "zh",
    "японский": "ja", "japanese": "ja", "ja": "ja", "日本語": "ja", "nihongo": "ja",
    "корейский": "ko", "korean": "ko", "ko": "ko", "한국어": "ko", "hangul": "ko",
    "арабский": "ar", "arabic": "ar", "ar": "ar", "العربية": "ar", "arab": "ar",
    "персидский": "fa", "persian": "fa", "fa": "fa", "farsi": "fa", "فارسی": "fa", "иранский": "fa",
    "иврит": "he", "hebrew": "he", "he": "he", "עברית": "he", "еврейский": "he",
    "хинди": "hi", "hindi": "hi", "hi": "hi", "हिन्दी": "hi", "индийский": "hi",
    "бенгальский": "bn", "bengali": "bn", "bn": "bn", "বাংলা": "bn",
    "урду": "ur", "urdu": "ur", "ur": "ur", "اردو": "ur",
    "тайский": "th", "thai": "th", "th": "th", "ไทย": "th", "сиамский": "th",
    "индонезийский": "id", "indonesian": "id", "id": "id", "bahasa indonesia": "id",
    "малайский": "ms", "malay": "ms", "ms": "ms", "bahasa melayu": "ms",
    "филиппинский": "tl", "filipino": "tl", "tl": "tl", "tagalog": "tl", "тагалог": "tl",
    "казахский": "kk", "kazakh": "kk", "kk": "kk", "қазақша": "kk", "казакша": "kk",
    "узбекский": "uz", "uzbek": "uz", "uz": "uz", "o'zbek": "uz", "ўзбек": "uz",
    "азербайджанский": "az", "azerbaijani": "az", "az": "az", "azərbaycan": "az",
    "грузинский": "ka", "georgian": "ka", "ka": "ka", "ქართული": "ka",
    "украинский": "uk", "ukrainian": "uk", "uk": "uk", "українська": "uk",
    "белорусский": "be", "belarusian": "be", "be": "be", "беларуская": "be",
    "болгарский": "bg", "bulgarian": "bg", "bg": "bg", "български": "bg",
    "сербский": "sr", "serbian": "sr", "sr": "sr", "српски": "sr",
    "хорватский": "hr", "croatian": "hr", "hr": "hr", "hrvatski": "hr",
    "словенский": "sl", "slovenian": "sl", "sl": "sl", "slovenščina": "sl",
    "словацкий": "sk", "slovak": "sk", "sk": "sk", "slovenčina": "sk",
    "чешский": "cs", "czech": "cs", "cs": "cs", "čeština": "cs",
    "польский": "pl", "polish": "pl", "pl": "pl", "polski": "pl",
    "литовский": "lt", "lithuanian": "lt", "lt": "lt", "lietuvių": "lt",
    "латышский": "lv", "latvian": "lv", "lv": "lv", "latviešu": "lv",
    "эстонский": "et", "estonian": "et", "et": "et", "eesti": "et",
    "финский": "fi", "finnish": "fi", "fi": "fi", "suomi": "fi",
    "шведский": "sv", "swedish": "sv", "sv": "sv", "svenska": "sv",
    "норвежский": "no", "norwegian": "no", "no": "no", "norsk": "no",
    "датский": "da", "danish": "da", "da": "da", "dansk": "da",
    "нидерландский": "nl", "dutch": "nl", "nl": "nl", "nederlands": "nl", "голландский": "nl",
    "греческий": "el", "greek": "el", "el": "el", "ελληνικά": "el",
    "румынский": "ro", "romanian": "ro", "ro": "ro", "română": "ro",
    "венгерский": "hu", "hungarian": "hu", "hu": "hu", "magyar": "hu",
    "албанский": "sq", "albanian": "sq", "sq": "sq", "shqip": "sq",
    "македонский": "mk", "macedonian": "mk", "mk": "mk", "македонски": "mk",
    "исландский": "is", "icelandic": "is", "is": "is", "íslenska": "is",
    "африкаанс": "af", "afrikaans": "af", "af": "af",
    "суахили": "sw", "swahili": "sw", "sw": "sw", "kiswahili": "sw",
    "амхарский": "am", "amharic": "am", "am": "am", "አማርኛ": "am",
    "йоруба": "yo", "yoruba": "yo", "yo": "yo",
    "зулу": "zu", "zulu": "zu", "zu": "zu",
    "сомалийский": "so", "somali": "so", "so": "so", "soomaali": "so",
    "непальский": "ne", "nepali": "ne", "ne": "ne", "नेपाली": "ne",
    "сингальский": "si", "sinhala": "si", "si": "si", "සිංහල": "si",
    "тамильский": "ta", "tamil": "ta", "ta": "ta", "தமிழ்": "ta",
    "телугу": "te", "telugu": "te", "te": "te", "తెలుగు": "te",
    "малаялам": "ml", "malayalam": "ml", "ml": "ml", "മലയാളം": "ml",
    "маратхи": "mr", "marathi": "mr", "mr": "mr", "मराठी": "mr",
    "гуджарати": "gu", "gujarati": "gu", "gu": "gu", "ગુજરાતી": "gu",
    "панджаби": "pa", "punjabi": "pa", "pa": "pa", "ਪੰਜਾਬੀ": "pa",
    "бирманский": "my", "burmese": "my", "my": "my", "မြန်မာ": "my",
    "кхмерский": "km", "khmer": "km", "km": "km", "ខ្មែរ": "km",
    "лаосский": "lo", "lao": "lo", "lo": "lo", "ລາວ": "lo",
    "монгольский": "mn", "mongolian": "mn", "mn": "mn", "монгол": "mn",
    "киргизский": "ky", "kyrgyz": "ky", "ky": "ky", "кыргызча": "ky",
    "таджикский": "tg", "tajik": "tg", "tg": "tg", "тоҷикӣ": "tg",
    "туркменский": "tk", "turkmen": "tk", "tk": "tk", "türkmençe": "tk",
    "пушту": "ps", "pashto": "ps", "ps": "ps", "پښتو": "ps",
    "курдский": "ku", "kurdish": "ku", "ku": "ku", "kurdî": "ku",
    "себуано": "ceb", "cebuano": "ceb", "ceb": "ceb",
    "яванский": "jv", "javanese": "jv", "jv": "jv", "basa jawa": "jv",
    "сунданский": "su", "sundanese": "su", "su": "su",
    "гаитянский": "ht", "haitian": "ht", "ht": "ht", "kreyòl": "ht",
    "эсперанто": "eo", "esperanto": "eo", "eo": "eo",
    "латинский": "la", "latin": "la", "la": "la", "latina": "la",
    "идиш": "yi", "yiddish": "yi", "yi": "yi", "ייִדיש": "yi",
    "валлийский": "cy", "welsh": "cy", "cy": "cy", "cymraeg": "cy",
    "ирландский": "ga", "irish": "ga", "ga": "ga", "gaeilge": "ga",
    "шотландский": "gd", "scottish gaelic": "gd", "gd": "gd", "gàidhlig": "gd",
    "баскский": "eu", "basque": "eu", "eu": "eu", "euskara": "eu",
    "каталанский": "ca", "catalan": "ca", "ca": "ca", "català": "ca",
    "галисийский": "gl", "galician": "gl", "gl": "gl",
    "гавайский": "haw", "hawaiian": "haw", "haw": "haw",
    "маори": "mi", "maori": "mi", "mi": "mi",
    "кечуа": "qu", "quechua": "qu", "qu": "qu",
    "чероки": "chr", "cherokee": "chr", "chr": "chr",
    "навахо": "nv", "navajo": "nv", "nv": "nv",
}


def load_lang():
    global _current_lang
    try:
        if os.path.exists(LANG_FILE):
            with open(LANG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _current_lang = data.get('lang', 'ru')
    except Exception as e:
        print(f"[I18N] load error: {e}")


def save_lang():
    try:
        with open(LANG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'lang': _current_lang}, f)
    except Exception as e:
        print(f"[I18N] save error: {e}")


def t(key, lang=None):
    l = lang or _current_lang
    if l in TRANSLATIONS and key in TRANSLATIONS[l]:
        return TRANSLATIONS[l][key]
    if 'ru' in TRANSLATIONS and key in TRANSLATIONS['ru']:
        return TRANSLATIONS['ru'][key]
    return key


def ai_translate_dict(target_code, target_name):
    if not OPENAI_API_KEY:
        return None
    base = TRANSLATIONS.get("ru", {})
    if not base:
        return None
    try:
        keys_json = json.dumps(base, ensure_ascii=False)
        prompt = (
            f"Translate this JSON dictionary to {target_name} ({target_code}).\n"
            "Rules:\n"
            "1. Keep JSON keys EXACTLY as they are (do NOT translate keys).\n"
            "2. Translate only VALUES.\n"
            "3. Keep emoji at start of values.\n"
            "4. Return ONLY valid JSON, no markdown, no explanations.\n\n"
            f"JSON:\n{keys_json}"
        )
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a professional translator. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 4000,
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            },
            timeout=60
        )
        if r.status_code != 200:
            print(f"[I18N] translate HTTP {r.status_code}")
            return None
        content = r.json()['choices'][0]['message']['content'].strip()
        content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content, flags=re.MULTILINE).strip()
        data = json.loads(content)
        if not isinstance(data, dict):
            return None
        return data
    except Exception as e:
        print(f"[I18N] translate error: {e}")
        return None


def load_translations_cache():
    cache_path = os.path.join(BASE_DIR, "translations_cache.json")
    try:
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for code, d in data.items():
                if isinstance(d, dict):
                    TRANSLATIONS[code] = d
            print(f"[I18N] Loaded {len(data)} cached translations")
    except Exception as e:
        print(f"[I18N] cache load error: {e}")


def set_lang(lang_code):
    global _current_lang
    code = LANG_ALIASES.get(lang_code.lower().strip(), lang_code.lower().strip())
    code = re.sub(r"[^a-z\-]", "", code)
    if not code:
        return False, "Invalid language code"

    if code in TRANSLATIONS:
        _current_lang = code
        save_lang()
        return True, LANG_NAMES.get(code, code)

    lang_name = LANG_NAMES.get(code, code)
    new_dict = ai_translate_dict(code, lang_name)
    if not new_dict:
        return False, f"Could not translate to {lang_name}. Check OPENAI_API_KEY."

    base = TRANSLATIONS.get("ru", {})
    for k, v in base.items():
        if k not in new_dict:
            new_dict[k] = v

    TRANSLATIONS[code] = new_dict
    LANG_NAMES.setdefault(code, lang_name)
    _current_lang = code
    save_lang()

    try:
        cache_path = os.path.join(BASE_DIR, "translations_cache.json")
        existing = {}
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        existing[code] = new_dict
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[I18N] cache save error: {e}")

    return True, lang_name
    # ==================== DATA STORES ====================
user_configs = {}
registered_ips = {}
generated_keys = {}
key_expiry = {}
user_profiles = {}

# ✅ РАСШИРЕННЫЙ DEFAULT_CONFIG — все старые + новые v1 + новые v3
DEFAULT_CONFIG = {
    # === СТАРЫЕ ===
    "HS_NECK": False,
    "HS_CHEST": False,
    "BYPASSV1": False,
    "BACKJUMPV1": False,
    "HIGH_SENSI": False,
    "ZIG_ZAG_MOVE": False,
    # === НОВЫЕ v1 ===
    "SPEED_RUN": False,
    "HIGH_JUMP": False,
    "HP_AP_MAX": False,
    "LOOT_MASTER": False,
    "AIM_PRO": False,
    "HEADSHOT_PRO": False,
    "ESP_RADAR": False,
    "BYPASS_PRO": False,
    # === НОВЫЕ v3 (100% client-side) ===
    "FULL_BRIGHT_PRO": False,
    "MEGA_RADAR": False,
    "HINT_MASTER": False,
    "LOUD_ENEMY": False,
    "QUIET_SELF": False,
    "INSTANT_USE": False,
    "LOOT_MEGA": False,
    "WIDE_FOV": False,
    "NO_CAMERA_SHAKE": False,
    "HUD_NAMES_PRO": False,
    "SPRINT_COMBO": False,
    "SWIM_PRO": False,
    "FLY_GLIDE_PRO": False,
    "FAST_SWITCH_PRO": False,
    "ANIM_SPEED_PRO": False,
    "NO_RECOIL_PRO": False,
    "VEHICLE_PRO_V3": False,
    "BALLISTIC_PRO": False,
    "EMOTE_MASTER": False,
    "SILENT_SELF": False,
    "AWARE_ENEMY": False,
    "UAV_SUPER": False,
    "SPECTATOR_PRO": False,
    "JUMPPAD_GOD": False,
    "GLIDER_PRO": False,
    "PHOTO_MODE_PRO": False,
    "AUTO_AIM_PRO": False,
    "VEHICLE_GOD": False,
    "HIT_SHOW_PRO": False,
    "MULTI_PING_PRO": False,
    "MOVEMENT_MASTER_PRO": False,
    "REPLAY_PRO": False,
    "VIEW_DISTANCE_PRO": False,
    "UI_AUDIO_PRO": False,
    "HITMARKER_PRO": False,
    "MAP_MARKER_PRO": False,
    "FULL_VISUAL_PRO": False,
    "FAST_UI_PRO": False,
    "GAMEPLAY_EXTRA": False,

    
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

# ==================== НОВЫЕ МОДУЛИ v1 ====================
SPEED_RUN_OVERRIDES = {
    "RunSpeed": {"var_type": "float", "var_value": "12.0"},
    "CrouchSpeed": {"var_type": "float", "var_value": "8.0"},
    "CreepSpeed": {"var_type": "float", "var_value": "5.0"},
    "DieingSpeed": {"var_type": "float", "var_value": "5.0"},
    "StropSpeed": {"var_type": "float", "var_value": "8.0"},
    "DashSpeedScale": {"var_type": "float", "var_value": "3.0"},
    "SwimSpeed": {"var_type": "float", "var_value": "8.0"},
    "SwimDashScale": {"var_type": "float", "var_value": "3.0"},
    "StropUseCooldown": {"var_type": "float", "var_value": "0.0"},
    "ZiplineUseCD": {"var_type": "float", "var_value": "0.0"},
    "ZipLineCancelCD": {"var_type": "float", "var_value": "0.0"},
}

HIGH_JUMP_OVERRIDES = {
    "MaxJumpHeight": {"var_type": "float", "var_value": "15.0"},
    "HighFallingHeight": {"var_type": "float", "var_value": "30.0"},
    "FountainHighFallingHeight": {"var_type": "float", "var_value": "30.0"},
    "LowGravityAreaFallingHeight": {"var_type": "float", "var_value": "30.0"},
    "SkyDivingRotationSpeed": {"var_type": "float", "var_value": "30.0"},
    "SkyDivingSpeedDelta": {"var_type": "float", "var_value": "30.0"},
    "ParachutingTurningRadius": {"var_type": "float", "var_value": "15.0"},
    "ParachutingMaxAngleTilt": {"var_type": "float", "var_value": "80.0"},
    "ParachutingTiltSpeed": {"var_type": "float", "var_value": "20.0"},
}

HP_AP_MAX_OVERRIDES = {
    "MaxAP": {"var_type": "float", "var_value": "500.0"},
    "DamageResistPerAP": {"var_type": "float", "var_value": "2.0"},
    "FastReviveAfterBooyah": {"var_type": "float", "var_value": "0.1"},
    "MaxRecentPlayersCount": {"var_type": "int", "var_value": "100"},
}

LOOT_MASTER_OVERRIDES = {
    "AutoPickupFunction": {"var_type": "bool", "var_value": "true"},
    "AutoPickUpInterval": {"var_type": "float", "var_value": "0.05"},
    "FastAutoPickUpInterval": {"var_type": "float", "var_value": "0.02"},
    "MaxAutoPickupMidkitCount": {"var_type": "int", "var_value": "20"},
    "MaxAutoPickupAssaultRifleAmmoMag": {"var_type": "int", "var_value": "30"},
    "MaxAutoPickupShotgunAmmoMag": {"var_type": "int", "var_value": "30"},
    "MaxAutoPickupSniperAmmoMag": {"var_type": "int", "var_value": "30"},
    "MaxAutoPickupPistolAmmoMag": {"var_type": "int", "var_value": "30"},
    "MaxAutoPickupUZIAmmoMag": {"var_type": "int", "var_value": "30"},
    "MaxAutoPickupSMGAmmoMag": {"var_type": "int", "var_value": "30"},
    "MaxAutoPickupGrenade": {"var_type": "int", "var_value": "10"},
    "MaxAutoPickupFrozenGrenade": {"var_type": "int", "var_value": "10"},
    "MaxAutoPickupFlameGrenade": {"var_type": "int", "var_value": "10"},
    "MaxAutoPickupIcewall": {"var_type": "int", "var_value": "5"},
    "MaxAutoPickupReplacerCount": {"var_type": "int", "var_value": "10"},
    "DefaultBagCapacity": {"var_type": "int", "var_value": "2000"},
    "LimitPickupItem": {"var_type": "bool", "var_value": "false"},
    "AttachEquipmentPickupLimit": {"var_type": "int", "var_value": "30"},
}

AIM_PRO_OVERRIDES = {
    "RotationSensitivityMin": {"var_type": "float", "var_value": "9.0"},
    "RotationSensitivityMax": {"var_type": "float", "var_value": "9.0"},
    "AimRotationSensitivityMin": {"var_type": "float", "var_value": "9.0"},
    "AimRotationSensitivityMax": {"var_type": "float", "var_value": "9.0"},
    "GooglePCRotationSensitivityMin": {"var_type": "float", "var_value": "9.0"},
    "GooglePCRotationSensitivityMax": {"var_type": "float", "var_value": "9.0"},
    "SensitivityMaxSetting": {"var_type": "float", "var_value": "9.0"},
    "Sensitivity1PMaxSetting": {"var_type": "float", "var_value": "9.0"},
    "X1ScopeMaxSetting": {"var_type": "float", "var_value": "9.0"},
    "X2ScopeMaxSetting": {"var_type": "float", "var_value": "9.0"},
    "X4ScopeMaxSetting": {"var_type": "float", "var_value": "9.0"},
    "X8ScopeMaxSetting": {"var_type": "float", "var_value": "9.0"},
    "FreeLookMaxSetting": {"var_type": "float", "var_value": "9.0"},
    "FreeLookCameraSensitivityScale": {"var_type": "float", "var_value": "3.0"},
    "FreeLookCameraSensitivityScaleOnVehicle": {"var_type": "float", "var_value": "3.0"},
    "UGC1PSensitivitySettingDefault": {"var_type": "float", "var_value": "9.0"},
}

HEADSHOT_PRO_OVERRIDES = {
    "HitDamageRatioHead": {"var_type": "float", "var_value": "3.0"},
    "HitDamageRatioBody": {"var_type": "float", "var_value": "1.5"},
    "HitDamageRatioLimb": {"var_type": "float", "var_value": "1.5"},
    "HitDamageRatioSniperExtension": {"var_type": "float", "var_value": "2.0"},
    "NoHeadshotTimeAfterPoseSwitch": {"var_type": "float", "var_value": "0.0"},
    "IsCrouchScatterOpen": {"var_type": "bool", "var_value": "false"},
    "CrouchScatterAngle": {"var_type": "float", "var_value": "0.0"},
    "CrouchScatterTime": {"var_type": "float", "var_value": "0.0"},
    "IsLyingScatterOpen": {"var_type": "bool", "var_value": "false"},
}

ESP_RADAR_OVERRIDES = {
    "ShowEnemyFireHint": {"var_type": "bool", "var_value": "true"},
    "ShowEnemyFootStepHint": {"var_type": "bool", "var_value": "true"},
    "ShowEnemyFireHintDefault": {"var_type": "bool", "var_value": "true"},
    "ShowEnemyFootStepHintDefault": {"var_type": "bool", "var_value": "true"},
    "EnableShowTargetOnMap": {"var_type": "bool", "var_value": "true"},
    "EnableShowTargetOnHud": {"var_type": "bool", "var_value": "true"},
    "EnableAutoEnemyMarkMerge": {"var_type": "bool", "var_value": "true"},
    "AutoEnemyMarkMergeDetectRange": {"var_type": "float", "var_value": "200.0"},
    "PlayerAssistantItemMarkDistance": {"var_type": "float", "var_value": "300.0"},
    "PlayerAssistantItemMarkTime": {"var_type": "float", "var_value": "30.0"},
    "ShowTeammateFiringOnMap": {"var_type": "bool", "var_value": "true"},
    "ShowEnemyFiringOnMap": {"var_type": "bool", "var_value": "true"},
}

BYPASS_PRO_OVERRIDES = {
    "EnableLocalColliderAntiHack": {"var_type": "bool", "var_value": "false"},
    "EnableLocalColliderValidation": {"var_type": "bool", "var_value": "false"},
    "EnableFileInfoEncryptionAndroid": {"var_type": "bool", "var_value": "false"},
    "EnableFileInfoEncryptionIOS": {"var_type": "bool", "var_value": "false"},
    "FFAntihackDefenceLevel": {"var_type": "string", "var_value": "0"},
    "FFAntihackLightInitOnThread": {"var_type": "bool", "var_value": "false"},
    "FFAntihackEmulatorCheckDisbaledClientVariant": {"var_type": "string", "var_value": ""},
    "FFAntihackSDKDetailEncryptBySHA1": {"var_type": "bool", "var_value": "false"},
    "FFANTIHACKEXT_SPLIT_THRESHOLD": {"var_type": "int", "var_value": "0"},
    "EnableFFAntihackInfoExtra": {"var_type": "bool", "var_value": "false"},
    "CleanFFAntiState": {"var_type": "bool", "var_value": "true"},
    "DisableGinInfoSend": {"var_type": "int", "var_value": "1"},
    "GinInfoBRAliveThreshold": {"var_type": "int", "var_value": "0"},
    "AntiHackResetSubgameInterval": {"var_type": "int", "var_value": "0"},
    "DisableKillRefreshGetTime": {"var_type": "int", "var_value": "0"},
    "EnableCheckFileStates": {"var_type": "bool", "var_value": "false"},
    "OptionalDeepFileCheck": {"var_type": "bool", "var_value": "false"},
    "EnableGGPDecryptFailureProtection": {"var_type": "bool", "var_value": "false"},
    "BugReportMaxCountPerSession": {"var_type": "int", "var_value": "0"},
    "EnableBugReportEarly": {"var_type": "int", "var_value": "0"},
    "EnableBugReportTime": {"var_type": "bool", "var_value": "false"},
    "Reportee_Damager_RecentlyMaxCnt": {"var_type": "int", "var_value": "0"},
    "Reportee_Killer_RecentlyMaxCnt": {"var_type": "int", "var_value": "0"},
    "KickUserInMatchGame": {"var_type": "bool", "var_value": "false"},
    "BlocklistMaxNum": {"var_type": "int", "var_value": "0"},
}

# ==================== НОВЫЕ МОДУЛИ v3 (100% client-side) ====================
FULL_BRIGHT_PRO_OVERRIDES = {
    "EnableLUTHighQuality": {"var_type": "bool", "var_value": "false"},
    "EnableLUTMidQuality": {"var_type": "bool", "var_value": "false"},
    "EnableBloom": {"var_type": "bool", "var_value": "false"},
    "EnablePlaneAO": {"var_type": "bool", "var_value": "false"},
    "EnableAOFields": {"var_type": "bool", "var_value": "false"},
    "EnableRimLighting": {"var_type": "bool", "var_value": "false"},
    "EnableBlackWhite": {"var_type": "bool", "var_value": "false"},
    "ShowBlackWhiteEffect": {"var_type": "bool", "var_value": "false"},
    "EnableCharacterBackLight": {"var_type": "bool", "var_value": "false"},
    "CharacterRecvShadow": {"var_type": "bool", "var_value": "false"},
    "DisableTerrainBlendingShadow": {"var_type": "bool", "var_value": "true"},
    "EnableGoldenAgeLensFlare": {"var_type": "bool", "var_value": "false"},
    "FlashEffectScale": {"var_type": "float", "var_value": "0.0"},
}

MEGA_RADAR_OVERRIDES = {
    "UavRange": {"var_type": "float", "var_value": "9999.0"},
    "UavModelDisplayRange": {"var_type": "float", "var_value": "9999.0"},
    "UavRevealTime": {"var_type": "float", "var_value": "9999.0"},
    "SensorBeaconHintAlwaysShow": {"var_type": "bool", "var_value": "true"},
    "SensorBeaconHintDutation": {"var_type": "float", "var_value": "9999.0"},
    "SensorBeaconHintCD": {"var_type": "float", "var_value": "0.0"},
    "RevengeInfoHintRange": {"var_type": "float", "var_value": "9999.0"},
    "EnableShowMaxHypePlayerPosInMap": {"var_type": "bool", "var_value": "true"},
    "EnableShowHypeEnemyHudLevel": {"var_type": "bool", "var_value": "true"},
}

HINT_MASTER_OVERRIDES = {
    "ShowEnemyFireHint": {"var_type": "bool", "var_value": "true"},
    "ShowEnemyFootStepHint": {"var_type": "bool", "var_value": "true"},
    "ShowEnemyFireHintDefault": {"var_type": "bool", "var_value": "true"},
    "ShowEnemyFootStepHintDefault": {"var_type": "bool", "var_value": "true"},
    "EnableFootstepMaterial": {"var_type": "bool", "var_value": "true"},
    "EnableAutoEnemyMarkMerge": {"var_type": "bool", "var_value": "true"},
    "EnableAutoEnemyMarkMergeBlinkEffect": {"var_type": "bool", "var_value": "true"},
    "AutoEnemyMarkMergeDetectRange": {"var_type": "float", "var_value": "999.0"},
    "PlayerAssistantItemMarkDistance": {"var_type": "float", "var_value": "999.0"},
    "PlayerAssistantItemMarkTime": {"var_type": "float", "var_value": "99.0"},
    "PlayerAssistantItemMarkCDTime": {"var_type": "float", "var_value": "0.0"},
    "PlayerAssistantAudioCDTime": {"var_type": "float", "var_value": "0.0"},
    "EnableUIHudItemMarkBtn": {"var_type": "bool", "var_value": "true"},
    "RemoveDeadTeammatesOnMap": {"var_type": "bool", "var_value": "false"},
    "DurationDeadTeammatesOnMap": {"var_type": "int", "var_value": "9999"},
    "CanEnemySeeActionCollection": {"var_type": "bool", "var_value": "false"},
}

LOUD_ENEMY_OVERRIDES = {
    "FireSoundMiddleSqrRange": {"var_type": "float", "var_value": "99999.0"},
    "FireSoundLongSqrRange": {"var_type": "float", "var_value": "99999.0"},
    "FootstepMaxAudibleDistanceSqr": {"var_type": "float", "var_value": "99999.0"},
    "WhizBySoundHappenRate": {"var_type": "float", "var_value": "1.0"},
    "WhizBySoundVolumeMin": {"var_type": "float", "var_value": "1.0"},
    "WhizBySoundVolumeMax": {"var_type": "float", "var_value": "1.0"},
    "GunTrace3PMinDistanceSqr": {"var_type": "float", "var_value": "0.0"},
    "GunTrace3PTimeInterval": {"var_type": "float", "var_value": "0.05"},
    "GunTrace3PTimeIntervalInMax": {"var_type": "float", "var_value": "0.05"},
    "GunTrace3PMaxDistance": {"var_type": "float", "var_value": "999.0"},
    "PriorityStepVolumeRate": {"var_type": "float", "var_value": "10.0"},
    "VehicleHitSoundMinSpeedSqr": {"var_type": "float", "var_value": "0.0"},
}

QUIET_SELF_OVERRIDES = {
    "WaitingRoom3PVolume": {"var_type": "float", "var_value": "0.0"},
    "PVEGunVolume": {"var_type": "float", "var_value": "0.0"},
    "TrainingWeaponVolumeInSocial": {"var_type": "float", "var_value": "0.0"},
    "LobbySocialAreaWeaponVolume": {"var_type": "float", "var_value": "0.0"},
    "SetMusicVolumeOnPlayAvatarVoice": {"var_type": "float", "var_value": "0.0"},
}

INSTANT_USE_OVERRIDES = {
    "AmmoBoxUsePrepareTime": {"var_type": "float", "var_value": "0.0"},
    "SmokedrumUsePrepareTime": {"var_type": "float", "var_value": "0.0"},
    "EatMushroomTime": {"var_type": "float", "var_value": "0.0"},
    "UseArmortoolsTime": {"var_type": "float", "var_value": "0.0"},
    "UseInfoBoxTime": {"var_type": "float", "var_value": "0.0"},
    "PickupInstantTime": {"var_type": "float", "var_value": "0.0"},
    "UseEnergyStoneBoxTime": {"var_type": "float", "var_value": "0.0"},
    "UseChokePointTime": {"var_type": "float", "var_value": "0.0"},
    "TreasuryGateOpenTime": {"var_type": "float", "var_value": "0.0"},
    "LevelInstrumentUseCD": {"var_type": "float", "var_value": "0.0"},
    "LevelWishingTreeUseCD": {"var_type": "float", "var_value": "0.0"},
    "WaitingCupUseCD": {"var_type": "float", "var_value": "0.0"},
    "FindTreasureMapTime": {"var_type": "float", "var_value": "0.0"},
    "FindFoxToriiTime": {"var_type": "float", "var_value": "0.0"},
    "TreasureHuntNormalTreasureDigTime": {"var_type": "float", "var_value": "0.0"},
    "TreasureHuntNormalTreasureDigAnimTime": {"var_type": "float", "var_value": "0.0"},
    "TreasureHuntOpenFrontDoorTime": {"var_type": "float", "var_value": "0.0"},
}

LOOT_MEGA_OVERRIDES = {
    "AutoPickupFunction": {"var_type": "bool", "var_value": "true"},
    "AutoPickUpInterval": {"var_type": "float", "var_value": "0.01"},
    "FastAutoPickUpInterval": {"var_type": "float", "var_value": "0.005"},
    "PauseAutoPickupCDTime": {"var_type": "float", "var_value": "0.0"},
    "MaxAutoPickupMidkitCount": {"var_type": "int", "var_value": "30"},
    "MaxAutoPickupAssaultRifleAmmoMag": {"var_type": "int", "var_value": "30"},
    "MaxAutoPickupShotgunAmmoMag": {"var_type": "int", "var_value": "30"},
    "MaxAutoPickupSniperAmmoMag": {"var_type": "int", "var_value": "30"},
    "MaxAutoPickupPistolAmmoMag": {"var_type": "int", "var_value": "30"},
    "MaxAutoPickupUZIAmmoMag": {"var_type": "int", "var_value": "30"},
    "MaxAutoPickupSMGAmmoMag": {"var_type": "int", "var_value": "30"},
    "MaxAutoPickupGrenade": {"var_type": "int", "var_value": "10"},
    "MaxAutoPickupFrozenGrenade": {"var_type": "int", "var_value": "10"},
    "MaxAutoPickupFlameGrenade": {"var_type": "int", "var_value": "10"},
    "MaxAutoPickupIcewall": {"var_type": "int", "var_value": "10"},
    "MaxAutoPickupReplacerCount": {"var_type": "int", "var_value": "10"},
    "MaxAutoPickupDeIcewallCount": {"var_type": "int", "var_value": "10"},
    "MaxAutoPickupMultiExplosiveCount": {"var_type": "int", "var_value": "10"},
    "MaxAutoPickupEMPCount": {"var_type": "int", "var_value": "10"},
    "MaxAutoPickupJumpPadCount": {"var_type": "int", "var_value": "10"},
    "MaxAutoPickupShieldRecoverCount": {"var_type": "int", "var_value": "10"},
    "AttachEquipmentPickupLimit": {"var_type": "int", "var_value": "30"},
    "DefaultBagCapacity": {"var_type": "int", "var_value": "2000"},
    "LimitPickupItem": {"var_type": "bool", "var_value": "false"},
}

WIDE_FOV_OVERRIDES = {
    "StropFOV": {"var_type": "float", "var_value": "120.0"},
    "StropFOVFadeDuration": {"var_type": "float", "var_value": "0.0"},
    "CannonFOV": {"var_type": "float", "var_value": "120.0"},
    "ActiveSkillCameraFOV": {"var_type": "float", "var_value": "120.0"},
    "GrapplingHookGunFOV": {"var_type": "float", "var_value": "120.0"},
    "JumpPadUpFOV": {"var_type": "float", "var_value": "120.0"},
    "JumpPadFOVFadeInDuration": {"var_type": "float", "var_value": "0.0"},
    "JumpPadFOVFadeOutDuration": {"var_type": "float", "var_value": "0.0"},
}

NO_CAMERA_SHAKE_OVERRIDES = {
    "SkyDivingCameraShakeFactor": {"var_type": "float", "var_value": "0.0"},
    "ParachutingCameraShakeFactor": {"var_type": "float", "var_value": "0.0"},
    "ParachutingCameraShakeDuring": {"var_type": "float", "var_value": "0.0"},
    "LandingCameraShakeDuration": {"var_type": "float", "var_value": "0.0"},
    "LandingCameraShakeFactor": {"var_type": "float", "var_value": "0.0"},
    "PVPFireShakeEnable": {"var_type": "bool", "var_value": "false"},
    "PVEFireShakeEnable": {"var_type": "bool", "var_value": "false"},
}

HUD_NAMES_PRO_OVERRIDES = {
    "SPHudNameScale": {"var_type": "float", "var_value": "3.0"},
    "SPHudNameFixedRadius": {"var_type": "float", "var_value": "9999.0"},
    "SPHudNameFreeRadius": {"var_type": "float", "var_value": "9999.0"},
    "SPHudNameShiftRadius": {"var_type": "float", "var_value": "9999.0"},
    "SPHudNameSightingAlpha": {"var_type": "float", "var_value": "1.0"},
    "SPHudNameMinAlpha": {"var_type": "float", "var_value": "1.0"},
    "SPHudNameMaxAlpha": {"var_type": "float", "var_value": "1.0"},
    "SPHudNameStartChangeAlphaDistance": {"var_type": "float", "var_value": "9999.0"},
    "SPHudNameMinAlphaDistance": {"var_type": "float", "var_value": "9999.0"},
    "SpectatorNamePlateScaleOffset": {"var_type": "float", "var_value": "3.0"},
    "SpectatorNamePlateScaleOffsetMiniMap": {"var_type": "float", "var_value": "3.0"},
    "PlayerHudNameInSkyOffset": {"var_type": "float", "var_value": "3.0"},
}

SPRINT_COMBO_OVERRIDES = {
    "RunSpeed": {"var_type": "float", "var_value": "10.0"},
    "DashSpeedScale": {"var_type": "float", "var_value": "2.0"},
    "CrouchSpeed": {"var_type": "float", "var_value": "7.0"},
    "CreepSpeed": {"var_type": "float", "var_value": "5.0"},
    "SwimSpeed": {"var_type": "float", "var_value": "7.0"},
    "SwimDashScale": {"var_type": "float", "var_value": "2.0"},
    "ShoalSpeedScale": {"var_type": "float", "var_value": "2.0"},
    "CatapultSpeed": {"var_type": "float", "var_value": "50.0"},
    "StropSpeed": {"var_type": "float", "var_value": "7.0"},
    "HealingWalkSpeedScale": {"var_type": "float", "var_value": "1.0"},
    "CarryingWalkSpeedScale": {"var_type": "float", "var_value": "1.0"},
}

SWIM_PRO_OVERRIDES = {
    "SwimSpeed": {"var_type": "float", "var_value": "15.0"},
    "SwimSurfSpeed": {"var_type": "float", "var_value": "15.0"},
    "SwimDashScale": {"var_type": "float", "var_value": "5.0"},
    "ShoalSpeedScale": {"var_type": "float", "var_value": "3.0"},
    "CanSwimSurfing": {"var_type": "bool", "var_value": "true"},
}

FLY_GLIDE_PRO_OVERRIDES = {
    "FoldWingGlidingStartMinHeight": {"var_type": "float", "var_value": "0.0"},
    "FoldWingGlidingAutoStopHeight": {"var_type": "float", "var_value": "0.0"},
    "FoldWingGlidingManualStopMinTime": {"var_type": "float", "var_value": "999.0"},
    "FoldWingGlidingHSpeed": {"var_type": "float", "var_value": "30.0"},
    "FoldWingGlidingVSpeed": {"var_type": "float", "var_value": "8.0"},
    "FoldWingFallingVSpeed": {"var_type": "float", "var_value": "2.0"},
    "FoldWingGlidingAngleDelta": {"var_type": "float", "var_value": "90.0"},
    "EnableSkySurfing": {"var_type": "bool", "var_value": "true"},
    "SkySurfingRotationSpeed": {"var_type": "float", "var_value": "90.0"},
    "SkySurfingSpeedDelta": {"var_type": "float", "var_value": "50.0"},
    "SkySurfingStanceButtonOffHeight": {"var_type": "float", "var_value": "999.0"},
    "SkyDivingSpeedDelta": {"var_type": "float", "var_value": "50.0"},
    "SkyDivingRotationSpeed": {"var_type": "float", "var_value": "90.0"},
}

FAST_SWITCH_PRO_OVERRIDES = {
    "SwapWeaponCD": {"var_type": "float", "var_value": "0.0"},
    "SwapWeaponInterval": {"var_type": "float", "var_value": "0.0"},
    "SwitchWeaponInterval": {"var_type": "float", "var_value": "0.0"},
    "GroupInviteCoolDown": {"var_type": "float", "var_value": "0.0"},
    "CardCoolDownCasual": {"var_type": "int", "var_value": "0"},
    "CardCoolDownAdvanced": {"var_type": "int", "var_value": "0"},
}

ANIM_SPEED_PRO_OVERRIDES = {
    "AnimSpeedRunFist": {"var_type": "float", "var_value": "3.0"},
    "AnimSpeedRunPistol": {"var_type": "float", "var_value": "3.0"},
    "AnimSpeedRunGun": {"var_type": "float", "var_value": "3.0"},
    "AnimSpeedRunAWM": {"var_type": "float", "var_value": "3.0"},
    "AnimSpeedDash": {"var_type": "float", "var_value": "3.0"},
    "AnimSpeedCrouch": {"var_type": "float", "var_value": "3.0"},
    "AnimSpeedCrawl": {"var_type": "float", "var_value": "3.0"},
    "AnimSpeedSwim": {"var_type": "float", "var_value": "3.0"},
    "MaxAnimSpeed": {"var_type": "float", "var_value": "5.0"},
}

NO_RECOIL_PRO_OVERRIDES = {
    "IsCrouchScatterOpen": {"var_type": "bool", "var_value": "false"},
    "CrouchScatterAngle": {"var_type": "float", "var_value": "0.0"},
    "CrouchScatterTime": {"var_type": "float", "var_value": "0.0"},
    "IsLyingScatterOpen": {"var_type": "bool", "var_value": "false"},
    "GunFireBoneDeltaAngeX": {"var_type": "float", "var_value": "0.0"},
    "GunFireBoneDeltaAngeX_Crouch": {"var_type": "float", "var_value": "0.0"},
    "GunFireBoneDeltaAngeZ_Crouch": {"var_type": "float", "var_value": "0.0"},
    "IKBoneRotateSpeed": {"var_type": "float", "var_value": "0.0"},
    "NoHeadshotTimeAfterPoseSwitch": {"var_type": "float", "var_value": "0.0"},
}

VEHICLE_PRO_V3_OVERRIDES = {
    "CarCrashProtectTimeForHitPlayer": {"var_type": "float", "var_value": "999.0"},
    "CarCrashProtectTimeForHitCar": {"var_type": "float", "var_value": "999.0"},
    "CarCrashProtectTimeForHitWall": {"var_type": "float", "var_value": "999.0"},
    "CarCrashDamageScaleToPlayer": {"var_type": "float", "var_value": "0.0"},
    "CarCrashDamageScaleToTeamate": {"var_type": "float", "var_value": "0.0"},
    "CarCrashDamageScaleToVehicle": {"var_type": "float", "var_value": "0.0"},
    "CarCrashDamageScaleWhenHitWall": {"var_type": "float", "var_value": "0.0"},
    "VehicleKillPersonMinSpeedSqr": {"var_type": "float", "var_value": "0.0"},
    "VehicleSkinHideDelay": {"var_type": "float", "var_value": "0.0"},
}

BALLISTIC_PRO_OVERRIDES = {
    "MissileTraceLength": {"var_type": "float", "var_value": "999.0"},
    "MissileStartPosOffsetFactor": {"var_type": "float", "var_value": "2.0"},
    "GunTraceHitDistanceThreshold": {"var_type": "float", "var_value": "9999.0"},
    "ShootTraceAdjustmentDistanceThreshold": {"var_type": "float", "var_value": "0.0"},
    "EnableShootTraceAdjustment": {"var_type": "bool", "var_value": "true"},
    "OneShotLimitInOneFrame": {"var_type": "int", "var_value": "999"},
}
# ══════════════════════════════════════════════════════
# v4 МОДУЛИ — на основе gamevar_full.txt
# ══════════════════════════════════════════════════════

# 🎭 EMOTE MASTER — расширенные эмоции/танцы
EMOTE_MASTER_OVERRIDES = {
    "FollowEmoteHeadCount": {"var_type": "int", "var_value": "99"},
    "FollowEmoteDriverDistance": {"var_type": "float", "var_value": "50.0"},
    "FollowEmotePassengerDistance": {"var_type": "float", "var_value": "50.0"},
    "FollowEmoteMaxHeightDiff": {"var_type": "float", "var_value": "50.0"},
    "FollowEmoteRenderSnapDistance": {"var_type": "float", "var_value": "0.0"},
    "FollowEmoteDissolveDelay": {"var_type": "float", "var_value": "0.0"},
    "FollowEmoteResponseBubbleDuration": {"var_type": "float", "var_value": "0.0"},
    "FollowEmoteButtonEffectDuration": {"var_type": "float", "var_value": "0.0"},
    "MultiPlayerEmoteDriverDistance": {"var_type": "float", "var_value": "99.0"},
    "MultiPlayerEmotePassengerDistance": {"var_type": "float", "var_value": "99.0"},
    "MultiPlayerEmotePassengerMaxHeight": {"var_type": "float", "var_value": "99.0"},
    "MultiPlayerEmoteViewDistance": {"var_type": "float", "var_value": "99.0"},
    "MaxEmoteFollower": {"var_type": "uint", "var_value": "99"},
    "AlwaysCanShowEmotePanel": {"var_type": "bool", "var_value": "true"},
    "SuperEmoteFakeLikeMaxCount": {"var_type": "int", "var_value": "9999"},
    "EmoteLeaderRange": {"var_type": "float", "var_value": "9999.0"},
    "Superemotetriggerrange": {"var_type": "float", "var_value": "9999.0"},
    "SuperemoteBtnHideTime": {"var_type": "float", "var_value": "9999.0"},
    "SuperEmoteChangeAimRotation": {"var_type": "bool", "var_value": "true"},
    "FollowEmoteSwitch": {"var_type": "bool", "var_value": "true"},
    "EnableFollowEmoteInCSMode": {"var_type": "bool", "var_value": "true"},
    "MultiPlayerEmoteIsDisVFX": {"var_type": "bool", "var_value": "false"},
}

# 🔊 SILENT MODE — тихие свои действия, громкие чужие
SILENT_SELF_OVERRIDES = {
    "WhizBySoundHappenRate": {"var_type": "float", "var_value": "0.0"},
    "WhizBySoundVolumeMin": {"var_type": "float", "var_value": "0.0"},
    "WhizBySoundVolumeMax": {"var_type": "float", "var_value": "0.0"},
    "SilenceWeaponHintRange": {"var_type": "float", "var_value": "0.0"},
    "PriorityStepVolumeRate": {"var_type": "float", "var_value": "0.0"},
    "VehicleHitSoundMinSpeedSqr": {"var_type": "float", "var_value": "0.0"},
    "SelfLowVolumeLevel": {"var_type": "int", "var_value": "0"},
    "OwnPlayerVoice": {"var_type": "int", "var_value": "0"},
}

# 👂 AWARE MODE — громкие враги, слышно далеко
AWARE_ENEMY_OVERRIDES = {
    "FireSoundMiddleSqrRange": {"var_type": "float", "var_value": "99999.0"},
    "FireSoundLongSqrRange": {"var_type": "float", "var_value": "99999.0"},
    "FootstepMaxAudibleDistanceSqr": {"var_type": "float", "var_value": "99999.0"},
    "BulletDropSoundDelay": {"var_type": "float", "var_value": "0.0"},
    "OtherUserHighVolumeLevel": {"var_type": "int", "var_value": "99"},
    "OtherUserVoiceMaxLevel": {"var_type": "int", "var_value": "99"},
    "EnableFootstepMaterial": {"var_type": "bool", "var_value": "true"},
    "VehicleSpeedEulerPerKm": {"var_type": "float", "var_value": "0.0"},
    "VehicleHitSoundMinSpeedSqr": {"var_type": "float", "var_value": "0.0"},
}

# 📡 UAV SUPER — радар на всю карту + долгий показ
UAV_SUPER_OVERRIDES = {
    "UavRange": {"var_type": "float", "var_value": "99999.0"},
    "UavModelDisplayRange": {"var_type": "float", "var_value": "99999.0"},
    "UavRevealTime": {"var_type": "float", "var_value": "99999.0"},
    "SensorBeaconHintAlwaysShow": {"var_type": "bool", "var_value": "true"},
    "SensorBeaconHintDutation": {"var_type": "float", "var_value": "99999.0"},
    "SensorBeaconHintCD": {"var_type": "float", "var_value": "0.0"},
    "RevengeInfoHintRange": {"var_type": "float", "var_value": "99999.0"},
    "EnableShowMaxHypePlayerPosInMap": {"var_type": "bool", "var_value": "true"},
    "EnableShowHypeEnemyHudLevel": {"var_type": "bool", "var_value": "true"},
    "EnableShowTargetOnMap": {"var_type": "bool", "var_value": "true"},
    "EnableShowTargetOnHud": {"var_type": "bool", "var_value": "true"},
    "ShowEnemyFireHint": {"var_type": "bool", "var_value": "true"},
    "ShowEnemyFootStepHint": {"var_type": "bool", "var_value": "true"},
    "EnableAutoEnemyMarkMerge": {"var_type": "bool", "var_value": "true"},
    "AutoEnemyMarkMergeDetectRange": {"var_type": "float", "var_value": "9999.0"},
    "AutoEnemyMarkDuration": {"var_type": "float", "var_value": "9999.0"},
    "PlayerAssistantItemMarkDistance": {"var_type": "float", "var_value": "99999.0"},
    "PlayerAssistantItemMarkTime": {"var_type": "float", "var_value": "9999.0"},
    "HudUAVHPRaycast": {"var_type": "bool", "var_value": "true"},
    "HudUAVHPRaycastInterval": {"var_type": "float", "var_value": "0.0"},
}

# 🎥 SPECTATOR PRO — быстрая камера наблюдателя
SPECTATOR_PRO_OVERRIDES = {
    "SpectatorCameraMoveSpeed": {"var_type": "float", "var_value": "99.0"},
    "SpectatorCameraFastMoveSpeedRatio": {"var_type": "float", "var_value": "20.0"},
    "SpectatorCamreraRotateSpeed": {"var_type": "float", "var_value": "99.0"},
    "SpectatorCameraMoveAcceleration": {"var_type": "float", "var_value": "999.0"},
    "SpectatorCameraMoveDeceleration": {"var_type": "float", "var_value": "999.0"},
    "SpectatorCameraMoveSpeedRatioMin": {"var_type": "float", "var_value": "0.0"},
    "SpectatorCameraMoveSpeedRatioMax": {"var_type": "float", "var_value": "20.0"},
    "SpectatorCameraRotateSpeedRatioMin": {"var_type": "float", "var_value": "0.0"},
    "SpectatorCameraRotateSpeedRatioMax": {"var_type": "float", "var_value": "20.0"},
    "SpectatorCameraSpeedChangeDelta": {"var_type": "float", "var_value": "99.0"},
    "SpectatorCameraMoveSpeedUp": {"var_type": "float", "var_value": "99.0"},
    "SpectatorCameraRotateSpeedUp": {"var_type": "float", "var_value": "99.0"},
    "SpectatorCameraMoveSlowDown": {"var_type": "float", "var_value": "0.0"},
    "SpectatorCameraRotateSlowDown": {"var_type": "float", "var_value": "0.0"},
    "SpectatorCameraRotate360Time": {"var_type": "float", "var_value": "0.1"},
    "SpectatorCameraHeight": {"var_type": "float", "var_value": "99.0"},
    "SpectatorCameraHDis": {"var_type": "float", "var_value": "0.5"},
    "SpectatorSoundRange": {"var_type": "float", "var_value": "99999.0"},
    "ObserverSwitchDelay": {"var_type": "float", "var_value": "0.0"},
    "ObserverUserControllerEnable": {"var_type": "bool", "var_value": "true"},
}

# 🚁 JUMP PAD GOD — идеальный джамппад
JUMPPAD_GOD_OVERRIDES = {
    "JumpPadUpFOV": {"var_type": "float", "var_value": "120.0"},
    "JumpPadFOVFadeInDuration": {"var_type": "float", "var_value": "0.0"},
    "JumpPadFOVFadeOutDuration": {"var_type": "float", "var_value": "0.0"},
    "JumpPadMaxHSpeed": {"var_type": "float", "var_value": "999.0"},
    "JumpPadFallingDefaultAnimNoramlizedTime": {"var_type": "float", "var_value": "0.0"},
    "MaxPropJumpPadAvailibleAngle": {"var_type": "float", "var_value": "180.0"},
    "JumpPadSmartFixAngle": {"var_type": "float", "var_value": "180.0"},
    "EnableJumpPadSmartCrossHair": {"var_type": "bool", "var_value": "true"},
    "CatapultSpeed": {"var_type": "float", "var_value": "999.0"},
    "PropCatapultSpeed": {"var_type": "float", "var_value": "999.0"},
    "CatapultHorizontalMinAngle": {"var_type": "float", "var_value": "-180.0"},
    "CatapultHorizontalMaxAngle": {"var_type": "float", "var_value": "180.0"},
    "CatapultVerticalMinAngle": {"var_type": "float", "var_value": "-90.0"},
    "CatapultVerticalMaxAngle": {"var_type": "float", "var_value": "90.0"},
}

# 🪂 GLIDER PRO — быстрое планирование/парашют
GLIDER_PRO_OVERRIDES = {
    "FoldWingGlidingStartMinHeight": {"var_type": "float", "var_value": "0.0"},
    "FoldWingGlidingAutoStopHeight": {"var_type": "float", "var_value": "0.0"},
    "FoldWingGlidingManualStopMinTime": {"var_type": "float", "var_value": "999.0"},
    "FoldWingGlidingHSpeed": {"var_type": "float", "var_value": "99.0"},
    "FoldWingGlidingVSpeed": {"var_type": "float", "var_value": "20.0"},
    "FoldWingFallingVSpeed": {"var_type": "float", "var_value": "1.0"},
    "FoldWingGlidingAngleDelta": {"var_type": "float", "var_value": "180.0"},
    "ParachutingMaxAngleTilt": {"var_type": "float", "var_value": "90.0"},
    "ParachutingMinAngleTilt": {"var_type": "float", "var_value": "-90.0"},
    "ParachutingTiltSpeed": {"var_type": "float", "var_value": "99.0"},
    "ParachutingMaxAngleRoll": {"var_type": "float", "var_value": "180.0"},
    "ParachutingMinAngleRoll": {"var_type": "float", "var_value": "-180.0"},
    "ParachutingRollSpeed": {"var_type": "float", "var_value": "99.0"},
    "ParachutingTurningRadius": {"var_type": "float", "var_value": "1.0"},
    "ParachutingOpenDuration": {"var_type": "float", "var_value": "0.0"},
    "SkyDivingSpeedDelta": {"var_type": "float", "var_value": "99.0"},
    "SkyDivingRotationSpeed": {"var_type": "float", "var_value": "99.0"},
    "SkyDivingTimeToOpenParachute": {"var_type": "float", "var_value": "999.0"},
    "SkyDivingTimeToOpenParachuteRebornDelta": {"var_type": "float", "var_value": "999.0"},
    "SkyDivingForceToOpenParachuteHeight": {"var_type": "float", "var_value": "0.0"},
    "SkyDivingForceToOpenParachuteHeightRebornDelta": {"var_type": "float", "var_value": "0.0"},
    "RebornSkyDivingSpeedRate": {"var_type": "float", "var_value": "999.0"},
    "EnableSkySurfing": {"var_type": "bool", "var_value": "true"},
    "SkySurfingRotationSpeed": {"var_type": "float", "var_value": "99.0"},
    "SkySurfingSpeedDelta": {"var_type": "float", "var_value": "99.0"},
    "SkySurfingStanceButtonOffHeight": {"var_type": "float", "var_value": "999.0"},
    "CanSwimSurfing": {"var_type": "bool", "var_value": "true"},
}

# 📸 PHOTO MODE PRO — расширенный режим фото
PHOTO_MODE_PRO_OVERRIDES = {
    "EnableCameraModeRotation": {"var_type": "bool", "var_value": "true"},
    "CameraModeCanStopVideoWhenStarting": {"var_type": "bool", "var_value": "true"},
    "CameraModeScreenShotOpt": {"var_type": "bool", "var_value": "true"},
    "CAMERA_MODE_INGAME_VERTICAL_TEMPLATE_ENABLE": {"var_type": "bool", "var_value": "true"},
    "CAMERA_MODE_PROJECTILE_WEAPON_FIRE_POSITION_FIXED": {"var_type": "bool", "var_value": "true"},
    "CAMERA_MODE_HUD_ALPHA": {"var_type": "float", "var_value": "0.0"},
    "CAMERA_MODE_MAIN_PANEL_MIN_ALPHA": {"var_type": "float", "var_value": "0.0"},
    "CAMERA_MODE_LOOP_EMOTE_DURATION": {"var_type": "float", "var_value": "9999.0"},
    "CAMERA_MODE_LOOP_EMOTE_DURATION_LOBBY": {"var_type": "float", "var_value": "9999.0"},
    "CAMERA_MODE_INGAME_ZOOM_MIN": {"var_type": "float", "var_value": "0.1"},
    "CAMERA_MODE_INGAME_ZOOM_MAX": {"var_type": "float", "var_value": "99.0"},
    "CAMERA_MODE_OUTGAME_ZOOM_MAX": {"var_type": "string", "var_value": "99.0"},
    "CAMERA_MODE_OUTGAME_ZOOM_DIST": {"var_type": "string", "var_value": "99.0"},
    "EnableFreeViewFixedMode": {"var_type": "bool", "var_value": "true"},
    "CameraModeScreenShotOpt": {"var_type": "bool", "var_value": "true"},
}

# 🎯 AUTO AIM PRO — умное наведение
AUTO_AIM_PRO_OVERRIDES = {
    "EnableAimAssistChange": {"var_type": "bool", "var_value": "true"},
    "NeedAimAssistOnChargeFinish": {"var_type": "bool", "var_value": "true"},
    "EnableAimAssistWhenStropDash": {"var_type": "bool", "var_value": "true"},
    "EnableBeAimAssistWhenStropDash": {"var_type": "bool", "var_value": "true"},
    "EnableSkillIgnoreAimAssistInVehicle": {"var_type": "bool", "var_value": "true"},
    "AimAssistTeammateScore": {"var_type": "float", "var_value": "0.0"},
    "AimAssistDragOutKnockdownMinDis": {"var_type": "float", "var_value": "0.0"},
    "IgnoreEnemyInAimingAdjust": {"var_type": "bool", "var_value": "true"},
    "CrossHairNullTargetDefaultAimingRed": {"var_type": "bool", "var_value": "true"},
    "EnableNewCrossHairTypeAimColor": {"var_type": "bool", "var_value": "true"},
    "EnableCrossHairColorChange": {"var_type": "bool", "var_value": "true"},
    "NoHeadshotTimeAfterPoseSwitch": {"var_type": "float", "var_value": "0.0"},
    "IsCrouchScatterOpen": {"var_type": "bool", "var_value": "false"},
    "IsLyingScatterOpen": {"var_type": "bool", "var_value": "false"},
    "CrouchScatterAngle": {"var_type": "float", "var_value": "0.0"},
    "CrouchScatterTime": {"var_type": "float", "var_value": "0.0"},
}

# 🚗 VEHICLE GOD — машина без урона + быстрая
VEHICLE_GOD_OVERRIDES = {
    "CarCrashProtectTimeForHitPlayer": {"var_type": "float", "var_value": "999.0"},
    "CarCrashProtectTimeForHitCar": {"var_type": "float", "var_value": "999.0"},
    "CarCrashProtectTimeForHitWall": {"var_type": "float", "var_value": "999.0"},
    "CarCrashDamageScaleToPlayer": {"var_type": "float", "var_value": "0.0"},
    "CarCrashDamageScaleToTeamate": {"var_type": "float", "var_value": "0.0"},
    "CarCrashDamageScaleToVehicle": {"var_type": "float", "var_value": "0.0"},
    "CarCrashDamageScaleToPlayerInVehicle": {"var_type": "float", "var_value": "0.0"},
    "CarCrashDamageScaleWhenHitWall": {"var_type": "float", "var_value": "0.0"},
    "VehicleKillPersonMinSpeedSqr": {"var_type": "float", "var_value": "0.0"},
    "VehicleSpeedEulerPerKm": {"var_type": "float", "var_value": "0.0"},
    "VehicleSkinHideDelay": {"var_type": "float", "var_value": "0.0"},
    "CarCrashSpeedScale": {"var_type": "float", "var_value": "0.0"},
    "CarCrashAngle": {"var_type": "float", "var_value": "0.0"},
    "UseNewCarCrash": {"var_type": "bool", "var_value": "false"},
    "VehicleResetTime": {"var_type": "float", "var_value": "0.0"},
    "VehicleResetThresholdSpped": {"var_type": "float", "var_value": "9999.0"},
    "DisableFlySnowEffect": {"var_type": "bool", "var_value": "true"},
    "EnableVehicleGroundPenetrationFix": {"var_type": "bool", "var_value": "false"},
}

# 🩺 HIT SHOW PRO — эффекты попадания
HIT_SHOW_PRO_OVERRIDES = {
    "EnableHeadShotHitEffect": {"var_type": "bool", "var_value": "true"},
    "HeadShotVFXLifeTime": {"var_type": "float", "var_value": "99.0"},
    "HeadShotHitEffectCooldown": {"var_type": "float", "var_value": "0.0"},
    "HeadShotHitEffectLifeTime": {"var_type": "float", "var_value": "99.0"},
    "HitFeedbackSoundCD": {"var_type": "float", "var_value": "0.0"},
    "HitFeedbackPromotion_ArmorBody_On": {"var_type": "bool", "var_value": "true"},
    "HitFeedbackPromotion_ArmorBody_HighlightTime": {"var_type": "float", "var_value": "99.0"},
    "HitFeedbackPromotion_ArmorBody_ShowTime": {"var_type": "float", "var_value": "99.0"},
    "HitFeedbackPromotion_ArmorBody_FadeTime": {"var_type": "float", "var_value": "0.0"},
    "HitFeedbackPromotion_ArmorBody_DisappearTime": {"var_type": "float", "var_value": "99.0"},
    "HitFeedbackPromotion_Vest_SoundDelay": {"var_type": "float", "var_value": "0.0"},
    "HitFeedbackPromotion_Helmet_SoundDelay": {"var_type": "float", "var_value": "0.0"},
    "HudHurtHint_DamageMin": {"var_type": "int", "var_value": "1"},
    "HudHurtHint_DamageMax": {"var_type": "int", "var_value": "999"},
    "HudHurtHint_ScaleMin": {"var_type": "float", "var_value": "10.0"},
    "HudHurtHint_ScaleMax": {"var_type": "float", "var_value": "10.0"},
    "ShowHitTrace": {"var_type": "bool", "var_value": "true"},
    "ShowHighPosHitHint": {"var_type": "bool", "var_value": "true"},
    "HighPosHitHintDistance": {"var_type": "float", "var_value": "999.0"},
    "Hint3DDisplayDuration": {"var_type": "float", "var_value": "99.0"},
    "HitmarkerTypeDefaultValue": {"var_type": "int", "var_value": "3"},
}

# 🎮 MULTI-MAP PING — пинг всех серверов
MULTI_PING_PRO_OVERRIDES = {
    "MultipleLobbyPing": {"var_type": "bool", "var_value": "true"},
    "PingCount": {"var_type": "int", "var_value": "99"},
    "Ping1": {"var_type": "int", "var_value": "10"},
    "Ping2": {"var_type": "int", "var_value": "20"},
    "PingMaxValue": {"var_type": "int", "var_value": "999"},
    "PingColor": {"var_type": "bool", "var_value": "true"},
    "CustomizedIntervalPingCounter": {"var_type": "bool", "var_value": "true"},
    "HidePingSignal": {"var_type": "bool", "var_value": "false"},
    "PingTimeout": {"var_type": "float", "var_value": "99.0"},
    "TCPPingTimeout": {"var_type": "float", "var_value": "99.0"},
    "AutoPingSyncToBackend": {"var_type": "bool", "var_value": "true"},
}

# 🏃 MOVEMENT MASTER PRO — расширенное движение
MOVEMENT_MASTER_PRO_OVERRIDES = {
    "FreeMoveAngularSpeed": {"var_type": "float", "var_value": "9999.0"},
    "FreeMoveAngularSpeedStand": {"var_type": "float", "var_value": "9999.0"},
    "FreeMoveAngularSpeedCrouch": {"var_type": "float", "var_value": "9999.0"},
    "FreeMoveAngularSpeedCreep": {"var_type": "float", "var_value": "9999.0"},
    "FreeMoveAngularSpeedKnockDown": {"var_type": "float", "var_value": "9999.0"},
    "ResetRotationSpeed": {"var_type": "float", "var_value": "9999.0"},
    "MaxSwingPitch": {"var_type": "float", "var_value": "90.0"},
    "MaxSwingRoll": {"var_type": "float", "var_value": "90.0"},
    "EnableInternalSetRotation": {"var_type": "bool", "var_value": "true"},
    "MaxRunSpeedUpScale": {"var_type": "float", "var_value": "3.0"},
    "MaxDashSpeedUpScale": {"var_type": "float", "var_value": "3.0"},
    "MaxWeaponAndSkillRunSpeedUpScale": {"var_type": "float", "var_value": "3.0"},
    "MaxUGCSpeedUpScale": {"var_type": "float", "var_value": "3.0"},
    "AccelerationOnFalling": {"var_type": "float", "var_value": "999.0"},
    "EnableAccelerationOnFalling": {"var_type": "bool", "var_value": "true"},
    "EnableCrossOverOnJumpAscent": {"var_type": "bool", "var_value": "true"},
    "EnableDashInFiring": {"var_type": "bool", "var_value": "true"},
    "EnableDashInClimb": {"var_type": "bool", "var_value": "true"},
    "EnableDashInHighFalling": {"var_type": "bool", "var_value": "true"},
    "EnableSlideOffFallingChangeDir": {"var_type": "bool", "var_value": "true"},
}

# 🎬 REPLAY PRO — расширенный реплей
REPLAY_PRO_OVERRIDES = {
    "AllowInGameReplayKit": {"var_type": "bool", "var_value": "true"},
    "ReplayEnableConfirmBox": {"var_type": "bool", "var_value": "false"},
    "ReplaykitMaxDuration": {"var_type": "float", "var_value": "9999.0"},
    "ReplaykitMinStorageGB": {"var_type": "float", "var_value": "0.0"},
    "MobileReplay_Enabled": {"var_type": "bool", "var_value": "true"},
    "MobileReplay_ForceOpen": {"var_type": "bool", "var_value": "true"},
    "MobileReplay_RecordPing": {"var_type": "bool", "var_value": "false"},
    "MobileReplay_SaveAfterPlay": {"var_type": "bool", "var_value": "true"},
    "MobileReplay_WhiteListForceSaveWhenPlay": {"var_type": "bool", "var_value": "true"},
    "MobileReplay_MinDiskSpace": {"var_type": "float", "var_value": "0.0"},
    "ReplayAutoAccelerateTime": {"var_type": "float", "var_value": "0.0"},
    "ReplayAutoSnapTime": {"var_type": "float", "var_value": "0.0"},
    "MaxTempReplayNumber": {"var_type": "int", "var_value": "999"},
    "UserUnityPlayerHighlihtPlayer": {"var_type": "bool", "var_value": "true"},
    "IsTeamingReplayEnable": {"var_type": "bool", "var_value": "true"},
    "UseMinimalEncoder": {"var_type": "bool", "var_value": "true"},
}

# 👁 VIEW DISTANCE PRO — дальность прорисовки
VIEW_DISTANCE_PRO_OVERRIDES = {
    "VegetationNewViewDistance": {"var_type": "int", "var_value": "999"},
    "RTShadowDistance": {"var_type": "float", "var_value": "9999.0"},
    "RTShadowDistanceOnAndroid": {"var_type": "float", "var_value": "9999.0"},
    "RTShadowNormalBias": {"var_type": "float", "var_value": "0.0"},
    "PetVisibleRange": {"var_type": "float", "var_value": "9999.0"},
    "WaitStreamingTelDistance": {"var_type": "float", "var_value": "0.0"},
    "WaitStreamingTelDuration": {"var_type": "float", "var_value": "0.0"},
    "LowMemPreviewStreamRange": {"var_type": "int", "var_value": "9999"},
    "StreamerMaxParallel": {"var_type": "int", "var_value": "999"},
    "DefaultGlobalMaximumLOD": {"var_type": "int", "var_value": "999"},
}

# 🎵 UI AUDIO PRO — громкость интерфейса
UI_AUDIO_PRO_OVERRIDES = {
    "LobbyChatDispearDelay": {"var_type": "float", "var_value": "9999.0"},
    "LobbyChatShowTime": {"var_type": "float", "var_value": "9999.0"},
    "LiftTopMessageShowTime": {"var_type": "float", "var_value": "9999.0"},
    "LiftTopMessageListShowTime": {"var_type": "float", "var_value": "9999.0"},
    "ChatClanLuckyBagMessageShowTime": {"var_type": "float", "var_value": "9999.0"},
    "ScreenShotMessageWindowTime": {"var_type": "float", "var_value": "9999.0"},
    "TeamChatBubbleDuration": {"var_type": "float", "var_value": "9999.0"},
    "QuickChatShowTime": {"var_type": "float", "var_value": "9999.0"},
    "QuickChatSendCD": {"var_type": "float", "var_value": "0.0"},
    "CardCloseTime": {"var_type": "float", "var_value": "0.0"},
    "ClanGroupInviteIconShowTime": {"var_type": "float", "var_value": "9999.0"},
    "ClanGroupInviteCoolDownTime": {"var_type": "float", "var_value": "0.0"},
    "TransferLeaderCd": {"var_type": "float", "var_value": "0.0"},
}

# 🎯 HITMARKER PRO — звуки и индикаторы попаданий
HITMARKER_PRO_OVERRIDES = {
    "IsPoenHeadShotSound": {"var_type": "bool", "var_value": "true"},
    "ShowDamageInfoIcon": {"var_type": "bool", "var_value": "true"},
    "ShowWeaponDamageInfoIcon": {"var_type": "bool", "var_value": "true"},
    "ShowWeaponPVEDamageInfoIcon": {"var_type": "bool", "var_value": "true"},
    "AccumulatedDamageDelay": {"var_type": "float", "var_value": "0.0"},
    "AccumulateContinuousFireDelay": {"var_type": "float", "var_value": "0.0"},
    "EnableTotalDmaggeHitLast": {"var_type": "bool", "var_value": "true"},
    "EnableTotalDamageHitmarker": {"var_type": "bool", "var_value": "true"},
    "ShowSpDetail": {"var_type": "bool", "var_value": "true"},
    "ShowSpDetailDefaultSp": {"var_type": "bool", "var_value": "true"},
    "TakeDamageDetail_DamangeMergeFrame": {"var_type": "int", "var_value": "0"},
    "TakeDamageDetail_SavedHistoryCount": {"var_type": "int", "var_value": "999"},
    "DamageShieldEffect": {"var_type": "int", "var_value": "1"},
}

# 📍 MAP MARKER PRO — маркеры на карте
MAP_MARKER_PRO_OVERRIDES = {
    "MarkScreenOffsetTop": {"var_type": "float", "var_value": "0.0"},
    "MarkScreenOffsetBottom": {"var_type": "float", "var_value": "0.0"},
    "MarkScreenOffsetLeft": {"var_type": "float", "var_value": "0.0"},
    "MarkScreenOffsetRight": {"var_type": "float", "var_value": "0.0"},
    "ItemMarkScreenOffsetTop": {"var_type": "float", "var_value": "0.0"},
    "ItemMarkScreenOffsetBottom": {"var_type": "float", "var_value": "0.0"},
    "ItemMarkScreenOffsetLeft": {"var_type": "float", "var_value": "0.0"},
    "ItemMarkScreenOffsetRight": {"var_type": "float", "var_value": "0.0"},
    "ItemMarkPressThreshold": {"var_type": "float", "var_value": "0.0"},
    "ItemMarkObjectCheckDistance": {"var_type": "float", "var_value": "999.0"},
    "ItemMarkWndAutoHideTime": {"var_type": "float", "var_value": "999.0"},
    "EnableUIHudItemMarkBtn": {"var_type": "bool", "var_value": "true"},
    "InGameItemMarkOneClickInterval": {"var_type": "float", "var_value": "0.0"},
    "InGameItemMarkAlphaThreshold": {"var_type": "float", "var_value": "0.0"},
    "InGameItemMarkResponseShowEffectDuration": {"var_type": "float", "var_value": "99.0"},
    "InGameItemMarkAlphaValue": {"var_type": "float", "var_value": "1.0"},
}

# 🎨 FULL VISUAL PRO — максимум визуала
FULL_VISUAL_PRO_OVERRIDES = {
    "EnableLUTHighQuality": {"var_type": "bool", "var_value": "false"},
    "EnableLUTMidQuality": {"var_type": "bool", "var_value": "false"},
    "EnableBloom": {"var_type": "bool", "var_value": "false"},
    "EnablePlaneAO": {"var_type": "bool", "var_value": "false"},
    "EnableAOFields": {"var_type": "bool", "var_value": "false"},
    "EnableRimLighting": {"var_type": "bool", "var_value": "false"},
    "EnableBlackWhite": {"var_type": "bool", "var_value": "false"},
    "ShowBlackWhiteEffect": {"var_type": "bool", "var_value": "false"},
    "EnableCharacterBackLight": {"var_type": "bool", "var_value": "false"},
    "CharacterRecvShadow": {"var_type": "bool", "var_value": "false"},
    "DisableTerrainBlendingShadow": {"var_type": "bool", "var_value": "true"},
    "FlashEffectScale": {"var_type": "float", "var_value": "0.0"},
    "EnableGoldenAgeLensFlare": {"var_type": "bool", "var_value": "false"},
    "OpenBrightnessStretch": {"var_type": "bool", "var_value": "true"},
    "DefaultBrightnessStretchThreshold": {"var_type": "float", "var_value": "0.0"},
    "DefaultBrightnessStretchSpeed": {"var_type": "float", "var_value": "99.0"},
    "PVPFireShakeEnable": {"var_type": "bool", "var_value": "false"},
    "PVEFireShakeEnable": {"var_type": "bool", "var_value": "false"},
    "EnablePlaneAO": {"var_type": "bool", "var_value": "false"},
}

# ⚡ FAST UI PRO — быстрый UI
FAST_UI_PRO_OVERRIDES = {
    "UIScreenOptimization": {"var_type": "bool", "var_value": "true"},
    "UIScreenDelayFrame": {"var_type": "int", "var_value": "0"},
    "OptUIPanel": {"var_type": "bool", "var_value": "true"},
    "EnableHighFreqPanelIsolation": {"var_type": "bool", "var_value": "true"},
    "UpdateUISprite": {"var_type": "bool", "var_value": "true"},
    "OptNGUIGetCompnentsGc": {"var_type": "bool", "var_value": "true"},
    "LazyCreateUIWidgetConers": {"var_type": "bool", "var_value": "true"},
    "OptimzeFrameTimeOB37": {"var_type": "bool", "var_value": "true"},
    "AllowForceCheckBtnChange": {"var_type": "bool", "var_value": "true"},
    "PanelLateUpdateToPreCull": {"var_type": "bool", "var_value": "true"},
    "EnablePanelUpdateSelfInterval": {"var_type": "bool", "var_value": "true"},
    "PanelUpdateSelfInterval": {"var_type": "int", "var_value": "0"},
    "UIDrawCallUseShaderNameCache": {"var_type": "bool", "var_value": "true"},
    "ForceSkipUIPanel": {"var_type": "bool", "var_value": "false"},
    "ForceSkipBigMapEnable": {"var_type": "bool", "var_value": "false"},
}

# 🎯 GAMEPLAY EXTRA — мелкие улучшения геймплея
GAMEPLAY_EXTRA_OVERRIDES = {
    "CanReloadContinueShoot": {"var_type": "bool", "var_value": "true"},
    "StopWeaponNetworkFireOnReloadSync": {"var_type": "bool", "var_value": "false"},
    "WeaponStateMachineStartFiringOnlyDoOnce": {"var_type": "bool", "var_value": "true"},
    "CanRunSpeedUpSkillContinueShoot": {"var_type": "bool", "var_value": "true"},
    "CanInvincibleContinueShoot": {"var_type": "bool", "var_value": "true"},
    "CanInvincibleReloadAndSwapWeapon": {"var_type": "bool", "var_value": "true"},
    "CanSwapWeaponContinueShoot": {"var_type": "bool", "var_value": "true"},
    "CanEnterWalkContinueShoot": {"var_type": "bool", "var_value": "true"},
    "MaxAP": {"var_type": "float", "var_value": "999.0"},
    "DamageResistPerAP": {"var_type": "float", "var_value": "5.0"},
    "DefaultBagCapacity": {"var_type": "int", "var_value": "9999"},
    "PickupInstantTime": {"var_type": "float", "var_value": "0.0"},
    "SwapWeaponCD": {"var_type": "float", "var_value": "0.0"},
    "SwitchWeaponInterval": {"var_type": "float", "var_value": "0.0"},
    "GroupInviteCoolDown": {"var_type": "float", "var_value": "0.0"},
    "MaxJumpHeight": {"var_type": "float", "var_value": "20.0"},
    "HighFallingHeight": {"var_type": "float", "var_value": "999.0"},
    "FountainHighFallingHeight": {"var_type": "float", "var_value": "999.0"},
    "LowGravityAreaFallingHeight": {"var_type": "float", "var_value": "999.0"},
    "StropFallingDamageMax": {"var_type": "int", "var_value": "0"},
    "EnableFireOnStrop": {"var_type": "bool", "var_value": "true"},
    "EnableStropDash": {"var_type": "bool", "var_value": "true"},
    "EnableStropAimAssist": {"var_type": "bool", "var_value": "true"},
}
# Старые заготовки (для совместимости)
PRECISAO_OVERRIDES = {}
HS_ALTO_OVERRIDES = {}
HS_ALTO_NECK_OVERRIDES = {}
ESP_ACTIVATED_OVERRIDES = {}

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
NOTIFICATIONS = []
FAVORITES = {}
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
        'key_expiry': {ip: exp.isoformat() for ip, exp in key_expiry.items()},
        'user_profiles': user_profiles,
        'favorites': FAVORITES
    }
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")


def load_data():
    global user_configs, registered_ips, generated_keys, key_expiry, user_profiles, FAVORITES
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            user_configs = data.get('user_configs', {})
            registered_ips = data.get('registered_ips', {})
            generated_keys = data.get('generated_keys', {})
            user_profiles = data.get('user_profiles', {})
            FAVORITES = data.get('favorites', {})
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
            user_profiles = {}
            FAVORITES = {}
    else:
        print("No existing data file found. Starting fresh.")
        user_configs = {}
        registered_ips = {}
        generated_keys = {}
        key_expiry = {}
        user_profiles = {}
        FAVORITES = {}
        save_data()


load_data()
load_lang()
load_translations_cache()


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
    else:
        # Автомиграция — если появились новые поля
        changed = False
        for k, v in DEFAULT_CONFIG.items():
            if k not in user_configs[client_ip]:
                user_configs[client_ip][k] = v
                changed = True
        if changed:
            save_data()
    return user_configs[client_ip]


def get_overrides_for_ip(client_ip):
    config = get_user_config(client_ip)
    overrides = {}
    # Старые
    if config.get("BYPASSV1", False):
        overrides.update(ANTI_BAN_OVERRIDES)
    if config.get("BACKJUMPV1", False):
        overrides.update(BACKJUMPV1_OVERRIDES)
    if config.get("HIGH_SENSI", False):
        overrides.update(HIGH_SENSI_OVERRIDES)
    if config.get("ZIG_ZAG_MOVE", False):
        overrides.update(ZIG_ZAG_MOVE_OVERRIDES)
    # Новые v1
    if config.get("SPEED_RUN", False):
        overrides.update(SPEED_RUN_OVERRIDES)
    if config.get("HIGH_JUMP", False):
        overrides.update(HIGH_JUMP_OVERRIDES)
    if config.get("HP_AP_MAX", False):
        overrides.update(HP_AP_MAX_OVERRIDES)
    if config.get("LOOT_MASTER", False):
        overrides.update(LOOT_MASTER_OVERRIDES)
    if config.get("AIM_PRO", False):
        overrides.update(AIM_PRO_OVERRIDES)
    if config.get("HEADSHOT_PRO", False):
        overrides.update(HEADSHOT_PRO_OVERRIDES)
    if config.get("ESP_RADAR", False):
        overrides.update(ESP_RADAR_OVERRIDES)
    if config.get("BYPASS_PRO", False):
        overrides.update(BYPASS_PRO_OVERRIDES)
    # Новые v3 (100% client-side)
    if config.get("FULL_BRIGHT_PRO", False):
        overrides.update(FULL_BRIGHT_PRO_OVERRIDES)
    if config.get("MEGA_RADAR", False):
        overrides.update(MEGA_RADAR_OVERRIDES)
    if config.get("HINT_MASTER", False):
        overrides.update(HINT_MASTER_OVERRIDES)
    if config.get("LOUD_ENEMY", False):
        overrides.update(LOUD_ENEMY_OVERRIDES)
    if config.get("QUIET_SELF", False):
        overrides.update(QUIET_SELF_OVERRIDES)
    if config.get("INSTANT_USE", False):
        overrides.update(INSTANT_USE_OVERRIDES)
    if config.get("LOOT_MEGA", False):
        overrides.update(LOOT_MEGA_OVERRIDES)
    if config.get("WIDE_FOV", False):
        overrides.update(WIDE_FOV_OVERRIDES)
    if config.get("NO_CAMERA_SHAKE", False):
        overrides.update(NO_CAMERA_SHAKE_OVERRIDES)
    if config.get("HUD_NAMES_PRO", False):
        overrides.update(HUD_NAMES_PRO_OVERRIDES)
    if config.get("SPRINT_COMBO", False):
        overrides.update(SPRINT_COMBO_OVERRIDES)
    if config.get("SWIM_PRO", False):
        overrides.update(SWIM_PRO_OVERRIDES)
    if config.get("FLY_GLIDE_PRO", False):
        overrides.update(FLY_GLIDE_PRO_OVERRIDES)
    if config.get("FAST_SWITCH_PRO", False):
        overrides.update(FAST_SWITCH_PRO_OVERRIDES)
    if config.get("ANIM_SPEED_PRO", False):
        overrides.update(ANIM_SPEED_PRO_OVERRIDES)
    if config.get("NO_RECOIL_PRO", False):
        overrides.update(NO_RECOIL_PRO_OVERRIDES)
    if config.get("VEHICLE_PRO_V3", False):
        overrides.update(VEHICLE_PRO_V3_OVERRIDES)
    if config.get("BALLISTIC_PRO", False):
        overrides.update(BALLISTIC_PRO_OVERRIDES)
# ==================== v4 модули ====================
    if config.get("EMOTE_MASTER", False):
        overrides.update(EMOTE_MASTER_OVERRIDES)
    if config.get("SILENT_SELF", False):
        overrides.update(SILENT_SELF_OVERRIDES)
    if config.get("AWARE_ENEMY", False):
        overrides.update(AWARE_ENEMY_OVERRIDES)
    if config.get("UAV_SUPER", False):
        overrides.update(UAV_SUPER_OVERRIDES)
    if config.get("SPECTATOR_PRO", False):
        overrides.update(SPECTATOR_PRO_OVERRIDES)
    if config.get("JUMPPAD_GOD", False):
        overrides.update(JUMPPAD_GOD_OVERRIDES)
    if config.get("GLIDER_PRO", False):
        overrides.update(GLIDER_PRO_OVERRIDES)
    if config.get("PHOTO_MODE_PRO", False):
        overrides.update(PHOTO_MODE_PRO_OVERRIDES)
    if config.get("AUTO_AIM_PRO", False):
        overrides.update(AUTO_AIM_PRO_OVERRIDES)
    if config.get("VEHICLE_GOD", False):
        overrides.update(VEHICLE_GOD_OVERRIDES)
    if config.get("HIT_SHOW_PRO", False):
        overrides.update(HIT_SHOW_PRO_OVERRIDES)
    if config.get("MULTI_PING_PRO", False):
        overrides.update(MULTI_PING_PRO_OVERRIDES)
    if config.get("MOVEMENT_MASTER_PRO", False):
        overrides.update(MOVEMENT_MASTER_PRO_OVERRIDES)
    if config.get("REPLAY_PRO", False):
        overrides.update(REPLAY_PRO_OVERRIDES)
    if config.get("VIEW_DISTANCE_PRO", False):
        overrides.update(VIEW_DISTANCE_PRO_OVERRIDES)
    if config.get("UI_AUDIO_PRO", False):
        overrides.update(UI_AUDIO_PRO_OVERRIDES)
    if config.get("HITMARKER_PRO", False):
        overrides.update(HITMARKER_PRO_OVERRIDES)
    if config.get("MAP_MARKER_PRO", False):
        overrides.update(MAP_MARKER_PRO_OVERRIDES)
    if config.get("FULL_VISUAL_PRO", False):
        overrides.update(FULL_VISUAL_PRO_OVERRIDES)
    if config.get("FAST_UI_PRO", False):
        overrides.update(FAST_UI_PRO_OVERRIDES)
    if config.get("GAMEPLAY_EXTRA", False):
        overrides.update(GAMEPLAY_EXTRA_OVERRIDES)
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


# ==================== USER PROFILES ====================
def get_user_profile(client_ip):
    if client_ip not in user_profiles:
        user_profiles[client_ip] = {
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "logins": 0,
            "nickname": "",
            "favorite_features": [],
            "presets": {}
        }
        save_data()
    return user_profiles[client_ip]


def update_user_profile(client_ip):
    profile = get_user_profile(client_ip)
    profile["last_seen"] = datetime.now().isoformat()
    profile["logins"] = profile.get("logins", 0) + 1
    save_data()


def save_preset(client_ip, name, config_data):
    profile = get_user_profile(client_ip)
    if "presets" not in profile:
        profile["presets"] = {}
    profile["presets"][name] = config_data
    save_data()


def apply_preset(client_ip, name):
    profile = get_user_profile(client_ip)
    preset = profile.get("presets", {}).get(name)
    if not preset:
        return False
    config = get_user_config(client_ip)
    for k, v in preset.items():
        if k in config:
            config[k] = v
    save_data()
    return True


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
    res = tg_api("getFile", {"file_id": file_id})
    if res and res.get("ok"):
        return res["result"].get("file_path")
    return None


def tg_download_file(file_path, save_to):
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
        tg_send(chat_id, t("access.denied"))
        return

    is_super = role in ("owner", "superadmin")
    is_owner = role == "owner"

    buttons = [
        [
            {"text": t("btn.keys"), "callback_data": "menu_keys_0"},
            {"text": t("btn.sessions"), "callback_data": "menu_sessions"}
        ],
        [
            {"text": t("btn.stats"), "callback_data": "menu_stats"},
            {"text": t("btn.admins"), "callback_data": "menu_admins"}
        ],
        [
            {"text": t("btn.search"), "callback_data": "menu_search"},
            {"text": t("btn.quick"), "callback_data": "menu_quick"}
        ],
        [
            {"text": t("btn.utils"), "callback_data": "menu_utils"},
            {"text": t("btn.reports"), "callback_data": "menu_reports"}
        ],
        [
            {"text": t("btn.fun"), "callback_data": "menu_fun"},
            {"text": t("btn.security"), "callback_data": "menu_security"}
        ],
    ]
    if is_super:
        buttons.append([
            {"text": t("btn.addadmin"), "callback_data": "menu_addadmin"}
        ])
    if is_owner:
        buttons.append([
            {"text": t("btn.backup"), "callback_data": "menu_backup"},
            {"text": t("btn.logs"), "callback_data": "menu_logs"}
        ])
        buttons.append([
            {"text": t("btn.broadcast"), "callback_data": "menu_broadcast"},
            {"text": t("btn.pass"), "callback_data": "menu_setpass"}
        ])
        buttons.append([
            {"text": t("btn.settings"), "callback_data": "menu_settings"},
            {"text": t("btn.tasks"), "callback_data": "menu_tasks"}
        ])

    tg_send_buttons(chat_id,
        f"{role_emoji(role)} <b>{t('menu.title')}</b>\n"
        f"{t('menu.role')}: <b>{t('role.' + role).upper()}</b>\n"
        f"{t('menu.id')}: <code>{chat_id}</code>\n\n"
        f"{t('menu.choose')}",
        buttons
    )


def tg_menu_keys(chat_id, message_id, page=0):
    if not generated_keys:
        text = f"📋 <b>{t('keys.none')}</b>"
        buttons = [[{"text": t("btn.create_key"), "callback_data": "quick_genkey"}],
                   [{"text": t("btn.back"), "callback_data": "menu_back"}]]
        tg_edit_message(chat_id, message_id, text, buttons)
        return
    keys_list = list(generated_keys.items())
    total = len(keys_list)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    chunk = keys_list[start:end]
    lines = [f"📋 <b>{t('keys.title')}</b> ({start+1}-{min(end, total)} / {total})\n"]
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
               [{"text": t("btn.create_key"), "callback_data": "quick_genkey"}],
               [{"text": t("btn.back"), "callback_data": "menu_back"}]]
    tg_edit_message(chat_id, message_id, text, buttons)


def tg_menu_sessions(chat_id, message_id):
    if not registered_ips:
        text = f"🌐 <b>{t('sessions.none')}</b>"
    else:
        lines = [f"🌐 <b>{t('sessions.title')} ({len(registered_ips)}):</b>\n"]
        for ip, key in list(registered_ips.items())[:15]:
            exp = key_expiry.get(ip)
            exp_str = exp.strftime('%d/%m/%Y') if exp else '-'
            lines.append(f"<code>{ip}</code>")
            lines.append(f"   └ {key} · до {exp_str}")
        text = "\n".join(lines)
    tg_edit_message(chat_id, message_id, text,
        [[{"text": t("btn.back"), "callback_data": "menu_back"}]])


def tg_menu_stats(chat_id, message_id):
    total_ips = len(registered_ips)
    total_keys = len(generated_keys)
    active_today = 0
    now = datetime.now()
    for ip, exp in key_expiry.items():
        if exp and exp > now:
            active_today += 1
    text = (
        f"📊 <b>{t('stats.title')}</b>\n\n"
        f"🔑 {t('stats.keys')}: <b>{total_keys}</b>\n"
        f"🌐 {t('stats.ips')}: <b>{total_ips}</b>\n"
        f"✅ Active: <b>{active_today}</b>\n"
        f"🤖 {t('stats.ai')}: <b>{sum(len(v) for v in _ai_requests.values())}</b>\n"
        f"👥 {t('stats.admins')}: <b>{1 + len(load_admins_data().get('admins', []))}</b>\n"
        f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    tg_edit_message(chat_id, message_id, text,
        [[{"text": t("btn.back"), "callback_data": "menu_back"}]])


def tg_menu_admins(chat_id, message_id):
    adata = load_admins_data()
    admins = adata.get('admins', [])
    lines = [f"👑 <b>Owner:</b> <code>{TELEGRAM_ADMIN_ID}</code>\n"]
    if admins:
        lines.append(f"⭐🎖 <b>Admins ({len(admins)}):</b>")
        for a in admins:
            em = role_emoji(a.get('role', 'admin'))
            lines.append(f"{em} <code>{a.get('id')}</code> [{a.get('role','admin')}]")
    else:
        lines.append("(empty)")
    tg_edit_message(chat_id, message_id, "\n".join(lines),
        [[{"text": t("btn.back"), "callback_data": "menu_back"}]])


def tg_menu_quick(chat_id, message_id):
    buttons = [
        [{"text": "🔑 Key (1 IP, 7d)", "callback_data": "quick_genkey"}],
        [{"text": "🔑 Key (5 IP, 30d)", "callback_data": "quick_genkey_big"}],
        [{"text": "📦 Bulk 10 keys", "callback_data": "quick_bulk10"}],
        [{"text": "📊 Stats", "callback_data": "menu_stats"}],
        [{"text": t("btn.back"), "callback_data": "menu_back"}]
    ]
    tg_edit_message(chat_id, message_id,
        f"🎯 <b>{t('btn.quick')}</b>\n\nChoose template:", buttons)


def tg_menu_utils(chat_id, message_id):
    text = (
        f"🛠 <b>{t('btn.utils')}</b>\n\n"
        "• <code>/short URL</code>\n"
        "• <code>/hash text</code>\n"
        "• <code>/b64enc text</code>\n"
        "• <code>/b64dec string</code>\n"
        "• <code>/pass 20</code>\n"
        "• <code>/weather Moscow</code>\n"
        "• <code>/currency 100 USD RUB</code>\n"
        "• <code>/qr KEY</code>\n"
    )
    tg_edit_message(chat_id, message_id, text,
        [[{"text": t("btn.back"), "callback_data": "menu_back"}]])


def tg_menu_reports(chat_id, message_id):
    text = (
        f"📈 <b>{t('btn.reports')}</b>\n\n"
        "• <code>/report</code>\n"
        "• <code>/heatmap</code>\n"
        "• <code>/activity</code>\n"
        "• <code>/export csv</code>\n"
    )
    tg_edit_message(chat_id, message_id, text,
        [[{"text": t("btn.back"), "callback_data": "menu_back"}]])


def tg_menu_fun(chat_id, message_id):
    text = (
        f"🎮 <b>{t('btn.fun')}</b>\n\n"
        "• <code>/bonus</code>\n"
        "• <code>/rep</code>\n"
        "• <code>/quiz</code>\n"
        "• <code>/guess</code>\n"
        "• <code>/events</code>\n"
    )
    tg_edit_message(chat_id, message_id, text,
        [[{"text": t("btn.back"), "callback_data": "menu_back"}]])


def tg_menu_security(chat_id, message_id):
    text = (
        f"🔒 <b>{t('btn.security')}</b>\n\n"
        "• <code>/ban 1.2.3.4 24</code>\n"
        "• <code>/unban 1.2.3.4</code>\n"
        "• <code>/iplookup 8.8.8.8</code>\n\n"
        f"🚫 Banned: <b>{len(BANNED_IPS) + len(IP_BLACKLIST)}</b>"
    )
    tg_edit_message(chat_id, message_id, text,
        [[{"text": t("btn.back"), "callback_data": "menu_back"}]])


def tg_menu_tasks(chat_id, message_id):
    if not SCHEDULED_TASKS:
        text = f"⏰ <b>{t('btn.tasks')}</b>\n\n<code>/schedule broadcast 3600 Text</code>"
    else:
        lines = [f"⏰ <b>{t('btn.tasks')} ({len(SCHEDULED_TASKS)}):</b>\n"]
        for tk in SCHEDULED_TASKS[:15]:
            left = int(tk['when'] - time.time())
            lines.append(f"• <code>{tk['id'][:12]}</code> · {tk['action']} · {left}s")
        text = "\n".join(lines)
    tg_edit_message(chat_id, message_id, text,
        [[{"text": t("btn.back"), "callback_data": "menu_back"}]])


# ==================== КАТЕГОРИЯ 2: КЛЮЧИ ====================
def tg_bulk_create_keys(chat_id, count, prefix, limit, days):
    try: count = max(1, min(int(count), 50))
    except: count = 1
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
        tg_send(chat_id, "No keys.")
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
                data = {"chat_id": str(chat_id), "caption": f"📦 Export: {len(generated_keys)} keys"}
                requests.post(url, files=files, data=data, timeout=60)
        try: os.remove(path)
        except: pass
    except Exception as e:
        tg_send(chat_id, f"❌ Error: {e}")


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
        except Exception as e:
            print(f"[TG] auto-delete error: {e}")
        time.sleep(3600)


def tg_extend_key(key, extra_days):
    key = normalize_key(key)
    if key not in generated_keys:
        return False, "Key not found"
    try: extra_days = max(1, int(extra_days))
    except: return False, "Invalid days"
    generated_keys[key]['days'] += extra_days
    save_data()
    return True, f"Extended by {extra_days}d. Total: {generated_keys[key]['days']}d"


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
                data = {"chat_id": str(chat_id), "caption": f"🔗 QR:\n<code>{key}</code>", "parse_mode": "HTML"}
                requests.post(tg_url, files=files, data=data, timeout=60)
            try: os.remove(path)
            except: pass
    except Exception as e:
        tg_send(chat_id, f"❌ QR error: {e}")
        # ==================== КАТЕГОРИЯ 3: БЕЗОПАСНОСТЬ ====================
def tg_ban_ip(ip, hours=24):
    try: hours = max(1, int(hours))
    except: hours = 24
    BANNED_IPS[ip] = time.time() + hours * 3600
    tg_log("ban_ip", "bot", f"{ip} for {hours}h")
    return f"IP {ip} banned for {hours}h"


def tg_unban_ip(ip):
    BANNED_IPS.pop(ip, None)
    IP_BLACKLIST.discard(ip)
    return f"IP {ip} unbanned"


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
        f"🔔 <b>NEW LOGIN</b>\n\n"
        f"IP: <code>{client_ip}</code>{geo_line}\n"
        f"Key: <code>{key}</code>\n"
        f"Until: {expiry_date.strftime('%d/%m/%Y')}"
    )
    tg_notify_all_admins(text)


# ==================== КАТЕГОРИЯ 4: AI ====================
def tg_ai_translate(text, target_lang="ru"):
    if not OPENAI_API_KEY: return None
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": f"Translate to {target_lang}. Only translation."},
                    {"role": "user", "content": text[:1500]}
                ],
                "max_tokens": 600, "temperature": 0.3
            }, timeout=25)
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content']
    except: pass
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
                    {"role": "system", "content": "Summarize in 3-5 sentences."},
                    {"role": "user", "content": text[:3000]}
                ],
                "max_tokens": 400, "temperature": 0.5
            }, timeout=25)
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content']
    except: pass
    return None


def tg_ai_describe_image(file_id, chat_id, caption=""):
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

        if caption.strip():
            user_prompt = (
                f"Пользователь прислал изображение с вопросом или заданием: «{caption.strip()}»\n\n"
                "Выполни его запрос на основе изображения. "
                "Отвечай на том же языке, на котором написан вопрос пользователя. "
                "Если это перевод — переводи. Если вопрос — отвечай на вопрос. "
                "Если просто просят описать — опиши."
            )
        else:
            user_prompt = (
                "Опиши это изображение кратко на русском языке. "
                "Что на нём изображено, кто, что делает, какой контекст."
            )

        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                }],
                "max_tokens": 1000
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
            tg_send(chat_id, f"🎨 <b>Done!</b>\n\n🔗 <a href='{img_url}'>Download</a>")
            return True
        else:
            tg_send(chat_id, f"❌ DALL-E: HTTP {r.status_code}")
    except Exception as e:
        tg_send(chat_id, f"❌ Error: {e}")
    return False


# ==================== КАТЕГОРИЯ 5: УТИЛИТЫ ====================
def tg_url_shorten(url):
    try:
        r = requests.get(f"https://tinyurl.com/api-create.php?url={url}", timeout=10)
        if r.status_code == 200:
            return r.text.strip()
    except: pass
    return None


def tg_hash_text(text, algo="sha256"):
    try:
        if algo == "md5": return hashlib.md5(text.encode()).hexdigest()
        elif algo == "sha1": return hashlib.sha1(text.encode()).hexdigest()
        elif algo == "sha512": return hashlib.sha512(text.encode()).hexdigest()
        else: return hashlib.sha256(text.encode()).hexdigest()
    except: return None


def tg_b64_encode(text):
    return base64.b64encode(text.encode()).decode()


def tg_b64_decode(text):
    try: return base64.b64decode(text.encode()).decode()
    except: return None


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
                    f"🌡 {cur.get('temp_C')}°C (feels {cur.get('FeelsLikeC')}°C)\n"
                    f"☁ {cur.get('weatherDesc',[{}])[0].get('value','?')}\n"
                    f"💧 {cur.get('humidity')}%\n"
                    f"💨 {cur.get('windspeedKmph')} km/h")
    except: pass
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
    except: pass
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
        f"🌅 <b>DAILY REPORT</b>",
        f"📅 {now.strftime('%d/%m/%Y %H:%M')}\n",
        f"🔑 {t('stats.keys')}: <b>{s['total_keys']}</b>",
        f"🌐 {t('stats.ips')}: <b>{s['active_ips']}</b>",
        f"👥 {t('stats.admins')}: <b>{s['admin_count']}</b>",
        f"🤖 {t('stats.ai')}: <b>{s['ai_reqs']}</b>",
        f"⚠ Expiring in 3 days: <b>{s['soon_expiring']}</b>\n",
        f"🏆 <b>Top-5 keys:</b>"
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
        except Exception as e:
            print(f"[TG] report scheduler error: {e}")
        time.sleep(60)


def tg_ip_heatmap():
    if not registered_ips:
        return "No data"
    lines = ["🗺 <b>IP Map:</b>\n"]
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
                            tg_notify_all_admins(f"📢 <b>Auto-broadcast:</b>\n\n{task['params'].get('text','')}")
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
                            tg_notify_all_admins("🧹 Auto-cleanup started")
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
        lines = ["⏰ <b>Keys expiring tomorrow:</b>\n"]
        for ip, key, exp in soon[:20]:
            lines.append(f"<code>{ip}</code> — {key} · {exp.strftime('%d/%m')}")
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
        return "📊 No activity data."
    sorted_admins = sorted(ADMIN_ACTIVITY.items(), key=lambda x: x[1]['actions'], reverse=True)
    lines = ["📊 <b>Top by activity:</b>\n"]
    for cid, data in sorted_admins[:15]:
        em = role_emoji(get_user_role(cid))
        lines.append(f"{em} <code>{cid}</code> — {data['actions']} · {data['last'][:16]}")
    return "\n".join(lines)


def tg_admin_dm(from_id, to_id, text):
    if get_user_role(from_id) == "guest":
        return "⛔ No rights."
    if get_user_role(to_id) == "guest":
        return "❌ Not admin."
    try:
        tg_send(to_id, f"📩 <b>Message from</b> <code>{from_id}</code>:\n\n{text}")
        return "✅ Sent."
    except Exception as e:
        return f"❌ Error: {e}"


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
        return f"⏰ Already claimed today!"
    DAILY_BONUS[cid] = today
    USER_REPUTATION[cid] = USER_REPUTATION.get(cid, 0) + 1
    return f"🎁 Bonus! Reputation: <b>{USER_REPUTATION[cid]}</b>"


def tg_add_achievement(chat_id, name):
    cid = str(chat_id)
    if cid not in USER_ACHIEVEMENTS:
        USER_ACHIEVEMENTS[cid] = []
    if name not in USER_ACHIEVEMENTS[cid]:
        USER_ACHIEVEMENTS[cid].append(name)
        tg_send(chat_id, f"🏅 <b>Achievement:</b> {name}")


def tg_quiz_start(chat_id):
    questions = [
        {"q": "2+2*2=?", "a": "6"},
        {"q": "Capital of Armenia?", "a": "yerevan"},
        {"q": "Days in year?", "a": "365"},
        {"q": "Bigger: 100 or 99?", "a": "100"},
        {"q": "Sky color?", "a": "blue"},
    ]
    q = random.choice(questions)
    tg_send(chat_id, f"🎮 <b>Quiz!</b>\n\n{q['q']}\n\n<i>Reply in chat</i>")
    return q['a']


def tg_check_quiz(chat_id, text):
    cid = str(chat_id)
    if cid in QUIZ_ANSWERS:
        expected = QUIZ_ANSWERS[cid]
        if text.strip().lower() == expected:
            del QUIZ_ANSWERS[cid]
            USER_REPUTATION[cid] = USER_REPUTATION.get(cid, 0) + 5
            tg_send(chat_id, f"✅ Correct! +5 rep\nTotal: {USER_REPUTATION[cid]}")
            return True
    return False


def tg_guess_number_start(chat_id):
    num = random.randint(1, 100)
    GUESS_NUMBERS[str(chat_id)] = num
    tg_send(chat_id, "🎲 <b>Guess the number</b>\n\n1-100. Write number.")
    return num


def tg_check_guess(chat_id, text):
    cid = str(chat_id)
    if cid not in GUESS_NUMBERS:
        return False
    try: guess = int(text.strip())
    except: return False
    target = GUESS_NUMBERS[cid]
    if guess == target:
        del GUESS_NUMBERS[cid]
        tg_send(chat_id, f"🎉 Correct! <b>{target}</b>")
        return True
    elif guess < target:
        tg_send(chat_id, "📈 More!")
    else:
        tg_send(chat_id, "📉 Less!")
    return True


def tg_events_calendar():
    now = datetime.now()
    return (
        f"📅 <b>Events</b>\n\n"
        f"🌅 Daily report: 09:00\n"
        f"⏰ Reminders: hourly\n"
        f"🧹 Auto-clean: hourly\n"
        f"📅 Now: {now.strftime('%d/%m/%Y %H:%M')}"
    )


# ==================== КАТЕГОРИЯ 10: ИНТЕГРАЦИИ ====================
def tg_google_sheets_sync():
    url = os.environ.get("GOOGLE_SHEETS_WEBHOOK", "")
    if not url:
        return False, "GOOGLE_SHEETS_WEBHOOK not set"
    try:
        data = {
            "keys": [{"key": k, "used": len(v['used_ips']), "days": v['days']} for k, v in generated_keys.items()],
            "ips": list(registered_ips.keys()),
            "at": datetime.now().isoformat()
        }
        r = requests.post(url, json=data, timeout=15)
        if r.status_code == 200:
            return True, "Synced"
    except Exception as e:
        return False, str(e)
    return False, "Failed"


def tg_send_email(to_email, subject, body):
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    if not all([smtp_host, smtp_user, smtp_pass]):
        return False, "SMTP not configured"
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
        return True, "Email sent"
    except Exception as e:
        return False, str(e)


def tg_send_youtube_info(url):
    try:
        r = requests.get(f"https://www.youtube.com/oembed?url={url}&format=json", timeout=10)
        if r.status_code == 200:
            d = r.json()
            return (f"🎬 <b>{d.get('title','?')}</b>\n\n"
                    f"👤 {d.get('author_name','?')}\n"
                    f"🌐 {d.get('provider_name','YouTube')}")
    except: pass
    return None


def tg_github_status():
    repo = os.environ.get("GITHUB_REPO", "")
    if not repo:
        return None
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}", timeout=10)
        if r.status_code == 200:
            d = r.json()
            return (f"🐙 <b>GitHub</b>\n\n"
                    f"📦 {d.get('name')}\n"
                    f"⭐ {d.get('stargazers_count')}\n"
                    f"🍴 {d.get('forks_count')}\n"
                    f"📅 {d.get('updated_at','')[:10]}")
    except: pass
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
                "line_items[0][price_data][product_data][name]": "TIGRAN MODZ",
                "line_items[0][price_data][unit_amount]": int(amount * 100),
                "line_items[0][quantity]": 1,
            }, timeout=15)
        if r.status_code == 200:
            return r.json().get('url')
    except: pass
    return None


def tg_achievements_checker():
    while True:
        try:
            for cid, data in ADMIN_ACTIVITY.items():
                if data['actions'] >= 10:
                    tg_add_achievement(cid, "🔥 Active admin (10+)")
                if data['actions'] >= 50:
                    tg_add_achievement(cid, "🚀 Pro (50+)")
            if len(generated_keys) >= 100:
                for cid in ADMIN_ACTIVITY.keys():
                    tg_add_achievement(cid, "💎 100+ keys")
        except Exception as e:
            print(f"[TG] achievements error: {e}")
        time.sleep(3600)


# ==================== OWNER AI-АГЕНТ ====================
def tg_owner_ai_agent(chat_id, text):
    if not OPENAI_API_KEY:
        return None
    system_prompt = (
    "Ты — умный агент управления Telegram-ботом TIGRAN MODZ.\n"
    "Ты должен понять что хочет пользователь и вернуть ТОЛЬКО JSON.\n\n"
    "ЕСЛИ ЭТО КОМАНДА УПРАВЛЕНИЯ — верни:\n"
    '{"action": "ТИП", "params": {...}}\n\n'
    "Доступные action:\n"
    "- create_key: {\"custom_key\":\"...\", \"prefix\":\"TIGRAN-MDZ-PROXY\", \"limit\":1, \"days\":7}\n"
    "- revoke_key: {\"key\":\"...\"}\n"
    "- list_keys: {}\n"
    "- list_sessions: {}\n"
    "- list_admins: {}\n"
    "- add_admin: {\"id\":\"123456789\", \"role\":\"admin|superadmin\"}\n"
    "- del_admin: {\"id\":\"123456789\"}\n"
    "- set_role: {\"id\":\"123456789\", \"role\":\"admin|superadmin\"}\n"
    "- set_language: {\"lang\":\"ru|en|vi|hy|...\"}\n"
    "- stats: {}\n"
    "- backup: {}\n"
    "ЕСЛИ ЭТО ВОПРОС / РАЗГОВОР / ПЕРЕВОД — верни:\n"
    '{"action": "chat", "params": {"question": "текст вопроса"}}\n\n'
    "ПРИМЕРЫ:\n"
    "'создай ключ на 30 дней' → {\"action\":\"create_key\",\"params\":{\"limit\":5,\"days\":30}}\n"
    "'удали ключ ABC-123' → {\"action\":\"revoke_key\",\"params\":{\"key\":\"ABC-123\"}}\n"
    "'сколько ключей?' → {\"action\":\"stats\",\"params\":{}}\n"
    "'поменяй язык на армянский' → {\"action\":\"set_language\",\"params\":{\"lang\":\"hy\"}}\n"
    "'привет как дела?' → {\"action\":\"chat\",\"params\":{\"question\":\"привет как дела?\"}}\n"
    "'переведи: я люблю кофе' → {\"action\":\"chat\",\"params\":{\"question\":\"переведи: я люблю кофе\"}}\n"
    "ВАЖНО: если сомневаешься — выбирай 'chat'.\n"
    "Верни ТОЛЬКО JSON.\n"
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
                tg_send(chat_id, f"⚠️ Key exists: <code>{new_key}</code>")
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
        tg_send(chat_id, f"🤖 <b>AI created key</b>\n\n<code>{new_key}</code>\n\nLimit: {limit} IP\nDays: {days}")
        return True
    if act == 'revoke_key':
        key = normalize_key(params.get('key', ''))
        if key in generated_keys:
            for ip in generated_keys[key]['used_ips']:
                registered_ips.pop(ip, None); key_expiry.pop(ip, None)
            del generated_keys[key]; save_data()
            tg_log("ai_revoke", chat_id, key)
            tg_send(chat_id, f"🤖 <b>AI deleted:</b>\n<code>{key}</code>")
        else:
            tg_send(chat_id, f"🤖 Key <code>{key}</code> not found.")
        return True
    if act == 'list_keys':
        if not generated_keys:
            tg_send(chat_id, "🤖 No keys.")
            return True
        lines = ["🤖 <b>Keys:</b>\n"]
        for k, v in list(generated_keys.items())[:30]:
            lines.append(f"<code>{k}</code> — {len(v['used_ips'])}/{v['limit']} · {v['days']}d")
        tg_send(chat_id, "\n".join(lines))
        return True
    if act == 'list_sessions':
        if not registered_ips:
            tg_send(chat_id, "🤖 No sessions.")
            return True
        lines = ["🤖 <b>Sessions:</b>\n"]
        for ip, key in list(registered_ips.items())[:30]:
            exp = key_expiry.get(ip)
            exp_str = exp.strftime('%d/%m/%Y') if exp else '-'
            lines.append(f"<code>{ip}</code> — {key} · {exp_str}")
        tg_send(chat_id, "\n".join(lines))
        return True
    if act == 'list_admins':
        data = load_admins_data()
        admins = data.get('admins', [])
        lines = [f"🤖 👑 <b>Owner:</b> <code>{TELEGRAM_ADMIN_ID}</code>\n"]
        if admins:
            lines.append(f"⭐🎖 <b>Admins ({len(admins)}):</b>")
            for a in admins:
                em = role_emoji(a.get('role', 'admin'))
                lines.append(f"{em} <code>{a.get('id')}</code> [{a.get('role','admin')}]")
        tg_send(chat_id, "\n".join(lines))
        return True
    if act == 'add_admin':
        new_id = str(params.get('id', '')).strip()
        new_role = (params.get('role') or 'admin').lower()
        if not new_id.isdigit():
            tg_send(chat_id, "🤖 ID must be numeric.")
            return True
        if new_role not in ('admin', 'superadmin'):
            new_role = 'admin'
        if new_id == str(TELEGRAM_ADMIN_ID):
            tg_send(chat_id, "🤖 Already owner.")
            return True
        data = load_admins_data()
        if any(str(a.get('id')) == new_id for a in data['admins']):
            tg_send(chat_id, f"🤖 <code>{new_id}</code> already admin.")
            return True
        data['admins'].append({
            "id": new_id, "name": "", "role": new_role,
            "added_by": str(chat_id), "added_at": datetime.now().isoformat()
        })
        save_admins_data(data)
        tg_log("ai_addadmin", chat_id, f"{new_id}:{new_role}")
        em = role_emoji(new_role)
        tg_send(chat_id, f"🤖 ✅ {em} Added <code>{new_id}</code> [{new_role}]")
        try: tg_send(new_id, f"{em} You are now ({new_role})!\nWrite /help")
        except: pass
        return True
    if act == 'del_admin':
        del_id = str(params.get('id', '')).strip()
        data = load_admins_data()
        if not any(str(a.get('id')) == del_id for a in data['admins']):
            tg_send(chat_id, f"🤖 <code>{del_id}</code> not found.")
            return True
        data['admins'] = [a for a in data['admins'] if str(a.get('id')) != del_id]
        save_admins_data(data)
        tg_log("ai_deladmin", chat_id, del_id)
        tg_send(chat_id, f"🤖 🗑 Removed <code>{del_id}</code>")
        return True
    if act == 'set_role':
        tgt_id = str(params.get('id', '')).strip()
        new_role = (params.get('role') or '').lower()
        if new_role not in ('admin', 'superadmin'):
            tg_send(chat_id, "🤖 Role: admin or superadmin.")
            return True
        data = load_admins_data()
        found = False
        for a in data['admins']:
            if str(a.get('id')) == tgt_id:
                a['role'] = new_role; found = True; break
        if not found:
            tg_send(chat_id, f"🤖 <code>{tgt_id}</code> not found.")
            return True
        save_admins_data(data)
        tg_send(chat_id, f"🤖 ✅ <code>{tgt_id}</code> → {role_emoji(new_role)} {new_role}")
        return True
    if act == 'set_language':
        new_lang_code = (params.get('lang') or '').lower().strip()
        if new_lang_code in LANG_ALIASES:
            new_lang_code = LANG_ALIASES[new_lang_code]
        ok, msg = set_lang(new_lang_code)
        if ok:
            tg_send(chat_id, f"🌐 <b>{t('lang.changed')}:</b> {msg}\n\n{t('menu.choose')}")
            tg_main_menu(chat_id)
        else:
            tg_send(chat_id, f"❌ {msg}")
        return True
    if act == 'stats':
        tg_send(chat_id,
            f"🤖 <b>{t('stats.title')}</b>\n\n"
            f"{t('stats.keys')}: {len(generated_keys)}\n"
            f"{t('stats.ips')}: {len(registered_ips)}\n"
            f"{t('stats.ai')}: {sum(len(v) for v in _ai_requests.values())}\n"
            f"{t('stats.admins')}: {1 + len(load_admins_data().get('admins', []))}")
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
            tg_send(chat_id, f"🤖 Error: {e}")
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
        tg_answer_callback(cb_id, t("access.denied"), alert=True)
        return
    tg_answer_callback(cb_id, "")
    try:
        if data.startswith("setlang_"):
            if not is_main_admin(chat_id):
                tg_answer_callback(cb_id, "⛔ Only owner", alert=True)
                return
            code = data.replace("setlang_", "")
            ok, msg = set_lang(code)
            if ok:
                tg_edit_message(chat_id, msg_id,
                    f"🌐 <b>{t('lang.changed')}:</b> {msg}",
                    [[{"text": t("btn.back"), "callback_data": "menu_back"}]])
                tg_main_menu(chat_id)
            else:
                tg_edit_message(chat_id, msg_id, f"❌ {msg}",
                    [[{"text": t("btn.back"), "callback_data": "menu_back"}]])
            return

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
                tg_answer_callback(cb_id, "⛔ Only owner", alert=True); return
            tg_menu_tasks(chat_id, msg_id); return
        if data == "menu_search":
            tg_edit_message(chat_id, msg_id,
                "🔍 <b>Search key</b>\n\n<code>/find PART_OF_KEY</code>",
                [[{"text": t("btn.back"), "callback_data": "menu_back"}]])
            return
        if data == "quick_genkey":
            new_key = generate_key("TIGRAN-MDZ-PROXY")
            generated_keys[new_key] = {
                'prefix': 'TIGRAN-MDZ-PROXY', 'limit': 1, 'days': 7,
                'created': datetime.now().isoformat(), 'used_ips': []
            }
            save_data()
            tg_log("genkey_btn", chat_id, new_key)
            tg_send(chat_id, f"✅ <b>{t('keys.created')}</b>\n\n<code>{new_key}</code>\n\n1 IP · 7d")
            return
        if data == "quick_genkey_big":
            new_key = generate_key("TIGRAN-MDZ-PROXY")
            generated_keys[new_key] = {
                'prefix': 'TIGRAN-MDZ-PROXY', 'limit': 5, 'days': 30,
                'created': datetime.now().isoformat(), 'used_ips': []
            }
            save_data()
            tg_log("genkey_btn", chat_id, new_key)
            tg_send(chat_id, f"✅ <b>{t('keys.created')}</b>\n\n<code>{new_key}</code>\n\n5 IP · 30d")
            return
        if data == "quick_bulk10":
            if not is_super_or_owner(chat_id):
                tg_answer_callback(cb_id, "⛔ No rights", alert=True); return
            keys = tg_bulk_create_keys(chat_id, 10, "TIGRAN-MDZ-PROXY", 1, 7)
            lines = [f"✅ <b>10 keys created:</b>\n"]
            for k in keys:
                lines.append(f"<code>{k}</code>")
            tg_send(chat_id, "\n".join(lines))
            return
        if data == "menu_addadmin":
            if not is_super_or_owner(chat_id):
                tg_answer_callback(cb_id, "⛔ No rights", alert=True); return
            tg_send(chat_id, "<code>/addadmin 123456789 admin</code>")
            return
        if data == "menu_backup":
            if not is_main_admin(chat_id):
                tg_answer_callback(cb_id, "⛔ Only owner", alert=True); return
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
                tg_answer_callback(cb_id, "⛔ Only owner", alert=True); return
            adata = load_admins_data()
            logs = adata.get('logs', [])[-15:]
            if not logs:
                tg_edit_message(chat_id, msg_id, "No logs yet.",
                    [[{"text": t("btn.back"), "callback_data": "menu_back"}]])
                return
            lines = ["📜 <b>Recent:</b>\n"]
            for l in logs:
                t_time = l.get('at', '')[:16].replace('T', ' ')
                lines.append(f"<code>{t_time}</code> · {l.get('by')} · <b>{l.get('action')}</b> {l.get('target','')}")
            tg_edit_message(chat_id, msg_id, "\n".join(lines),
                [[{"text": t("btn.back"), "callback_data": "menu_back"}]])
            return
        if data == "menu_broadcast":
            if not is_main_admin(chat_id):
                tg_answer_callback(cb_id, "⛔ Only owner", alert=True); return
            tg_send(chat_id, "📢 <code>/broadcast Text</code>")
            return
        if data == "menu_setpass":
            if not is_main_admin(chat_id):
                tg_answer_callback(cb_id, "⛔ Only owner", alert=True); return
            tg_send(chat_id, "🔑 <code>/setpass NewPassword</code>")
            return
        if data == "menu_settings":
            if not is_main_admin(chat_id):
                tg_answer_callback(cb_id, "⛔ Only owner", alert=True); return
            settings_text = (
                f"⚙ <b>Settings</b>\n\n"
                f"🔒 Secure cookies: ON\n"
                f"🛡 Security headers: ON\n"
                f"⏱ AI rate-limit: <b>{AI_RATE_LIMIT}/h</b>\n"
                f"🔐 Max login attempts: <b>{MAX_LOGIN_ATTEMPTS}</b>\n"
                f"🌍 Trust proxy: <b>{'Yes' if TRUST_PROXY else 'No'}</b>\n"
                f"🌐 <b>{t('lang.current')}:</b> {LANG_NAMES.get(_current_lang, _current_lang)}"
            )
            tg_edit_message(chat_id, msg_id, settings_text,
                [[{"text": t("btn.back"), "callback_data": "menu_back"}]])
            return
        tg_answer_callback(cb_id, "⚠ Unknown", alert=False)
    except Exception as e:
        print(f"[TG] callback error: {e}")
        tg_send(chat_id, f"❌ Error: {e}")
        # ==================== КОМАНДЫ БОТА ====================
def tg_handle_command(chat_id, text):
    role = get_user_role(chat_id)
    if role == "guest":
        tg_send(chat_id,
            f"{t('access.denied')}\n\n"
            f"{t('access.your_id')}: <code>{chat_id}</code>\n\n"
            f"{t('access.ask_admin')}"
        )
        return

    tg_admin_register_activity(chat_id, "command")

    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower() if parts else ""
    args = parts[1].split() if len(parts) > 1 else []
    rest = parts[1] if len(parts) > 1 else ""

    if cmd in ("/start", "/help"):
        is_owner = role == "owner"
        is_super = role in ("owner", "superadmin")
        help_text = (
            f"{role_emoji(role)} <b>{t('menu.title')}</b>\n"
            f"{t('menu.role')}: <b>{t('role.' + role).upper()}</b> · ID: <code>{chat_id}</code>\n\n"
            "🔑 <b>Keys:</b>\n"
            "/genkey [prefix] [limit] [days]\n"
            "/keys · /revoke KEY · /extend KEY 30 · /qr KEY\n"
            "/bulk 10 PREFIX 1 7 · /export csv|json\n"
            "/sessions · /stats · /find PART\n\n"
            "🛠 <b>Utils:</b>\n"
            "/short · /hash · /b64enc · /b64dec\n"
            "/pass 20 · /weather · /currency\n\n"
            "🎮 <b>Fun:</b>\n"
            "/bonus · /rep · /quiz · /guess · /events\n\n"
        )
        if is_super:
            help_text += (
                "\n🎖 <b>Admins:</b>\n"
                "/admins · /addadmin ID role · /deladmin ID\n"
                "/setrole ID role · /dm ID Text · /poll Q|A|B\n"
            )
        if is_owner:
            help_text += (
                "\n👑 <b>Owner only:</b>\n"
                "/setpass PASS · /broadcast TEXT\n"
                "/backup · /logs · /report · /heatmap · /activity\n"
                "/ban IP · /unban IP\n"
                "/schedule broadcast 3600 TEXT · /tasks\n"
                "/sheets · /email · /github · /stripe · /lang\n"
            )
        help_text += "\n🤖 <b>AI:</b> write without / — AI responds\n🖼 <b>Photo:</b> send — AI describes"
        tg_send(chat_id, help_text)
        tg_main_menu(chat_id)
        return

    if cmd == "/lang":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only OWNER."); return
        buttons = []
        row = []
        for code, name in LANG_NAMES.items():
            row.append({"text": name, "callback_data": f"setlang_{code}"})
            if len(row) == 3:
                buttons.append(row); row = []
        if row: buttons.append(row)
        tg_send_buttons(chat_id,
            f"🌐 <b>{t('lang.current')}:</b> {LANG_NAMES.get(_current_lang, _current_lang)}\n\n"
            f"Choose language:",
            buttons)
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
        tg_send(chat_id, f"✅ <b>{t('keys.created')}</b>\n\n<code>{new_key}</code>\n\nLimit IP: {limit}\nDays: {days}")
        return

    if cmd == "/keys":
        if not generated_keys:
            tg_send(chat_id, t("keys.none")); return
        lines = [f"📋 <b>{t('keys.title')}:</b>\n"]
        for k, v in list(generated_keys.items())[:30]:
            lines.append(f"<code>{k}</code> — {len(v['used_ips'])}/{v['limit']} · {v['days']}d")
        tg_send(chat_id, "\n".join(lines))
        return

    if cmd == "/revoke":
        if not args: tg_send(chat_id, "/revoke KEY"); return
        key = normalize_key(args[0])
        if key in generated_keys:
            for ip in generated_keys[key]['used_ips']:
                registered_ips.pop(ip, None); key_expiry.pop(ip, None)
            del generated_keys[key]; save_data()
            tg_log("revoke", chat_id, key)
            tg_send(chat_id, f"🗑 Revoked: <code>{key}</code>")
        else:
            tg_send(chat_id, f"❌ {t('keys.not_found')}")
        return

    if cmd == "/bulk":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ No rights."); return
        if len(args) < 1:
            tg_send(chat_id, "<code>/bulk 10 PREFIX 1 7</code>")
            return
        cnt = args[0]
        pf = args[1] if len(args) > 1 else "TIGRAN-MDZ-PROXY"
        lim = args[2] if len(args) > 2 else 1
        days_ = args[3] if len(args) > 3 else 7
        keys = tg_bulk_create_keys(chat_id, cnt, pf, lim, days_)
        lines = [f"✅ <b>{len(keys)} keys created:</b>\n"]
        for k in keys[:30]:
            lines.append(f"<code>{k}</code>")
        tg_send(chat_id, "\n".join(lines))
        return

    if cmd == "/export":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ No rights."); return
        fmt = args[0].lower() if args else "csv"
        tg_send(chat_id, "📦 Preparing...")
        tg_export_keys(chat_id, fmt)
        return

    if cmd == "/extend":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ No rights."); return
        if len(args) < 2:
            tg_send(chat_id, "<code>/extend KEY 30</code>"); return
        ok, msg = tg_extend_key(args[0], args[1])
        tg_send(chat_id, f"{'✅' if ok else '❌'} {msg}")
        return

    if cmd == "/qr":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ No rights."); return
        if not args:
            tg_send(chat_id, "<code>/qr KEY</code>"); return
        tg_send(chat_id, "🔗 Generating QR...")
        tg_qr_for_key(chat_id, args[0])
        return

    if cmd == "/sessions":
        if not registered_ips:
            tg_send(chat_id, t("sessions.none")); return
        lines = [f"🌐 <b>{t('sessions.title')}:</b>\n"]
        for ip, key in list(registered_ips.items())[:30]:
            exp = key_expiry.get(ip)
            exp_str = exp.strftime('%d/%m/%Y') if exp else '-'
            lines.append(f"<code>{ip}</code> — {key} · {exp_str}")
        tg_send(chat_id, "\n".join(lines))
        return

    if cmd == "/stats":
        tg_send(chat_id,
            f"📊 <b>{t('stats.title')}</b>\n\n"
            f"{t('stats.keys')}: {len(generated_keys)}\n"
            f"{t('stats.ips')}: {len(registered_ips)}\n"
            f"{t('stats.ai')}: {sum(len(v) for v in _ai_requests.values())}\n"
            f"{t('stats.admins')}: {1 + len(load_admins_data().get('admins', []))}\n"
            f"Banned: {len(BANNED_IPS) + len(IP_BLACKLIST)}")
        return

    if cmd == "/find":
        if not args:
            tg_send(chat_id, "<code>/find PART</code>"); return
        query = normalize_key(" ".join(args))
        found = [(k, v) for k, v in generated_keys.items() if query in k]
        if not found:
            tg_send(chat_id, f"🔍 <code>{query}</code> — {t('keys.not_found')}"); return
        lines = [f"🔍 <b>Found: {len(found)}</b>\n"]
        for k, v in found[:15]:
            lines.append(f"<code>{k}</code> — {len(v['used_ips'])}/{v['limit']} · {v['days']}d")
        tg_send(chat_id, "\n".join(lines))
        return

    if cmd == "/short":
        if not args:
            tg_send(chat_id, "<code>/short URL</code>"); return
        res = tg_url_shorten(args[0])
        tg_send(chat_id, f"🔗 {res}" if res else "❌ Failed.")
        return
    if cmd == "/hash":
        if not args:
            tg_send(chat_id, "<code>/hash text</code>"); return
        if args[0].lower() in ("md5", "sha1", "sha256", "sha512"):
            algo = args[0].lower(); txt = " ".join(args[1:])
        else:
            algo = "sha256"; txt = " ".join(args)
        h = tg_hash_text(txt, algo)
        tg_send(chat_id, f"🔐 <b>{algo.upper()}:</b>\n<code>{h}</code>")
        return
    if cmd == "/b64enc":
        if not args: tg_send(chat_id, "<code>/b64enc text</code>"); return
        tg_send(chat_id, f"📦 <code>{tg_b64_encode(' '.join(args))}</code>")
        return
    if cmd == "/b64dec":
        if not args: tg_send(chat_id, "<code>/b64dec string</code>"); return
        res = tg_b64_decode(args[0])
        tg_send(chat_id, f"📦 <code>{res}</code>" if res else "❌ Invalid")
        return
    if cmd == "/pass":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ No rights."); return
        length = args[0] if args else 16
        pw = tg_password_gen(length)
        tg_send(chat_id, f"🔑 <b>Password:</b>\n<code>{pw}</code>")
        return
    if cmd == "/weather":
        if not args: tg_send(chat_id, "<code>/weather Moscow</code>"); return
        tg_send(chat_id, "🌤 Loading...")
        res = tg_weather(" ".join(args))
        tg_send(chat_id, res or "❌ Not found.")
        return
    if cmd == "/currency":
        if len(args) < 3:
            tg_send(chat_id, "<code>/currency 100 USD RUB</code>"); return
        res = tg_currency_convert(args[0], args[1].upper(), args[2].upper())
        tg_send(chat_id, res or "❌ Failed.")
        return

    if cmd == "/report":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only owner."); return
        tg_send(chat_id, "📊 Gathering...")
        tg_send_daily_report()
        return
    if cmd == "/heatmap":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ No rights."); return
        tg_send(chat_id, tg_ip_heatmap())
        return
    if cmd == "/activity":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only owner."); return
        tg_send(chat_id, tg_admins_activity_report())
        return

    if cmd == "/schedule":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only owner."); return
        if len(args) < 3:
            tg_send(chat_id, "<code>/schedule broadcast 3600 Text</code>"); return
        action = args[0]
        try: delay = int(args[1])
        except: tg_send(chat_id, "❌ Invalid seconds"); return
        text_arg = " ".join(args[2:]) if len(args) > 2 else ""
        tg_schedule_task(chat_id, delay, action, {'text': text_arg})
        tg_send(chat_id, f"⏰ Scheduled <b>{action}</b> in {delay}s.")
        return
    if cmd == "/tasks":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only owner."); return
        if not SCHEDULED_TASKS:
            tg_send(chat_id, "📭 No tasks."); return
        lines = [f"⏰ <b>Tasks ({len(SCHEDULED_TASKS)}):</b>\n"]
        for t_ in SCHEDULED_TASKS:
            left = int(t_['when'] - time.time())
            lines.append(f"• <code>{t_['id'][:12]}</code> · {t_['action']} · {left}s")
        tg_send(chat_id, "\n".join(lines))
        return

    if cmd == "/ban":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only owner."); return
        if not args:
            tg_send(chat_id, "<code>/ban 1.2.3.4 24</code>"); return
        ip = args[0]
        hours = args[1] if len(args) > 1 else 24
        msg = tg_ban_ip(ip, hours)
        tg_send(chat_id, f"🚫 {msg}")
        return
    if cmd == "/unban":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only owner."); return
        if not args:
            tg_send(chat_id, "<code>/unban 1.2.3.4</code>"); return
        msg = tg_unban_ip(args[0])
        tg_send(chat_id, f"✅ {msg}")
        return
    if cmd == "/iplookup":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ No rights."); return
        if not args:
            tg_send(chat_id, "<code>/iplookup 8.8.8.8</code>"); return
        geo = tg_get_ip_geo(args[0])
        tg_send(chat_id, f"🌍 <b>IP {args[0]}</b>\n\n{geo}" if geo else "❌ Failed.")
        return

    if cmd == "/translate":
        if not args:
            tg_send(chat_id, "<code>/translate hello world</code>"); return
        tg_send(chat_id, "🌐 Translating...")
        res = tg_ai_translate(" ".join(args))
        tg_send(chat_id, res or "❌ Failed.")
        return
    if cmd == "/image":
        if not args:
            tg_send(chat_id, "<code>/image cat in space</code>"); return
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ No rights."); return
        tg_send(chat_id, "🎨 Generating... (30-60s)")
        tg_ai_generate_image(chat_id, " ".join(args))
        return

    if cmd == "/admins":
        data = load_admins_data()
        admins = data.get('admins', [])
        lines = [f"👑 <b>Owner:</b>\n<code>{TELEGRAM_ADMIN_ID}</code>\n"]
        if admins:
            lines.append(f"⭐🎖 <b>Admins ({len(admins)}):</b>")
            for a in admins:
                em = role_emoji(a.get('role', 'admin'))
                lines.append(f"{em} <code>{a.get('id')}</code> [{a.get('role','admin')}]")
        tg_send(chat_id, "\n".join(lines))
        return
    if cmd == "/addadmin":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ No rights."); return
        if not args:
            tg_send(chat_id, "<code>/addadmin 123456789 admin</code>"); return
        new_id = str(args[0]).strip()
        new_role = args[1].lower() if len(args) > 1 else "admin"
        if not new_id.isdigit():
            tg_send(chat_id, "❌ ID must be numeric."); return
        if new_role not in ("admin", "superadmin"):
            tg_send(chat_id, "❌ Role: admin/superadmin"); return
        if new_role == "superadmin" and not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only OWNER can assign superadmin."); return
        if new_id == str(TELEGRAM_ADMIN_ID):
            tg_send(chat_id, "⚠️ Already owner."); return
        data = load_admins_data()
        if any(str(a.get('id')) == new_id for a in data['admins']):
            tg_send(chat_id, f"⚠️ <code>{new_id}</code> already."); return
        data['admins'].append({
            "id": new_id, "name": "", "role": new_role,
            "added_by": str(chat_id), "added_at": datetime.now().isoformat()
        })
        save_admins_data(data)
        tg_log("addadmin", chat_id, f"{new_id}:{new_role}")
        em = role_emoji(new_role)
        tg_send(chat_id, f"✅ {em} Added <code>{new_id}</code> [{new_role}]")
        try: tg_send(new_id, f"{em} You are now ({new_role})!\nWrite /help")
        except: pass
        return
    if cmd == "/deladmin":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ No rights."); return
        if not args:
            tg_send(chat_id, "/deladmin 123456789"); return
        del_id = str(args[0]).strip()
        data = load_admins_data()
        target = [a for a in data['admins'] if str(a.get('id')) == del_id]
        if not target:
            tg_send(chat_id, f"❌ <code>{del_id}</code> not found."); return
        if target[0].get('role') == "superadmin" and not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only OWNER can remove superadmin."); return
        data['admins'] = [a for a in data['admins'] if str(a.get('id')) != del_id]
        save_admins_data(data)
        tg_log("deladmin", chat_id, del_id)
        tg_send(chat_id, f"🗑 Removed: <code>{del_id}</code>")
        return
    if cmd == "/setrole":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ No rights."); return
        if len(args) < 2:
            tg_send(chat_id, "/setrole ID role"); return
        tgt_id, new_role = str(args[0]).strip(), args[1].lower()
        if new_role not in ("admin", "superadmin"):
            tg_send(chat_id, "❌ Role: admin/superadmin"); return
        if new_role == "superadmin" and not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only OWNER can give superadmin."); return
        data = load_admins_data()
        found = False
        for a in data['admins']:
            if str(a.get('id')) == tgt_id:
                a['role'] = new_role; found = True; break
        if not found:
            tg_send(chat_id, "❌ Not found."); return
        save_admins_data(data)
        tg_log("setrole", chat_id, f"{tgt_id}:{new_role}")
        tg_send(chat_id, f"✅ <code>{tgt_id}</code> → {role_emoji(new_role)} {new_role}")
        return
    if cmd == "/dm":
        if get_user_role(chat_id) == "guest":
            tg_send(chat_id, "⛔ No rights."); return
        if len(args) < 2:
            tg_send(chat_id, "<code>/dm 123456789 Text</code>"); return
        to_id = args[0]
        text_msg = " ".join(args[1:])
        res = tg_admin_dm(chat_id, to_id, text_msg)
        tg_send(chat_id, res)
        return
    if cmd == "/poll":
        if not is_super_or_owner(chat_id):
            tg_send(chat_id, "⛔ No rights."); return
        raw = " ".join(args)
        if "|" not in raw:
            tg_send(chat_id, "<code>/poll Q|A|B|C</code>"); return
        parts_p = [p.strip() for p in raw.split("|") if p.strip()]
        if len(parts_p) < 3:
            tg_send(chat_id, "❌ Min 3 parts"); return
        tg_poll_create(chat_id, parts_p[0], parts_p[1:])
        return

    if cmd == "/bonus":
        tg_send(chat_id, tg_daily_bonus(chat_id))
        return
    if cmd == "/rep":
        cid = str(chat_id)
        tg_send(chat_id, f"⭐ Rep: <b>{USER_REPUTATION.get(cid, 0)}</b>")
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
    if cmd == "/clear":
        _ai_memory[chat_id] = []
        tg_send(chat_id, "🧹 История AI очищена. Начнём заново!")
        return


    if cmd == "/sheets":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only owner."); return
        ok, msg = tg_google_sheets_sync()
        tg_send(chat_id, f"{'✅' if ok else '❌'} {msg}")
        return
    if cmd == "/email":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only owner."); return
        if len(args) < 2:
            tg_send(chat_id, "<code>/email a@b.com Subject|Body</code>"); return
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
            tg_send(chat_id, "<code>/youtube URL</code>"); return
        res = tg_send_youtube_info(args[0])
        tg_send(chat_id, res or "❌ Not found.")
        return
    if cmd == "/github":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only owner."); return
        res = tg_github_status()
        tg_send(chat_id, res or "❌ GITHUB_REPO not set.")
        return
    if cmd == "/stripe":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only owner."); return
        if not args:
            tg_send(chat_id, "<code>/stripe 10</code>"); return
        try: amt = float(args[0])
        except: tg_send(chat_id, "❌ Invalid amount"); return
        link = tg_stripe_payment_link(amt)
        tg_send(chat_id, f"💳 {link}" if link else "❌ Stripe not configured.")
        return

    if cmd == "/setpass":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only OWNER."); return
        if not rest.strip():
            tg_send(chat_id, "<code>/setpass NewPassword</code>"); return
        global ADMIN_PASS_HASH
        try:
            new_hash = generate_password_hash(rest.strip())
            set_admin_pass_hash(new_hash)
            ADMIN_PASS_HASH = new_hash
            tg_log("setpass", chat_id, "")
            tg_send(chat_id, "✅ <b>Password changed!</b>")
        except Exception as e:
            tg_send(chat_id, f"❌ {e}")
        return
    if cmd == "/broadcast":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only OWNER."); return
        if not rest.strip():
            tg_send(chat_id, "/broadcast Text"); return
        data = load_admins_data()
        ok = 0
        for a in data.get('admins', []):
            try: tg_send(a['id'], f"📢 <b>Broadcast:</b>\n\n{rest}"); ok += 1
            except: pass
        tg_send(chat_id, f"✅ Sent to {ok} admins.")
        return
    if cmd == "/backup":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only OWNER."); return
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
            tg_send(chat_id, f"🤖 Error: {e}")
        return
    if cmd == "/logs":
        if not is_main_admin(chat_id):
            tg_send(chat_id, "⛔ Only OWNER.")
            return

        data = load_admins_data()
        logs = data.get('logs', [])[-15:]

        if not logs:
            tg_send(chat_id, "No logs.")
            return

        lines = ["📜 <b>Recent:</b>\n"]

        for l in logs:
            t_time = l.get('at', '')[:16].replace('T', ' ')
            lines.append(
                f"<code>{t_time}</code> · {l.get('by')} · "
                f"<b>{l.get('action')}</b> {l.get('target', '')}"
            )

        tg_send(chat_id, "\n".join(lines))
        return

    if cmd == "/tigranaitoolstutorial" or text.strip().lower() == "tigranaitoolstutorial":
        tg_send(chat_id, "🔓 <b>СЕКРЕТНЫЙ КОД ПРИНЯТ!</b>")

        tutorial_text = (
            "<b>📘 TIGRAN AI TOOLS</b>\n\n"
            "<b>1. Combiloader</b>\n"
            "• https://almisoft.ru/\n"
            "• https://almisoft.ru/ctpro.htm\n\n"

            "<b>2. PCMflash</b>\n"
            "• https://pcmflash.ru/\n"
            "• https://pcmflash.ru/legal/\n\n"

            "<b>3. WinOLS</b>\n"
            "• https://www.evc.de/\n"
            "• https://www.evc.de/en/download/down_winols.asp\n\n"

            "<b>4. ECM Titanium</b>\n"
            "• https://www.alientech-tools.com/\n"
            "• https://alientech-usa.com/collections/ecm-titanium-software/products/ecm-titanium\n\n"

            "<b>5. KESS v2 / KTAG</b>\n"
            "• https://www.alientech-tools.com/\n"
            "• https://www.alientech-tools.com/it/tag/kessv2-es/\n"
            "• https://www.alientech-tools.com/it/tag/k-tag-it-2/\n\n"

            "<b>6. MPPS</b>\n"
            "• https://amtcartech.com/\n"
            "• https://amtcartech.com/faqs/\n\n"

            "<b>7. Galletto 1260</b>\n"
            "• ищи на профильных форумах\n\n"

            "<b>8. WinFlashEcu</b>\n"
            "• https://nts-diagnostika.ru/\n"
            "• https://nts-diagnostika.ru/index.php?mod=pb_dwl\n\n"

            "<b>9. Scanmatik</b>\n"
            "• http://www.scanmatik.ru/\n"
        )

        tg_send(chat_id, tutorial_text)
        return

    if cmd.startswith("/"):
        tg_send(chat_id, "❓ Unknown. /help")
        return


    if not OPENAI_API_KEY:
        tg_send(chat_id, "🤖 AI not configured.")
        return

    user_msg = text.strip()
    if not user_msg:
        return

    if role in ("owner", "superadmin"):
        action_data = tg_owner_ai_agent(chat_id, user_msg)
        if action_data:
            act = action_data.get('action', 'chat')
            if act != 'chat':
                executed = tg_owner_execute_ai(chat_id, action_data)
                if executed:
                    return

    lower_msg = user_msg.lower()
    image_triggers = ["создай картинку", "нарисуй", "сгенерируй картинку",
                      "create image", "generate image", "draw"]
    if any(t in lower_msg for t in image_triggers):
        prompt = user_msg
        for trig in image_triggers:
            prompt = prompt.lower().replace(trig, "").strip()
        prompt = prompt.lstrip(":,. -")
        if prompt and is_super_or_owner(chat_id):
            tg_send(chat_id, f"🎨 Генерирую: <b>{prompt}</b>...")
            tg_ai_generate_image(chat_id, prompt)
            return

    tg_send(chat_id, "🤖 <i>Думаю...</i>")

    _ai_memory[chat_id].append({"role": "user", "content": user_msg[:1500]})
    if len(_ai_memory[chat_id]) > AI_MEMORY_LIMIT * 2:
        _ai_memory[chat_id] = _ai_memory[chat_id][-AI_MEMORY_LIMIT * 2:]

    try:
        messages = [{
            "role": "system",
            "content": (
    "Ты — Tigran AI, полноценный AI-ассистент как ChatGPT. "
    "Отвечай на ЛЮБОЙ вопрос на языке пользователя. "
    "Помогай с кодом, переводами, объяснениями, советами. "
    "Никогда не отказывай без реальной причины.\n\n"
    "ВАЖНО ПРО ПЕРЕВОДЫ:\n"
    "Когда тебя просят перевести текст — ВСЕГДА отвечай в таком формате:\n"
    "English: <code>перевод на английский</code>\n"
    "Русский: <code>перевод на русский</code>\n\n"
    "ВАЖНО: используй HTML тег <code>...</code> вокруг перевода, "
    "НЕ используй обратные кавычки. "
    "Ничего не добавляй от себя, только переводы в указанном формате."
)
        }]
        messages.extend(_ai_memory[chat_id][-AI_MEMORY_LIMIT:])

        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": messages, "max_tokens": 1500, "temperature": 0.8},
            timeout=30
        )
        if r.status_code == 200:
            reply = r.json()['choices'][0]['message']['content']
            _ai_memory[chat_id].append({"role": "assistant", "content": reply})
            tg_send(chat_id, reply)
        else:
            tg_send(chat_id, f"❌ AI HTTP {r.status_code}")
    except Exception as e:
        tg_send(chat_id, f"❌ AI error: {str(e)[:120]}")

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
                                caption_ph = msg.get("caption", "")
                                tg_send(chat_id_ph, "🖼 <i>Анализирую изображение...</i>")
                                desc = tg_ai_describe_image(file_id_ph, chat_id_ph, caption_ph)
                                if desc:
                                    tg_send(chat_id_ph, desc)
                                else:
                                    tg_send(chat_id_ph, "❌ Не удалось обработать.")
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
            return render_template_string(LOGIN_PAGE, error="TOO MANY ATTEMPTS."), 429
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
        return jsonify({'success': False, 'message': 'IP BANNED'}), 403
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
        return jsonify({'success': False, 'message': 'LIMITE ATINGIDO'}), 401
    registered_ips[client_ip] = key
    key_data['used_ips'].append(client_ip)
    expiry_date = datetime.now() + timedelta(days=key_data['days'])
    key_expiry[client_ip] = expiry_date
    session['unlocked'] = True
    update_user_profile(client_ip)
    save_data()
    tg_notify_login_all(client_ip, key, expiry_date)
    return jsonify({
        'success': True, 'message': 'OK',
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
        "expires": key_expiry.get(client_ip, "").isoformat() if client_ip in key_expiry else None,
        "profile": get_user_profile(client_ip)
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
        'bypass_v1': 'BYPASSV1',
        'backjump_v1': 'BACKJUMPV1',
        'high_sensi': 'HIGH_SENSI',
        'zig_zag_move': 'ZIG_ZAG_MOVE',
        'speed_run': 'SPEED_RUN',
        'high_jump': 'HIGH_JUMP',
        'hp_ap_max': 'HP_AP_MAX',
        'loot_master': 'LOOT_MASTER',
        'aim_pro': 'AIM_PRO',
        'headshot_pro': 'HEADSHOT_PRO',
        'esp_radar': 'ESP_RADAR',
        'bypass_pro': 'BYPASS_PRO',
        'full_bright_pro': 'FULL_BRIGHT_PRO',
        'mega_radar': 'MEGA_RADAR',
        'hint_master': 'HINT_MASTER',
        'loud_enemy': 'LOUD_ENEMY',
        'quiet_self': 'QUIET_SELF',
        'instant_use': 'INSTANT_USE',
        'loot_mega': 'LOOT_MEGA',
        'wide_fov': 'WIDE_FOV',
        'no_camera_shake': 'NO_CAMERA_SHAKE',
        'hud_names_pro': 'HUD_NAMES_PRO',
        'sprint_combo': 'SPRINT_COMBO',
        'swim_pro': 'SWIM_PRO',
        'fly_glide_pro': 'FLY_GLIDE_PRO',
        'fast_switch_pro': 'FAST_SWITCH_PRO',
        'anim_speed_pro': 'ANIM_SPEED_PRO',
        'no_recoil_pro': 'NO_RECOIL_PRO',
        'vehicle_pro_v3': 'VEHICLE_PRO_V3',
        'ballistic_pro': 'BALLISTIC_PRO',
        'emote_master': 'EMOTE_MASTER',
        'silent_self': 'SILENT_SELF',
        'aware_enemy': 'AWARE_ENEMY',
        'uav_super': 'UAV_SUPER',
        'spectator_pro': 'SPECTATOR_PRO',
        'jumppad_god': 'JUMPPAD_GOD',
        'glider_pro': 'GLIDER_PRO',
        'photo_mode_pro': 'PHOTO_MODE_PRO',
        'auto_aim_pro': 'AUTO_AIM_PRO',
        'vehicle_god': 'VEHICLE_GOD',
        'hit_show_pro': 'HIT_SHOW_PRO',
        'multi_ping_pro': 'MULTI_PING_PRO',
        'movement_master_pro': 'MOVEMENT_MASTER_PRO',
        'replay_pro': 'REPLAY_PRO',
        'view_distance_pro': 'VIEW_DISTANCE_PRO',
        'ui_audio_pro': 'UI_AUDIO_PRO',
        'hitmarker_pro': 'HITMARKER_PRO',
        'map_marker_pro': 'MAP_MARKER_PRO',
        'full_visual_pro': 'FULL_VISUAL_PRO',
        'fast_ui_pro': 'FAST_UI_PRO',
        'gameplay_extra': 'GAMEPLAY_EXTRA',
    }
    config_key = feature_map.get(feature)
    if not config_key:
        return jsonify({"error": "RECURSO INVÁLIDO"}), 400
    config = get_user_config(client_ip)
    config[config_key] = value
    save_data()
    return jsonify({"success": True, "ip": client_ip, "feature": feature, "value": value})
@app.route('/api/toggle_all', methods=['POST'])
def api_toggle_all():
    """Массовое включение/выключение всех модулей"""
    client_ip = get_client_ip()
    data = request.json or {}
    value = bool(data.get('value', False))
    config = get_user_config(client_ip)
    for k in DEFAULT_CONFIG.keys():
        config[k] = value
    save_data()
    return jsonify({"success": True, "count": len(DEFAULT_CONFIG), "value": value})


@app.route('/api/preset/save', methods=['POST'])
def api_preset_save():
    client_ip = get_client_ip()
    data = request.json or {}
    name = str(data.get('name', 'default')).strip()[:32]
    if not name:
        return jsonify({"error": "invalid name"}), 400
    config = get_user_config(client_ip)
    save_preset(client_ip, name, dict(config))
    return jsonify({"success": True, "name": name})


@app.route('/api/preset/load', methods=['POST'])
def api_preset_load():
    client_ip = get_client_ip()
    data = request.json or {}
    name = str(data.get('name', '')).strip()
    ok = apply_preset(client_ip, name)
    if ok:
        return jsonify({"success": True, "config": get_user_config(client_ip)})
    return jsonify({"error": "preset not found"}), 404


@app.route('/api/preset/list', methods=['GET'])
def api_preset_list():
    client_ip = get_client_ip()
    profile = get_user_profile(client_ip)
    return jsonify({"presets": list(profile.get("presets", {}).keys())})


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
        return jsonify({'error': 'AI limit exceeded.'}), 429
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
                "You are Tigran AI — full-featured AI assistant like ChatGPT. "
                "Answer ANY question. Detect language and reply in same language."
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
        return jsonify({'error': f'AI error: {str(e)[:120]}'}), 500


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
    const p=document.createElement('div');p.id='aiPanel';p.innerHTML='<div id="aiHead"><span>◉ AI ASSISTANT</span><span style="cursor:pointer" id="aiX">✕</span></div><div id="aiLog"><div class="m a">Hello! I am AI assistant.</div></div><form id="aiForm"><input id="aiInput" placeholder="Ask..." autocomplete="off"><button id="aiSend" type="submit">▶</button></form>';
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
        else{log.insertAdjacentHTML('beforeend','<div class="m a" style="color:#ff8e8e"></div>');log.lastChild.textContent='⚠ '+(d.error||'Error');playError()}
      }catch(err){log.lastChild.remove();log.insertAdjacentHTML('beforeend','<div class="m a" style="color:#ff8e8e">⚠ Failed</div>');playError()}
      log.scrollTop=log.scrollHeight;
    };
  }
})();
"""


# ==================== HTML PAGES ====================
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
.error{margin-top:14px;color:#ff8e8e;font:700 11px monospace}
.foot{margin-top:30px;color:#6b5a70;font:10px monospace}
@media(max-width:780px){.login-shell{grid-template-columns:1fr}.manifest{padding:32px 22px;min-height:240px}.manifest h1{font-size:38px}.form-panel{padding:32px 22px}}
</style></head><body>
<canvas id="neonBg"></canvas><div id="neonCursor"></div><button id="muteBtn">🔊</button>
<div class="wrap"><main class="login-shell glass fade-in">
<section class="manifest"><div><div class="mark"><i class="fa-solid fa-bolt"></i> TIGRAN MODZ PROXY</div><div class="scan"></div><div style="margin-top:60px" class="label">PRIVATE CONTROL SYSTEM</div><h1>Enter the <span class="neon-text">operator</span> console.</h1><p>Admin area.</p></div><div style="font:11px monospace;color:#7a6578">NODE / 07 · AUTH REQUIRED</div></section>
<section class="form-panel"><div class="label">ADMIN AUTHENTICATION</div><h2>Login</h2><p class="sub">Enter credentials.</p>
<form method="POST"><div class="field"><label for="u">Username</label><input id="u" name="username" required></div><div class="field"><label for="p">Password</label><input id="p" type="password" name="password" required></div><button class="glow-btn" type="submit">Login <i class="fa-solid fa-arrow-right"></i></button>{% if error %}<div class="error">{{ error }}</div>{% endif %}</form>
<div class="foot"><i class="fa-solid fa-shield-halved"></i> PROTECTED SESSION</div></section>
</main></div>
<script>""" + NEON_JS + """</script></body></html>"""

KEY_PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TIGRAN MODZ · ACCESS</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>""" + NEON_CSS + """
.access{width:min(1000px,100%);display:grid;grid-template-columns:1.05fr .95fr;min-height:620px}
.visual{padding:48px;display:flex;flex-direction:column;justify-content:space-between}
.brand{font-weight:900;letter-spacing:3px;font-size:18px}
.brand b{color:var(--p1)}
.visual h1{font-size:60px;line-height:.9;letter-spacing:-4px;margin:20px 0 0;max-width:400px}
.visual p{color:var(--muted);line-height:1.7;max-width:340px;margin-top:16px;font-size:14px}
.info-strip{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:24px}
.info-card{background:rgba(10,5,20,.6);border:1px solid var(--line);border-radius:12px;padding:11px 12px;font:11px monospace}
.info-card small{display:block;color:var(--muted);font-size:9px;margin-bottom:5px}
.info-card b{color:var(--p3);font-size:13px}
.access-form{padding:48px 42px;display:flex;flex-direction:column;justify-content:center}
.access-form h2{font-size:30px;margin:12px 0 6px}
#keyError{color:#ff8e8e;margin-top:14px;font:700 11px monospace}
@media(max-width:780px){.access{grid-template-columns:1fr}.visual{padding:28px 20px}.visual h1{font-size:38px}.access-form{padding:28px 20px}}
</style></head><body>
<canvas id="neonBg"></canvas><div id="neonCursor"></div><button id="muteBtn">🔊</button>
<div class="wrap"><main class="access glass fade-in">
<section class="visual"><div><div class="brand"><i class="fa-solid fa-key"></i> TIGRAN MODZ <b>PROXY</b></div><div class="scan"></div><div style="margin-top:40px" class="label">ACCESS GATE</div><h1>One key. <span class="neon-text">Full access.</span></h1><p>Use admin-issued key.</p></div>
<div class="info-strip">
<div class="info-card"><small>Country</small><b id="uCountry">—</b></div>
<div class="info-card"><small>City</small><b id="uCity">—</b></div>
<div class="info-card"><small>Time</small><b id="uTime">--:--:--</b></div>
<div class="info-card"><small>Weather</small><b id="uWeather">—</b></div>
</div></section>
<section class="access-form"><div class="label">USER ACCESS</div><h2>Validate</h2><p class="sub">Paste your key.</p>
<form id="keyForm"><div class="field"><label for="k">Access key</label><input id="k" required placeholder="TIGRAN-MDZ-PROXY-0000"></div><button class="glow-btn" type="submit">Open dashboard</button><div id="keyError"></div></form>
</section>
</main></div>
<script>""" + NEON_JS + """
fetch('/api/user/info').then(r=>r.json()).then(d=>{
  document.getElementById('uCountry').textContent=(d.country||'—')+(d.country_code?' ('+d.country_code+')':'');
  document.getElementById('uCity').textContent=d.city||'—';
  if(d.timezone){function tick(){try{document.getElementById('uTime').textContent=new Date().toLocaleTimeString('ru-RU',{timeZone:d.timezone,hour12:false})}catch(e){}}tick();setInterval(tick,1000)}
  if(d.weather){document.getElementById('uWeather').textContent=(d.weather.temp||'?')+'°C · '+(d.weather.desc||'')}
}).catch(()=>{});
document.getElementById('keyForm').addEventListener('submit',async e=>{
  e.preventDefault();const b=e.target.querySelector('button'),m=document.getElementById('keyError');
  b.disabled=true;m.textContent='VALIDATING...';
  try{
    const r=await fetch('/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:document.getElementById('k').value.trim()})});
    const d=await r.json();if(!r.ok||!d.success)throw Error(d.message||'INVALID KEY');
    playSuccess();m.style.color='#22d3ee';m.textContent='✓ ACCESS GRANTED';
    setTimeout(()=>location.href='/dashboard',700);
  }catch(err){m.style.color='#ff8e8e';m.textContent=err.message;playError();b.disabled=false}
});
</script></body></html>"""

ADMIN_DASHBOARD = """<!doctype html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TIGRAN MODZ · ADMIN</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>""" + NEON_CSS + """
.admin{min-height:100vh;display:grid;grid-template-columns:240px 1fr;position:relative;z-index:2}
.nav{padding:26px 18px;background:rgba(10,5,20,.7);border-right:1px solid var(--line);display:flex;flex-direction:column}
.brand{font-weight:900;letter-spacing:2px;font-size:15px}
.brand span{color:var(--p1)}
.nav-links{margin-top:40px;display:grid;gap:6px}
.nav-links a{padding:12px 14px;color:var(--muted);text-decoration:none;font:700 10px monospace;text-transform:uppercase;border-radius:12px;cursor:none}
.nav-links a:hover,.nav-links a.active{background:linear-gradient(90deg,rgba(255,45,149,.15),transparent);border:1px solid rgba(255,45,149,.35);color:#fff}
.logout{display:block;margin-top:auto;padding:12px 14px;color:#ff9a9a;text-decoration:none;font:700 10px monospace;border-radius:12px;border:1px solid rgba(255,100,100,.25);text-align:center;cursor:none}
.workspace{padding:32px 40px;max-width:1300px;width:100%}
.bar{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:26px;flex-wrap:wrap;gap:14px}
.bar h1{font-size:38px;margin:8px 0 0}
.eyebrow{font:700 10px monospace;color:var(--p3)}
.profile{font:11px monospace;padding:8px 14px;border-radius:999px;background:rgba(34,211,238,.1);border:1px solid rgba(34,211,238,.3)}
.cards{display:grid;grid-template-columns:1.2fr .8fr;gap:16px;margin-top:24px}
.card{background:rgba(20,10,30,.55);border:1px solid var(--line);border-radius:18px;padding:22px}
.card h2{font-size:13px;letter-spacing:1px;text-transform:uppercase;color:var(--p3)}
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
.generated{margin-top:14px;padding:12px;border-radius:10px;background:rgba(34,211,238,.08);border:1px solid rgba(34,211,238,.3);color:#8ff0ff;font:800 15px monospace}
@media(max-width:820px){.admin{grid-template-columns:1fr}.workspace{padding:20px 14px}.cards{grid-template-columns:1fr}}
</style></head><body data-ai="1">
<canvas id="neonBg"></canvas><div id="neonCursor"></div><button id="muteBtn">🔊</button>
<main class="admin">
<aside class="nav">
<div class="brand"><i class="fa-solid fa-bolt"></i> TIGRAN MODZ <span>PROXY</span></div>
<div class="nav-links"><a class="active" href="/admin/dashboard">Overview</a><a href="#keys">Keys</a><a href="#ips">Sessions</a></div>
<a class="logout" href="/admin/logout">Logout</a>
</aside>
<section class="workspace">
<header class="bar fade-in"><div><div class="eyebrow">ADMIN CONTROL</div><h1 class="neon-text">Operations</h1></div><div class="profile">● ONLINE</div></header>
<div class="cards fade-in">
<section class="card"><h2>New key</h2>
<div class="field"><label>Prefix</label><input id="keyPrefix" value="TIGRAN-MDZ-PROXY"></div>
<div class="field"><label>IP limit</label><input id="ipLimit" type="number" value="1" min="1"></div>
<div class="field"><label>Days</label><input id="keyDays" type="number" value="7" min="1"></div>
<button class="glow-btn" style="width:100%" onclick="generateKey()">Generate</button>
<div id="generatedKey" class="generated" style="display:none"></div>
</section>
<section class="card"><h2>Summary</h2>
<div class="stats"><div class="stat"><small>TOTAL KEYS</small><strong>{{ keys|length }}</strong></div><div class="stat"><small>ACTIVE IPS</small><strong>{{ ips|length }}</strong></div></div>
</section></div>
<section class="card wide fade-in"><h2>Keys</h2><table><thead><tr><th>KEY</th><th>LIMIT</th><th>USES</th><th>DAYS</th><th>ACTION</th></tr></thead><tbody>{% for key, data in keys.items() %}<tr><td><span class="badge">{{ key }}</span></td><td>{{ data.limit }}</td><td>{{ data.used_ips|length }}</td><td>{{ data.days }}</td><td><button class="danger" onclick="revokeKey('{{ key }}')">REVOKE</button></td></tr>{% else %}<tr><td colspan="5">No keys.</td></tr>{% endfor %}</tbody></table></section>
<section class="card wide fade-in"><h2>Sessions</h2><table><thead><tr><th>IP</th><th>KEY</th><th>EXPIRES</th><th>STATUS</th></tr></thead><tbody>{% for ip, key in ips.items() %}<tr><td>{{ ip }}</td><td><span class="badge">{{ key }}</span></td><td>{% if key_expiry[ip] %}{{ key_expiry[ip].strftime('%d/%m/%Y') }}{% else %}-{% endif %}</td><td>● ACTIVE</td></tr>{% else %}<tr><td colspan="4">No sessions.</td></tr>{% endfor %}</tbody></table></section>
</section></main>
<script>""" + NEON_JS + """
async function generateKey(){const o=document.getElementById('generatedKey');o.style.display='block';o.textContent='...';try{const r=await fetch('/admin/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prefix:document.getElementById('keyPrefix').value.trim()||'TIGRAN-MDZ-PROXY',limit:Math.max(1,parseInt(document.getElementById('ipLimit').value)||1),days:Math.max(1,parseInt(document.getElementById('keyDays').value)||7)})});const d=await r.json();if(!r.ok||!d.key)throw Error(d.error||'Err');o.textContent='✓ '+d.key;playSuccess();setTimeout(()=>location.reload(),1400)}catch(e){o.textContent='ERROR: '+e.message;playError()}}
async function revokeKey(key){if(!confirm('Revoke '+key+'?'))return;const r=await fetch('/admin/revoke',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})});const d=await r.json();if(d.success){playSuccess();location.reload()}else{alert(d.error||'Err');playError()}}
</script></body></html>"""

# ==================== DASHBOARD_PAGE — расширенный со всеми 30+ модулями ====================
DASHBOARD_PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TIGRAN MODZ · DASHBOARD</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>""" + NEON_CSS + """
.app{min-height:100vh;display:grid;grid-template-columns:240px 1fr;position:relative;z-index:2}
.side{padding:26px 18px;background:rgba(10,5,20,.7);border-right:1px solid var(--line);display:flex;flex-direction:column}
.brand{font-weight:900;letter-spacing:2px;font-size:15px}
.brand span{color:var(--p1)}
.side nav{margin-top:40px;display:grid;gap:6px}
.side nav div{padding:12px 14px;color:var(--muted);font:700 10px monospace;text-transform:uppercase;border-radius:12px;cursor:none}
.side nav div.active{background:linear-gradient(90deg,rgba(255,45,149,.18),transparent);border:1px solid rgba(255,45,149,.4);color:#fff}
.side-foot{margin-top:auto;color:#6b5a70;font:10px monospace}
.main{padding:32px 40px;max-width:1250px;width:100%}
.top{display:flex;justify-content:space-between;padding-bottom:26px;border-bottom:1px solid var(--line);flex-wrap:wrap;gap:14px}
.top h1{margin:8px 0 0;font-size:36px}
.eyebrow{font:700 10px monospace;color:var(--p3)}
.status{display:flex;gap:8px;align-items:center;color:#ff7ec0;font:700 10px monospace;padding:8px 14px;border-radius:999px;background:rgba(255,45,149,.1);border:1px solid rgba(255,45,149,.3)}
.dot{width:8px;height:8px;background:var(--p1);border-radius:50%}
.info-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:26px 0}
.info-card{background:rgba(20,10,30,.6);border:1px solid var(--line);border-radius:14px;padding:14px}
.info-card i{color:var(--p3);font-size:14px}
.info-card small{display:block;color:var(--muted);font:700 9px monospace;text-transform:uppercase;margin:6px 0 4px}
.info-card b{color:#fff;font-size:15px;font-weight:800;display:block}
.ip{margin:6px 0 22px;display:flex;align-items:center;gap:12px;padding:14px 18px;background:rgba(20,10,30,.6);border:1px solid var(--line);border-radius:14px;font:12px monospace;color:#c8b9d0;flex-wrap:wrap}
.tag{padding:5px 10px;border-radius:8px;background:linear-gradient(135deg,var(--p1),var(--p2));color:#fff;font:800 9px monospace}
.preset-bar{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 20px}
.preset-bar button{padding:10px 16px;border-radius:10px;border:1px solid var(--line);background:rgba(20,10,30,.7);color:#c8b9d0;font:700 10px monospace;cursor:none;transition:.2s}
.preset-bar button:hover{border-color:var(--p1);color:#fff}
.preset-bar .primary{background:linear-gradient(135deg,var(--p1),var(--p3));color:#fff;border:0}
.preset-bar .danger{background:rgba(255,80,80,.15);border-color:rgba(255,80,80,.4);color:#ffaaaa}
.section-title{display:flex;align-items:center;gap:10px;margin:26px 0 12px;font:800 11px monospace;color:#c8b9d0;text-transform:uppercase}
.controls{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.control{display:flex;align-items:center;gap:14px;background:rgba(20,10,30,.55);border:1px solid var(--line);border-radius:16px;padding:16px;cursor:none;transition:.2s}
.control:hover{border-color:rgba(255,45,149,.5);transform:translateX(3px)}
.icon{width:36px;height:36px;display:grid;place-items:center;background:rgba(255,45,149,.15);border-radius:10px;color:var(--p1);font-size:14px;flex-shrink:0}
.info{flex:1;min-width:0}
.name{font-size:12px;font-weight:800}
.desc{color:var(--muted);font:10px monospace;margin-top:4px}
.sw{width:36px;height:20px;border-radius:20px;background:#322a38;padding:2px;transition:.25s;flex-shrink:0}
.sw .th{width:16px;height:16px;border-radius:50%;background:#8a7a90;transition:.25s}
.sw.on{background:linear-gradient(135deg,var(--p1),var(--p3))}
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
<div class="info-card"><i class="fa-solid fa-globe"></i><small>Country</small><b id="uCountry">—</b></div>
<div class="info-card"><i class="fa-solid fa-location-dot"></i><small>City</small><b id="uCity">—</b></div>
<div class="info-card"><i class="fa-solid fa-clock"></i><small>Time</small><b id="uTime">--:--:--</b></div>
<div class="info-card"><i class="fa-solid fa-calendar"></i><small>Date</small><b id="uDate">—</b></div>
<div class="info-card"><i class="fa-solid fa-cloud-sun"></i><small>Weather</small><b id="uWeather">—</b></div>
<div class="info-card"><i class="fa-solid fa-moon"></i><small>Period</small><b id="uDayNight">—</b></div>
<div class="info-card"><i class="fa-solid fa-mobile-screen"></i><small>Device</small><b id="uDevice">—</b></div>
<div class="info-card"><i class="fa-solid fa-battery-three-quarters"></i><small>Battery</small><b id="uBattery">—</b></div>
</div>
<div class="ip"><span id="ipDisplay">LOADING...</span><b class="tag">AUTHORIZED</b><b class="tag" style="background:linear-gradient(135deg,var(--p3),var(--p2))" id="keyDisplay">—</b></div>

<div class="preset-bar">
<button class="primary" onclick="comboOn()">🚀 KILLER COMBO (ВКЛ ВСЁ)</button>
<button class="danger" onclick="comboOff()">⛔ ВЫКЛ ВСЁ</button>
<button onclick="savePreset()">💾 Сохранить пресет</button>
<button onclick="loadPreset()">📂 Загрузить</button>
<button onclick="loadPresetList()">📋 Список</button>
</div>

<!-- ========== AIM & DAMAGE ========== -->
<div class="section-title">🎯 AIM & DAMAGE</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('hs_neck')"><div class="icon"><i class="fa-solid fa-crosshairs"></i></div><div class="info"><div class="name">HS PESCOÇO</div><div class="desc">PRECISION TARGET</div></div><div class="sw" id="sw_hs_neck"><div class="th"></div></div></div>
<div class="control" onclick="toggle('hs_chest')"><div class="icon"><i class="fa-solid fa-bullseye"></i></div><div class="info"><div class="name">HS PEITO</div><div class="desc">PRECISION TARGET</div></div><div class="sw" id="sw_hs_chest"><div class="th"></div></div></div>
<div class="control" onclick="toggle('aim_pro')"><div class="icon"><i class="fa-solid fa-crosshairs"></i></div><div class="info"><div class="name">AIM PRO</div><div class="desc">MAX SENSITIVITY</div></div><div class="sw" id="sw_aim_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('headshot_pro')"><div class="icon"><i class="fa-solid fa-skull"></i></div><div class="info"><div class="name">HEADSHOT PRO</div><div class="desc">HEAD DAMAGE BOOST</div></div><div class="sw" id="sw_headshot_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('no_recoil_pro')"><div class="icon"><i class="fa-solid fa-wind"></i></div><div class="info"><div class="name">NO RECOIL</div><div class="desc">ZERO Oтдaча</div></div><div class="sw" id="sw_no_recoil_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('ballistic_pro')"><div class="icon"><i class="fa-solid fa-rocket"></i></div><div class="info"><div class="name">BALLISTIC PRO</div><div class="desc">TRACE + LIMITS</div></div><div class="sw" id="sw_ballistic_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('high_sensi')"><div class="icon"><i class="fa-solid fa-sliders"></i></div><div class="info"><div class="name">SENSI ALTA</div><div class="desc">CONTROL PROFILE</div></div><div class="sw" id="sw_high_sensi"><div class="th"></div></div></div>
</div>

<!-- ========== MOVEMENT ========== -->
<div class="section-title">⚡ MOVEMENT</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('speed_run')"><div class="icon"><i class="fa-solid fa-person-running"></i></div><div class="info"><div class="name">SPEED RUN</div><div class="desc">MAX RUN/PRONE/SWIM</div></div><div class="sw" id="sw_speed_run"><div class="th"></div></div></div>
<div class="control" onclick="toggle('high_jump')"><div class="icon"><i class="fa-solid fa-arrow-up-from-bracket"></i></div><div class="info"><div class="name">HIGH JUMP</div><div class="desc">x3 JUMP HEIGHT</div></div><div class="sw" id="sw_high_jump"><div class="th"></div></div></div>
<div class="control" onclick="toggle('sprint_combo')"><div class="icon"><i class="fa-solid fa-bolt"></i></div><div class="info"><div class="name">SPRINT COMBO</div><div class="desc">SAFE SPEED PACK</div></div><div class="sw" id="sw_sprint_combo"><div class="th"></div></div></div>
<div class="control" onclick="toggle('swim_pro')"><div class="icon"><i class="fa-solid fa-water"></i></div><div class="info"><div class="name">SWIM PRO</div><div class="desc">FAST SWIM</div></div><div class="sw" id="sw_swim_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('fly_glide_pro')"><div class="icon"><i class="fa-solid fa-dove"></i></div><div class="info"><div class="name">FLY GLIDE</div><div class="desc">GLIDE/FOLD WING</div></div><div class="sw" id="sw_fly_glide_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('backjump_v1')"><div class="icon"><i class="fa-solid fa-arrow-up"></i></div><div class="info"><div class="name">BACKJUMP</div><div class="desc">MOVEMENT MODULE</div></div><div class="sw" id="sw_backjump_v1"><div class="th"></div></div></div>
<div class="control" onclick="toggle('zig_zag_move')"><div class="icon"><i class="fa-solid fa-arrows-left-right"></i></div><div class="info"><div class="name">ZIG ZAG</div><div class="desc">MOVEMENT MODULE</div></div><div class="sw" id="sw_zig_zag_move"><div class="th"></div></div></div>
<div class="control" onclick="toggle('vehicle_pro_v3')"><div class="icon"><i class="fa-solid fa-car"></i></div><div class="info"><div class="name">VEHICLE PRO</div><div class="desc">CAR GOD MODE</div></div><div class="sw" id="sw_vehicle_pro_v3"><div class="th"></div></div></div>
</div>

<!-- ========== HP & LOOT ========== -->
<div class="section-title">💪 HP & LOOT</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('hp_ap_max')"><div class="icon"><i class="fa-solid fa-heart"></i></div><div class="info"><div class="name">HP + AP MAX</div><div class="desc">MAX HP + ARMOR</div></div><div class="sw" id="sw_hp_ap_max"><div class="th"></div></div></div>
<div class="control" onclick="toggle('loot_master')"><div class="icon"><i class="fa-solid fa-box-open"></i></div><div class="info"><div class="name">LOOT MASTER</div><div class="desc">AUTO PICKUP + BIG BAG</div></div><div class="sw" id="sw_loot_master"><div class="th"></div></div></div>
<div class="control" onclick="toggle('loot_mega')"><div class="icon"><i class="fa-solid fa-truck-fast"></i></div><div class="info"><div class="name">LOOT MEGA</div><div class="desc">INSTANT PICKUP 30+</div></div><div class="sw" id="sw_loot_mega"><div class="th"></div></div></div>
<div class="control" onclick="toggle('instant_use')"><div class="icon"><i class="fa-solid fa-stopwatch"></i></div><div class="info"><div class="name">INSTANT USE</div><div class="desc">0s USE TIME</div></div><div class="sw" id="sw_instant_use"><div class="th"></div></div></div>
</div>

<!-- ========== ESP & RADAR ========== -->
<div class="section-title">👁 ESP & RADAR</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('esp_radar')"><div class="icon"><i class="fa-solid fa-eye"></i></div><div class="info"><div class="name">ESP + RADAR</div><div class="desc">ENEMY STEPS/FIRE/HP</div></div><div class="sw" id="sw_esp_radar"><div class="th"></div></div></div>
<div class="control" onclick="toggle('mega_radar')"><div class="icon"><i class="fa-solid fa-satellite-dish"></i></div><div class="info"><div class="name">MEGA RADAR</div><div class="desc">WHOLE MAP UAV</div></div><div class="sw" id="sw_mega_radar"><div class="th"></div></div></div>
<div class="control" onclick="toggle('hint_master')"><div class="icon"><i class="fa-solid fa-bell"></i></div><div class="info"><div class="name">HINT MASTER</div><div class="desc">ALL HINTS ON</div></div><div class="sw" id="sw_hint_master"><div class="th"></div></div></div>
<div class="control" onclick="toggle('loud_enemy')"><div class="icon"><i class="fa-solid fa-volume-high"></i></div><div class="info"><div class="name">LOUD ENEMY</div><div class="desc">HEAR ENEMY FAR</div></div><div class="sw" id="sw_loud_enemy"><div class="th"></div></div></div>
</div>

<!-- ========== VISION & VISUAL ========== -->
<div class="section-title">☀ VISION & VISUAL</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('full_bright_pro')"><div class="icon"><i class="fa-solid fa-sun"></i></div><div class="info"><div class="name">FULL BRIGHT</div><div class="desc">BRIGHT + NO FX</div></div><div class="sw" id="sw_full_bright_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('wide_fov')"><div class="icon"><i class="fa-solid fa-expand"></i></div><div class="info"><div class="name">WIDE FOV</div><div class="desc">FOV 120</div></div><div class="sw" id="sw_wide_fov"><div class="th"></div></div></div>
<div class="control" onclick="toggle('no_camera_shake')"><div class="icon"><i class="fa-solid fa-video"></i></div><div class="info"><div class="name">NO CAM SHAKE</div><div class="desc">STABLE CAMERA</div></div><div class="sw" id="sw_no_camera_shake"><div class="th"></div></div></div>
<div class="control" onclick="toggle('hud_names_pro')"><div class="icon"><i class="fa-solid fa-tag"></i></div><div class="info"><div class="name">HUD NAMES PRO</div><div class="desc">BIG NAME PLATES</div></div><div class="sw" id="sw_hud_names_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('quiet_self')"><div class="icon"><i class="fa-solid fa-volume-xmark"></i></div><div class="info"><div class="name">QUIET SELF</div><div class="desc">OWN VOLUME 0</div></div><div class="sw" id="sw_quiet_self"><div class="th"></div></div></div>
<div class="control" onclick="toggle('anim_speed_pro')"><div class="icon"><i class="fa-solid fa-person-walking"></i></div><div class="info"><div class="name">ANIM SPEED PRO</div><div class="desc">FAST ANIMATIONS</div></div><div class="sw" id="sw_anim_speed_pro"><div class="th"></div></div></div>
</div>

<!-- ========== v4 NEW MODULES ========== -->
<div class="section-title">🎭 EMOTE & AUDIO</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('emote_master')"><div class="icon"><i class="fa-solid fa-masks-theater"></i></div><div class="info"><div class="name">EMOTE MASTER</div><div class="desc">ЛИМИТ ЭМОЦИЙ 99+</div></div><div class="sw" id="sw_emote_master"><div class="th"></div></div></div>
<div class="control" onclick="toggle('silent_self')"><div class="icon"><i class="fa-solid fa-volume-xmark"></i></div><div class="info"><div class="name">SILENT SELF</div><div class="desc">СВОИ ЗВУКИ 0</div></div><div class="sw" id="sw_silent_self"><div class="th"></div></div></div>
<div class="control" onclick="toggle('aware_enemy')"><div class="icon"><i class="fa-solid fa-ear-listen"></i></div><div class="info"><div class="name">AWARE ENEMY</div><div class="desc">СЛЫШНО ВРАГОВ ДАЛЕКО</div></div><div class="sw" id="sw_aware_enemy"><div class="th"></div></div></div>
<div class="control" onclick="toggle('ui_audio_pro')"><div class="icon"><i class="fa-solid fa-comment-dots"></i></div><div class="info"><div class="name">UI AUDIO PRO</div><div class="desc">ДОЛГИЕ СООБЩЕНИЯ</div></div><div class="sw" id="sw_ui_audio_pro"><div class="th"></div></div></div>
</div>

<div class="section-title">📡 RADAR & UAV</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('uav_super')"><div class="icon"><i class="fa-solid fa-satellite-dish"></i></div><div class="info"><div class="name">UAV SUPER</div><div class="desc">99999 ДАЛЬНОСТЬ + ПОСТОЯННО</div></div><div class="sw" id="sw_uav_super"><div class="th"></div></div></div>
<div class="control" onclick="toggle('map_marker_pro')"><div class="icon"><i class="fa-solid fa-map-location-dot"></i></div><div class="info"><div class="name">MAP MARKER PRO</div><div class="desc">МГНОВЕННЫЕ МЕТКИ</div></div><div class="sw" id="sw_map_marker_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('multi_ping_pro')"><div class="icon"><i class="fa-solid fa-signal"></i></div><div class="info"><div class="name">MULTI PING PRO</div><div class="desc">ПИНГ 99 СЕРВЕРОВ</div></div><div class="sw" id="sw_multi_ping_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('spectator_pro')"><div class="icon"><i class="fa-solid fa-video"></i></div><div class="info"><div class="name">SPECTATOR PRO</div><div class="desc">КАМЕРА НАБЛЮДАТЕЛЯ x20</div></div><div class="sw" id="sw_spectator_pro"><div class="th"></div></div></div>
</div>

<div class="section-title">⚡ MOVEMENT EXTRA v4</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('jumppad_god')"><div class="icon"><i class="fa-solid fa-arrow-up-from-bracket"></i></div><div class="info"><div class="name">JUMPPAD GOD</div><div class="desc">999 СКОРОСТЬ + FOV 120</div></div><div class="sw" id="sw_jumppad_god"><div class="th"></div></div></div>
<div class="control" onclick="toggle('glider_pro')"><div class="icon"><i class="fa-solid fa-parachute-box"></i></div><div class="info"><div class="name">GLIDER PRO</div><div class="desc">ПАРАШЮТ + ГЛАЙД x99</div></div><div class="sw" id="sw_glider_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('movement_master_pro')"><div class="icon"><i class="fa-solid fa-person-skating"></i></div><div class="info"><div class="name">MOVEMENT MASTER</div><div class="desc">+300% СКОРОСТЬ</div></div><div class="sw" id="sw_movement_master_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('gameplay_extra')"><div class="icon"><i class="fa-solid fa-gamepad"></i></div><div class="info"><div class="name">GAMEPLAY EXTRA</div><div class="desc">HP/AP/РЮКЗАК МАКС</div></div><div class="sw" id="sw_gameplay_extra"><div class="th"></div></div></div>
</div>

<div class="section-title">🎯 HIT & AIM</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('auto_aim_pro')"><div class="icon"><i class="fa-solid fa-crosshairs"></i></div><div class="info"><div class="name">AUTO AIM PRO</div><div class="desc">УМНОЕ НАВЕДЕНИЕ</div></div><div class="sw" id="sw_auto_aim_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('hit_show_pro')"><div class="icon"><i class="fa-solid fa-bullseye"></i></div><div class="info"><div class="name">HIT SHOW PRO</div><div class="desc">ЭФФЕКТЫ ПОПАДАНИЯ x99</div></div><div class="sw" id="sw_hit_show_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('hitmarker_pro')"><div class="icon"><i class="fa-solid fa-bolt"></i></div><div class="info"><div class="name">HITMARKER PRO</div><div class="desc">ПОКАЗ УРОНА</div></div><div class="sw" id="sw_hitmarker_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('vehicle_god')"><div class="icon"><i class="fa-solid fa-car-side"></i></div><div class="info"><div class="name">VEHICLE GOD</div><div class="desc">МАШИНА БЕЗ УРОНА</div></div><div class="sw" id="sw_vehicle_god"><div class="th"></div></div></div>
</div>

<div class="section-title">🎨 VISUAL & UI</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('full_visual_pro')"><div class="icon"><i class="fa-solid fa-eye"></i></div><div class="info"><div class="name">FULL VISUAL PRO</div><div class="desc">ЧИСТЫЙ ВИЗУАЛ</div></div><div class="sw" id="sw_full_visual_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('fast_ui_pro')"><div class="icon"><i class="fa-solid fa-gauge-high"></i></div><div class="info"><div class="name">FAST UI PRO</div><div class="desc">БЫСТРЫЙ ИНТЕРФЕЙС</div></div><div class="sw" id="sw_fast_ui_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('view_distance_pro')"><div class="icon"><i class="fa-solid fa-binoculars"></i></div><div class="info"><div class="name">VIEW DISTANCE</div><div class="desc">ДАЛЬНОСТЬ 9999</div></div><div class="sw" id="sw_view_distance_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('photo_mode_pro')"><div class="icon"><i class="fa-solid fa-camera"></i></div><div class="info"><div class="name">PHOTO MODE PRO</div><div class="desc">РАСШИРЕННОЕ ФОТО</div></div><div class="sw" id="sw_photo_mode_pro"><div class="th"></div></div></div>
</div>

<div class="section-title">🎬 MISC</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('replay_pro')"><div class="icon"><i class="fa-solid fa-film"></i></div><div class="info"><div class="name">REPLAY PRO</div><div class="desc">РАСШИРЕННЫЙ РЕПЛЕЙ</div></div><div class="sw" id="sw_replay_pro"><div class="th"></div></div></div>
</div>

<!-- ========== ANTI-CHEAT BYPASS ========== -->
<div class="section-title">🛡 BYPASS / ANTI-BAN</div>
<div class="controls fade-in">
<div class="control" onclick="toggle('bypass_pro')"><div class="icon"><i class="fa-solid fa-shield-halved"></i></div><div class="info"><div class="name">BYPASS PRO</div><div class="desc">ADVANCED ANTI-CHEAT OFF</div></div><div class="sw" id="sw_bypass_pro"><div class="th"></div></div></div>
<div class="control" onclick="toggle('bypass_v1')"><div class="icon"><i class="fa-solid fa-shield"></i></div><div class="info"><div class="name">BYPASS BASIC</div><div class="desc">CLASSIC ANTI-BAN</div></div><div class="sw" id="sw_bypass_v1"><div class="th"></div></div></div>
<div class="control" onclick="toggle('fast_switch_pro')"><div class="icon"><i class="fa-solid fa-gun"></i></div><div class="info"><div class="name">FAST SWITCH</div><div class="desc">INSTANT SWAP</div></div><div class="sw" id="sw_fast_switch_pro"><div class="th"></div></div></div>
</div>

</section></main>
<div id="toast"></div>
<script>""" + NEON_JS + """
const names={
  hs_neck:'HS PESCOÇO',hs_chest:'HS PEITO',high_sensi:'SENSI ALTA',
  aim_pro:'AIM PRO',headshot_pro:'HEADSHOT PRO',no_recoil_pro:'NO RECOIL',ballistic_pro:'BALLISTIC PRO',
  speed_run:'SPEED RUN',high_jump:'HIGH JUMP',sprint_combo:'SPRINT COMBO',swim_pro:'SWIM PRO',fly_glide_pro:'FLY GLIDE',
  backjump_v1:'BACKJUMP',zig_zag_move:'ZIG ZAG',vehicle_pro_v3:'VEHICLE PRO',
  hp_ap_max:'HP + AP MAX',loot_master:'LOOT MASTER',loot_mega:'LOOT MEGA',instant_use:'INSTANT USE',
  esp_radar:'ESP + RADAR',mega_radar:'MEGA RADAR',hint_master:'HINT MASTER',loud_enemy:'LOUD ENEMY',
  full_bright_pro:'FULL BRIGHT',wide_fov:'WIDE FOV',no_camera_shake:'NO CAM SHAKE',hud_names_pro:'HUD NAMES PRO',
  quiet_self:'QUIET SELF',anim_speed_pro:'ANIM SPEED PRO',
  bypass_pro:'BYPASS PRO',bypass_v1:'BYPASS BASIC',fast_switch_pro:'FAST SWITCH',
  emote_master:'EMOTE MASTER',silent_self:'SILENT SELF',aware_enemy:'AWARE ENEMY',ui_audio_pro:'UI AUDIO PRO',
  uav_super:'UAV SUPER',map_marker_pro:'MAP MARKER PRO',multi_ping_pro:'MULTI PING PRO',spectator_pro:'SPECTATOR PRO',
  jumppad_god:'JUMPPAD GOD',glider_pro:'GLIDER PRO',movement_master_pro:'MOVEMENT MASTER',gameplay_extra:'GAMEPLAY EXTRA',
  auto_aim_pro:'AUTO AIM PRO',hit_show_pro:'HIT SHOW PRO',hitmarker_pro:'HITMARKER PRO',vehicle_god:'VEHICLE GOD',
  full_visual_pro:'FULL VISUAL',fast_ui_pro:'FAST UI PRO',view_distance_pro:'VIEW DISTANCE',photo_mode_pro:'PHOTO MODE',
  replay_pro:'REPLAY PRO'
};
function toast(m){const t_=document.getElementById('toast');t_.textContent=m;t_.classList.add('show');clearTimeout(t_._t);t_._t=setTimeout(()=>t_.classList.remove('show'),2000)}
fetch('/api/ip/check').then(r=>r.json()).then(d=>{
  document.getElementById('ipDisplay').textContent=d.ip||'N/A';
  if(d.key)document.getElementById('keyDisplay').textContent=d.key;
});
fetch('/api/user/info').then(r=>r.json()).then(d=>{
  document.getElementById('uCountry').textContent=(d.country||'—')+(d.country_code?' ('+d.country_code+')':'');
  document.getElementById('uCity').textContent=d.city||'—';
  if(d.timezone){function tick(){try{const n=new Date();document.getElementById('uTime').textContent=n.toLocaleTimeString('ru-RU',{timeZone:d.timezone,hour12:false});document.getElementById('uDate').textContent=n.toLocaleDateString('ru-RU',{timeZone:d.timezone,day:'2-digit',month:'short'})}catch(e){}}tick();setInterval(tick,1000)}
  if(d.weather){document.getElementById('uWeather').textContent=(d.weather.temp||'?')+'°C';document.getElementById('uDayNight').textContent=d.weather.is_day?'☀ DAY':'🌙 NIGHT'}
});
(function(){const ua=navigator.userAgent;let os='';if(/Android/i.test(ua))os='Android';else if(/iPhone|iPad/i.test(ua))os='iOS';else if(/Windows/i.test(ua))os='Windows';else if(/Mac/i.test(ua))os='macOS';else if(/Linux/i.test(ua))os='Linux';let br='Browser';if(/Chrome/i.test(ua)&&!/Edg/i.test(ua))br='Chrome';else if(/Firefox/i.test(ua))br='Firefox';else if(/Safari/i.test(ua))br='Safari';document.getElementById('uDevice').textContent=os+' · '+br;if(navigator.getBattery){navigator.getBattery().then(b=>{function u(){document.getElementById('uBattery').textContent=Math.round(b.level*100)+'%'+(b.charging?' ⚡':'')}u();b.addEventListener('levelchange',u)})}})();

const map={
  hs_neck:'HS_NECK',hs_chest:'HS_CHEST',high_sensi:'HIGH_SENSI',
  aim_pro:'AIM_PRO',headshot_pro:'HEADSHOT_PRO',no_recoil_pro:'NO_RECOIL_PRO',ballistic_pro:'BALLISTIC_PRO',
  speed_run:'SPEED_RUN',high_jump:'HIGH_JUMP',sprint_combo:'SPRINT_COMBO',swim_pro:'SWIM_PRO',fly_glide_pro:'FLY_GLIDE_PRO',
  backjump_v1:'BACKJUMPV1',zig_zag_move:'ZIG_ZAG_MOVE',vehicle_pro_v3:'VEHICLE_PRO_V3',
  hp_ap_max:'HP_AP_MAX',loot_master:'LOOT_MASTER',loot_mega:'LOOT_MEGA',instant_use:'INSTANT_USE',
  esp_radar:'ESP_RADAR',mega_radar:'MEGA_RADAR',hint_master:'HINT_MASTER',loud_enemy:'LOUD_ENEMY',
  full_bright_pro:'FULL_BRIGHT_PRO',wide_fov:'WIDE_FOV',no_camera_shake:'NO_CAMERA_SHAKE',hud_names_pro:'HUD_NAMES_PRO',
  quiet_self:'QUIET_SELF',anim_speed_pro:'ANIM_SPEED_PRO',
  bypass_pro:'BYPASS_PRO',bypass_v1:'BYPASSV1',fast_switch_pro:'FAST_SWITCH_PRO',
  emote_master:'EMOTE_MASTER',silent_self:'SILENT_SELF',aware_enemy:'AWARE_ENEMY',uav_super:'UAV_SUPER',
  spectator_pro:'SPECTATOR_PRO',jumppad_god:'JUMPPAD_GOD',glider_pro:'GLIDER_PRO',photo_mode_pro:'PHOTO_MODE_PRO',
  auto_aim_pro:'AUTO_AIM_PRO',vehicle_god:'VEHICLE_GOD',hit_show_pro:'HIT_SHOW_PRO',multi_ping_pro:'MULTI_PING_PRO',
  movement_master_pro:'MOVEMENT_MASTER_PRO',replay_pro:'REPLAY_PRO',view_distance_pro:'VIEW_DISTANCE_PRO',
  ui_audio_pro:'UI_AUDIO_PRO',hitmarker_pro:'HITMARKER_PRO',map_marker_pro:'MAP_MARKER_PRO',
  full_visual_pro:'FULL_VISUAL_PRO',fast_ui_pro:'FAST_UI_PRO',gameplay_extra:'GAMEPLAY_EXTRA'
};

fetch('/api/status').then(r=>r.json()).then(d=>{
  const c=d.config||{};
  Object.keys(map).forEach(f=>{const el=document.getElementById('sw_'+f);if(el)el.className='sw'+(c[map[f]]?' on':'')});
});

function toggle(feature){
  const el=document.getElementById('sw_'+feature);
  if(!el)return;
  const val=!el.classList.contains('on');
  el.className='sw'+(val?' on':'');
  fetch('/api/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({feature,value:val})})
    .then(r=>r.json())
    .then(d=>{if(d.success){toast((names[feature]||feature)+' '+(val?'ON':'OFF'));if(val)playSuccess()}else throw Error()})
    .catch(()=>{el.className='sw'+(!val?' on':'');toast('ERROR');playError()});
}

function comboOn(){
  toast('🚀 ВКЛЮЧАЮ ВСЁ...');
  fetch('/api/toggle_all',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:true})})
    .then(r=>r.json()).then(d=>{
      Object.keys(map).forEach(f=>{const el=document.getElementById('sw_'+f);if(el)el.className='sw on'});
      toast('🚀 ВСЁ ВКЛЮЧЕНО');playSuccess();
    });
}
function comboOff(){
  toast('⛔ ВЫКЛЮЧАЮ ВСЁ...');
  fetch('/api/toggle_all',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:false})})
    .then(r=>r.json()).then(d=>{
      Object.keys(map).forEach(f=>{const el=document.getElementById('sw_'+f);if(el)el.className='sw'});
      toast('⛔ ВСЁ ВЫКЛЮЧЕНО');playError();
    });
}
function savePreset(){
  const name=prompt('Название пресета:');
  if(!name)return;
  fetch('/api/preset/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})})
    .then(r=>r.json()).then(d=>{if(d.success){toast('💾 Пресет сохранён: '+name);playSuccess()}else{toast('ERROR');playError()}});
}
function loadPreset(){
  const name=prompt('Имя пресета:');
  if(!name)return;
  fetch('/api/preset/load',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})})
    .then(r=>r.json()).then(d=>{
      if(d.success){
        const c=d.config||{};
        Object.keys(map).forEach(f=>{const el=document.getElementById('sw_'+f);if(el)el.className='sw'+(c[map[f]]?' on':'')});
        toast('📂 Загружен: '+name);playSuccess();
      }else{toast('❌ Не найден');playError()}
    });
}
function loadPresetList(){
  fetch('/api/preset/list').then(r=>r.json()).then(d=>{
    const list=d.presets||[];
    if(!list.length){toast('Пресетов нет');return}
    alert('Пресеты:\\n'+list.join('\\n'));
  });
}
</script></body></html>"""

AI_PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TIGRAN AI</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>""" + NEON_CSS + """
.aigrid{position:relative;z-index:2;display:grid;grid-template-columns:290px 1fr;height:100vh;overflow:hidden}
.aiside{background:rgba(10,5,20,.85);border-right:1px solid var(--line);display:flex;flex-direction:column;padding:14px;overflow:hidden}
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
    <button class="primary" onclick="newChat()">+ NEW</button>
    <button onclick="exportChats()">EXPORT</button>
    <button onclick="document.getElementById('imp').click()">IMPORT</button>
    <input type="file" id="imp" accept=".json" style="display:none" onchange="importChats(event)">
  </div>
  <div class="chatlist" id="chatlist"></div>
  <div class="aibottom">
    <a href="/dashboard">← PANEL</a>
    <button onclick="clearAll()">CLEAR</button>
  </div>
</aside>
<section class="aimain">
  <header class="aihead">
    <div class="ttl"><i class="fa-solid fa-comments"></i> Chat</div>
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
      <textarea id="ta" placeholder="Type message..." rows="1"></textarea>
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
function newChat(){const c={id:uid(),title:'New chat',msgs:[],created:Date.now()};state.chats.unshift(c);state.activeId=c.id;save();renderList();renderMsgs();document.getElementById('aiside')?.classList.remove('open')}
function selectChat(id){state.activeId=id;save();renderList();renderMsgs()}
function delChat(e,id){e.stopPropagation();if(!confirm('Delete?'))return;state.chats=state.chats.filter(c=>c.id!==id);if(state.activeId===id){state.activeId=state.chats[0]?.id||null;if(!state.activeId)return newChat()}save();renderList();renderMsgs()}
function clearAll(){if(!confirm('Delete ALL?'))return;state.chats=[];state.activeId=null;save();newChat()}
function exportChats(){const blob=new Blob([JSON.stringify(state,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='tigran_chats.json';a.click()}
function importChats(e){const f=e.target.files[0];if(!f)return;const r=new FileReader();r.onload=()=>{try{const d=JSON.parse(r.result);if(d.chats){state.chats=[...d.chats,...state.chats];save();renderList();alert('OK')}}catch(err){alert('Err')}};r.readAsText(f);e.target.value=''}
function renderList(){const el=document.getElementById('chatlist');if(!state.chats.length){el.innerHTML='<div style="color:#6b5a70;font:11px monospace;padding:10px;text-align:center">Empty</div>';return}el.innerHTML=state.chats.map(c=>'<div class="chatitem'+(c.id===state.activeId?' active':'')+'" onclick="selectChat(\\''+c.id+'\\')"><span class="ttl">'+escapeHtml(c.title)+'</span><i class="fa-solid fa-trash del" onclick="delChat(event,\\''+c.id+'\\')"></i></div>').join('')}
function fmt(t){let s=escapeHtml(t);s=s.replace(/```([\\s\\S]*?)```/g,(m,c)=>'<pre><code>'+c+'</code></pre>');s=s.replace(/`([^`]+)`/g,'<code>$1</code>');s=s.replace(/\\*\\*([^*]+)\\*\\*/g,'<b>$1</b>');s=s.replace(/\\n/g,'<br>');return s}
function renderMsgs(){const box=document.getElementById('msgs');const c=active();if(!c||!c.msgs.length){box.innerHTML='<div class="empty"><h2>TIGRAN AI</h2><p>Ask anything.</p><div class="chips"><button class="chip" onclick="quick(\\'Hi!\\')">Hi</button><button class="chip" onclick="quick(\\'Write Python function\\')">Code</button></div></div>';return}box.innerHTML=c.msgs.map(m=>{if(m.role==='user')return '<div class="msg u"><div class="av">U</div><div class="bub">'+escapeHtml(m.content).replace(/\\n/g,'<br>')+'</div></div>';return '<div class="msg a"><div class="av">AI</div><div class="bub">'+fmt(m.content)+'</div></div>'}).join('');box.scrollTop=box.scrollHeight}
async function sendMsg(){const ta=document.getElementById('ta');const text=ta.value.trim();if(!text)return;if(!active())newChat();const c=active();c.msgs.push({role:'user',content:text});if(c.msgs.filter(m=>m.role==='user').length===1)c.title=text.slice(0,42);ta.value='';save();renderList();renderMsgs();await callAI(c)}
async function callAI(c){const box=document.getElementById('msgs');box.insertAdjacentHTML('beforeend','<div class="msg a" id="typing"><div class="av">AI</div><div class="bub"><span class="typing"><i></i><i></i><i></i></span></div></div>');box.scrollTop=box.scrollHeight;try{const r=await fetch('/api/ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:c.msgs[c.msgs.length-1].content,history:c.msgs.slice(0,-1),model:state.model})});const d=await r.json();document.getElementById('typing')?.remove();if(d.reply){c.msgs.push({role:'assistant',content:d.reply});save();renderMsgs();playSuccess()}else{c.msgs.push({role:'assistant',content:'⚠ '+(d.error||'Err')});save();renderMsgs()}}catch(e){document.getElementById('typing')?.remove();c.msgs.push({role:'assistant',content:'⚠ Error'});save();renderMsgs()}}
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
    print(f"  Lang: {_current_lang}")
    print(f"  Modules: {len(DEFAULT_CONFIG)}")
    print("="*50 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)