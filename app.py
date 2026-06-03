import os
import hmac
import hashlib
import time
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "YOUR_PAGE_ACCESS_TOKEN")
VERIFY_TOKEN      = os.environ.get("VERIFY_TOKEN", "YOUR_VERIFY_TOKEN")
APP_SECRET        = os.environ.get("APP_SECRET", "YOUR_APP_SECRET")
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY")

GRAPH_API_URL = "https://graph.facebook.com/v19.0/me/messages"
GROQ_API_URL  = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """Bạn là trợ lý AI của Homestay Trăng Non tại Phan Thiết.
Nhiệm vụ: tư vấn và hỗ trợ khách hàng qua Facebook Messenger.

Quy tắc trả lời:
- Luôn trả lời bằng tiếng Việt, thân thiện, nhiệt tình như nhân viên lễ tân
- Ngắn gọn, dễ hiểu (dưới 200 từ)
- Dùng emoji phù hợp để tin nhắn sinh động hơn
- Không bịa thông tin nếu không chắc chắn
- Nếu khách muốn đặt phòng, hỏi: tên, ngày check-in, ngày check-out, số người
- Nếu khách muốn xác nhận đặt phòng hoặc có câu hỏi phức tạp, nhờ để lại SĐT để chủ nhà liên hệ lại
- Hotline: 083 285 0488

=== THÔNG TIN PHÒNG ===
Tổng cộng 3 phòng:

1. Phòng Tiêu Chuẩn (2 phòng):
   - Giá trong tuần (T2-T5): 370.000đ/đêm
   - Giá cuối tuần (T6, T7, CN & lễ tết): 400.000đ/đêm

2. Phòng Cao Cấp (1 phòng):
   - Giá trong tuần (T2-T5): 440.000đ/đêm
   - Giá cuối tuần (T6, T7, CN & lễ tết): 480.000đ/đêm

=== GIỜ CHECK-IN / CHECK-OUT ===
- Check-in: 14:00
- Check-out: 12:00
- Nhận phòng sớm hoặc trả phòng trễ: phụ phí 50.000đ/giờ

=== XE THUÊ ===
- Có cho thuê xe ga: 150.000đ/ngày (tính 24 tiếng từ lúc lấy xe)
- Loại xe: Honda Vision hoặc Honda Airblade

=== ĐỖ XE HƠI ===
- Homestay không có chỗ đậu xe hơi
- Quý khách vui lòng đậu xe ngoài đường Lê Duẩn, đi bộ vào khoảng 50m
- Quý khách tự bảo quản xe

=== VỊ TRÍ & XUNG QUANH ===
- Địa chỉ: 17/14B Lương Văn Năm, KP3, P. Phú Trinh, Phan Thiết
- Nằm ở trung tâm Phan Thiết, yên tĩnh, phù hợp nghỉ dưỡng
- Gần biển Đồi Dương và Thương Chánh (2km)
- Gần chợ Phan Thiết & phố ăn uống (1.5km)
- Gần café check-in: Mơ Hoang, Café Bồng Bềnh (2km)
- Dễ di chuyển đến Mũi Né, NovaWorld, quán café ven biển (12km)
"""

conversation_history: dict[str, list] = {}
MAX_HISTORY = 10


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook đã được xác thực!")
        return challenge, 200
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def receive_message():
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(request.data, signature):
        return "Unauthorized", 401

    data = request.get_json()
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event["sender"]["id"]
                if "message" in event:
                    handle_message(sender_id, event["message"])
                elif "postback" in event:
                    handle_postback(sender_id, event["postback"])
    return jsonify({"status": "ok"}), 200


