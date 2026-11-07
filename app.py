from flask import Flask, request, jsonify, send_from_directory
import os
import sqlite3      # Python 自带的 SQLite 工具，不用安装
import requests

app = Flask(__name__, static_folder=".", static_url_path="")

# ===== Key 改从环境变量读取（V0.3 安全改造）=====
# 代码里只剩“变量名”，没有真实 Key 值。
# 本地启动前，先在 PowerShell 运行：
#   $env:ARK_API_KEY = "你的Key"     （仅当前窗口有效）
# Render 上则填在 Environment 里。
API_KEY = os.environ.get("ARK_API_KEY", "")
ENDPOINT_ID = os.environ.get("ARK_ENDPOINT_ID", "ep-20261104143157-ng6d4")
ARK_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
# ===== V0.4：收藏改用 SQLite 存（真正存得住）=====
DB_PATH = "favorites.db"   # 整个数据库就是项目文件夹里这一个文件

def init_db():
    """启动时确保收藏表存在：没有就建一张，有就直接用"""
    conn = sqlite3.connect(DB_PATH)          # 打开账本（没有会自动新建）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)                                      # 建表：两列，id 自动编号
    conn.commit()                             # 确认写入
    conn.close()                              # 合上账本

init_db()   # 程序一启动就执行一次

def get_all_favorites():
    """翻开账本，把所有收藏按存入顺序读出来（这次连 id 一起带回，方便删除）"""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, name FROM favorites ORDER BY id").fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1]} for r in rows]   # 每条长这样：{"id": 3, "name": "豆豆"}


@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route('/api/favorite', methods=['POST'])
def add_favorite():
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:                              # 空名字不存
        return jsonify({'saved': False, 'all': get_all_favorites()})
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO favorites (name) VALUES (?)", (name,))  # 存进账本
    conn.commit()
    conn.close()
    return jsonify({'saved': True, 'all': get_all_favorites()})

@app.route('/api/favorites', methods=['GET'])
def list_favorites():
    return jsonify({'all': get_all_favorites()})

# ★ 删除接口：DELETE /api/favorite/几号
@app.route('/api/favorite/<int:fav_id>', methods=['DELETE'])
def delete_favorite(fav_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM favorites WHERE id = ?", (fav_id,))  # ★ 带 WHERE！删指定那行
    conn.commit()
    conn.close()
    return jsonify({'deleted': True, 'all': get_all_favorites()})


@app.route("/api/generate", methods=["POST"])
def generate():
    if not API_KEY:
        return jsonify({"error": "服务器未配置 ARK_API_KEY 环境变量"}), 500
    data = request.get_json()
    pet_type = data.get("type", "宠物")
    mood = data.get("mood", "活泼")

    prompt = (
        f"你是宠物起名专家。请为一只{pet_type}、性格{mood}的宠物起10个中文名字。"
        f"要求：每个名字简短好听、贴合该性格，不要编号，直接输出10个名字，用顿号分隔。"
    )

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": ENDPOINT_ID,
        "messages": [{"role": "user", "content": prompt}],
        "thinking": {"type": "disabled"},
    }

    try:
        resp = requests.post(ARK_URL, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return jsonify({"names": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG") == "1")