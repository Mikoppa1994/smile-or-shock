import cv2
import mediapipe as mp
import time
import random
import ctypes
import ctypes.wintypes
import numpy as np

import config
from camera import CameraAsync
from serial_io import SerialController
from debug import DebugTracker
from ui import OptionsUI


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


def run():
    cam = CameraAsync(config.CAMERA_WIDTH, config.CAMERA_HEIGHT)
    serial_ctrl = SerialController(config.SERIAL_BAUD)
    debug = DebugTracker(max_history=6)

    mpFaceMesh = mp.solutions.face_mesh
    faceMesh = mpFaceMesh.FaceMesh()
    mpDraw = mp.solutions.drawing_utils
    drawSpec = mpDraw.DrawingSpec(thickness=1, circle_radius=1, color=(0, 255, 0))

    state = {
        "ratio_ema": None,
        "smiling": False,
        "baseline": None,
        "session_seconds": config.SESSION_SECONDS,
        "remaining_seconds": float(config.SESSION_SECONDS),
        "penalty_rate": config.PENALTY_RATE,
        "last_tick": time.time(),
        "display_mode": "countdown",
        "next_switch_time": time.time() + random.uniform(3.0, 8.0),
        "messages": list(config.MESSAGES),
        "current_message": random.choice(config.MESSAGES),
        "session_started": False,
        "options_locked": False,
        "warmup_active": False,
        "warmup_start": 0.0,
        "warmup_duration": config.WARMUP_DURATION,
        "warmup_done_hold": config.WARMUP_DONE_HOLD,
        "tease_mode": False,
        "challenge_mode": False,
        "serial_ctrl": serial_ctrl,
        "selected_port": config.SERIAL_PORT,
        "intensity_min_a": config.INTENSITY_MIN_A,
        "intensity_max_a": config.INTENSITY_MAX_A,
        "intensity_step_a": config.INTENSITY_STEP_A,
        "intensity_window_a": config.INTENSITY_WINDOW_A,
        "fail_count_a": 0,
        "intensity_min_b": config.INTENSITY_MIN_B,
        "intensity_max_b": config.INTENSITY_MAX_B,
        "intensity_step_b": config.INTENSITY_STEP_B,
        "intensity_window_b": config.INTENSITY_WINDOW_B,
        "fail_count_b": 0,
        "channel_a_enabled": config.CHANNEL_A_ENABLED,
        "channel_b_enabled": config.CHANNEL_B_ENABLED,
        "duration_s": config.DURATION_S,
        "timeout_s": config.TIMEOUT_S,
        "last_send_time": 0.0,
        "active_until": 0.0,
        "last_sent_channels": set(),
        "tease_next_time": time.time() + random.uniform(config.TEASE_INTERVAL_MIN, config.TEASE_INTERVAL_MAX),
        "tease_active_until": 0.0,
        "tease_last_channels": set(),
        "tease_duration_s": config.TEASE_DURATION_S,
        "super_warning_active": False,
        "super_warning_end": 0.0,
        "super_challenge_active": False,
        "super_challenge_end": 0.0,
        "next_super_warning_time": time.time() + random.uniform(config.SUPER_COOLDOWN_MIN_S, config.SUPER_COOLDOWN_MAX_S),
    }

    # Options window (custom UI + controls in one window)
    cv2.namedWindow("Options", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Options", cv2.WND_PROP_TOPMOST, 1)
    cv2.setWindowProperty("Image", cv2.WND_PROP_TOPMOST, 0)

    options_ui = OptionsUI(state)
    cv2.setMouseCallback("Options", options_ui.on_mouse)

    pTime = 0

    while True:
        success, img = cam.read()
        now = time.time()
        dt = now - state["last_tick"]
        state["last_tick"] = now

        # Center the options window over the camera window before session starts
        if not state["session_started"] and not state["options_locked"]:
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

            ui = options_ui.draw(serial_ctrl)
            cv2.imshow("Options", ui)

        # Read options
        if not state["session_started"] and not state["options_locked"]:
            state["session_seconds"] = int(options_ui.sliders[0]["value"])
            state["duration_s"] = int(options_ui.sliders[1]["value"])
            state["timeout_s"] = int(options_ui.sliders[2]["value"])
            state["penalty_rate"] = max(1.0, float(options_ui.sliders[3]["value"]))
            state["intensity_min_a"] = int(options_ui.sliders[4]["value"])
            state["intensity_max_a"] = int(options_ui.sliders[5]["value"])
            state["intensity_step_a"] = int(options_ui.sliders[6]["value"])
            state["intensity_window_a"] = int(options_ui.sliders[7]["value"])
            state["intensity_min_b"] = int(options_ui.sliders[8]["value"])
            state["intensity_max_b"] = int(options_ui.sliders[9]["value"])
            state["intensity_step_b"] = int(options_ui.sliders[10]["value"])
            state["intensity_window_b"] = int(options_ui.sliders[11]["value"])
            if state["intensity_max_a"] < state["intensity_min_a"]:
                state["intensity_max_a"] = state["intensity_min_a"]
                options_ui.sliders[5]["value"] = state["intensity_max_a"]
            if state["intensity_max_b"] < state["intensity_min_b"]:
                state["intensity_max_b"] = state["intensity_min_b"]
                options_ui.sliders[9]["value"] = state["intensity_max_b"]
            state["remaining_seconds"] = float(state["session_seconds"])

        if success and img is not None:
            h0, w0 = img.shape[:2]
            scale = 1.8
            nw, nh = int(w0 / scale), int(h0 / scale)
            x1 = (w0 - nw) // 2
            y1 = (h0 - nh) // 2
            img = img[y1:y1+nh, x1:x1+nw]
            img = cv2.resize(img, (w0, h0), interpolation=cv2.INTER_LINEAR)

        results = None
        if success and img is not None:
            imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = faceMesh.process(imgRGB)

        if results and results.multi_face_landmarks:
            for faceLms in results.multi_face_landmarks:
                mpDraw.draw_landmarks(img, faceLms, mpFaceMesh.FACEMESH_CONTOURS, drawSpec, drawSpec)
                h, w, _ = img.shape
                lm = faceLms.landmark

                def d(p1, p2):
                    return ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5

                width = d(lm[config.LIP_LEFT], lm[config.LIP_RIGHT])
                height = max(d(lm[config.LIP_UPPER], lm[config.LIP_LOWER]), 0.001)
                eye_dist = max(d(lm[config.EYE_LEFT], lm[config.EYE_RIGHT]), 0.001)
                ratio = (height / width) / eye_dist

                if state["ratio_ema"] is None:
                    state["ratio_ema"] = ratio
                else:
                    state["ratio_ema"] = (0.2 * ratio) + (0.8 * state["ratio_ema"])

                if state["baseline"] is not None:
                    super_off = max(0.0, config.SUPER_ON_OFFSET - 0.10)
                    on_thr = state["baseline"] + (config.SUPER_ON_OFFSET if state["challenge_mode"] else 0.0)
                    off_thr = state["baseline"] + (super_off if state["challenge_mode"] else -0.10)
                    if not state["smiling"] and state["ratio_ema"] > on_thr:
                        state["smiling"] = True
                    elif state["smiling"] and state["ratio_ema"] < off_thr:
                        state["smiling"] = False

                if state["session_started"] and state["challenge_mode"]:
                    if state["super_warning_active"] and now >= state["super_warning_end"]:
                        state["super_warning_active"] = False
                        state["super_challenge_active"] = True
                        duration = random.uniform(config.SUPER_CHALLENGE_MIN_S, config.SUPER_CHALLENGE_MAX_S)
                        state["super_challenge_end"] = now + duration
                    elif (not state["super_warning_active"] and not state["super_challenge_active"]
                          and now >= state["next_super_warning_time"]):
                        state["super_warning_active"] = True
                        state["super_warning_end"] = now + config.SUPER_WARNING_DURATION_S

                    if state["super_challenge_active"] and now >= state["super_challenge_end"]:
                        state["super_challenge_active"] = False
                        state["next_super_warning_time"] = now + random.uniform(config.SUPER_COOLDOWN_MIN_S, config.SUPER_COOLDOWN_MAX_S)

                    if state["super_challenge_active"] and not state["smiling"] and serial_ctrl.ser:
                        try:
                            channels_to_send = []
                            if state["channel_a_enabled"]:
                                channels_to_send.append("A")
                            if state["channel_b_enabled"]:
                                channels_to_send.append("B")

                            if "A" in channels_to_send:
                                base_a = min(state["intensity_max_a"], state["intensity_min_a"] + state["fail_count_a"] * state["intensity_step_a"])
                                high_a = min(state["intensity_max_a"], base_a + state["intensity_window_a"])
                                super_a = min(state["intensity_max_a"], high_a + config.SUPER_PUNISH_EXTRA)
                                serial_ctrl.write(f"A{super_a}\n")
                                if config.DEBUG:
                                    debug.add_serial(f"A{super_a}")
                            if "B" in channels_to_send:
                                base_b = min(state["intensity_max_b"], state["intensity_min_b"] + state["fail_count_b"] * state["intensity_step_b"])
                                high_b = min(state["intensity_max_b"], base_b + state["intensity_window_b"])
                                super_b = min(state["intensity_max_b"], high_b + config.SUPER_PUNISH_EXTRA)
                                serial_ctrl.write(f"B{super_b}\n")
                                if config.DEBUG:
                                    debug.add_serial(f"B{super_b}")

                            state["last_sent_channels"] = set(channels_to_send)
                            state["last_send_time"] = now
                            state["active_until"] = now + state["duration_s"]
                        except Exception:
                            pass
                        state["super_challenge_active"] = False
                        state["next_super_warning_time"] = now + random.uniform(config.SUPER_COOLDOWN_MIN_S, config.SUPER_COOLDOWN_MAX_S)

                if state["session_started"] and not state["smiling"] and serial_ctrl.ser:
                    now = time.time()
                    if state["super_challenge_active"]:
                        pass
                    elif now - state["last_send_time"] >= state["timeout_s"] and state["active_until"] <= now:
                        try:
                            channels_to_send = []
                            if state["channel_a_enabled"] and state["channel_b_enabled"]:
                                choice = random.choice(["A", "B", "AB"])
                                if choice in ("A", "AB"):
                                    channels_to_send.append("A")
                                if choice in ("B", "AB"):
                                    channels_to_send.append("B")
                            elif state["channel_a_enabled"]:
                                channels_to_send.append("A")
                            elif state["channel_b_enabled"]:
                                channels_to_send.append("B")

                            if "A" in channels_to_send:
                                base_a = min(state["intensity_max_a"], state["intensity_min_a"] + state["fail_count_a"] * state["intensity_step_a"])
                                high_a = min(state["intensity_max_a"], base_a + state["intensity_window_a"])
                                intensity_a = random.randint(base_a, high_a)
                                serial_ctrl.write(f"A{intensity_a}\n")
                                if config.DEBUG:
                                    debug.add_serial(f"A{intensity_a}")
                                state["fail_count_a"] += 1
                            if "B" in channels_to_send:
                                base_b = min(state["intensity_max_b"], state["intensity_min_b"] + state["fail_count_b"] * state["intensity_step_b"])
                                high_b = min(state["intensity_max_b"], base_b + state["intensity_window_b"])
                                intensity_b = random.randint(base_b, high_b)
                                serial_ctrl.write(f"B{intensity_b}\n")
                                if config.DEBUG:
                                    debug.add_serial(f"B{intensity_b}")
                                state["fail_count_b"] += 1

                            state["last_sent_channels"] = set(channels_to_send)
                            state["last_send_time"] = now
                            state["active_until"] = now + state["duration_s"]
                        except Exception:
                            pass

                if state["session_started"] and state["smiling"] and state["tease_mode"] and serial_ctrl.ser:
                    now = time.time()
                    if state["active_until"] <= now and state["tease_active_until"] <= now and now >= state["tease_next_time"]:
                        try:
                            tease_channels = []
                            if state["channel_a_enabled"]:
                                tease_channels.append("A")
                            if state["channel_b_enabled"]:
                                tease_channels.append("B")
                            if tease_channels:
                                if "A" in tease_channels:
                                    serial_ctrl.write(f"A{state['intensity_min_a']}\n")
                                    if config.DEBUG:
                                        debug.add_serial(f"A{state['intensity_min_a']}")
                                if "B" in tease_channels:
                                    serial_ctrl.write(f"B{state['intensity_min_b']}\n")
                                    if config.DEBUG:
                                        debug.add_serial(f"B{state['intensity_min_b']}")
                                state["tease_last_channels"] = set(tease_channels)
                                state["tease_active_until"] = now + state["tease_duration_s"]
                        except Exception:
                            pass
                        state["tease_next_time"] = now + random.uniform(config.TEASE_INTERVAL_MIN, config.TEASE_INTERVAL_MAX)

                if state["session_started"] and serial_ctrl.ser and state["active_until"] > 0 and time.time() >= state["active_until"]:
                    try:
                        if "A" in state["last_sent_channels"]:
                            serial_ctrl.write("A0\n")
                            if config.DEBUG:
                                debug.add_serial("A0")
                        if "B" in state["last_sent_channels"]:
                            serial_ctrl.write("B0\n")
                            if config.DEBUG:
                                debug.add_serial("B0")
                    except Exception:
                        pass
                    state["active_until"] = 0.0
                    state["last_sent_channels"] = set()

                if state["session_started"] and serial_ctrl.ser and state["tease_active_until"] > 0 and time.time() >= state["tease_active_until"]:
                    try:
                        if state["active_until"] <= time.time():
                            if "A" in state["tease_last_channels"] and "A" not in state["last_sent_channels"]:
                                serial_ctrl.write("A0\n")
                                if config.DEBUG:
                                    debug.add_serial("A0")
                            if "B" in state["tease_last_channels"] and "B" not in state["last_sent_channels"]:
                                serial_ctrl.write("B0\n")
                                if config.DEBUG:
                                    debug.add_serial("B0")
                    except Exception:
                        pass
                    state["tease_active_until"] = 0.0
                    state["tease_last_channels"] = set()

                color = (0, 255, 0) if state["smiling"] else (0, 0, 255)
                cv2.putText(img, f"Smile: {'YES' if state['smiling'] else 'NO'}", (10, 110),
                            cv2.FONT_HERSHEY_PLAIN, 2, color, 2)
                if state["super_warning_active"]:
                    text = config.SUPER_WARNING_TEXT
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    scale = 5.5
                    thickness = 10
                    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
                    x = (w - tw) // 2
                    y = (h + th) // 2
                    cv2.putText(img, text, (x, y), font, scale, (0, 0, 255), thickness)
                elif state["super_challenge_active"]:
                    if int(now * 2) % 2 == 0:
                        text = "KEEP HOLDING"
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        scale = 3.5
                        thickness = 8
                        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
                        x = (w - tw) // 2
                        y = (h + th) // 2
                        cv2.putText(img, text, (x, y), font, scale, (0, 0, 255), thickness)
                if config.DEBUG:
                    normal_req = state["baseline"] if state["baseline"] is not None else None
                    super_req = (state["baseline"] + config.SUPER_ON_OFFSET) if state["baseline"] is not None else None
                    req_normal_text = f"{normal_req:.3f}" if normal_req is not None else "N/A"
                    req_super_text = f"{super_req:.3f}" if super_req is not None else "N/A"
                    ratio_text = f"{state['ratio_ema']:.3f}" if state["ratio_ema"] is not None else "N/A"
                    dbg_scale = 2.4
                    dbg_color = color
                    cv2.putText(img, f"Ratio: {ratio_text}", (10, 260),
                                cv2.FONT_HERSHEY_PLAIN, dbg_scale, dbg_color, 2)
                    cv2.putText(img, f"Req normal: {req_normal_text}", (10, 310),
                                cv2.FONT_HERSHEY_PLAIN, dbg_scale, dbg_color, 2)
                    cv2.putText(img, f"Req super: {req_super_text}", (10, 360),
                                cv2.FONT_HERSHEY_PLAIN, dbg_scale, dbg_color, 2)

                    right_x = max(10, w - 360)
                    cv2.putText(img, "Serial:", (right_x, 260),
                                cv2.FONT_HERSHEY_PLAIN, dbg_scale, dbg_color, 2)
                    y_serial = 310
                    for msg in debug.history:
                        cv2.putText(img, msg, (right_x, y_serial),
                                    cv2.FONT_HERSHEY_PLAIN, dbg_scale, dbg_color, 2)
                        y_serial += 50
                if not state["session_started"]:
                    cv2.putText(img, f"Ratio: {state['ratio_ema']:.2f}", (10, 150),
                                cv2.FONT_HERSHEY_PLAIN, 2, color, 2)
                if state["baseline"] is None:
                    cv2.putText(img, "Press S to set smile baseline", (10, 190),
                                cv2.FONT_HERSHEY_PLAIN, 1.5, (0, 255, 255), 2)
                elif not state["session_started"]:
                    cv2.putText(img, f"Smile baseline: {state['baseline']:.2f}", (10, 190),
                                cv2.FONT_HERSHEY_PLAIN, 1.5, (0, 255, 255), 2)

        # Update session countdown (only after calibration)
        if state["session_started"] and state["remaining_seconds"] > 0:
            if not state["smiling"]:
                state["remaining_seconds"] += state["penalty_rate"] * dt
            else:
                state["remaining_seconds"] = max(0.0, state["remaining_seconds"] - dt)

        # Randomly change display mode
        if now >= state["next_switch_time"]:
            state["display_mode"] = random.choices(
                ["countdown", "hidden", "message"],
                weights=[0.6, 0.2, 0.2],
                k=1
            )[0]
            if state["display_mode"] == "message":
                state["current_message"] = random.choice(state["messages"])
            state["next_switch_time"] = now + random.uniform(3.0, 8.0)

        # Warm-up screen
        if state["warmup_active"] and img is not None:
            elapsed = time.time() - state["warmup_start"]
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
            x = (img.shape[1] - tw) // 2
            y = (img.shape[0] + th) // 2
            cv2.putText(img, text, (x, y), font, scale, color, thickness)
            if elapsed >= state["warmup_duration"] + state["warmup_done_hold"]:
                state["warmup_active"] = False
                state["session_started"] = True

        # Draw countdown / message (only after session starts)
        if state["session_started"] and not state["warmup_active"] and img is not None:
            minutes = int(state["remaining_seconds"]) // 60
            seconds = int(state["remaining_seconds"]) % 60
            countdown_text = f"{minutes:02d}:{seconds:02d}"

            if not state["smiling"]:
                font = cv2.FONT_HERSHEY_SIMPLEX
                scale = 12
                thickness = 10
                (tw, th), _ = cv2.getTextSize(countdown_text, font, scale, thickness)
                x = (img.shape[1] - tw) // 2
                y = (img.shape[0] + th) // 2
                cv2.putText(img, countdown_text, (x, y), font, scale, (0, 0, 255), thickness)
            else:
                if state["display_mode"] == "countdown":
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    scale = 1.8
                    thickness = 3
                    (tw, th), _ = cv2.getTextSize(countdown_text, font, scale, thickness)
                    x = img.shape[1] - tw - 10
                    y = 40
                    cv2.putText(img, countdown_text, (x, y), font, scale, (255, 255, 255), thickness)
                elif state["display_mode"] == "message":
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    scale = 1.8
                    thickness = 3
                    (tw, th), _ = cv2.getTextSize(state["current_message"], font, scale, thickness)
                    x = img.shape[1] - tw - 10
                    y = 40
                    cv2.putText(img, state["current_message"], (x, y), font, scale, (0, 255, 255), thickness)

        cTime = time.time()
        dt_fps = cTime - pTime
        _ = 1 / dt_fps if dt_fps > 0 else 0.0
        pTime = cTime

        if img is None:
            img = np.zeros((720, 1280, 3), dtype=np.uint8)
            cv2.putText(img, "Camera starting - it may take minute...", (40, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (200, 200, 200), 2)
        cv2.imshow("Image", img)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("s"), ord("S")) and state["ratio_ema"] is not None:
            state["baseline"] = state["ratio_ema"]
            state["smiling"] = False
            state["warmup_active"] = True
            state["warmup_start"] = time.time()
            if not state["options_locked"]:
                state["options_locked"] = True
                cv2.destroyWindow("Options")
        elif key in (ord("q"), ord("Q")):
            break

    if serial_ctrl.ser:
        try:
            serial_ctrl.disconnect()
        except Exception:
            pass
    cam.release()


if __name__ == "__main__":
    run()
