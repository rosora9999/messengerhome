import os
import hmac
import hashlib
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# =============================================
# CẤU HÌNH
# =============================================
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "YOUR_PAGE_ACCESS_TOKEN")
VERIFY_TOKEN      = os.environ.get("VERIFY_TOKEN", "YOUR_VERIFY_TOKEN")
APP_SECRET        = os.environ.get("APP_SECRET", "YOUR_APP_SECRET")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")

GRAPH_API_URL  = "https://graph.facebook.com/v19.0/me/messages"
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash-lite:generateContent"
)

# =============================================
# SYSTEM PROMPT — chỉnh theo business của bạn
# =============================================
SYSTEM_PROMPT = """Bạn là trợ lý AI của Homestay Trăng Non tại Phan Thiết.
Nhiệm vụ: tư vấn và hỗ trợ khách hàng qua Facebook Messenger.

Quy tắc trả lời:
- Luôn trả lời bằng tiếng Việt, thân thiện, nhiệt tình như nhân viên lễ tân
- Ngắn gọn, dễ hiểu (dưới 200 từ)
- Dùng emoji phù hợp để tin nhắn sinh động hơn
- Không bịa thông tin nếu không chắc chắn
- Nếu khách muốn đặt phòng, hỏi: tên, ngày check-in, ngày check-out, số người
- Nếu câu hỏi phức tạp hoặc khách muốn xác nhận đặt phòng, nhờ khách để lại SĐT để chủ nhà liên hệ lại

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
- Nằm ở trung tâm Phan Thiết, yên tĩnh, phù hợp nghỉ dưỡng
- Gần biển Đồi Dương và Thương Chánh (2km)
- Gần chợ Phan Thiết & phố ăn uống (1.5km)
- Gần café check-in: Mơ Hoang, Café Bồng Bềnh (2km)
- Dễ di chuyển đến Mũi Né, NovaWorld, quán café ven biển (12km)
"""

# Lưu lịch sử hội thoại theo sender_id (in-memory)
# Mỗi user giữ tối đa 10 lượt để tránh token quá dài
conversation_history: dict[str, list] = {}
MAX_HISTORY = 10


# =============================================
# XÁC THỰC WEBHOOK
# =============================================
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook đã được xác thực!")
        return challenge, 200
    return "Forbidden", 403


# =============================================
# NHẬN TIN NHẮN TỪ FACEBOOK
# =============================================
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


# =============================================
# XỬ LÝ TIN NHẮN
# =============================================
def handle_message(sender_id: str, message: dict):
    text = message.get("text", "").strip()

    if not text:
        send_text(sender_id, "Mình chưa đọc được tin nhắn này 😅 Bạn thử gửi text nhé!")
        return

    # Các lệnh đặc biệt — xử lý trước khi gọi AI
    lower = text.lower()
    if lower in ("hi", "hello", "xin chào", "chào", "bắt đầu"):
        send_quick_replies(
            sender_id,
            "👋 Xin chào! Mình là trợ lý AI, có thể giúp gì cho bạn?",
            [
                {"title": "📦 Sản phẩm", "payload": "PRODUCTS"},
                {"title": "📞 Liên hệ",  "payload": "CONTACT"},
                {"title": "❓ Hỗ trợ",   "payload": "SUPPORT"},
            ],
        )
        return

    if lower in ("/reset", "xóa lịch sử"):
        conversation_history.pop(sender_id, None)
        send_text(sender_id, "🔄 Đã xóa lịch sử hội thoại. Chúng ta bắt đầu lại nhé!")
        return

    # Gọi Gemini AI
    reply = ask_gemini(sender_id, text)
    send_text(sender_id, reply)


# =============================================
# XỬ LÝ POSTBACK
# =============================================
def handle_postback(sender_id: str, postback: dict):
    payload = postback.get("payload", "")

    responses = {
        "PRODUCTS":    "🛍️ Xem sản phẩm tại: https://example.com/products",
        "CONTACT":     "📞 Hotline: 1800-xxxx\n📧 Email: hello@example.com",
        "SUPPORT":     "🆘 Bạn gặp vấn đề gì? Cứ mô tả, mình sẽ hỗ trợ ngay!",
        "GET_STARTED": "👋 Chào mừng! Gõ bất cứ điều gì để bắt đầu.",
    }

    reply = responses.get(payload)
    if reply:
        send_text(sender_id, reply)
    else:
        # Postback không có sẵn → cho AI trả lời
        ask_and_send(sender_id, postback.get("title", payload))


# =============================================
# GEMINI AI
# =============================================
def ask_gemini(sender_id: str, user_text: str) -> str:
    """Gửi tin nhắn đến Gemini Flash, có nhớ lịch sử hội thoại."""

    # Lấy hoặc tạo lịch sử
    history = conversation_history.setdefault(sender_id, [])

    # Thêm tin nhắn mới của user
    history.append({"role": "user", "parts": [{"text": user_text}]})

    # Giữ tối đa MAX_HISTORY lượt (mỗi lượt = 1 user + 1 model)
    if len(history) > MAX_HISTORY * 2:
        history[:] = history[-(MAX_HISTORY * 2):]

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": history,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 300,
        },
    }

    try:
        resp = requests.post(
            GEMINI_API_URL,
            params={"key": GEMINI_API_KEY},
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        reply_text = (
            data["candidates"][0]["content"]["parts"][0]["text"].strip()
        )

        # Lưu câu trả lời của AI vào lịch sử
        history.append({"role": "model", "parts": [{"text": reply_text}]})

        return reply_text

    except requests.exceptions.Timeout:
        return "⏱️ AI đang bận, bạn thử lại sau vài giây nhé!"
    except Exception as e:
        print(f"❌ Lỗi Gemini: {e}")
        return "Xin lỗi, mình đang gặp sự cố kỹ thuật. Bạn liên hệ hotline 1800-xxxx để được hỗ trợ nhé!"


def ask_and_send(sender_id: str, text: str):
    reply = ask_gemini(sender_id, text)
    send_text(sender_id, reply)


# =============================================
# GỬI TIN NHẮN
# =============================================
def send_text(recipient_id: str, text: str):
    _send({
        "recipient": {"id": recipient_id},
        "message":   {"text": text},
    })


def send_quick_replies(recipient_id: str, text: str, replies: list):
    _send({
        "recipient": {"id": recipient_id},
        "message": {
            "text": text,
            "quick_replies": [
                {
                    "content_type": "text",
                    "title":   r["title"],
                    "payload": r["payload"],
                }
                for r in replies
            ],
        },
    })


def send_image(recipient_id: str, image_url: str):
    _send({
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {"url": image_url, "is_reusable": True},
            }
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


# =============================================
# BẢO MẬT
# =============================================
def verify_signature(payload: bytes, signature: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        APP_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


# =============================================
# KHỞI ĐỘNG
# =============================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
