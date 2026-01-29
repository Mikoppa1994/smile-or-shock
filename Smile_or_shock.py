import cv2
import mediapipe as mp
import time
import serial
import serial.tools.list_ports
import random
import ctypes
import ctypes.wintypes
import numpy as np

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
mpFaceMesh = mp.solutions.face_mesh
faceMesh = mpFaceMesh.FaceMesh()
mpDraw = mp.solutions.drawing_utils
drawSpec = mpDraw.DrawingSpec(thickness=1, circle_radius=1, color=(0, 255, 0))
pTime = 0
cTime = 0

# Lip landmark indices for smile detection
LIP_LEFT, LIP_RIGHT, LIP_UPPER, LIP_LOWER = 61, 291, 13, 14
# Eye corner indices for normalization
EYE_LEFT, EYE_RIGHT = 33, 263
ratio_ema = None
smiling = False
baseline = None
on_offset = 0.10
off_offset = 0.18

# Session countdown + display behavior
session_seconds = 300
remaining_seconds = float(session_seconds)
penalty_rate = 2.0                                   # rate:1= 1s failed = +1s session remain. rate:2= 1s failed = +2s session remain 
last_tick = time.time()
display_mode = "countdown"
next_switch_time = time.time() + random.uniform(3.0, 8.0)
messages = [
    "Keep going",
    "Stay focused",
    "Smile check",
    "You got this",
    "Eyes up",
]
current_message = random.choice(messages)
session_started = False
options_locked = False
warmup_active = False
warmup_start = 0.0
warmup_duration = 4
warmup_done_hold = 1.0

# Serial output when not smiling
SERIAL_PORT = "COM3"
SERIAL_BAUD = 9600
intensity_min_a = 20
intensity_max_a = 90
intensity_step_a = 2
intensity_window_a = 5
fail_count_a = 0

intensity_min_b = 20
intensity_max_b = 90
intensity_step_b = 2
intensity_window_b = 5
fail_count_b = 0

channel_a_enabled = True
channel_b_enabled = False
duration_s = 5
timeout_s = 15
last_send_time = 0.0
active_until = 0.0
last_sent_channels = set()
ser = None
ser_status = "Disconnected"
ser_error = ""
available_ports = []
selected_port = SERIAL_PORT
dropdown_open = False
port_dropdown_rect = (0, 0, 0, 0)
port_item_rects = []
connect_btn_rect = (0, 0, 0, 0)

def _refresh_ports():
    global available_ports, selected_port
    ports = [p.device for p in serial.tools.list_ports.comports()]
    available_ports = ports
    if ports:
        if selected_port not in ports:
            selected_port = ports[0]
    else:
        selected_port = None

def _connect_serial(port):
    global ser, ser_status, ser_error
    if ser:
        try:
            ser.close()
        except Exception:
            pass
        ser = None
    if not port:
        ser_status = "No port selected"
        ser_error = ""
        return
    try:
        ser = serial.Serial(port, SERIAL_BAUD, timeout=0.1)
        ser_status = f"Connected ({port})"
        ser_error = ""
    except Exception as e:
        ser = None
        ser_status = f"Failed ({port})"
        ser_error = str(e)
        print(f"Serial open failed: {e}")

def _disconnect_serial():
    global ser, ser_status, ser_error
    if ser:
        try:
            ser.close()
        except Exception:
            pass
    ser = None
    ser_status = "Disconnected"
    ser_error = ""

# Options window (custom UI + controls in one window)
cv2.namedWindow("Options", cv2.WINDOW_NORMAL)
cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
cv2.setWindowProperty("Options", cv2.WND_PROP_TOPMOST, 1)
cv2.setWindowProperty("Image", cv2.WND_PROP_TOPMOST, 0)
options_btn = {"x": 0, "y": 0, "w": 200, "h": 50}
dragging = None
sliders = [
    {"label": "Session seconds", "min": 1, "max": 3600, "value": session_seconds},
    {"label": "On duration (sec)", "min": 1, "max": 30, "value": duration_s},
    {"label": "Cooldown (sec)", "min": 1, "max": 60, "value": timeout_s},
    {"label": "Penalty x (1-10)", "min": 1, "max": 10, "value": int(penalty_rate)},
    {"label": "A min", "min": 0, "max": 100, "value": intensity_min_a},
    {"label": "A max", "min": 0, "max": 100, "value": intensity_max_a},
    {"label": "A step", "min": 1, "max": 10, "value": intensity_step_a},
    {"label": "A window", "min": 0, "max": 20, "value": intensity_window_a},
    {"label": "B min", "min": 0, "max": 100, "value": intensity_min_b},
    {"label": "B max", "min": 0, "max": 100, "value": intensity_max_b},
    {"label": "B step", "min": 1, "max": 10, "value": intensity_step_b},
    {"label": "B window", "min": 0, "max": 20, "value": intensity_window_b},
]

