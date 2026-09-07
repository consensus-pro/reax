from . import create_app
from flask import send_from_directory, request
import os
from .utils import return_db_conn

app = create_app()

with app.app_context():
    try:
        from .utils import get_db, return_db_conn
        conn = get_db()
        return_db_conn()
    except Exception:
        pass

@app.route('/svg/<path:filename>')
def serve_svg(filename):
    svg_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'svg')
    return send_from_directory(svg_dir, filename)

@app.route('/template/style.css')
def serve_css():
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'template')
    return send_from_directory(template_dir, 'style.css')

@app.route('/api/toast.js')
def serve_toast_js():
    return send_from_directory(os.path.dirname(__file__), 'toast.js')

@app.errorhandler(404)
def not_found(e):
    return send_from_directory(os.path.dirname(__file__), "404.html"), 404

@app.after_request
def after_request(response):
    if response.status_code == 200 and request.method == 'GET':
        from .utils import update_page_view
        update_page_view(request.path)
    if request.path.startswith(('/svg/', '/template/style.css', '/api/toast.js')):
        response.headers['Cache-Control'] = 'public, max-age=86400'
    return response

@app.teardown_appcontext
def close_db_conn(exception=None):
    return_db_conn()

if __name__ == "__main__":
    app.run(debug=True)