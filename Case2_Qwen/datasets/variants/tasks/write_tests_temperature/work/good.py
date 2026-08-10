class Thermometer:
    def __init__(self):
        self.readings = []

    def record(self, celsius: float) -> None:
        self.readings.append(celsius)

    def min_max(self):
        if not self.readings:
            raise ValueError("no readings")
        return min(self.readings), max(self.readings)

    def average(self):
        if not self.readings:
            raise ValueError("no readings")
        return round(sum(self.readings) / len(self.readings), 2)
