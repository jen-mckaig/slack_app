"""
Run this test to configure the Slack events listener.
"""

from flask import Flask, Response, request

app = Flask(__name__)


@app.route("/slack/events", methods=["POST"])
def test():
    request_json = request.get_json(silent=True, force=True)
    resp = Response(request_json.get("challenge"))
    resp.headers["Content-Type"] = "text/plain"
    return resp


if __name__ == "__main__":
    app.run(debug=True, port=3000)
