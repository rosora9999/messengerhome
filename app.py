import os
import hmac
import hashlib
import random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import requests
from date_parser import parse_date_range

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "YOUR_PAGE_ACCESS_TOKEN")
VERIFY_TOKEN      = os.environ.get("VERIFY_TOKEN", "YOUR_VERIFY_TOKEN")
APP_SECRET        = os.environ.get("APP_SECRET", "YOUR_APP_SECRET")
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY")
GOHOST_API_KEY    = os.environ.get("GOHOST_API_KEY", "YOUR_GOHOST_API_KEY")
GOHOST_API_SECRET = os.environ.get("GOHOST_API_SECRET", "YOUR_GOHOST_API_SECRET")

GRAPH_API_URL  = "https://graph.facebook.com/v19.0/me/messages"
GROQ_API_URL   = "https://api.groq.com/openai/v1/chat/completions"
GOHOST_API_URL = "https://platform.gohost.vn/pms/api/public/v1"

TENANT_ID       = "9d37978e-2409-402d-a286-082d82f91c27"
ROOM_TIEU_CHUAN = "6c621484-9b51-46de-8448-917bb677e14d"
ROOM_CAO_CAP    = "c7613c8a-5f93-4d71-8ae0-1ee24a2e6585"

PHOTOS_TIEU_CHUAN = [
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780480966/1_8_cw4v9l.jpg",
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780480966/1_1_o2qntc.jpg",
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780480955/1_3_parrlk.jpg",
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780480954/1_6_o8dujo.jpg",
    "https://res.cloudinary.com/dlmttxts9/image/upload/v1780480953/1_5_u149j2.jpg",
]
PHOTO_PAYMENT = "https://res.cloudinary.com/dlmttxts9/image/upload/v1780482041/stk_Thien_bidv_ebjjd5.jpg"
PHOTO_LUU_Y   = "https://res.cloudinary.com/dlmttxts9/image/upload/v1780482638/luu_y_kulrzc.jpg"

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
- Nếu khách hỏi xem ảnh phòng tiêu chuẩn, trả lời đúng: "SEND_PHOTOS_TIEU_CHUAN"
- Nếu khách hỏi xem ảnh phòng cao cấp, trả lời đúng: "SEND_PHOTOS_CAO_CAP"
- Nếu khách hỏi xem ảnh phòng (không nói rõ loại), hỏi lại: muốn xem phòng tiêu chuẩn hay cao cấp?
- Nếu khách hỏi phòng còn trống không / còn phòng không (không có ngày cụ thể), trả lời: "CHECK_AVAILABILITY"
- Nếu khách muốn đặt phòng, hỏi đủ: tên, SĐT, ngày check-in, ngày check-out, số người, loại phòng
- Sau khi có đủ thông tin đặt phòng, trả lời đúng: "SEND_PAYMENT_INFO"
- Hotline: 083 285 0488

=== THÔNG TIN PHÒNG ===
Tổng cộng 3 phòng:
1. Phòng Tiêu Chuẩn (2 phòng): Trong tuần 370k, cuối tuần 400k/đêm
2. Phòng Cao Cấp (1 phòng): Trong tuần 440k, cuối tuần 480k/đêm

=== GIỜ CHECK-IN / CHECK-OUT ===
Check-in: 14:00 / Check-out: 12:00 / Sớm/trễ: phụ phí 50k/giờ

=== XE THUÊ ===
Xe ga 150k/ngày (24h) — Honda Vision hoặc Airblade

=== ĐỖ XE HƠI ===
Không có bãi xe hơi. Đậu đường Lê Duẩn, đi bộ vào ~50m, tự bảo quản xe.

=== CHÍNH SÁCH THÚ CƯNG ===
Dưới 4kg, phụ thu 50k/con/đêm. Khách tự dọn chất thải.

