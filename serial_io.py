import serial
import serial.tools.list_ports


class SerialController:
    def __init__(self, baud):
        self.baud = baud
        self.ser = None
        self.status = "Disconnected"
        self.error = ""
        self.available_ports = []

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.available_ports = ports
        return ports

    def connect(self, port):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        if not port:
            self.status = "No port selected"
            self.error = ""
            return False
        try:
            self.ser = serial.Serial(port, self.baud, timeout=0.1)
            self.status = f"Connected ({port})"
            self.error = ""
            return True
        except Exception as e:
            self.ser = None
            self.status = f"Failed ({port})"
            self.error = str(e)
            print(f"Serial open failed: {e}")
            return False

    def disconnect(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        self.status = "Disconnected"
        self.error = ""

    def is_connected(self):
        return self.ser is not None and self.ser.is_open

    def write(self, msg):
        if self.ser:
            self.ser.write(msg.encode())
