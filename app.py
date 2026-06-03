import os
import hmac
import hashlib
import random
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "YOUR_PAGE_ACCESS_TOKEN")
VERIFY_TOKEN      = os.environ.get("VERIFY_TOKEN", "YOUR_VERIFY_TOKEN")
APP_SECRET        = os.environ.get("APP_SECRET", "YOUR_APP_SECRET")
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY")

GRAPH_API_URL = "https://graph.facebook.com/v19.0/me/messages"
GROQ_API_URL  = "https://api.groq.com/openai/v1/chat/completions"

# =============================================
# ẢNH PHÒNG
# =============================================
PHOTOS_TIEU_CHUAN = [
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780480966/1_8_cw4v9l.jpg",
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780480966/1_1_o2qntc.jpg",
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780480955/1_3_parrlk.jpg",
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780480954/1_6_o8dujo.jpg",
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780480953/1_5_u149j2.jpg",
]

PHOTOS_CAO_CAP = [
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780481177/IMG_9994_b9cxiv.jpg",
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780481177/IMG_0220_pb3njf.jpg",
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780481175/IMG_9986_sh2i9u.jpg",
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780481158/IMG_9969_w5yy5n.jpg",
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780481157/IMG_0145_gouf2q.jpg",
]

SYSTEM_PROMPT = """Bạn là trợ lý AI của Homestay Trăng Non tại Phan Thiết.
Nhiệm vụ: tư vấn và hỗ trợ khách hàng qua Facebook Messenger.

Quy tắc trả lời:
- Luôn trả lời bằng tiếng Việt, thân thiện, nhiệt tình như nhân viên lễ tân
- Ngắn gọn, dễ hiểu (dưới 200 từ)
- KHÔNG dùng emoji trong câu trả lời
- KHÔNG bắt đầu bằng lời chào như "Xin chào", "Chào bạn" cho mỗi tin nhắn
- Trả lời thẳng vào câu hỏi của khách
- Không bịa thông tin nếu không chắc chắn
- Nếu khách muốn đặt phòng, hỏi: tên, ngày check-in, ngày check-out, số người
- Nếu khách hỏi xem ảnh phòng tiêu chuẩn, trả lời: "SEND_PHOTOS_TIEU_CHUAN"
- Nếu khách hỏi xem ảnh phòng cao cấp, trả lời: "SEND_PHOTOS_CAO_CAP"
- Nếu khách hỏi xem ảnh phòng (không nói rõ loại), hỏi lại: muốn xem phòng tiêu chuẩn hay cao cấp?
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

=== CHÍNH SÁCH THÚ CƯNG ===
- Chỉ nhận thú nuôi nhỏ dưới 4kg
- Phụ thu 50.000đ/thú nuôi/đêm
- Khách tự dọn chất thải, nếu homestay phải dọn sẽ thu phí 50.000đ - 200.000đ
- Khách chịu trách nhiệm đền bù tài sản theo giá mua mới nếu có thiệt hại

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
        send_text(sender_id, "Mình chưa đọc được tin nhắn này. Bạn thử gửi text nhé!")
        return

    lower = text.lower()
    if lower in ("hi", "hello", "xin chào", "chào", "bắt đầu"):
        send_quick_replies(
            sender_id,
            "Chào mừng đến với Trăng Non Homestay! Mình có thể giúp gì cho bạn?",
            [
                {"title": "Giá phòng",    "payload": "PRICES"},
                {"title": "Xem ảnh phòng","payload": "PHOTOS_MENU"},
                {"title": "Vị trí",       "payload": "LOCATION"},
                {"title": "Liên hệ",      "payload": "CONTACT"},
            ],
        )
        return

    if lower in ("/reset", "xóa lịch sử"):
        conversation_history.pop(sender_id, None)
        send_text(sender_id, "Đã xóa lịch sử. Chúng ta bắt đầu lại nhé!")
        return

    reply = ask_groq(sender_id, text)

    # Kiểm tra nếu AI muốn gửi ảnh
    if "SEND_PHOTOS_TIEU_CHUAN" in reply:
        send_text(sender_id, "Đây là ảnh phòng Tiêu Chuẩn:")
        send_photos(sender_id, PHOTOS_TIEU_CHUAN, limit=4)
    elif "SEND_PHOTOS_CAO_CAP" in reply:
        send_text(sender_id, "Đây là ảnh phòng Cao Cấp:")
        send_photos(sender_id, PHOTOS_CAO_CAP, limit=4)
    else:
        send_text(sender_id, reply)


def handle_postback(sender_id: str, postback: dict):
    payload = postback.get("payload", "")

    if payload == "PHOTOS_MENU":
        send_quick_replies(
            sender_id,
            "Bạn muốn xem ảnh phòng nào?",
            [
                {"title": "Phòng Tiêu Chuẩn", "payload": "PHOTOS_TIEU_CHUAN"},
                {"title": "Phòng Cao Cấp",    "payload": "PHOTOS_CAO_CAP"},
            ],
        )
        return

    if payload == "PHOTOS_TIEU_CHUAN":
        send_text(sender_id, "Đây là ảnh phòng Tiêu Chuẩn:")
        send_photos(sender_id, PHOTOS_TIEU_CHUAN, limit=4)
        return

    if payload == "PHOTOS_CAO_CAP":
        send_text(sender_id, "Đây là ảnh phòng Cao Cấp:")
        send_photos(sender_id, PHOTOS_CAO_CAP, limit=4)
        return

    responses = {
        "PRICES":   "Giá phòng Trăng Non:\n\nPhòng Tiêu Chuẩn:\n- Trong tuần: 370k/đêm\n- Cuối tuần: 400k/đêm\n\nPhòng Cao Cấp:\n- Trong tuần: 440k/đêm\n- Cuối tuần: 480k/đêm\n\nBạn muốn đặt phòng ngày nào?",
        "LOCATION": "Trăng Non Homestay\n17/14B Lương Văn Năm, KP3, P. Phú Trinh, Phan Thiết\n\nGần biển Đồi Dương (2km)\nGần chợ & phố ăn uống (1.5km)\nGần café check-in (2km)",
        "CONTACT":  "Hotline: 083 285 0488\n17/14B Lương Văn Năm, Phan Thiết\n\nGọi hoặc nhắn tin bất cứ lúc nào!",
        "GET_STARTED": "Chào mừng đến với Trăng Non Homestay! Gõ bất cứ điều gì để bắt đầu.",
    }
    reply = responses.get(payload)
    if reply:
        send_text(sender_id, reply)
    else:
        reply = ask_groq(sender_id, postback.get("title", payload))
        send_text(sender_id, reply)


def send_photos(recipient_id: str, photos: list, limit: int = 4):
    """Gửi tối đa `limit` ảnh, chọn ngẫu nhiên nếu có nhiều hơn."""
    selected = random.sample(photos, min(limit, len(photos)))
    for url in selected:
        _send({
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": "image",
                    "payload": {"url": url, "is_reusable": True},
                }
            },
        })


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
        return "Mình đang bận, bạn thử lại sau vài giây nhé!"
    except Exception as e:
        print(f"Lỗi Groq: {e}")
        return "Xin lỗi, hệ thống đang bận. Vui lòng liên hệ hotline 083 285 0488 để được hỗ trợ nhé!"


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
        print(f"Lỗi gửi tin: {resp.status_code} - {resp.text}")
    return resp


def verify_signature(payload: bytes, signature: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