=== VỊ TRÍ ===
17/14B Lương Văn Năm, KP3, P. Phú Trinh, Phan Thiết
Gần biển Đồi Dương (2km), chợ (1.5km), café Mơ Hoang/Bồng Bềnh (2km), Mũi Né (12km)
"""

conversation_history: dict[str, list] = {}
MAX_HISTORY = 10

# Từ khóa liên quan đến ngày tháng
DATE_KEYWORDS = [
    "ngày", "tháng", "tuần", "hôm nay", "ngày mai", "ngày kia",
    "thứ", "cuối tuần", "còn phòng", "có phòng", "trống không",
    "check", "đặt phòng", "/", "-"
]


def gohost_headers():
    return {
        "Authorization": f"Bearer {GOHOST_API_KEY}:{GOHOST_API_SECRET}",
        "Accept": "application/json",
    }


def check_room_availability(checkin: str, checkout: str) -> str:
    try:
        resp = requests.get(
            f"{GOHOST_API_URL}/properties/{TENANT_ID}/bookings",
            headers=gohost_headers(),
            params={
                "start_date": checkin,
                "end_date": checkout,
                "per_page": 50,
            },
            timeout=10,
        )
        resp.raise_for_status()
        bookings = resp.json().get("data", [])

        # Bỏ qua booking đã hủy
        active = [b for b in bookings if b.get("status") not in ("cancelled", "no_show")]
        booked_tc = sum(1 for b in active if b.get("room_type_id") == ROOM_TIEU_CHUAN)
        booked_cc = sum(1 for b in active if b.get("room_type_id") == ROOM_CAO_CAP)

        con_tc = max(0, 2 - booked_tc)
        con_cc = max(0, 1 - booked_cc)

        # Format ngày hiển thị
        ci = datetime.strptime(checkin, "%Y-%m-%d").strftime("%d/%m/%Y")
        co = datetime.strptime(checkout, "%Y-%m-%d").strftime("%d/%m/%Y")

        result = f"Tình trạng phòng {ci} - {co}:\n\n"
        result += f"Phong Tieu Chuan: {'Con ' + str(con_tc) + ' phong' if con_tc > 0 else 'Het phong'}\n"
        result += f"Phong Cao Cap: {'Con phong' if con_cc > 0 else 'Het phong'}\n"

        if con_tc == 0 and con_cc == 0:
            result += "\nRat tiec het phong trong thoi gian nay. Ban thu ngay khac hoac lien he 083 285 0488."
        else:
            result += "\nBan muon dat phong loai nao?"
        return result

    except Exception as e:
        print(f"Loi GoHost: {e}")
        return "Hien khong kiem tra duoc lich phong. Vui long lien he 083 285 0488 de kiem tra truc tiep nhe!"


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
                print(f"SENDER_ID: {sender_id}")
                if "message" in event:
                    handle_message(sender_id, event["message"])
                elif "postback" in event:
                    handle_postback(sender_id, event["postback"])
    return jsonify({"status": "ok"}), 200


def handle_message(sender_id: str, message: dict):
    text = message.get("text", "").strip()
    if not text:
        send_text(sender_id, "Minh chua doc duoc tin nhan nay. Ban thu gui text nhe!")
        return

    lower = text.lower()

    if lower in ("hi", "hello", "xin chào", "chào", "bắt đầu"):
        send_quick_replies(
            sender_id,
            "Chao mung den voi Trang Non Homestay! Minh co the giup gi cho ban?",
            [
                {"title": "Gia phong",      "payload": "PRICES"},
                {"title": "Kiem tra phong", "payload": "CHECK_AVAIL_MENU"},
                {"title": "Xem anh phong",  "payload": "PHOTOS_MENU"},
                {"title": "Lien he",        "payload": "CONTACT"},
            ],
        )
        return

    if lower in ("/reset", "xóa lịch sử"):
        conversation_history.pop(sender_id, None)
        send_text(sender_id, "Da xoa lich su. Chung ta bat dau lai nhe!")
        return

    # Tự động parse ngày nếu text có chứa từ khóa ngày tháng
    if any(kw in lower for kw in DATE_KEYWORDS):
        checkin, checkout = parse_date_range(lower)
        if checkin and checkout:
            result = check_room_availability(checkin, checkout)
            send_text(sender_id, result)
            return

    reply = ask_groq(sender_id, text)

    if "SEND_PHOTOS_TIEU_CHUAN" in reply:
        send_text(sender_id, "Anh phong Tieu Chuan:")
        send_photos(sender_id, PHOTOS_TIEU_CHUAN, limit=4)
    elif "SEND_PHOTOS_CAO_CAP" in reply:
        send_text(sender_id, "Anh phong Cao Cap:")
        send_photos(sender_id, PHOTOS_CAO_CAP, limit=4)
    elif "SEND_PAYMENT_INFO" in reply:
        send_text(sender_id, "Vui long chuyen khoan de dat phong:")
        _send({"recipient": {"id": sender_id}, "message": {"attachment": {"type": "image", "payload": {"url": PHOTO_PAYMENT, "is_reusable": True}}}})
        import time; time.sleep(1)
        send_text(sender_id, "Luu y khi o tai Trang Non Homestay:")
        _send({"recipient": {"id": sender_id}, "message": {"attachment": {"type": "image", "payload": {"url": PHOTO_LUU_Y, "is_reusable": True}}}})
        import time; time.sleep(1)
        send_text(sender_id, "Cam on ban da tin tuong va lua chon Trang Non Homestay. Hen gap ban tai Phan Thiet nhe! Moi thac mac lien he 083 285 0488.")
    elif "CHECK_AVAILABILITY" in reply:
        send_quick_replies(
            sender_id,
            "Ban muon kiem tra phong thoi gian nao? Nhan ngay thang hoac chon:",
            [
                {"title": "Cuoi tuan nay", "payload": "AVAIL_THIS_WEEKEND"},
                {"title": "Tuan toi",      "payload": "AVAIL_NEXT_WEEK"},
            ],
        )
    else:
        send_text(sender_id, reply)


def handle_postback(sender_id: str, postback: dict):
    payload = postback.get("payload", "")

    if payload == "PHOTOS_MENU":
        send_quick_replies(sender_id, "Ban muon xem anh phong nao?", [
            {"title": "Phong Tieu Chuan", "payload": "PHOTOS_TIEU_CHUAN"},
            {"title": "Phong Cao Cap",    "payload": "PHOTOS_CAO_CAP"},
        ])
        return

    if payload == "PHOTOS_TIEU_CHUAN":
        send_text(sender_id, "Anh phong Tieu Chuan:")
        send_photos(sender_id, PHOTOS_TIEU_CHUAN, limit=4)
        return

    if payload == "PHOTOS_CAO_CAP":
        send_text(sender_id, "Anh phong Cao Cap:")
        send_photos(sender_id, PHOTOS_CAO_CAP, limit=4)
        return

    if payload == "CHECK_AVAIL_MENU":
        send_quick_replies(sender_id, "Ban muon kiem tra phong thoi gian nao?", [
            {"title": "Cuoi tuan nay", "payload": "AVAIL_THIS_WEEKEND"},
            {"title": "Tuan toi",      "payload": "AVAIL_NEXT_WEEK"},
            {"title": "Nhap ngay khac","payload": "AVAIL_CUSTOM"},
        ])
        return

    if payload == "AVAIL_THIS_WEEKEND":
        today = datetime.now()
        days_to_sat = (5 - today.weekday()) % 7 or 7
        sat = today + timedelta(days=days_to_sat)
        sun = sat + timedelta(days=1)
        send_text(sender_id, check_room_availability(sat.strftime("%Y-%m-%d"), sun.strftime("%Y-%m-%d")))
        return

    if payload == "AVAIL_NEXT_WEEK":
        today = datetime.now()
        next_mon = today + timedelta(days=(7 - today.weekday()))
        next_sun = next_mon + timedelta(days=6)
        send_text(sender_id, check_room_availability(next_mon.strftime("%Y-%m-%d"), next_sun.strftime("%Y-%m-%d")))
        return

    if payload == "AVAIL_CUSTOM":
        send_text(sender_id, "Ban nhan ngay muon check-in, vi du:\n- 15/6\n- 15/6 - 17/6\n- thu 6\n- cuoi tuan nay")
        return

    responses = {
        "PRICES":  "Gia phong Trang Non:\n\nPhong Tieu Chuan:\n- Trong tuan: 370k/dem\n- Cuoi tuan: 400k/dem\n\nPhong Cao Cap:\n- Trong tuan: 440k/dem\n- Cuoi tuan: 480k/dem",
        "CONTACT": "Hotline: 083 285 0488\n17/14B Luong Van Nam, Phan Thiet",
        "GET_STARTED": "Chao mung den voi Trang Non Homestay!",
    }
    reply = responses.get(payload)
    if reply:
        send_text(sender_id, reply)
    else:
        send_text(sender_id, ask_groq(sender_id, postback.get("title", payload)))


def ask_groq(sender_id: str, user_text: str) -> str:
    history = conversation_history.setdefault(sender_id, [])
    history.append({"role": "user", "content": user_text})
    if len(history) > MAX_HISTORY * 2:
        history[:] = history[-(MAX_HISTORY * 2):]

    try:
        resp = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history,
                "max_tokens": 300,
                "temperature": 0.7,
            },
            timeout=15,
        )
        resp.raise_for_status()
        reply_text = resp.json()["choices"][0]["message"]["content"].strip()
        history.append({"role": "assistant", "content": reply_text})
        return reply_text
    except requests.exceptions.Timeout:
        return "Minh dang ban, ban thu lai sau vai giay nhe!"
    except Exception as e:
        print(f"Loi Groq: {e}")
        return "Xin loi, he thong dang ban. Lien he 083 285 0488 de duoc ho tro nhe!"


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


def send_photos(recipient_id: str, photos: list, limit: int = 4):
    selected = random.sample(photos, min(limit, len(photos)))
    for url in selected:
        _send({
            "recipient": {"id": recipient_id},
            "message": {"attachment": {"type": "image", "payload": {"url": url, "is_reusable": True}}},
        })


def _send(payload: dict):
    resp = requests.post(
        GRAPH_API_URL,
        params={"access_token": PAGE_ACCESS_TOKEN},
        json=payload,
        timeout=10,
    )
    if not resp.ok:
        print(f"Loi gui tin: {resp.status_code} - {resp.text}")
    return resp


def verify_signature(payload: bytes, signature: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
