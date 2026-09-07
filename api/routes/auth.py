from flask import Blueprint, request, jsonify, session, render_template, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import RealDictCursor
from ..utils import get_db, generate_code, is_valid_email, is_allowed_email
from .captcha import verify_captcha
import re
from datetime import datetime, timezone, timedelta

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/")
def index():
    if session.get("username"):
        return render_template("index.html")
    return redirect("/login")

@auth_bp.route("/register")
def register_page():
    return render_template("register.html")

@auth_bp.route("/login")
def login_page():
    return render_template("login.html")

@auth_bp.route("/api/send-code", methods=["POST"])
def send_code():
    data = request.get_json()
    email_raw = data.get("email")
    token = data.get("captcha_token")
    user_input = data.get("captcha", "").strip().upper()

    # 仅验证，不删除
    ok, msg = verify_captcha(token, user_input, remove=False)
    if not ok:
        return jsonify({"success": False, "error": msg}), 400

    if not email_raw:
        return jsonify({"success": False, "error": "请输入邮箱"}), 400

    email = email_raw.lower().strip()
    if not is_valid_email(email):
        return jsonify({"success": False, "error": "邮箱格式错误"}), 400

    try:
        if not is_allowed_email(email):
            return jsonify({"success": False, "error": "请使用正规邮箱注册"}), 400
    except Exception:
        return jsonify({"success": False, "error": "检测器加载失败"}), 500

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM email_verifications WHERE expires_at < NOW() - INTERVAL '1 day'")
    conn.commit()

    cur.execute("SELECT id FROM users WHERE LOWER(email) = %s", (email,))
    existing = cur.fetchone()
    if existing:
        return jsonify({"success": False, "error": "该邮箱已被注册"}), 400

    cur.execute(
        "SELECT 1 FROM email_verifications WHERE email = %s AND created_at > NOW() - INTERVAL '60 seconds'",
        (email,)
    )
    if cur.fetchone():
        return jsonify({"success": False, "error": "请等待 60 秒后再试"}), 429

    code = generate_code()
    expires_at = datetime.now(timezone(timedelta(hours=8))) + timedelta(minutes=10)

    cur.execute(
        """
        INSERT INTO email_verifications (email, code, created_at, expires_at)
        VALUES (%s, %s, NOW(), %s)
        ON CONFLICT (email) 
        DO UPDATE SET code = %s, created_at = NOW(), expires_at = %s
        """,
        (email, code, expires_at, code, expires_at)
    )
    conn.commit()

    try:
        import resend
        resend.Emails.send(
            params={
                "from": "T8000X网络 <noreply@t8000x.top>",
                "to": email,
                "subject": "注册验证码",
                "html": f"<p>您的验证码是：<strong>{code}</strong>，有效期10分钟。</p>"
            }
        )
        return jsonify({"success": True, "message": "验证码已发送"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@auth_bp.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    email_raw = data.get("email")
    code = data.get("code")
    captcha_token = data.get("captcha_token")
    captcha_input = data.get("captcha", "").strip().upper()

    # 验证并删除（注册完成）
    ok, msg = verify_captcha(captcha_token, captcha_input, remove=True)
    if not ok:
        return jsonify({"success": False, "error": msg}), 400

    if not all([username, password, email_raw, code]):
        return jsonify({"success": False, "error": "有字段未填"}), 400

    email = email_raw.lower().strip()
    if not is_valid_email(email):
        return jsonify({"success": False, "error": "邮箱格式错误"}), 400

    try:
        if not is_allowed_email(email):
            return jsonify({"success": False, "error": "请使用正规邮箱注册"}), 400
    except Exception:
        return jsonify({"success": False, "error": "检测器加载失败"}), 500

    if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9]+$', username):
        return jsonify({"success": False, "error": "用户名只能包含中文、字母、数字"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT code FROM email_verifications WHERE email = %s AND expires_at > NOW()",
        (email,)
    )
    row = cur.fetchone()
    if not row or row[0] != code:
        return jsonify({"success": False, "error": "邮箱验证码错误或已过期"}), 400

    cur.execute("DELETE FROM email_verifications WHERE email = %s", (email,))
    conn.commit()

    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    if cur.fetchone():
        return jsonify({"success": False, "error": "账号已存在"}), 400

    password_hash = generate_password_hash(password)
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash, email, created_at) VALUES (%s, %s, %s, NOW())",
            (username, password_hash, email)
        )
        conn.commit()
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        user_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO user_stats (user_id, total_points, checkin_days) VALUES (%s, 0, 0)",
            (user_id,)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        return jsonify({"success": False, "error": "注册失败，请重试"}), 400

    return jsonify({"success": True, "message": "注册成功"})

@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    token = data.get("captcha_token")
    user_input = data.get("captcha", "").strip().upper()

    ok, msg = verify_captcha(token, user_input, remove=True)
    if not ok:
        return jsonify({"success": False, "error": msg}), 400

    if not username or not password:
        return jsonify({"success": False, "error": "账号或密码未填"}), 400

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cur.fetchone()

    if not user:
        return jsonify({"success": False, "error": "账号或密码错误"}), 401

    if not check_password_hash(user["password_hash"], password):
        return jsonify({"success": False, "error": "账号或密码错误"}), 401

    session["username"] = username
    return jsonify({"success": True, "message": "登录成功 欢迎回来"})

@auth_bp.route("/api/logout", methods=["POST"])
def logout():
    session.pop("username", None)
    session.pop("admin", None)
    return jsonify({"success": True, "message": "已退出登录"})