import os
import hmac
import hashlib
import random
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import requests
from date_parser import parse_date_range

app = Flask(__name__)

@app.after_request
def add_ngrok_header(response):
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "YOUR_PAGE_ACCESS_TOKEN")
VERIFY_TOKEN      = os.environ.get("VERIFY_TOKEN", "YOUR_VERIFY_TOKEN")
APP_SECRET        = os.environ.get("APP_SECRET", "YOUR_APP_SECRET")
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY")
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
GOHOST_API_KEY    = os.environ.get("GOHOST_API_KEY", "YOUR_GOHOST_API_KEY")
GOHOST_API_SECRET = os.environ.get("GOHOST_API_SECRET", "YOUR_GOHOST_API_SECRET")

GRAPH_API_URL  = "https://graph.facebook.com/v19.0/me/messages"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
GROQ_API_URL   = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GOHOST_API_URL = "https://platform.gohost.vn/pms/api/public/v1"

TENANT_ID       = "9d37978e-2409-402d-a286-082d82f91c27"
ROOM_TIEU_CHUAN = "6c621484-9b51-46de-8448-917bb677e14d"
ROOM_CAO_CAP    = "c7613c8a-5f93-4d71-8ae0-1ee24a2e6585"

# ID Messenger của chủ nhà
OWNER_ID = "9639287556127249"

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

Quy tắc trả lời:
- Luôn trả lời bằng tiếng Việt, thân thiện, nhiệt tình như nhân viên lễ tân
- Ngắn gọn, dễ hiểu (dưới 200 từ)
- KHÔNG dùng emoji trong câu trả lời
- Luôn viết tiếng Việt có đầy đủ dấu trong mọi câu trả lời
- KHÔNG bắt đầu bằng lời chào như "Xin chào", "Chào bạn" cho mỗi tin nhắn
- Trả lời thẳng vào câu hỏi của khách
- Không bịa thông tin nếu không chắc chắn
- Nếu khách hỏi xem ảnh phòng tiêu chuẩn, trả lời đúng: "SEND_PHOTOS_TIEU_CHUAN"
- Nếu khách hỏi xem ảnh phòng cao cấp, trả lời đúng: "SEND_PHOTOS_CAO_CAP"
- Nếu khách hỏi xem ảnh phòng (không nói rõ loại), hỏi lại: muốn xem phòng tiêu chuẩn hay cao cấp?
- Nếu khách hỏi phòng còn trống không (không có ngày cụ thể), trả lời: "CHECK_AVAILABILITY"
- Khi thu thập đủ thông tin đặt phòng (tên, SĐT, check-in, check-out, loại phòng), trả lời: "SEND_PAYMENT_INFO"
- Hotline: 083 285 0488

=== THÔNG TIN PHÒNG ===
Tổng cộng 3 phòng:
1. Phòng Tiêu Chuẩn (2 phòng): Trong tuần 370k, cuối tuần 400k/đêm
2. Phòng Cao Cấp (1 phòng): Trong tuần 440k, cuối tuần 480k/đêm

=== GIỜ CHECK-IN / CHECK-OUT ===
Check-in: 14:00 / Check-out: 12:00 / Sớm/trễ: phụ phí 50k/giờ

=== CHÍNH SÁCH CỌC ===
- Yêu cầu cọc 50% tổng tiền phòng để giữ phòng
- Nếu khách cọc ít hơn 50% vẫn chấp nhận
- KHÔNG giữ phòng nếu khách không cọc

=== CHÍNH SÁCH HỦY / ĐỔI NGÀY ===
- Hủy trước 7 ngày: hoàn 100% cọc
- Hủy trong vòng 7 ngày: thu 50% cọc
- Hủy trong vòng 1 ngày: thu 100% cọc (không hoàn)

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

# Lưu thông tin đặt phòng đang chờ xác nhận
# pending_bookings[sender_id] = {thông tin đặt phòng}
pending_bookings: dict = {}
conversation_history: dict[str, list] = {}
MAX_HISTORY = 10

DATE_KEYWORDS = [
    "ngày", "tháng", "tuần", "hôm nay", "ngày mai", "ngày kia",
    "thứ", "cuối tuần", "còn phòng", "có phòng", "trống không",
    "check", "/",
]


