from flask import Flask, request, jsonify, send_from_directory
import os
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


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


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