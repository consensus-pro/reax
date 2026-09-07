from flask import Blueprint, request, jsonify, session, render_template
from psycopg2.extras import RealDictCursor
from ..utils import get_db
from datetime import timedelta

user_bp = Blueprint('user', __name__)

@user_bp.route("/user")
def user_page():
    return render_template("user.html")

@user_bp.route("/api/user", methods=["GET"])
def get_user():
    target_username = request.args.get("username")
    
    if not target_username:
        username = session.get("username")
        if not username:
            return jsonify({"success": False, "error": "未登录"}), 401
    else:
        username = target_username

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT u.username, u.email, u.signature, u.gender, u.created_at, u.qq_number,
               COALESCE(s.total_points, 0) as total_points,
               COALESCE(s.checkin_days, 0) as checkin_days,
               (SELECT COUNT(*) + 1 FROM user_stats WHERE total_points > COALESCE(s.total_points, 0)) as rank
        FROM users u
        LEFT JOIN user_stats s ON u.id = s.user_id
        WHERE u.username = %s
    """, (username,))
    user = cur.fetchone()

    if not user:
        return jsonify({"success": False, "error": "用户不存在"}), 404

    created_at = None
    if user.get("created_at"):
        created_at = (user["created_at"] + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")

    gender = user.get("gender")
    if not gender or gender.strip() == "":
        gender = "不愿透露"

    total_points = user.get("total_points") or 0
    rank = user.get("rank")
    if total_points <= 0 or not rank:
        rank = None

    return jsonify({
        "success": True,
        "username": user["username"],
        "email": user["email"],
        "signature": user.get("signature") or "未填写",
        "gender": gender,
        "created_at": created_at,
        "qq_number": user.get("qq_number") or "",
        "total_points": total_points,
        "checkin_days": user.get("checkin_days") or 0,
        "rank": rank
    })