def gohost_headers():
    return {
        "Authorization": f"Bearer {GOHOST_API_KEY}:{GOHOST_API_SECRET}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def check_room_availability(checkin: str, checkout: str) -> str:
    try:
        # Lấy booking từ checkin-1 để bắt booking đang ở dở
        ci_dt = datetime.strptime(checkin, "%Y-%m-%d")
        start = (ci_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        resp = requests.get(
            f"{GOHOST_API_URL}/properties/{TENANT_ID}/bookings",
            headers=gohost_headers(),
            params={"start_date": start, "end_date": checkout, "per_page": 50},
            timeout=10,
        )
        resp.raise_for_status()
        bookings = resp.json().get("data", [])
        # Lọc booking còn hiệu lực VÀ overlap với khoảng ngày check-in/out
        ci_dt = datetime.strptime(checkin, "%Y-%m-%d")
        co_dt = datetime.strptime(checkout, "%Y-%m-%d")
        active = []
        for b in bookings:
            if b.get("status") in ("cancelled", "no_show"):
                continue
            b_ci = datetime.strptime(b.get("checkin_date", "2000-01-01"), "%Y-%m-%d")
            b_co = datetime.strptime(b.get("checkout_date", "2000-01-01"), "%Y-%m-%d")
            # Overlap nếu b_ci < co_dt VÀ b_co > ci_dt
            if b_ci < co_dt and b_co > ci_dt:
                active.append(b)

        # Đếm phòng từ room_type name trong booking_rooms
        booked_tc = 0
        booked_cc = 0
        for b in active:
            rooms = b.get("booking_rooms", [])
            for r in rooms:
                room_type = r.get("room_type", "").lower()
                if "tieu chuan" in room_type or "tiêu chuẩn" in room_type:
                    booked_tc += 1
                elif "cao cap" in room_type or "cao cấp" in room_type:
                    booked_cc += 1
        print(f"Booked TC: {booked_tc}, CC: {booked_cc}")
        con_tc = max(0, 2 - booked_tc)
        con_cc = max(0, 1 - booked_cc)

        ci = datetime.strptime(checkin, "%Y-%m-%d").strftime("%d/%m/%Y")
        co = datetime.strptime(checkout, "%Y-%m-%d").strftime("%d/%m/%Y")
        result = f"Tinh trang phong {ci} - {co}:\n\n"
        result += f"Phong Tieu Chuan: {'Con ' + str(con_tc) + ' phong' if con_tc > 0 else 'Het phong'}\n"
        result += f"Phong Cao Cap: {'Con phong' if con_cc > 0 else 'Het phong'}\n"
        if con_tc == 0 and con_cc == 0:
            result += "\nRat tiec het phong. Ban thu ngay khac hoac lien he 083 285 0488."
        else:
            result += "\nBan muon dat phong loai nao?"
        return result
    except Exception as e:
        print(f"Loi GoHost: {e}")
        return "Hiện không kiểm tra được lịch phòng. Liên hệ 083 285 0488 để kiểm tra nhé!"


def create_gohost_booking(info: dict) -> bool:
    """Tạo đơn đặt phòng trên GoHost."""
    try:
        room_type_id = ROOM_CAO_CAP if "cao cap" in info.get("loai_phong", "").lower() else ROOM_TIEU_CHUAN
        payload = {
            "room_type_id": room_type_id,
            "checkin_date": info["checkin"],
            "checkout_date": info["checkout"],
            "guest_name": info["ten"],
            "guest_phone": info["sdt"],
            "num_adults": int(info.get("so_nguoi", 1)),
            "note": f"Dat phong qua Messenger bot. Co coc.",
        }
        resp = requests.post(
            f"{GOHOST_API_URL}/properties/{TENANT_ID}/bookings",
            headers=gohost_headers(),
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        print(f"Tao don GoHost thanh cong: {resp.json()}")
        return True
    except Exception as e:
        print(f"Loi tao don GoHost: {e}")
        return False


def notify_owner(sender_id: str, info: dict):
    """Gửi thông báo cho chủ nhà kèm nút Xác nhận / Từ chối."""
    ci = datetime.strptime(info["checkin"], "%Y-%m-%d").strftime("%d/%m/%Y")
    co = datetime.strptime(info["checkout"], "%Y-%m-%d").strftime("%d/%m/%Y")
    msg = (
        f"DON DAT PHONG MOI!\n\n"
        f"Tên: {info['ten']}\n"
        f"SĐT: {info['sdt']}\n"
        f"Check-in: {ci}\n"
        f"Check-out: {co}\n"
        f"Loại phòng: {info['loai_phong']}\n"
        f"Số người: {info.get('so_nguoi', 1)}\n\n"
        f"Khách đã báo đã cọc. Bạn kiểm tra và xác nhận nhé!"
    )
    # Gửi tin nhắn cho chủ nhà kèm nút
    _send({
        "recipient": {"id": OWNER_ID},
        "message": {
            "text": msg,
            "quick_replies": [
                {
                    "content_type": "text",
                    "title": "XÁC NHẬN ĐẶT PHÒNG",
                    "payload": f"CONFIRM_BOOKING:{sender_id}",
                },
                {
                    "content_type": "text",
                    "title": "TỪ CHỐI",
                    "payload": f"REJECT_BOOKING:{sender_id}",
                },
            ],
        },
    })


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

    # Chủ nhà nhấn XÁC NHẬN hoặc TỪ CHỐI (quick reply từ thông báo)
    if lower.startswith("xac nhan dat phong") or lower.startswith("tu choi"):
        # Xử lý trong handle_postback với payload
        return

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

    # Khách báo đã cọc xong
    CK_KEYWORDS = ["da coc", "coc roi", "da chuyen", "chuyen roi", "da thanh toan", 
                    "đã cọc", "cọc rồi", "đã chuyển", "chuyển rồi", "đã thanh toán", 
                    "thanh toán rồi", "chuyen khoan roi", "ck roi", "ck xong", "đã ck", 
                    "chuyen xong", "ck rồi", "chuyển khoản rồi", "chuyển khoản xong",
                    "đã chuyển khoản", "coc xong", "cọc xong", "ck", "chuyển r",
                    "chuyển tiền rồi", "đã chuyển tiền"]
    if any(kw in lower for kw in CK_KEYWORDS):
        # Gửi cảm ơn + lưu ý cho khách
        send_text(sender_id, "Cảm ơn bạn đã chuyển khoản! Home sẽ kiểm tra và xác nhận cho bạn sớm nhất nhé.")
        import time; time.sleep(1)
        send_text(sender_id, "Trong thời gian chờ, đây là một số lưu ý khi ở tại Trăng Non Homestay:")
        import time; time.sleep(1)
        _send({"recipient": {"id": sender_id}, "message": {"attachment": {"type": "image", "payload": {"url": PHOTO_LUU_Y, "is_reusable": True}}}})
        # Thông báo cho chủ nhà nếu có thông tin đặt phòng
        if sender_id in pending_bookings:
            import time; time.sleep(2)
            info = pending_bookings.get(sender_id, {})
            notify_owner(sender_id, info)
        return

    # Parse ngày tháng tự động - chỉ khi có từ khóa kiểm tra phòng rõ ràng
    CHECK_TRIGGERS = ["còn phòng", "con phong", "có phòng", "co phong", "trống không", "trong khong", "kiểm tra phòng", "kiem tra phong"]
    DATE_ONLY_TRIGGERS = ["ngày mai", "ngay mai", "cuối tuần", "cuoi tuan", "thứ ", "thu "]
    
    has_check_trigger = any(kw in lower for kw in CHECK_TRIGGERS)
    has_date_only = any(kw in lower for kw in DATE_ONLY_TRIGGERS)
    
    if has_check_trigger or has_date_only:
        checkin, checkout = parse_date_range(lower)
        if checkin and checkout:
            result = check_room_availability(checkin, checkout)
            send_text(sender_id, result)
            return

    reply = ask_openai(sender_id, text)

    if "SEND_PHOTOS_TIEU_CHUAN" in reply:
        send_text(sender_id, "Ảnh phòng Tiêu Chuẩn:")
        send_photos(sender_id, PHOTOS_TIEU_CHUAN, limit=4)
    elif "SEND_PHOTOS_CAO_CAP" in reply:
        send_text(sender_id, "Ảnh phòng Cao Cấp:")
        send_photos(sender_id, PHOTOS_CAO_CAP, limit=4)
    elif "SEND_PAYMENT_INFO" in reply:
        # Lưu thông tin đặt phòng từ lịch sử hội thoại
        history = conversation_history.get(sender_id, [])
        info = extract_booking_info(history)
        if info:
            pending_bookings[sender_id] = info
        send_text(sender_id, "Vui lòng chuyển khoản để giữ phòng (cọc tối thiểu 50% tổng tiền):")
        _send({"recipient": {"id": sender_id}, "message": {"attachment": {"type": "image", "payload": {"url": PHOTO_PAYMENT, "is_reusable": True}}}})
        import time; time.sleep(1)
        send_text(sender_id, "Sau khi chuyển khoản xong, bạn nhắn 'đã cọc' để thông báo cho chúng mình nhé!")
    elif "CHECK_AVAILABILITY" in reply:
        send_quick_replies(
            sender_id,
            "Bạn muốn kiểm tra phòng thời gian nào?",
            [
                {"title": "Cuối tuần này", "payload": "AVAIL_THIS_WEEKEND"},
                {"title": "Tuần tới",      "payload": "AVAIL_NEXT_WEEK"},
                {"title": "Nhập ngày khác","payload": "AVAIL_CUSTOM"},
            ],
        )
    else:
        send_text(sender_id, reply)


def extract_booking_info(history: list) -> dict:
    """Trích xuất thông tin đặt phòng từ lịch sử hội thoại."""
    import re
    full_text = " ".join([m.get("content", "") for m in history])

    info = {
        "ten": "Khach",
        "sdt": "Chua co",
        "checkin": "",
        "checkout": "",
        "loai_phong": "Tieu chuan",
        "so_nguoi": "1",
    }

    # Tìm SĐT
    sdt = re.search(r"(0\d{9})", full_text)
    if sdt:
        info["sdt"] = sdt.group(1)

    # Tìm loại phòng
    if "cao cap" in full_text.lower():
        info["loai_phong"] = "Cao cap"

    # Tìm ngày
    checkin, checkout = parse_date_range(full_text)
    if checkin:
        info["checkin"] = checkin
        info["checkout"] = checkout or (datetime.strptime(checkin, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    return info


def handle_postback(sender_id: str, postback: dict):
    payload = postback.get("payload", "")

    # Chủ nhà xác nhận đặt phòng
    if payload.startswith("CONFIRM_BOOKING:"):
        guest_id = payload.split(":")[1]
        info = pending_bookings.get(guest_id)
        if info:
            success = create_gohost_booking(info)
            if success:
                send_text(sender_id, f"Da tao don tren GoHost thanh cong!\nKhach: {info['ten']} - {info['sdt']}")
                send_text(guest_id, f"Phòng của bạn đã được xác nhận! Hẹn gặp bạn tại Trăng Non Homestay. Mọi thắc mắc liên hệ 083 285 0488 nhé!")
                pending_bookings.pop(guest_id, None)
            else:
                send_text(sender_id, "Lỗi tạo đơn trên GoHost. Vui lòng tạo thủ công nhé!")
        else:
            send_text(sender_id, "Không tìm thấy thông tin đặt phòng. Có thể khách đã hủy.")
        return

    # Chủ nhà từ chối
    if payload.startswith("REJECT_BOOKING:"):
        guest_id = payload.split(":")[1]
        send_text(sender_id, "Đã từ chối đặt phòng.")
        send_text(guest_id, "Rất tiếc phòng của bạn chưa được xác nhận. Vui lòng liên hệ 083 285 0488 để biết thêm chi tiết nhé!")
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
        send_photos(sender_id, PHOTOS_TIEU_CHUAN, limit=4)
        return

    if payload == "PHOTOS_CAO_CAP":
        send_text(sender_id, "Ảnh phòng Cao Cấp:")
        send_photos(sender_id, PHOTOS_CAO_CAP, limit=4)
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
        send_text(sender_id, "Ban nhan ngay muon check-in, vi du:\n- 15/6\n- 15/6 - 17/6\n- thu 6\n- cuoi tuan nay")
        return

    responses = {
        "PRICES":  "Gia phong Trang Non:\n\nPhong Tieu Chuan:\n- Trong tuan: 370k/dem\n- Cuoi tuan: 400k/dem\n\nPhong Cao Cap:\n- Trong tuan: 440k/dem\n- Cuoi tuan: 480k/dem",
        "CONTACT": "Hotline: 083 285 0488\n17/14B Luong Van Nam, Phan Thiet",
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
        SDT_PHRASES = ["số điện thoại", "phone", "sđt", "số đt"]
        if any(p in reply_text.lower() for p in SDT_PHRASES):
            full_history = " ".join([m.get("content","") for m in history])
            has_name = any(kw in full_history.lower() for kw in ["tên", "mình là", "tôi là", "em là"])
            if has_name:
                return "SEND_PAYMENT_INFO"

        history.append({"role": "assistant", "content": reply_text})
        return reply_text

    except requests.exceptions.Timeout:
        print("OPENAI TIMEOUT!")
        return "Mình đang bận, bạn thử lại sau vài giây nhé!"
    except Exception as e:
        print(f"LỖI OPENAI: {e}")
        return "Xin lỗi, hệ thống đang bận. Liên hệ 083 285 0488 để được hỗ trợ nhé!"


def ask_openai(sender_id: str, user_text: str) -> str:
    history = conversation_history.setdefault(sender_id, [])
    history.append({"role": "user", "content": user_text})
    if len(history) > MAX_HISTORY * 2:
        history[:] = history[-(MAX_HISTORY * 2):]

    try:
        print(f"Dang goi Groq API... key: {GROQ_API_KEY[:10]}...")
        resp = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gemma2-9b-it",
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history,
                "max_tokens": 300,
                "temperature": 0.7,
            },
            timeout=15,
        )
        print(f"Groq response status: {resp.status_code}")
        resp.raise_for_status()
        reply_text = resp.json()["choices"][0]["message"]["content"].strip()
        print(f"Groq reply: {reply_text[:50]}")
        
        # Nếu AI hỏi SĐT → bỏ qua, kích hoạt SEND_PAYMENT_INFO luôn
        SDT_PHRASES = ["số điện thoại", "so dien thoai", "phone", "sđt", "sdt", 
                       "liên hệ", "lien he", "số đt", "so dt"]
        if any(p in reply_text.lower() for p in SDT_PHRASES):
            # Kiểm tra xem trong lịch sử đã có tên chưa
            full_history = " ".join([m.get("content","") for m in history])
            has_name = any(kw in full_history.lower() for kw in ["tên", "ten", "mình là", "minh la", "tôi là", "toi la"])
            if has_name:
                return "SEND_PAYMENT_INFO"
        
        history.append({"role": "assistant", "content": reply_text})
        return reply_text
    except requests.exceptions.Timeout:
        return "Mình đang bận, bạn thử lại sau vài giây nhé!"
    except Exception as e:
        print(f"Loi Groq: {e}")
        # Fallback sang Groq nếu Gemini lỗi
    print("Gemini thất bại, fallback sang Groq...")
    return ask_openai(sender_id, user_text)


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
        SDT_PHRASES = ["số điện thoại", "phone", "sđt", "số đt"]
        if any(p in reply_text.lower() for p in SDT_PHRASES):
            full_history = " ".join([m.get("content","") for m in history])
            has_name = any(kw in full_history.lower() for kw in ["tên", "mình là", "tôi là", "em là"])
            if has_name:
                return "SEND_PAYMENT_INFO"

        history.append({"role": "assistant", "content": reply_text})
        return reply_text

    except requests.exceptions.Timeout:
        print("OPENAI TIMEOUT!")
        return "Mình đang bận, bạn thử lại sau vài giây nhé!"
    except Exception as e:
        print(f"LỖI OPENAI: {e}")
        return "Xin lỗi, hệ thống đang bận. Liên hệ 083 285 0488 để được hỗ trợ nhé!"


def ask_openai(sender_id: str, user_text: str) -> str:
    history = conversation_history.setdefault(sender_id, [])
    history.append({"role": "user", "parts": [{"text": user_text}]})
    if len(history) > MAX_HISTORY * 2:
        history[:] = history[-(MAX_HISTORY * 2):]

    for attempt in range(3):
        try:
            resp = requests.post(
                GEMINI_API_URL,
                params={"key": GEMINI_API_KEY},
                json={
                    "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                    "contents": history,
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 400},
                },
                timeout=15,
            )
            if resp.status_code == 429:
                import time; time.sleep(5)
                continue
            resp.raise_for_status()
            reply_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

            # Lọc nếu AI hỏi SĐT
            SDT_PHRASES = ["số điện thoại", "phone", "sđt", "số đt"]
            if any(p in reply_text.lower() for p in SDT_PHRASES):
                full_history = " ".join([p.get("parts",[{}])[0].get("text","") for p in history])
                has_name = any(kw in full_history.lower() for kw in ["tên", "mình là", "tôi là", "em là"])
                if has_name:
                    return "SEND_PAYMENT_INFO"

            history.append({"role": "model", "parts": [{"text": reply_text}]})
            return reply_text

        except requests.exceptions.Timeout:
            return "Mình đang bận, bạn thử lại sau vài giây nhé!"
        except Exception as e:
            print(f"Lỗi Gemini (lần {attempt+1}): {e}")
            import time; time.sleep(3)

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