def handle_message(sender_id: str, message: dict):
    text = message.get("text", "").strip()
    if not text:
        send_text(sender_id, "Mình chưa đọc được tin nhắn này 😅 Bạn thử gửi text nhé!")
        return

    lower = text.lower()
    if lower in ("hi", "hello", "xin chào", "chào", "bắt đầu"):
        send_quick_replies(
            sender_id,
            "👋 Xin chào! Mình là trợ lý AI của Trăng Non Homestay, có thể giúp gì cho bạn?",
            [
                {"title": "🛏️ Giá phòng",  "payload": "PRICES"},
                {"title": "📍 Vị trí",      "payload": "LOCATION"},
                {"title": "🛵 Thuê xe",     "payload": "MOTORBIKE"},
                {"title": "📞 Liên hệ",     "payload": "CONTACT"},
            ],
        )
        return

    if lower in ("/reset", "xóa lịch sử"):
        conversation_history.pop(sender_id, None)
        send_text(sender_id, "🔄 Đã xóa lịch sử. Chúng ta bắt đầu lại nhé!")
        return

    reply = ask_groq(sender_id, text)
    send_text(sender_id, reply)


def handle_postback(sender_id: str, postback: dict):
    payload = postback.get("payload", "")
    responses = {
        "PRICES":    "🛏️ Giá phòng Trăng Non:\n\n• Phòng Tiêu Chuẩn:\n  - Trong tuần: 370k/đêm\n  - Cuối tuần: 400k/đêm\n\n• Phòng Cao Cấp:\n  - Trong tuần: 440k/đêm\n  - Cuối tuần: 480k/đêm\n\nBạn muốn đặt phòng ngày nào? 😊",
        "LOCATION":  "📍 Trăng Non Homestay\n17/14B Lương Văn Năm, KP3, P. Phú Trinh, Phan Thiết\n\n🏖️ Gần biển Đồi Dương (2km)\n🛒 Gần chợ & phố ăn uống (1.5km)\n☕ Gần café check-in (2km)",
        "MOTORBIKE": "🛵 Thuê xe ga: 150k/ngày (24 tiếng)\nCó Honda Vision hoặc Airblade\n\nLiên hệ: 083 285 0488 để đặt trước nhé!",
        "CONTACT":   "📞 Hotline: 083 285 0488\n🏠 17/14B Lương Văn Năm, Phan Thiết\n\nGọi hoặc nhắn tin bất cứ lúc nào! 😊",
        "GET_STARTED": "👋 Chào mừng đến với Trăng Non Homestay!\nGõ bất cứ điều gì để bắt đầu.",
    }
    reply = responses.get(payload)
    if reply:
        send_text(sender_id, reply)
    else:
        reply = ask_groq(sender_id, postback.get("title", payload))
        send_text(sender_id, reply)


def ask_groq(sender_id: str, user_text: str) -> str:
    history = conversation_history.setdefault(sender_id, [])
    history.append({"role": "user", "content": user_text})
    if len(history) > MAX_HISTORY * 2:
        history[:] = history[-(MAX_HISTORY * 2):]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    try:
        resp = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "max_tokens": 300,
                "temperature": 0.7,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        reply_text = data["choices"][0]["message"]["content"].strip()
        history.append({"role": "assistant", "content": reply_text})
        return reply_text

    except requests.exceptions.Timeout:
        return "⏱️ Mình đang bận, bạn thử lại sau vài giây nhé!"
    except Exception as e:
        print(f"❌ Lỗi Groq: {e}")
        return "Xin lỗi, hệ thống đang bận. Vui lòng liên hệ hotline 083 285 0488 để được hỗ trợ nhé! 🙏"


def send_text(recipient_id: str, text: str):
    _send({"recipient": {"id": recipient_id}, "message": {"text": text}})


def send_quick_replies(recipient_id: str, text: str, replies: list):
    _send({
        "recipient": {"id": recipient_id},
        "message": {
            "text": text,
            "quick_replies": [
                {"content_type": "text", "title": r["title"], "payload": r["payload"]}
                for r in replies
            ],
        },
    })


def _send(payload: dict):
    resp = requests.post(
        GRAPH_API_URL,
        params={"access_token": PAGE_ACCESS_TOKEN},
        json=payload,
        timeout=10,
    )
    if not resp.ok:
        print(f"❌ Lỗi gửi tin: {resp.status_code} – {resp.text}")
    return resp


def verify_signature(payload: bytes, signature: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
