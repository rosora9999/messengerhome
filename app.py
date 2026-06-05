import os
import hmac
import hashlib
import random
import re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import requests
from date_parser import parse_date_range

app = Flask(__name__)

@app.after_request
def add_ngrok_header(response):
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN      = os.environ.get("VERIFY_TOKEN", "")
APP_SECRET        = os.environ.get("APP_SECRET", "")
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY", "")
GOHOST_API_KEY    = os.environ.get("GOHOST_API_KEY", "")
GOHOST_API_SECRET = os.environ.get("GOHOST_API_SECRET", "")

GRAPH_API_URL  = "https://graph.facebook.com/v19.0/me/messages"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
GOHOST_API_URL = "https://platform.gohost.vn/pms/api/public/v1"

TENANT_ID       = "9d37978e-2409-402d-a286-082d82f91c27"
ROOM_TIEU_CHUAN = "6c621484-9b51-46de-8448-917bb677e14d"
ROOM_CAO_CAP    = "c7613c8a-5f93-4d71-8ae0-1ee24a2e6585"
OWNER_ID        = "9639287556127249"

PHOTO_PAYMENT = "https://res.cloudinary.com/dlmttxts9/image/upload/v1780482041/stk_Thien_bidv_ebjjd5.jpg"
PHOTO_LUU_Y   = "https://res.cloudinary.com/dlmttxts9/image/upload/v1780482638/luu_y_kulrzc.jpg"

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

PHONG CÁCH GIAO TIẾP:
- Tự xưng là "home", gọi khách là "bạn"
- Nhắn tin ngắn gọn, tự nhiên như nhắn Zalo
- Mỗi ý một dòng ngắn, thân thiện, đôi khi dùng "ạ", "nha", "nhé", "à"
- KHÔNG dùng emoji
- Luôn viết tiếng Việt có đầy đủ dấu

QUY TẮC XỬ LÝ:
- Nếu bạn hỏi xem ảnh phòng tiêu chuẩn → trả lời đúng: "SEND_PHOTOS_TIEU_CHUAN"
- Nếu bạn hỏi xem ảnh phòng cao cấp → trả lời đúng: "SEND_PHOTOS_CAO_CAP"
- Nếu bạn hỏi xem ảnh phòng không rõ loại → hỏi lại loại phòng
- Nếu bạn hỏi còn phòng không (không có ngày) → trả lời: "CHECK_AVAILABILITY"
- Khi tính giá: thứ 2-5 là trong tuần, thứ 6-7-CN và lễ tết là cuối tuần
- Hotline: 083 285 0488

QUY TẮC KHI KHÁCH HỎI PHÒNG:
1. Hỏi ngày check-in và check-out
2. Sau khi có ngày → trả lời: "CHECK_AVAILABILITY_WITH_DATE" để hệ thống kiểm tra và báo phòng còn trống + giá
3. KHÔNG hỏi khách muốn loại phòng nào — hệ thống tự báo còn phòng nào

QUY TẮC ĐẶT PHÒNG - RẤT QUAN TRỌNG:
- Khi khách nói muốn đặt phòng → dựa vào thông tin check-in/out đã có → NGAY LẬP TỨC trả lời: "SEND_PAYMENT_INFO"
- KHÔNG hỏi thêm tên, số điện thoại, loại phòng, số người hay bất kỳ thông tin nào khác
- Ví dụ: khách đã nói in 27/6 out 28/6, sau đó nói "đặt phòng" → trả lời "SEND_PAYMENT_INFO" ngay

=== THÔNG TIN PHÒNG ===
1. Phòng Tiêu Chuẩn (2 phòng): Trong tuần 370k, cuối tuần 400k/đêm
2. Phòng Cao Cấp (1 phòng): Trong tuần 440k, cuối tuần 480k/đêm

=== GIỜ CHECK-IN / CHECK-OUT ===
Check-in: 14:00 / Check-out: 12:00 / Sớm-trễ: phụ phí 50k/giờ

