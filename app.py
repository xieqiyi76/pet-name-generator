from flask import Flask, request, jsonify, send_from_directory
import os
import sqlite3      # Python 自带的 SQLite 工具，不用安装
import uuid         # 生成随机手环号用（Python 自带）
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
# ===== V0.5：游客手环（Cookie）识别 "谁是谁" =====
DB_PATH = "favorites.db"   # 整个数据库就是项目文件夹里这一个文件

def init_db():
    """启动时确保收藏表存在：没有就建一张，有就直接用"""
    conn = sqlite3.connect(DB_PATH)          # 打开账本（没有会自动新建）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'guest'   -- 新增：记录是哪个游客存的
        )
    """)
    # 旧表升级：如果表已存在但还没有 user_id 列，就现场补上（老收藏归到 'guest'）
    cols = [row[1] for row in conn.execute("PRAGMA table_info(favorites)")]
    if "user_id" not in cols:
        conn.execute("ALTER TABLE favorites ADD COLUMN user_id TEXT NOT NULL DEFAULT 'guest'")
    conn.commit()
    conn.close()

init_db()

def get_all_favorites(uid):
    """只读指定访客自己的收藏（按手环号过滤）"""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, name FROM favorites WHERE user_id = ? ORDER BY id",
        (uid,)
    ).fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1]} for r in rows]

def get_uid():
    """取当前访客的手环号；没有手环就现场造一个"""
    uid = request.cookies.get("pet_uid")    # 从 Cookie 里找手环
    if uid:
        return uid, None                     # 老访客：有手环
    new_uid = str(uuid.uuid4())              # 新访客：造一个随机号（如 a3f8b2c1-...）
    return new_uid, new_uid                  # 第二个值不为空 = 要发给浏览器

def attach_cookie(resp, new_uid):
    """如果刚才造了新手环，把它塞进响应里发给浏览器"""
    if new_uid:
        resp.set_cookie("pet_uid", new_uid, max_age=60*60*24*365)  # 有效期一年
    return resp


@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route('/api/favorite', methods=['POST'])
def add_favorite():
    uid, new_uid = get_uid()                   # 先看手环，必要时造新的
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:                              # 空名字不存
        return attach_cookie(
            jsonify({'saved': False, 'all': get_all_favorites(uid)}), new_uid)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO favorites (name, user_id) VALUES (?, ?)", (name, uid))  # 存账本时记上是谁存的
    conn.commit()
    conn.close()
    return attach_cookie(
        jsonify({'saved': True, 'all': get_all_favorites(uid)}), new_uid)

@app.route('/api/favorites', methods=['GET'])
def list_favorites():
    uid, new_uid = get_uid()
    return attach_cookie(
        jsonify({'all': get_all_favorites(uid)}), new_uid)

# ★ 删除接口：DELETE /api/favorite/几号（只能删自己的！）
@app.route('/api/favorite/<int:fav_id>', methods=['DELETE'])
def delete_favorite(fav_id):
    uid, new_uid = get_uid()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM favorites WHERE id = ? AND user_id = ?", (fav_id, uid))  # 双保险：编号对 + 手环对
    conn.commit()
    conn.close()
    return attach_cookie(
        jsonify({'deleted': True, 'all': get_all_favorites(uid)}), new_uid)


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