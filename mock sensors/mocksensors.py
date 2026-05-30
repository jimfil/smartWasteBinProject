import time
import random
import math

# Mock Ultrasonic Sensor
class MockUltrasonicSensor:
    def __init__(self, bin_height_cm=100):
        """
        Initializes the mock sensor.
        :param bin_height_cm: The total depth of the empty bin in centimeters.
        """
        self.bin_height = bin_height_cm
        self.SPEED_OF_SOUND_CM_PER_US = 0.0343  # Speed of sound: ~343 m/s or 0.0343 cm/µs
        
    def _calculate_pulse_width(self, distance_cm):
        """
        Converts a distance into the round-trip echo pulse width in seconds.
        Formula: t = (distance * 2) / speed_of_sound
        """
        # Round trip time in microseconds
        time_us = (distance_cm * 2) / self.SPEED_OF_SOUND_CM_PER_US
        # Convert to seconds for Python's time.sleep()
        return time_us / 1_000_000

    def read_echo_pulse_width(self, current_fill_level_pct):
        """
        Simulates triggering the sensor and reading the Echo pin pulse width.
        :param current_fill_level_pct: How full the bin is (0 to 100)
        :return: Pulse width in seconds (simulating the physical high pulse duration)
        """
        # Ensure percentage is bounded between 0 and 100
        current_fill_level_pct = max(0, min(100, current_fill_level_pct))
        
        # Calculate actual distance to the trash surface
        filled_height = (current_fill_level_pct / 100.0) * self.bin_height
        actual_distance = self.bin_height - filled_height
        
        # Add a tiny bit of random environmental noise/fluctuation (+/- 0.5 cm)
        actual_distance += random.uniform(-0.5, 0.5)
        actual_distance = max(2.0, actual_distance) # HC-SR04 minimum physical limit is ~2cm
        
        # Calculate how long the Echo pin *should* stay HIGH
        pulse_width_seconds = self._calculate_pulse_width(actual_distance)
        
        # Simulate the physical hardware behavior (blocking while Echo is HIGH)
        # Note: In a real simulation script, this mimics the time the microcontroller waits.
        time.sleep(pulse_width_seconds) 
        
        return pulse_width_seconds

# --- HOW TO DECODE THE MOCK SENSOR ---
def decode_pulse_to_distance(pulse_width_seconds):
    """
    Converts the pulse width back into distance using your formula:
    distance = (t_us / 58) or (t_seconds * 1,000,000) / 58
    """
    pulse_width_us = pulse_width_seconds * 1_000_000
    distance_cm = pulse_width_us / 58
    return distance_cm

# Mock Temperature Sensor
class MockTemperatureSensor:
    def __init__(self, base_temp=22.0, daily_variance=5.0):
        """
        Initializes the mock temperature sensor.
        :param base_temp: The average baseline room temperature in Celsius.
        :param daily_variance: How much the temperature swings above/below baseline during the day.
        """
        self.base_temp = base_temp
        self.variance = daily_variance

    def _get_diurnal_offset(self):
        """
        Uses the current system time to simulate a 24-hour temperature cycle.
        Highest temperatures usually occur in late afternoon, lowest in early morning.
        """
        # Get current time components
        now = time.localtime()
        current_hour = now.tm_hour + (now.tm_min / 60.0)
        
        # Sine wave shifted so peak is roughly at 15:00 (3 PM) and trough at 3:00 AM
        # Period is 24 hours (2 * pi / 24)
        angle = (current_hour - 9) * (2 * math.pi / 24)
        return math.sin(angle) * self.variance

    def read_temperature_celsius(self):
        """
        Simulates reading the sensor. Returns temperature in Celsius.
        """
        # 1. Get the baseline cycle temperature for the current time of day
        expected_temp = self.base_temp + self._get_diurnal_offset()
        
        # 2. Inject random hardware/environmental noise (+/- 0.3°C)
        noise = random.uniform(-0.3, 0.3)
        final_temp = expected_temp + noise
        
        return round(final_temp, 2)

    def read_temperature_fahrenheit(self):
        """
        Convenience method to return Fahrenheit conversion.
        Formula: (C * 9/5) + 32
        """
        celsius = self.read_temperature_celsius()
        fahrenheit = (celsius * 9/5) + 32
        return round(fahrenheit, 2) 

# Mock Weight Sensor
class MockWeightSensor:
    def __init__(self, max_capacity_kg=50.0):
        """
        Initializes the mock load cell sensor.
        :param max_capacity_kg: The physical maximum limit the scale can handle before maxing out.
        """
        self.max_capacity = max_capacity_kg
        self.current_raw_weight = 0.0
        self.offset = 0.0  # Used for taring/zeroing the scale

    def tare(self):
        """
        Resets the baseline of the scale to 0.0. 
        Simulates zeroing out the weight of the physical bin liner or container itself.
        """
        # Set the offset to match the current weight so the net reading becomes zero
        self.offset = self.current_raw_weight
        print("[Sensor Action] Scale Tared / Zeroed.")

    def add_trash(self, weight_kg):
        """
        Simulates someone physically throwing an item into the bin.
        """
        self.current_raw_weight += weight_kg
        if self.current_raw_weight > self.max_capacity:
            self.current_raw_weight = self.max_capacity

    def empty_bin(self):
        """
        Simulates a waste truck lifting and completely emptying the bin.
        """
        self.current_raw_weight = 0.0 + self.offset

    def read_weight_kg(self):
        """
        Simulates reading the weight from the HX711/Load Cell circuit.
        Returns the net weight in kilograms.
        """
        # Calculate net weight based on the tare offset
        net_weight = self.current_raw_weight - self.offset
        
        # Inject minor sensor drift/noise typical of load cells (+/- 0.02 kg or 20 grams)
        noise = random.uniform(-0.02, 0.02)
        final_reading = net_weight + noise
        
        # Real scales don't usually register negative numbers due to noise when empty
        if final_reading < 0.01:
            final_reading = 0.0
            
        return round(final_reading, 2)

# Battery Percentage Mock
class MockBatterySensor:
    def __init__(self, initial_pct=100.0):
        """
        Initializes the mock battery with a fixed percentage.
        :param initial_pct: The fixed battery percentage (0.0 to 100.0)
        """
        # Ensure the value is locked between 0 and 100 right from the start
        self.battery_level = max(0.0, min(100.0, float(initial_pct)))

    def set_percentage(self, new_pct):
        """
        Manually update the battery to a specific percentage if needed.
        """
        self.battery_level = max(0.0, min(100.0, float(new_pct)))

    def read_percentage(self):
        """
        Returns the current battery percentage.
        """
        return round(self.battery_level, 2)