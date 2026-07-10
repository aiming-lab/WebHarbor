"""Webmd mirror — Flask app."""
import os
from flask import Flask, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webmd-dev-secret-please-change"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/_health")
def health():
    return {"ok": True, "site": "webmd"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