def _draw_options_ui():
    img = (24 * np.ones((520, 760, 3), dtype=np.uint8))
    cv2.putText(img, "Session Options", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (230, 230, 230), 2)
    _refresh_ports()

    def draw_section(title, x, y, w):
        cv2.rectangle(img, (x, y - 18), (x + w, y + 160), (45, 45, 45), 1)
        cv2.putText(img, title, (x + 10, y - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    def draw_slider(s, x, y, w):
        cv2.putText(img, f"{s['label']}: {s['value']}", (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1)
        bar_y = y + 10
        cv2.rectangle(img, (x, bar_y), (x + w, bar_y + 6), (70, 70, 70), -1)
        t = (s["value"] - s["min"]) / max(1, (s["max"] - s["min"]))
        knob_x = int(x + t * w)
        cv2.circle(img, (knob_x, bar_y + 3), 7, (80, 200, 80), -1)
        s["bar"] = (x, bar_y - 6, x + w, bar_y + 12)
        return y + 34

    left_x, right_x = 20, 400
    col_w = 320

    # Session section (left)
    draw_section("SESSION", left_x, 60, col_w)
    y = 70
    for s in sliders[0:4]:
        y = draw_slider(s, left_x + 10, y, col_w - 20)

    # Channel section (right)
    draw_section("CHANNELS", right_x, 60, col_w)
    y = 70
    cv2.putText(img, "Enable:", (right_x + 10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    box_a = (right_x + 90, y - 12, 22, 22)
    box_b = (right_x + 170, y - 12, 22, 22)
    cv2.rectangle(img, (box_a[0], box_a[1]), (box_a[0] + box_a[2], box_a[1] + box_a[3]), (200, 200, 200), 2)
    cv2.rectangle(img, (box_b[0], box_b[1]), (box_b[0] + box_b[2], box_b[1] + box_b[3]), (200, 200, 200), 2)
    if channel_a_enabled:
        cv2.line(img, (box_a[0] + 4, box_a[1] + 12), (box_a[0] + 10, box_a[1] + 18), (80, 200, 80), 2)
        cv2.line(img, (box_a[0] + 10, box_a[1] + 18), (box_a[0] + 18, box_a[1] + 4), (80, 200, 80), 2)
    if channel_b_enabled:
        cv2.line(img, (box_b[0] + 4, box_b[1] + 12), (box_b[0] + 10, box_b[1] + 18), (80, 200, 80), 2)
        cv2.line(img, (box_b[0] + 10, box_b[1] + 18), (box_b[0] + 18, box_b[1] + 4), (80, 200, 80), 2)
    cv2.putText(img, "A", (box_a[0] + 28, box_a[1] + 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    cv2.putText(img, "B", (box_b[0] + 28, box_b[1] + 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    global toggle_a_rect, toggle_b_rect
    toggle_a_rect = box_a
    toggle_b_rect = box_b

    # Channel A sliders
    y = 120
    cv2.putText(img, "Channel A", (right_x + 10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
    y += 20
    for s in sliders[4:8]:
        y = draw_slider(s, right_x + 10, y, col_w - 20)

    # Channel B sliders
    y += 10
    cv2.putText(img, "Channel B", (right_x + 10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
    y += 20
    for s in sliders[8:12]:
        y = draw_slider(s, right_x + 10, y, col_w - 20)

    # Apply button
    options_btn["x"] = 280
    options_btn["y"] = 455
    options_btn["w"] = 200
    options_btn["h"] = 45
    x, y, w, h = options_btn["x"], options_btn["y"], options_btn["w"], options_btn["h"]
    cv2.rectangle(img, (x, y), (x + w, y + h), (80, 200, 80), -1)
    cv2.putText(img, "APPLY", (x + 50, y + 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    # Serial status (draw first so dropdown layers above)
    cv2.putText(img, f"Status: {ser_status}", (20, 420),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # Serial port dropdown
    cv2.putText(img, "COM Port", (20, 330),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (210, 210, 210), 1)
    dd_x, dd_y, dd_w, dd_h = 20, 340, 200, 28
    cv2.rectangle(img, (dd_x, dd_y), (dd_x + dd_w, dd_y + dd_h), (70, 70, 70), -1)
    dd_text = selected_port if selected_port else "None"
    cv2.putText(img, dd_text, (dd_x + 8, dd_y + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1)
    cv2.putText(img, "v" if not dropdown_open else "^", (dd_x + dd_w - 18, dd_y + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1)
    global port_dropdown_rect, port_item_rects
    port_dropdown_rect = (dd_x, dd_y, dd_w, dd_h)
    port_item_rects = []
    if dropdown_open:
        item_h = 24
        for i, port in enumerate(available_ports):
            iy = dd_y + dd_h + (i * item_h)
            cv2.rectangle(img, (dd_x, iy), (dd_x + dd_w, iy + item_h), (60, 60, 60), -1)
            cv2.putText(img, port, (dd_x + 8, iy + 17),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1)
            port_item_rects.append((dd_x, iy, dd_w, item_h, port))

    # Connect/Disconnect button
    is_connected = ser is not None and ser.is_open
    cx, cy, cw, ch = 230, 340, 120, 28
    btn_color = (80, 200, 80) if is_connected else (80, 140, 220)
    btn_label = "DISCONNECT" if is_connected else "CONNECT"
    cv2.rectangle(img, (cx, cy), (cx + cw, cy + ch), btn_color, -1)
    cv2.putText(img, btn_label, (cx + 5, cy + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    global connect_btn_rect
    connect_btn_rect = (cx, cy, cw, ch)

    return img

def _on_options_mouse(event, x, y, flags, param):
    global options_locked, dragging, channel_a_enabled, channel_b_enabled, selected_port, dropdown_open, ser_status
    if options_locked:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        # Dropdown selection
        ddx, ddy, ddw, ddh = port_dropdown_rect
        if ddx <= x <= ddx + ddw and ddy <= y <= ddy + ddh:
            dropdown_open = not dropdown_open
            return
        if dropdown_open:
            for rx, ry, rw, rh, port in port_item_rects:
                if rx <= x <= rx + rw and ry <= y <= ry + rh:
                    selected_port = port
                    ser_status = f"Selected ({port})"
                    dropdown_open = False
                    return
            dropdown_open = False

        # Connect button
        cx, cy, cw, ch = connect_btn_rect
        if cx <= x <= cx + cw and cy <= y <= cy + ch:
            if ser is not None and ser.is_open:
                _disconnect_serial()
            else:
                _connect_serial(selected_port)
            return

        bx, by, bw, bh = options_btn["x"], options_btn["y"], options_btn["w"], options_btn["h"]
        if bx <= x <= bx + bw and by <= y <= by + bh:
            options_locked = True
            cv2.destroyWindow("Options")
            return
        ax, ay, aw, ah = toggle_a_rect
        bx2, by2, bw2, bh2 = toggle_b_rect
        if ax <= x <= ax + aw and ay <= y <= ay + ah:
            channel_a_enabled = not channel_a_enabled
            return
        if bx2 <= x <= bx2 + bw2 and by2 <= y <= by2 + bh2:
            channel_b_enabled = not channel_b_enabled
            return
        for i, s in enumerate(sliders):
            x0, y0, x1, y1 = s.get("bar", (0, 0, 0, 0))
            if x0 <= x <= x1 and y0 <= y <= y1:
                dragging = i
                break
    elif event == cv2.EVENT_LBUTTONUP:
        dragging = None
    elif event == cv2.EVENT_MOUSEMOVE and dragging is not None:
        s = sliders[dragging]
        x0, _, x1, _ = s.get("bar", (0, 0, 0, 0))
        x_clamped = max(x0, min(x1, x))
        t = (x_clamped - x0) / max(1, (x1 - x0))
        s["value"] = int(round(s["min"] + t * (s["max"] - s["min"])))

cv2.setMouseCallback("Options", _on_options_mouse)

def _get_window_rect(title):
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return None
    rect = ctypes.wintypes.RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return (rect.left, rect.top, rect.right, rect.bottom)
    return None

def _get_virtual_screen():
    user32 = ctypes.windll.user32
    x = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
    y = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
    w = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
    h = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
    return x, y, w, h

while True:
    success, img = cap.read()
    now = time.time()
    dt = now - last_tick
    last_tick = now

    # Center the options window over the camera window before session starts
    if not session_started and success and not options_locked:
        opt_w, opt_h = 760, 520
        cv2.resizeWindow("Options", opt_w, opt_h)
        rect = None
        try:
            rect = _get_window_rect("Image")
        except Exception:
            rect = None
        if rect:
            left, top, right, bottom = rect
            cx = (left + right) // 2
            cy = (top + bottom) // 2
            x = cx - opt_w // 2
            y = cy - opt_h // 2
            cv2.moveWindow("Options", x, y)
        else:
            vx, vy, vw, vh = _get_virtual_screen()
            x = vx + (vw - opt_w) // 2
            y = vy + (vh - opt_h) // 2
            cv2.moveWindow("Options", x, y)

        ui = _draw_options_ui()
        cv2.imshow("Options", ui)

    # Read options
    if not session_started and not options_locked:
        session_seconds = int(sliders[0]["value"])
        duration_s = int(sliders[1]["value"])
        timeout_s = int(sliders[2]["value"])
        penalty_rate = max(1.0, float(sliders[3]["value"]))
        intensity_min_a = int(sliders[4]["value"])
        intensity_max_a = int(sliders[5]["value"])
        intensity_step_a = int(sliders[6]["value"])
        intensity_window_a = int(sliders[7]["value"])
        intensity_min_b = int(sliders[8]["value"])
        intensity_max_b = int(sliders[9]["value"])
        intensity_step_b = int(sliders[10]["value"])
        intensity_window_b = int(sliders[11]["value"])
        if intensity_max_a < intensity_min_a:
            intensity_max_a = intensity_min_a
            sliders[5]["value"] = intensity_max_a
        if intensity_max_b < intensity_min_b:
            intensity_max_b = intensity_min_b
            sliders[9]["value"] = intensity_max_b
        remaining_seconds = float(session_seconds)
    if success:
        h0, w0 = img.shape[:2]
        scale = 1.8
        nw, nh = int(w0 / scale), int(h0 / scale)
        x1 = (w0 - nw) // 2
        y1 = (h0 - nh) // 2
        img = img[y1:y1+nh, x1:x1+nw]
        img = cv2.resize(img, (w0, h0), interpolation=cv2.INTER_LINEAR)
    imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = faceMesh.process(imgRGB)
    if results.multi_face_landmarks:
        for faceLms in results.multi_face_landmarks:
            mpDraw.draw_landmarks(img, faceLms, mpFaceMesh.FACEMESH_CONTOURS, drawSpec, drawSpec)
            h, w, c = img.shape
            lm = faceLms.landmark

            def d(p1, p2):
                return ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5

            width = d(lm[LIP_LEFT], lm[LIP_RIGHT])
            height = max(d(lm[LIP_UPPER], lm[LIP_LOWER]), 0.001)
            eye_dist = max(d(lm[EYE_LEFT], lm[EYE_RIGHT]), 0.001)
            ratio = (height / width) / eye_dist

            if ratio_ema is None:
                ratio_ema = ratio
            else:
                ratio_ema = (0.2 * ratio) + (0.8 * ratio_ema)

            if baseline is not None:
                if not smiling and ratio_ema > baseline - on_offset:
                    smiling = True
                elif smiling and ratio_ema < baseline - off_offset:
                    smiling = False

            if session_started and not smiling and ser:
                now = time.time()
                if now - last_send_time >= timeout_s and active_until <= now:
                    try:
                        channels_to_send = []
                        if channel_a_enabled and channel_b_enabled:
                            choice = random.choice(["A", "B", "AB"])
                            if choice in ("A", "AB"):
                                channels_to_send.append("A")
                            if choice in ("B", "AB"):
                                channels_to_send.append("B")
                        elif channel_a_enabled:
                            channels_to_send.append("A")
                        elif channel_b_enabled:
                            channels_to_send.append("B")

                        if "A" in channels_to_send:
                            base_a = min(intensity_max_a, intensity_min_a + fail_count_a * intensity_step_a)
                            high_a = min(intensity_max_a, base_a + intensity_window_a)
                            intensity_a = random.randint(base_a, high_a)
                            ser.write(f"A{intensity_a}\n".encode())
                            fail_count_a += 1
                        if "B" in channels_to_send:
                            base_b = min(intensity_max_b, intensity_min_b + fail_count_b * intensity_step_b)
                            high_b = min(intensity_max_b, base_b + intensity_window_b)
                            intensity_b = random.randint(base_b, high_b)
                            ser.write(f"B{intensity_b}\n".encode())
                            fail_count_b += 1

                        last_sent_channels = set(channels_to_send)
                        last_send_time = now
                        active_until = now + duration_s
                    except Exception:
                        pass

            if session_started and ser and active_until > 0 and time.time() >= active_until:
                try:
                    if "A" in last_sent_channels:
                        ser.write(b"A0\n")
                    if "B" in last_sent_channels:
                        ser.write(b"B0\n")
                except Exception:
                    pass
                active_until = 0.0
                last_sent_channels = set()

            color = (0, 255, 0) if smiling else (0, 0, 255)
            cv2.putText(img, f"Smile: {'YES' if smiling else 'NO'}", (10, 110),
                        cv2.FONT_HERSHEY_PLAIN, 2, color, 2)
            if not session_started:
                cv2.putText(img, f"Ratio: {ratio_ema:.2f}", (10, 150),
                            cv2.FONT_HERSHEY_PLAIN, 2, color, 2)
            if baseline is None:
                cv2.putText(img, "Press S to set smile baseline", (10, 190),
                            cv2.FONT_HERSHEY_PLAIN, 1.5, (0, 255, 255), 2)
            elif not session_started:
                cv2.putText(img, f"Smile baseline: {baseline:.2f}", (10, 190),
                            cv2.FONT_HERSHEY_PLAIN, 1.5, (0, 255, 255), 2)

    # Update session countdown (only after calibration)
    if session_started and remaining_seconds > 0:
        if not smiling:
            remaining_seconds += penalty_rate * dt
        else:
            remaining_seconds = max(0.0, remaining_seconds - dt)

    # Randomly change display mode
    if now >= next_switch_time:
        display_mode = random.choices(
            ["countdown", "hidden", "message"],
            weights=[0.6, 0.2, 0.2],
            k=1
        )[0]
        if display_mode == "message":
            current_message = random.choice(messages)
        next_switch_time = now + random.uniform(3.0, 8.0)

    # Warm-up screen
    if warmup_active:
        elapsed = time.time() - warmup_start
        if elapsed < 1.0:
            text = "GET READY!"
            color = (0, 0, 255)
            scale = 10.0
        elif elapsed < 2.0:
            text = "3"
            color = (0, 0, 255)
            scale = 30.0
        elif elapsed < 3.0:
            text = "2"
            color = (0, 0, 255)
            scale = 30.0
        elif elapsed < 4.0:
            text = "1"
            color = (0, 0, 255)
            scale = 30.0
        else:
            text = "SMILE!"
            color = (0, 0, 255)
            scale = 10.0
        font = cv2.FONT_HERSHEY_SIMPLEX
        thickness = 10
        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        x = (w - tw) // 2
        y = (h + th) // 2
        cv2.putText(img, text, (x, y), font, scale, color, thickness)
        if elapsed >= warmup_duration + warmup_done_hold:
            warmup_active = False
            session_started = True
    # Draw countdown / message (only after session starts)
    if session_started and not warmup_active:
        minutes = int(remaining_seconds) // 60
        seconds = int(remaining_seconds) % 60
        countdown_text = f"{minutes:02d}:{seconds:02d}"

        if not smiling:
            # Big red countdown centered
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 12
            thickness = 10
            (tw, th), _ = cv2.getTextSize(countdown_text, font, scale, thickness)
            x = (w - tw) // 2
            y = (h + th) // 2
            cv2.putText(img, countdown_text, (x, y), font, scale, (0, 0, 255), thickness)
        else:
            if display_mode == "countdown":
                # Top-right corner
                font = cv2.FONT_HERSHEY_SIMPLEX
                scale = 1.8
                thickness = 3
                (tw, th), _ = cv2.getTextSize(countdown_text, font, scale, thickness)
                x = w - tw - 10
                y = 40
                cv2.putText(img, countdown_text, (x, y), font, scale, (255, 255, 255), thickness)
            elif display_mode == "message":
                font = cv2.FONT_HERSHEY_SIMPLEX
                scale = 1.8
                thickness = 3
                (tw, th), _ = cv2.getTextSize(current_message, font, scale, thickness)
                x = w - tw - 10
                y = 40
                cv2.putText(img, current_message, (x, y), font, scale, (0, 255, 255), thickness)

    cTime = time.time()
    fps = 1/(cTime - pTime)
    pTime = cTime
    # FPS hidden
    cv2.imshow("Image", img)
    key = cv2.waitKey(1) & 0xFF
    if key in (ord("s"), ord("S")) and ratio_ema is not None:
        baseline = ratio_ema
        smiling = False
        warmup_active = True
        warmup_start = time.time()
        if not options_locked:
            options_locked = True
            cv2.destroyWindow("Options")
    elif key in (ord("q"), ord("Q")):
        break

if ser:
    try:
        ser.close()
    except Exception:
        pass
    
