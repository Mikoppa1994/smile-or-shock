class DebugTracker:
    def __init__(self, max_history=6):
        self.last_serial = ""
        self.history = []
        self.max_history = max_history

    def add_serial(self, msg):
        self.last_serial = msg
        self.history.append(msg)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
