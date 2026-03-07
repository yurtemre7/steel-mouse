class MockMouse:
    def __init__(self, name: str, level=50, is_charging=False):
        self.name: str = name
        self.level: int = level
        self.is_charging: bool = is_charging

    @property
    def battery(self):
        result = {
            "level": self.level,
            "is_charging": self.is_charging,
        }
        return result

    def setLevel(self, level: int):
        self.level = level

    def setCharging(self, is_charging: bool):
        self.is_charging = is_charging

    def setName(self, name: str):
        self.name = name

    def close(self):
        pass
