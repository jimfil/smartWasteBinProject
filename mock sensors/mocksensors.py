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
    def __init__(self, initial_temp_c=22.0):
        """
        Initializes the mock temperature sensor with a fixed value.
        :param initial_temp_c: The starting temperature in Celsius.
        """
        self.current_temp_c = float(initial_temp_c)

    def set_temperature_celsius(self, new_temp_c):
        """
        Manually update the temperature registered by the sensor.
        """
        self.current_temp_c = float(new_temp_c)

    def read_temperature_celsius(self):
        """
        Returns the current temperature in Celsius.
        """
        return round(self.current_temp_c, 2)

    def read_temperature_fahrenheit(self):
        """
        Returns the current temperature converted to Fahrenheit.
        Formula: (C * 9/5) + 32
        """
        fahrenheit = (self.current_temp_c * 9/5) + 32
        return round(fahrenheit, 2)

# Mock Weight Sensor
class MockWeightSensor:
    def __init__(self, initial_weight_kg=0.0):
        """
        Initializes the mock weight sensor with a fixed weight.
        :param initial_weight_kg: The starting weight in kilograms.
        """
        # Ensure weight cannot be negative
        self.current_weight = max(0.0, float(initial_weight_kg))

    def set_weight_kg(self, new_weight_kg):
        """
        Manually update the weight registered by the sensor.
        """
        self.current_weight = max(0.0, float(new_weight_kg))

    def read_weight_kg(self):
        """
        Returns the current weight reading.
        """
        return round(self.current_weight, 2)

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