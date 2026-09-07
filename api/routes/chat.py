from flask import Blueprint, request, jsonify, session, render_template, redirect
from psycopg2.extras import RealDictCursor
from ..utils import get_db
import html
import pusher
import os
import oss2
import uuid

chat_bp = Blueprint('chat', __name__)

pusher_client = pusher.Pusher(
    app_id=os.environ.get("PUSHER_APP_ID"),
    key=os.environ.get("PUSHER_KEY"),
    secret=os.environ.get("PUSHER_SECRET"),
    cluster=os.environ.get("PUSHER_CLUSTER"),
    ssl=True
)

@chat_bp.route("/api/messages", methods=["GET"])
def get_messages():
    username = session.get("username")
    if not username:
        return jsonify({"success": False, "error": "未登录"}), 401

    limit = request.args.get("limit", default=20, type=int)
    offset = request.args.get("offset", default=0, type=int)
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1
    if offset < 0:
        offset = 0

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT m.username, m.content, m.created_at, u.qq_number
        FROM messages m
        LEFT JOIN users u ON m.username = u.username
        ORDER BY m.created_at DESC
        LIMIT %s OFFSET %s
    """, (limit, offset))
    messages = cur.fetchall()
    messages.reverse()

    for msg in messages:
        if msg.get("qq_number"):
            msg["avatar_url"] = f"https://q1.qlogo.cn/g?b=qq&nk={msg['qq_number']}&s=640"
        else:
            msg["avatar_url"] = None
    return jsonify({"success": True, "messages": messages})

@chat_bp.route("/api/send-message", methods=["POST"])
def send_message():
    username = session.get("username")
    if not username:
        return jsonify({"success": False, "error": "未登录"}), 401

    data = request.get_json()
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"success": False, "error": "消息不能为空"}), 400
    if len(content) > 500:
        return jsonify({"success": False, "error": "消息太长"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users 
        SET last_message_time = NOW() 
        WHERE username = %s 
          AND (last_message_time IS NULL OR last_message_time < NOW() - INTERVAL '1 second')
    """, (username,))
    if cur.rowcount == 0:
        return jsonify({"success": False, "error": "发送过于频繁"}), 429
    conn.commit()

    content = html.escape(content)
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT qq_number FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    if not user:
        session.pop("username", None)
        return jsonify({"success": False, "error": "用户不存在，请重新登录"}), 401

    avatar_url = None
    if user.get("qq_number"):
        avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user['qq_number']}&s=640"

    cur.execute(
        "INSERT INTO messages (username, content) VALUES (%s, %s) RETURNING id",
        (username, content)
    )
    inserted_id = cur.fetchone()["id"]
    conn.commit()

    try:
        pusher_client.trigger("chat", "new-message", {
            "username": username,
            "content": content,
            "avatar_url": avatar_url
        })
    except Exception as e:
        pass

    return jsonify({"success": True, "message": "发送成功", "id": inserted_id})

@chat_bp.route("/api/pusher/config", methods=["GET"])
def pusher_config():
    return jsonify({
        "success": True,
        "key": os.environ.get("PUSHER_KEY", ""),
        "cluster": os.environ.get("PUSHER_CLUSTER", "ap1")
    })

@chat_bp.route("/api/upload-image", methods=["POST"])
def upload_image():
    username = session.get("username")
    if not username:
        return jsonify({"success": False, "error": "未登录"}), 401

    if 'image' not in request.files:
        return jsonify({"success": False, "error": "未选择图片"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "error": "文件名为空"}), 400

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 7.5 * 1024 * 1024:
        return jsonify({"success": False, "error": "图片不能超过7.5MB"}), 400

    OSS_ACCESS_KEY_ID = os.environ.get("OSS_ACCESS_KEY_ID")
    OSS_ACCESS_KEY_SECRET = os.environ.get("OSS_ACCESS_KEY_SECRET")
    OSS_ENDPOINT = os.environ.get("OSS_ENDPOINT")
    OSS_BUCKET_NAME = os.environ.get("OSS_BUCKET_NAME")

    if not all([OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_ENDPOINT, OSS_BUCKET_NAME]):
        return jsonify({"success": False, "error": "OSS配置未完整"}), 500

    try:
        auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
        bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)
        file_bytes = file.read()
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'jpg'
        new_filename = f"{uuid.uuid4().hex}.{ext}"
        bucket.put_object(new_filename, file_bytes)
        image_url = f"https://{OSS_BUCKET_NAME}.{OSS_ENDPOINT}/{new_filename}"
    except Exception as e:
        return jsonify({"success": False, "error": f"OSS上传失败: {str(e)}"}), 500

    img_markdown = f"![图片]({image_url})"

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users 
        SET last_message_time = NOW() 
        WHERE username = %s 
          AND (last_message_time IS NULL OR last_message_time < NOW() - INTERVAL '1 second')
    """, (username,))
    if cur.rowcount == 0:
        return jsonify({"success": False, "error": "发送过于频繁"}), 429
    conn.commit()

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT qq_number FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    if not user:
        session.pop("username", None)
        return jsonify({"success": False, "error": "用户不存在"}), 401

    avatar_url = None
    if user.get("qq_number"):
        avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user['qq_number']}&s=640"

    cur.execute(
        "INSERT INTO messages (username, content) VALUES (%s, %s) RETURNING id",
        (username, img_markdown)
    )
    msg_id = cur.fetchone()["id"]
    conn.commit()

    try:
        pusher_client.trigger("chat", "new-message", {
            "username": username,
            "content": img_markdown,
            "avatar_url": avatar_url
        })
    except Exception as e:
        pass

    return jsonify({"success": True, "message": "图片已发送", "id": msg_id})