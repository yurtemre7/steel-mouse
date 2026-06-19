import time


class BatteryEstimator:
    def __init__(self, max_samples=20):
        self.history = []
        self.max_samples = max_samples
        self._last_level = None

    def add_sample(self, charge_level):
        if charge_level is None:
            return
        now = time.time()
        if self._last_level is not None and charge_level == self._last_level:
            return
        self.history.append((now, charge_level))
        self._last_level = charge_level
        if len(self.history) > self.max_samples:
            self.history.pop(0)

    def get_remaining_seconds(self):
        if len(self.history) < 2:
            return None

        total_rate = 0
        count = 0
        for i in range(1, len(self.history)):
            t_diff = self.history[i][0] - self.history[i - 1][0]
            c_diff = self.history[i - 1][1] - self.history[i][1]
            if t_diff > 0 and c_diff > 0:
                total_rate += c_diff / t_diff
                count += 1

        if count == 0:
            return None

        avg_rate = total_rate / count
        current_level = self.history[-1][1]

        if avg_rate <= 0 or current_level <= 0:
            return None

        remaining_seconds = int(current_level / avg_rate)
        return max(remaining_seconds, 0)

    def get_discharge_rate_per_hour(self):
        remaining = self.get_remaining_seconds()
        if remaining is None or remaining <= 0:
            return None
        current_level = self.history[-1][1] if self.history else 0
        return current_level / (remaining / 3600)

    def reset(self):
        self.history.clear()
        self._last_level = None
