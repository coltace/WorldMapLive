from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from backend.services.assistant import AssistantUnavailable, approved_public_context, generate_reply
from extensions import limiter

assistant_bp = Blueprint("assistant", __name__)


def _user_rate_key():
    user_id = current_user.get_id()
    return f"user:{user_id}" if user_id else request.remote_addr or "anonymous"


@assistant_bp.post("/chat")
@login_required
@limiter.limit("10 per minute", key_func=_user_rate_key)
def chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400
    message = data.get("message")
    max_chars = int(current_app.config.get("ASSISTANT_MAX_INPUT_CHARS", 2000))
    if not isinstance(message, str) or not message.strip() or len(message) > max_chars:
        return jsonify({"error": f"Message must contain 1 to {max_chars} characters"}), 400
    if not current_app.config.get("ASSISTANT_ENABLED"):
        return jsonify({"error": "Assistant is temporarily unavailable"}), 503
    try:
        context = approved_public_context(message.strip())
        reply = generate_reply(message.strip(), context)
    except AssistantUnavailable:
        return jsonify({"error": "Assistant is temporarily unavailable"}), 503
    return jsonify({"reply": reply})
