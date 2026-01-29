import cv2
import numpy as np


class OptionsUI:
    def __init__(self, state):
        self.state = state
        self.options_btn = {"x": 0, "y": 0, "w": 200, "h": 50}
        self.dragging = None
        self.sliders = [
            {"label": "Session seconds", "min": 1, "max": 3600, "value": state["session_seconds"]},
            {"label": "On duration (sec)", "min": 1, "max": 30, "value": state["duration_s"]},
            {"label": "Cooldown (sec)", "min": 1, "max": 60, "value": state["timeout_s"]},
            {"label": "Penalty x (1-10)", "min": 1, "max": 10, "value": int(state["penalty_rate"])},
            {"label": "A min", "min": 0, "max": 100, "value": state["intensity_min_a"]},
            {"label": "A max", "min": 0, "max": 100, "value": state["intensity_max_a"]},
            {"label": "A step", "min": 1, "max": 10, "value": state["intensity_step_a"]},
            {"label": "A window", "min": 0, "max": 20, "value": state["intensity_window_a"]},
            {"label": "B min", "min": 0, "max": 100, "value": state["intensity_min_b"]},
            {"label": "B max", "min": 0, "max": 100, "value": state["intensity_max_b"]},
            {"label": "B step", "min": 1, "max": 10, "value": state["intensity_step_b"]},
            {"label": "B window", "min": 0, "max": 20, "value": state["intensity_window_b"]},
        ]
        self.dropdown_open = False
        self.port_dropdown_rect = (0, 0, 0, 0)
        self.port_item_rects = []
        self.connect_btn_rect = (0, 0, 0, 0)
        self.toggle_a_rect = (0, 0, 0, 0)
        self.toggle_b_rect = (0, 0, 0, 0)
        self.toggle_tease_rect = (0, 0, 0, 0)
        self.toggle_challenge_rect = (0, 0, 0, 0)

    def draw(self, serial_ctrl):
        img = (24 * np.ones((520, 760, 3), dtype=np.uint8))
        cv2.putText(img, "Session Options", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (230, 230, 230), 2)

        ports = serial_ctrl.refresh_ports()
        if ports:
            if self.state["selected_port"] not in ports:
                self.state["selected_port"] = ports[0]
        else:
            self.state["selected_port"] = None

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
        for s in self.sliders[0:4]:
            y = draw_slider(s, left_x + 10, y, col_w - 20)

        # Modes section (left, below session)
        draw_section("MODES", left_x, 250, col_w)
        y = 260
        cv2.putText(img, "Tease mode", (left_x + 10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        box_tease = (left_x + 120, y - 12, 22, 22)
        cv2.rectangle(img, (box_tease[0], box_tease[1]), (box_tease[0] + box_tease[2], box_tease[1] + box_tease[3]), (200, 200, 200), 2)
        if self.state["tease_mode"]:
            cv2.line(img, (box_tease[0] + 4, box_tease[1] + 12), (box_tease[0] + 10, box_tease[1] + 18), (80, 200, 80), 2)
            cv2.line(img, (box_tease[0] + 10, box_tease[1] + 18), (box_tease[0] + 18, box_tease[1] + 4), (80, 200, 80), 2)

        y += 34
        cv2.putText(img, "Challenge (super smile)", (left_x + 10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        box_challenge = (left_x + 220, y - 12, 22, 22)
        cv2.rectangle(img, (box_challenge[0], box_challenge[1]), (box_challenge[0] + box_challenge[2], box_challenge[1] + box_challenge[3]), (200, 200, 200), 2)
        if self.state["challenge_mode"]:
            cv2.line(img, (box_challenge[0] + 4, box_challenge[1] + 12), (box_challenge[0] + 10, box_challenge[1] + 18), (80, 200, 80), 2)
            cv2.line(img, (box_challenge[0] + 10, box_challenge[1] + 18), (box_challenge[0] + 18, box_challenge[1] + 4), (80, 200, 80), 2)

        self.toggle_tease_rect = box_tease
        self.toggle_challenge_rect = box_challenge

        # Channel section (right)
        draw_section("CHANNELS", right_x, 60, col_w)
        y = 70
        cv2.putText(img, "Enable:", (right_x + 10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        box_a = (right_x + 90, y - 12, 22, 22)
        box_b = (right_x + 170, y - 12, 22, 22)
        cv2.rectangle(img, (box_a[0], box_a[1]), (box_a[0] + box_a[2], box_a[1] + box_a[3]), (200, 200, 200), 2)
        cv2.rectangle(img, (box_b[0], box_b[1]), (box_b[0] + box_b[2], box_b[1] + box_b[3]), (200, 200, 200), 2)
        if self.state["channel_a_enabled"]:
            cv2.line(img, (box_a[0] + 4, box_a[1] + 12), (box_a[0] + 10, box_a[1] + 18), (80, 200, 80), 2)
            cv2.line(img, (box_a[0] + 10, box_a[1] + 18), (box_a[0] + 18, box_a[1] + 4), (80, 200, 80), 2)
        if self.state["channel_b_enabled"]:
            cv2.line(img, (box_b[0] + 4, box_b[1] + 12), (box_b[0] + 10, box_b[1] + 18), (80, 200, 80), 2)
            cv2.line(img, (box_b[0] + 10, box_b[1] + 18), (box_b[0] + 18, box_b[1] + 4), (80, 200, 80), 2)
        cv2.putText(img, "A", (box_a[0] + 28, box_a[1] + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        cv2.putText(img, "B", (box_b[0] + 28, box_b[1] + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        self.toggle_a_rect = box_a
        self.toggle_b_rect = box_b

        # Channel A sliders
        y = 120
        cv2.putText(img, "Channel A", (right_x + 10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        y += 20
        for s in self.sliders[4:8]:
            y = draw_slider(s, right_x + 10, y, col_w - 20)

        # Channel B sliders
        y += 10
        cv2.putText(img, "Channel B", (right_x + 10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        y += 20
        for s in self.sliders[8:12]:
            y = draw_slider(s, right_x + 10, y, col_w - 20)

        # Apply button
        self.options_btn["x"] = 280
        self.options_btn["y"] = 455
        self.options_btn["w"] = 200
        self.options_btn["h"] = 45
        x, y, w, h = self.options_btn["x"], self.options_btn["y"], self.options_btn["w"], self.options_btn["h"]
        cv2.rectangle(img, (x, y), (x + w, y + h), (80, 200, 80), -1)
        cv2.putText(img, "APPLY", (x + 50, y + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

        # Serial status (draw first so dropdown layers above)
        cv2.putText(img, f"Status: {serial_ctrl.status}", (20, 420),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        # Serial port dropdown
        cv2.putText(img, "COM Port", (20, 330),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (210, 210, 210), 1)
        dd_x, dd_y, dd_w, dd_h = 20, 340, 200, 28
        cv2.rectangle(img, (dd_x, dd_y), (dd_x + dd_w, dd_y + dd_h), (70, 70, 70), -1)
        dd_text = self.state["selected_port"] if self.state["selected_port"] else "None"
        cv2.putText(img, dd_text, (dd_x + 8, dd_y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1)
        cv2.putText(img, "v" if not self.dropdown_open else "^", (dd_x + dd_w - 18, dd_y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1)
        self.port_dropdown_rect = (dd_x, dd_y, dd_w, dd_h)
        self.port_item_rects = []
        if self.dropdown_open:
            item_h = 24
            for i, port in enumerate(serial_ctrl.available_ports):
                iy = dd_y + dd_h + (i * item_h)
                cv2.rectangle(img, (dd_x, iy), (dd_x + dd_w, iy + item_h), (60, 60, 60), -1)
                cv2.putText(img, port, (dd_x + 8, iy + 17),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1)
                self.port_item_rects.append((dd_x, iy, dd_w, item_h, port))

        # Connect/Disconnect button
        is_connected = serial_ctrl.is_connected()
        cx, cy, cw, ch = 230, 340, 120, 28
        btn_color = (80, 200, 80) if is_connected else (80, 140, 220)
        btn_label = "DISCONNECT" if is_connected else "CONNECT"
        cv2.rectangle(img, (cx, cy), (cx + cw, cy + ch), btn_color, -1)
        cv2.putText(img, btn_label, (cx + 5, cy + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        self.connect_btn_rect = (cx, cy, cw, ch)

        return img

    def on_mouse(self, event, x, y, flags, param):
        if self.state["options_locked"]:
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            ddx, ddy, ddw, ddh = self.port_dropdown_rect
            if ddx <= x <= ddx + ddw and ddy <= y <= ddy + ddh:
                self.dropdown_open = not self.dropdown_open
                return
            if self.dropdown_open:
                for rx, ry, rw, rh, port in self.port_item_rects:
                    if rx <= x <= rx + rw and ry <= y <= ry + rh:
                        self.state["selected_port"] = port
                        self.dropdown_open = False
                        return
                self.dropdown_open = False

            cx, cy, cw, ch = self.connect_btn_rect
            if cx <= x <= cx + cw and cy <= y <= cy + ch:
                if self.state["serial_ctrl"].is_connected():
                    self.state["serial_ctrl"].disconnect()
                else:
                    self.state["serial_ctrl"].connect(self.state["selected_port"])
                return

            bx, by, bw, bh = self.options_btn["x"], self.options_btn["y"], self.options_btn["w"], self.options_btn["h"]
            if bx <= x <= bx + bw and by <= y <= by + bh:
                self.state["options_locked"] = True
                cv2.destroyWindow("Options")
                return

            tx, ty, tw, th = self.toggle_tease_rect
            if tx <= x <= tx + tw and ty <= y <= ty + th:
                self.state["tease_mode"] = not self.state["tease_mode"]
                return
            cx2, cy2, cw2, ch2 = self.toggle_challenge_rect
            if cx2 <= x <= cx2 + cw2 and cy2 <= y <= cy2 + ch2:
                self.state["challenge_mode"] = not self.state["challenge_mode"]
                return

            ax, ay, aw, ah = self.toggle_a_rect
            bx2, by2, bw2, bh2 = self.toggle_b_rect
            if ax <= x <= ax + aw and ay <= y <= ay + ah:
                self.state["channel_a_enabled"] = not self.state["channel_a_enabled"]
                return
            if bx2 <= x <= bx2 + bw2 and by2 <= y <= by2 + bh2:
                self.state["channel_b_enabled"] = not self.state["channel_b_enabled"]
                return
            for i, s in enumerate(self.sliders):
                x0, y0, x1, y1 = s.get("bar", (0, 0, 0, 0))
                if x0 <= x <= x1 and y0 <= y <= y1:
                    self.dragging = i
                    break
        elif event == cv2.EVENT_LBUTTONUP:
            self.dragging = None
        elif event == cv2.EVENT_MOUSEMOVE and self.dragging is not None:
            s = self.sliders[self.dragging]
            x0, _, x1, _ = s.get("bar", (0, 0, 0, 0))
            x_clamped = max(x0, min(x1, x))
            t = (x_clamped - x0) / max(1, (x1 - x0))
            s["value"] = int(round(s["min"] + t * (s["max"] - s["min"])))
