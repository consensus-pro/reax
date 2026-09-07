from flask import Blueprint, request, jsonify, session, render_template
from psycopg2.extras import RealDictCursor
from ..utils import get_db
from datetime import timedelta, datetime, timezone
import random

profile_bp = Blueprint('profile', __name__)

@profile_bp.route("/profile")
def profile_page():
    return render_template("profile.html")

@profile_bp.route("/api/update-signature", methods=["POST"])
def update_signature():
    username = session.get("username")
    if not username:
        return jsonify({"success": False, "error": "未登录"}), 401

    data = request.get_json()
    signature = data.get("signature", "").strip()
    if not signature:
        signature = "未填写"
    if len(signature) > 20:
        return jsonify({"success": False, "error": "签名不能超过20字"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET signature = %s WHERE username = %s", (signature, username))
    conn.commit()
    return jsonify({"success": True, "message": "签名已修改", "signature": signature})

@profile_bp.route("/api/update-gender", methods=["POST"])
def update_gender():
    username = session.get("username")
    if not username:
        return jsonify({"success": False, "error": "未登录"}), 401

    data = request.get_json()
    gender = data.get("gender", "").strip()
    allowed = ["男", "女", "其他", "不愿透露"]
    if gender not in allowed:
        return jsonify({"success": False, "error": "性别不合法"}), 400
    if gender == "不愿透露":
        gender = None

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET gender = %s WHERE username = %s", (gender, username))
    conn.commit()
    return jsonify({"success": True, "message": "性别修改成功", "gender": gender or "不愿透露"})

@profile_bp.route("/api/bind-qq", methods=["POST"])
def bind_qq():
    username = session.get("username")
    if not username:
        return jsonify({"success": False, "error": "未登录"}), 401

    data = request.get_json()
    qq_number = data.get("qq_number", "").strip()
    if not qq_number:
        return jsonify({"success": False, "error": "QQ号不能为空"}), 400
    if not qq_number.isdigit() or len(qq_number) < 5 or len(qq_number) > 11:
        return jsonify({"success": False, "error": "请输入正确的QQ号"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET qq_number = %s WHERE username = %s", (qq_number, username))
    conn.commit()
    return jsonify({"success": True, "message": "QQ绑定成功"})

@profile_bp.route("/api/checkin", methods=["POST"])
def checkin():
    username = session.get("username")
    if not username:
        return jsonify({"success": False, "error": "未登录"}), 401

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    if not user:
        session.pop("username", None)
        return jsonify({"success": False, "error": "用户不存在"}), 401

    user_id = user["id"]
    today = datetime.now(timezone(timedelta(hours=8))).date()

    cur.execute("SELECT last_checkin_date, total_points, checkin_days FROM user_stats WHERE user_id = %s", (user_id,))
    stats = cur.fetchone()

    if stats and stats["last_checkin_date"] == today:
        return jsonify({"success": False, "error": "今日已签到"}), 400

    points = random.randint(-50, 200)
    new_total = (stats["total_points"] if stats else 0) + points
    new_days = (stats["checkin_days"] if stats else 0) + 1

    if stats:
        cur.execute(
            "UPDATE user_stats SET total_points = %s, checkin_days = %s, last_checkin_date = %s WHERE user_id = %s",
            (new_total, new_days, today, user_id)
        )
    else:
        cur.execute(
            "INSERT INTO user_stats (user_id, total_points, checkin_days, last_checkin_date) VALUES (%s, %s, %s, %s)",
            (user_id, new_total, new_days, today)
        )
    conn.commit()
    return jsonify({"success": True, "message": f"签到成功，获得{points}积分", "points": points, "total": new_total})

@profile_bp.route("/api/ranking", methods=["GET"])
def get_ranking():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT u.username, u.qq_number, s.total_points, s.checkin_days,
               ROW_NUMBER() OVER (ORDER BY s.total_points DESC) as rank
        FROM user_stats s
        JOIN users u ON u.id = s.user_id
        WHERE s.total_points > 0
        ORDER BY s.total_points DESC
        LIMIT 100
    """)
    ranking = cur.fetchall()

    for item in ranking:
        if item.get("qq_number"):
            item["avatar_url"] = f"https://q1.qlogo.cn/g?b=qq&nk={item['qq_number']}&s=640"
        else:
            item["avatar_url"] = None
    return jsonify({"success": True, "ranking": ranking})

@profile_bp.route("/api/transfer", methods=["POST"])
def transfer_points():
    username = session.get("username")
    if not username:
        return jsonify({"success": False, "error": "未登录"}), 401

    data = request.get_json()
    target = data.get("target", "").strip()
    points_str = data.get("points")
    if not target or points_str is None:
        return jsonify({"success": False, "error": "参数不足"}), 400
    if target == username:
        return jsonify({"success": False, "error": "不能转给自己"}), 400

    try:
        points = int(points_str)
    except ValueError:
        return jsonify({"success": False, "error": "积分必须是整数"}), 400
    if points <= 0:
        return jsonify({"success": False, "error": "积分必须大于0"}), 400

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT id FROM users WHERE username = %s", (target,))
    target_user = cur.fetchone()
    if not target_user:
        return jsonify({"success": False, "error": "用户不存在"}), 404

    cur.execute("SELECT total_points FROM user_stats WHERE user_id = (SELECT id FROM users WHERE username = %s)", (username,))
    sender_stats = cur.fetchone()
    if not sender_stats:
        return jsonify({"success": False, "error": "您没有积分记录"}), 400
    if sender_stats["total_points"] < points:
        return jsonify({"success": False, "error": "积分不足"}), 400

    try:
        cur.execute("UPDATE user_stats SET total_points = total_points - %s WHERE user_id = (SELECT id FROM users WHERE username = %s)", (points, username))
        cur.execute("UPDATE user_stats SET total_points = total_points + %s WHERE user_id = (SELECT id FROM users WHERE username = %s)", (points, target))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": "转账失败"}), 500

    return jsonify({"success": True, "message": "转账成功"})

@profile_bp.route("/api/announcement", methods=["GET"])
def get_announcement():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT title, content, is_active, updated_at FROM announcement WHERE id = 1")
    row = cur.fetchone()
    if not row:
        return jsonify({"success": False, "error": "公告不存在"}), 404
    return jsonify({
        "success": True,
        "title": row["title"],
        "content": row["content"],
        "is_active": row["is_active"],
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
    })