=== CHÍNH SÁCH CỌC ===
- Cọc 50% tổng tiền phòng để giữ phòng (ít hơn vẫn ok)
- KHÔNG giữ phòng nếu không cọc

=== CHÍNH SÁCH HỦY / ĐỔI NGÀY ===
- Hủy trước 7 ngày: hoàn 100% cọc
- Hủy trong vòng 7 ngày: thu 50% cọc
- Hủy trong vòng 1 ngày: thu 100% cọc

=== XE THUÊ ===
Xe ga 150k/ngày (24h) — Honda Vision hoặc Airblade

=== ĐỖ XE HƠI ===
Không có bãi xe. Đậu đường Lê Duẩn, đi bộ vào 50m, tự bảo quản.

=== CHÍNH SÁCH THÚ CƯNG ===
Dưới 4kg, phụ thu 50k/con/đêm. Khách tự dọn chất thải.

=== VỊ TRÍ ===
17/14B Lương Văn Năm, KP3, P. Phú Trinh, Phan Thiết
Gần biển Đồi Dương (2km), chợ (1.5km), café Mơ Hoang/Bồng Bềnh (2km), Mũi Né (12km)
"""

conversation_history: dict = {}
pending_bookings: dict = {}
MAX_HISTORY = 10

CHECK_TRIGGERS = ["còn phòng", "con phong", "có phòng", "co phong", "trống không", "kiểm tra phòng"]
DATE_TRIGGERS  = ["ngày mai", "cuối tuần", "thứ ", "tuần tới"]
CK_KEYWORDS    = ["đã cọc", "cọc rồi", "đã chuyển", "chuyển rồi", "đã thanh toán",
                  "cọc xong", "chuyển xong", "ck rồi", "ck xong", "đã ck",
                  "chuyển khoản rồi", "chuyển khoản xong", "đã chuyển khoản",
                  "ck", "chuyển r", "đã chuyển tiền", "da coc", "coc roi"]


def gohost_headers():
    return {
        "Authorization": f"Bearer {GOHOST_API_KEY}:{GOHOST_API_SECRET}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def check_room_availability(checkin: str, checkout: str) -> str:
    try:
        ci_dt = datetime.strptime(checkin, "%Y-%m-%d")
        co_dt = datetime.strptime(checkout, "%Y-%m-%d")
        start = (ci_dt - timedelta(days=1)).strftime("%Y-%m-%d")

        resp = requests.get(
            f"{GOHOST_API_URL}/properties/{TENANT_ID}/bookings",
            headers=gohost_headers(),
            params={"start_date": start, "end_date": checkout, "per_page": 50},
            timeout=10,
        )
        resp.raise_for_status()
        bookings = resp.json().get("data", [])

        active = []
        for b in bookings:
            if b.get("status") in ("cancelled", "no_show"):
                continue
            b_ci = datetime.strptime(b.get("checkin_date", "2000-01-01"), "%Y-%m-%d")
            b_co = datetime.strptime(b.get("checkout_date", "2000-01-01"), "%Y-%m-%d")
            if b_ci < co_dt and b_co > ci_dt:
                active.append(b)

        booked_tc = 0
        booked_cc = 0
        for b in active:
            for r in b.get("booking_rooms", []):
                room_type = r.get("room_type", "").lower()
                if "tieu chuan" in room_type or "tiêu chuẩn" in room_type:
                    booked_tc += 1
                elif "cao cap" in room_type or "cao cấp" in room_type:
                    booked_cc += 1

        con_tc = max(0, 2 - booked_tc)
        con_cc = max(0, 1 - booked_cc)

        ci = ci_dt.strftime("%d/%m/%Y")
        co = co_dt.strftime("%d/%m/%Y")
        result = f"Tình trạng phòng {ci} - {co}:\n\n"
        result += f"Phòng Tiêu Chuẩn: {'Còn ' + str(con_tc) + ' phòng' if con_tc > 0 else 'Hết phòng'}\n"
        result += f"Phòng Cao Cấp: {'Còn phòng' if con_cc > 0 else 'Hết phòng'}\n"
        if con_tc == 0 and con_cc == 0:
            result += "\nRất tiếc hết phòng. Bạn thử ngày khác hoặc liên hệ 083 285 0488."
        else:
            result += "\nBạn muốn đặt phòng loại nào?"
        return result
    except Exception as e:
        print(f"Lỗi GoHost: {e}")
        return "Hiện không kiểm tra được lịch phòng. Liên hệ 083 285 0488 nhé!"


def create_gohost_booking(info: dict) -> bool:
    try:
        room_type_id = ROOM_CAO_CAP if "cao" in info.get("loai_phong", "").lower() else ROOM_TIEU_CHUAN
        resp = requests.post(
            f"{GOHOST_API_URL}/properties/{TENANT_ID}/bookings",
            headers=gohost_headers(),
            json={
                "room_type_id": room_type_id,
                "checkin_date": info["checkin"],
                "checkout_date": info["checkout"],
                "guest_name": info["ten"],
                "guest_phone": info.get("sdt", ""),
                "num_adults": 1,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"Lỗi tạo đơn GoHost: {e}")
        return False


def notify_owner(sender_id: str, info: dict):
    ci = datetime.strptime(info.get("checkin","2000-01-01"), "%Y-%m-%d").strftime("%d/%m/%Y") if info.get("checkin") else "?"
    co = datetime.strptime(info.get("checkout","2000-01-01"), "%Y-%m-%d").strftime("%d/%m/%Y") if info.get("checkout") else "?"
    msg = (
        f"ĐƠN ĐẶT PHÒNG MỚI!\n\n"
        f"Tên: {info.get('ten','?')}\n"
        f"Check-in: {ci}\n"
        f"Check-out: {co}\n"
        f"Loại phòng: {info.get('loai_phong','?')}\n\n"
        f"Khách đã báo đã cọc. Bạn kiểm tra và xác nhận nhé!"
    )
    _send({
        "recipient": {"id": OWNER_ID},
        "message": {
            "text": msg,
            "quick_replies": [
                {"content_type": "text", "title": "XÁC NHẬN ĐẶT PHÒNG", "payload": f"CONFIRM_BOOKING:{sender_id}"},
                {"content_type": "text", "title": "TỪ CHỐI", "payload": f"REJECT_BOOKING:{sender_id}"},
            ],
        },
    })


def extract_booking_info(history: list) -> dict:
    full_text = " ".join([m.get("content", "") for m in history])
    info = {"ten": "Khách", "sdt": "", "checkin": "", "checkout": "", "loai_phong": "Tiêu chuẩn"}
    sdt = re.search(r"(0\d{9})", full_text)
    if sdt:
        info["sdt"] = sdt.group(1)
    if "cao cấp" in full_text.lower() or "cao cap" in full_text.lower():
        info["loai_phong"] = "Cao cấp"
    checkin, checkout = parse_date_range(full_text)
    if checkin:
        info["checkin"] = checkin
        info["checkout"] = checkout or (datetime.strptime(checkin, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    return info


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
        send_text(sender_id, "Mình chưa đọc được tin nhắn này. Bạn thử gửi text nhé!")
        return

    lower = text.lower()

    if lower in ("hi", "hello", "xin chào", "chào", "bắt đầu"):
        send_quick_replies(
            sender_id,
            "Chào mừng đến với Trăng Non Homestay! Mình có thể giúp gì cho bạn?",
            [
                {"title": "Giá phòng",      "payload": "PRICES"},
                {"title": "Kiểm tra phòng", "payload": "CHECK_AVAIL_MENU"},
                {"title": "Xem ảnh phòng",  "payload": "PHOTOS_MENU"},
                {"title": "Liên hệ",        "payload": "CONTACT"},
            ],
        )
        return

    if lower in ("/reset", "xóa lịch sử"):
        conversation_history.pop(sender_id, None)
        send_text(sender_id, "Đã xóa lịch sử. Chúng ta bắt đầu lại nhé!")
        return

    # Khách báo đã cọc
    if any(kw in lower for kw in CK_KEYWORDS):
        send_text(sender_id, "Cảm ơn bạn đã chuyển khoản! Home sẽ kiểm tra và xác nhận sớm nhất nhé.")
        import time; time.sleep(1)
        send_text(sender_id, "Trong thời gian chờ, đây là một số lưu ý khi ở tại Trăng Non Homestay:")
        import time; time.sleep(1)
        _send({"recipient": {"id": sender_id}, "message": {"attachment": {"type": "image", "payload": {"url": PHOTO_LUU_Y, "is_reusable": True}}}})
        if sender_id in pending_bookings:
            import time; time.sleep(2)
            notify_owner(sender_id, pending_bookings[sender_id])
        return

    # Kiểm tra phòng tự động
    if any(kw in lower for kw in CHECK_TRIGGERS + DATE_TRIGGERS):
        checkin, checkout = parse_date_range(lower)
        if checkin and checkout:
            send_text(sender_id, check_room_availability(checkin, checkout))
            return

    reply = ask_openai(sender_id, text)

    if "SEND_PHOTOS_TIEU_CHUAN" in reply:
        send_text(sender_id, "Ảnh phòng Tiêu Chuẩn:")
        send_photos(sender_id, PHOTOS_TIEU_CHUAN)
    elif "SEND_PHOTOS_CAO_CAP" in reply:
        send_text(sender_id, "Ảnh phòng Cao Cấp:")
        send_photos(sender_id, PHOTOS_CAO_CAP)
    elif "SEND_PAYMENT_INFO" in reply:
        info = extract_booking_info(conversation_history.get(sender_id, []))
        pending_bookings[sender_id] = info
        send_text(sender_id, "Vui lòng chuyển khoản để giữ phòng (cọc tối thiểu 50% tổng tiền):")
        import time; time.sleep(1)
        _send({"recipient": {"id": sender_id}, "message": {"attachment": {"type": "image", "payload": {"url": PHOTO_PAYMENT, "is_reusable": True}}}})
        import time; time.sleep(1)
        send_text(sender_id, "Sau khi chuyển khoản xong, bạn nhắn 'đã cọc' để thông báo cho home nhé!")
    elif "CHECK_AVAILABILITY" in reply:
        send_quick_replies(sender_id, "Bạn muốn kiểm tra phòng thời gian nào?", [
            {"title": "Cuối tuần này", "payload": "AVAIL_THIS_WEEKEND"},
            {"title": "Tuần tới",      "payload": "AVAIL_NEXT_WEEK"},
            {"title": "Nhập ngày khác","payload": "AVAIL_CUSTOM"},
        ])
    else:
        send_text(sender_id, reply)


def handle_postback(sender_id: str, postback: dict):
    payload = postback.get("payload", "")

    if payload.startswith("CONFIRM_BOOKING:"):
        guest_id = payload.split(":")[1]
        info = pending_bookings.get(guest_id, {})
        if info:
            success = create_gohost_booking(info)
            if success:
                send_text(sender_id, f"Đã tạo đơn trên GoHost!\nKhách: {info.get('ten','?')}")
                send_text(guest_id, "Phòng của bạn đã được xác nhận! Hẹn gặp bạn tại Trăng Non Homestay. Liên hệ 083 285 0488 nếu cần nhé!")
                pending_bookings.pop(guest_id, None)
            else:
                send_text(sender_id, "Lỗi tạo đơn GoHost. Vui lòng tạo thủ công nhé!")
        return

    if payload.startswith("REJECT_BOOKING:"):
        guest_id = payload.split(":")[1]
        send_text(sender_id, "Đã từ chối đặt phòng.")
        send_text(guest_id, "Rất tiếc phòng chưa được xác nhận. Liên hệ 083 285 0488 để biết thêm nhé!")
        pending_bookings.pop(guest_id, None)
        return

    if payload == "PHOTOS_MENU":
        send_quick_replies(sender_id, "Bạn muốn xem ảnh phòng nào?", [
            {"title": "Phòng Tiêu Chuẩn", "payload": "PHOTOS_TIEU_CHUAN"},
            {"title": "Phòng Cao Cấp",    "payload": "PHOTOS_CAO_CAP"},
        ])
        return

    if payload == "PHOTOS_TIEU_CHUAN":
        send_text(sender_id, "Ảnh phòng Tiêu Chuẩn:")
        send_photos(sender_id, PHOTOS_TIEU_CHUAN)
        return

    if payload == "PHOTOS_CAO_CAP":
        send_text(sender_id, "Ảnh phòng Cao Cấp:")
        send_photos(sender_id, PHOTOS_CAO_CAP)
        return

    if payload == "CHECK_AVAIL_MENU":
        send_quick_replies(sender_id, "Bạn muốn kiểm tra phòng thời gian nào?", [
            {"title": "Cuối tuần này", "payload": "AVAIL_THIS_WEEKEND"},
            {"title": "Tuần tới",      "payload": "AVAIL_NEXT_WEEK"},
            {"title": "Nhập ngày khác","payload": "AVAIL_CUSTOM"},
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
        send_text(sender_id, "Bạn nhắn ngày muốn check-in, ví dụ:\n- 15/6\n- 15/6 - 17/6\n- thứ 6\n- cuối tuần này")
        return

    responses = {
        "PRICES":  "Giá phòng Trăng Non:\n\nPhòng Tiêu Chuẩn:\n- Trong tuần: 370k/đêm\n- Cuối tuần: 400k/đêm\n\nPhòng Cao Cấp:\n- Trong tuần: 440k/đêm\n- Cuối tuần: 480k/đêm",
        "CONTACT": "Hotline: 083 285 0488\n17/14B Lương Văn Năm, Phan Thiết",
        "GET_STARTED": "Chào mừng đến với Trăng Non Homestay!",
    }
    reply = responses.get(payload)
    if reply:
        send_text(sender_id, reply)
    else:
        send_text(sender_id, ask_openai(sender_id, postback.get("title", payload)))


def ask_openai(sender_id: str, user_text: str) -> str:
    history = conversation_history.setdefault(sender_id, [])
    history.append({"role": "user", "content": user_text})
    if len(history) > MAX_HISTORY * 2:
        history[:] = history[-(MAX_HISTORY * 2):]

    try:
        print(f"Đang gọi OpenAI...")
        resp = requests.post(
            OPENAI_API_URL,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history,
                "max_tokens": 400,
                "temperature": 0.7,
            },
            timeout=15,
        )
        print(f"OpenAI status: {resp.status_code}")
        resp.raise_for_status()
        reply_text = resp.json()["choices"][0]["message"]["content"].strip()
        print(f"OpenAI reply: {reply_text[:80]}")

        # Lọc nếu AI hỏi SĐT
        if any(p in reply_text.lower() for p in ["số điện thoại", "phone", "sđt"]):
            full = " ".join([m.get("content","") for m in history])
            if any(kw in full.lower() for kw in ["tên", "mình là", "tôi là", "em là"]):
                return "SEND_PAYMENT_INFO"

        history.append({"role": "assistant", "content": reply_text})
        return reply_text

    except requests.exceptions.Timeout:
        print("OPENAI TIMEOUT!")
        return "Mình đang bận, bạn thử lại sau vài giây nhé!"
    except Exception as e:
        print(f"LỖI OPENAI: {e}")
        return "Xin lỗi, hệ thống đang bận. Liên hệ 083 285 0488 để được hỗ trợ nhé!"


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
        _send({"recipient": {"id": recipient_id}, "message": {"attachment": {"type": "image", "payload": {"url": url, "is_reusable": True}}}})


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
