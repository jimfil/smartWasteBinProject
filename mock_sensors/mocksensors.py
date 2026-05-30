import time
import random
import math
import json
import uuid
import os
import signal
from datetime import datetime, timezone
import click
import paho.mqtt.client as mqtt

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

# --- SIMULATION & MQTT PUBLISHING LOGIC ---

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_MODELS_DIR = os.path.join(_SCRIPT_DIR, "..", "src", "models")
if not os.path.exists(_MODELS_DIR):
    _MODELS_DIR = os.path.join(_SCRIPT_DIR, "src", "models")

def _load_context() -> dict:
    path = os.path.join(_MODELS_DIR, "context.jsonld")
    if os.path.exists(path):
        try:
            with open(path) as f:
                ctx = json.load(f)
            return ctx["@context"]
        except Exception:
            pass
    return {
        "@vocab": "https://schema.org/",
        "sosa": "http://www.w3.org/ns/sosa/",
        "ssn": "http://www.w3.org/ns/ssn/",
        "saref": "https://saref.etsi.org/core/",
        "bot": "https://w3id.org/bot#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "schema": "https://schema.org/",
        "pipeline": "https://github.com/jimfil/smartWasteBinProject/blob/main/docs/ontology.md#"
    }

def _load_bin_height_cm() -> float:
    path = os.path.join(_MODELS_DIR, "wastebin.jsonld")
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
            return float(data.get("pipeline:heightCm", 14.5))
        except Exception:
            pass
    return 14.5

JSONLD_CONTEXT = _load_context()
BIN_HEIGHT_CM = _load_bin_height_cm()

stop_flag = False

def handle_sigint(sig, frame):
    global stop_flag
    print("\n[Mock Sensors] Ctrl+C detected, terminating...")
    stop_flag = True

class SimulationState:
    def __init__(self, initial_fill_pct=10.0, initial_battery_pct=100.0):
        self.fill_pct = initial_fill_pct
        self.battery_pct = initial_battery_pct
        self.seq = 0
        self.run_id = str(uuid.uuid4())

def on_message(client, userdata, msg):
    topic = msg.topic
    payload_str = msg.payload.decode("utf-8", errors="replace")
    
    try:
        data = json.loads(payload_str)
        # Reset fill level to 0% if bin is emptied or solved
        if "emptied" in topic or data.get("state") == "emptied" or "solved" in topic:
            state = userdata.get("state") if isinstance(userdata, dict) else None
            if state:
                print(f"[Mock Sensors] Received bin empty/solved event! Resetting simulated fill level to 0.0%.")
                state.fill_pct = 0.0
    except Exception:
        pass

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[Mock Sensors] Connected to MQTT broker successfully!")
    else:
        print(f"[Mock Sensors] Connection failed with code {rc}")

@click.command()
@click.option("--bin-id", default="bin-01", help="Identifier of the wastebin")
@click.option("--broker", default="localhost", help="MQTT Broker address")
@click.option("--port", type=int, default=1883, help="MQTT Broker port")
@click.option("--interval", type=float, default=5.0, help="Publish interval in seconds")
@click.option("--verbose", is_flag=True, help="Print details of published events")
def main(bin_id, broker, port, interval, verbose):
    global stop_flag
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    state = SimulationState(initial_fill_pct=10.0, initial_battery_pct=100.0)

    # Initialize mock sensors
    ultrasonic_sensor = MockUltrasonicSensor(bin_height_cm=BIN_HEIGHT_CM)
    temp_sensor = MockTemperatureSensor(initial_temp_c=22.0)
    weight_sensor = MockWeightSensor(initial_weight_kg=0.5)
    battery_sensor = MockBatterySensor(initial_pct=100.0)

    # Setup MQTT Client
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, userdata={"state": state})
    except AttributeError:
        client = mqtt.Client(userdata={"state": state})
        
    client.on_connect = on_connect
    client.on_message = on_message

    if verbose:
        print(f"[Mock Sensors] Connecting to broker {broker}:{port}...")
    
    try:
        client.connect(broker, port, keepalive=60)
    except Exception as e:
        print(f"[Mock Sensors] Error connecting to broker: {e}. Ensure the Mosquitto service is running.")
        return

    client.loop_start()

    # Subscribe to status and solved topics for reset coordination
    status_topic = f"smartbin/{bin_id}/status"
    solved_topic = f"smartbin/{bin_id}/alerts/solved"
    client.subscribe(status_topic, qos=1)
    client.subscribe(solved_topic, qos=1)
    
    if verbose:
        print(f"[Mock Sensors] Subscribed to status reset topics: {status_topic}, {solved_topic}")
        print(f"[Mock Sensors] Starting publication loop. Run ID: {state.run_id}")

    try:
        while not stop_flag:
            # 1. Update fill percentage (grow slowly, cap at 100%)
            if state.fill_pct >= 100.0:
                state.fill_pct = 100.0
            else:
                state.fill_pct += random.uniform(0.5, 2.5)
                if state.fill_pct > 100.0:
                    state.fill_pct = 100.0

            # 2. Drain battery very slowly
            state.battery_pct = max(0.0, state.battery_pct - random.uniform(0.01, 0.05))

            # 3. Telemetry generation using classes
            pulse_width = ultrasonic_sensor.read_echo_pulse_width(state.fill_pct)
            distance = decode_pulse_to_distance(pulse_width)

            temp_c = temp_sensor.read_temperature_celsius()
            new_temp = max(-10.0, min(50.0, temp_c + random.uniform(-0.2, 0.2)))
            temp_sensor.set_temperature_celsius(new_temp)
            temp_f = temp_sensor.read_temperature_fahrenheit()

            # Correlate weight with fill percentage
            simulated_weight = 0.5 + (state.fill_pct / 100.0) * 7.5 + random.uniform(-0.1, 0.1)
            simulated_weight = max(0.0, simulated_weight)
            weight_sensor.set_weight_kg(simulated_weight)
            weight_kg = weight_sensor.read_weight_kg()
            weight_g = weight_kg * 1000.0

            battery_sensor.set_percentage(state.battery_pct)
            battery_pct = battery_sensor.read_percentage()

            timestamp = utc_now_iso()
            state.seq += 1

            # 4. Formulate JSON-LD payload observation records
            ultrasonic_payload = {
                "@context": JSONLD_CONTEXT,
                "@type": "sosa:Observation",
                "device_id": f"urn:dev:team05:ultrasonic-01",
                "sensor_ref": f"urn:dev:team05:ultrasonic-01",
                "wastebin_ref": f"urn:wastebin:{bin_id}",
                "environment_ref": "urn:env:kypes-02",
                "event_time": timestamp,
                "event_type": "ultrasonic",
                "distance_cm": round(distance, 2),
                "fill_pct": int(round(state.fill_pct)),
                "pulse_width_s": round(pulse_width, 6),
                "seq": state.seq,
                "run_id": state.run_id
            }

            temp_payload = {
                "@context": JSONLD_CONTEXT,
                "@type": "sosa:Observation",
                "device_id": f"urn:dev:team05:temp-01",
                "sensor_ref": f"urn:dev:team05:temp-01",
                "wastebin_ref": f"urn:wastebin:{bin_id}",
                "environment_ref": "urn:env:kypes-02",
                "event_time": timestamp,
                "event_type": "temperature",
                "temperature_c": temp_c,
                "temperature_f": temp_f,
                "seq": state.seq,
                "run_id": state.run_id
            }

            weight_payload = {
                "@context": JSONLD_CONTEXT,
                "@type": "sosa:Observation",
                "device_id": f"urn:dev:team05:weight-01",
                "sensor_ref": f"urn:dev:team05:weight-01",
                "wastebin_ref": f"urn:wastebin:{bin_id}",
                "environment_ref": "urn:env:kypes-02",
                "event_time": timestamp,
                "event_type": "weight",
                "weight_kg": weight_kg,
                "weight_g": round(weight_g, 2),
                "seq": state.seq,
                "run_id": state.run_id
            }

            battery_payload = {
                "@context": JSONLD_CONTEXT,
                "@type": "sosa:Observation",
                "device_id": f"urn:dev:team05:battery-01",
                "sensor_ref": f"urn:dev:team05:battery-01",
                "wastebin_ref": f"urn:wastebin:{bin_id}",
                "environment_ref": "urn:env:kypes-02",
                "event_time": timestamp,
                "event_type": "battery",
                "battery_pct": battery_pct,
                "seq": state.seq,
                "run_id": state.run_id
            }

            # 5. Publish structured telemetry
            u_topic = f"smartbin/{bin_id}/ultrasonic-01/events"
            t_topic = f"smartbin/{bin_id}/temp-01/events"
            w_topic = f"smartbin/{bin_id}/weight-01/events"
            b_topic = f"smartbin/{bin_id}/battery-01/events"

            client.publish(u_topic, json.dumps(ultrasonic_payload), qos=1)
            client.publish(t_topic, json.dumps(temp_payload), qos=1)
            client.publish(w_topic, json.dumps(weight_payload), qos=1)
            client.publish(b_topic, json.dumps(battery_payload), qos=1)

            # 6. Legacy telemetry endpoints for backwards compatibility
            legacy_fill_topic = f"smartbin/{bin_id}/fill_level"
            legacy_weight_topic = f"smartbin/{bin_id}/weight"

            client.publish(legacy_fill_topic, str(int(round(state.fill_pct))), qos=1, retain=True)
            client.publish(legacy_weight_topic, str(round(weight_g, 2)), qos=1, retain=True)

            if verbose:
                print(f"[{timestamp}] Published sequence #{state.seq}:")
                print(f"  * Fill: {state.fill_pct:.1f}% -> Distance: {distance:.2f} cm (topic: {u_topic})")
                print(f"  * Temp: {temp_c:.2f}°C / {temp_f:.2f}°F (topic: {t_topic})")
                print(f"  * Weight: {weight_kg:.2f} kg / {weight_g:.1f} g (topic: {w_topic})")
                print(f"  * Battery: {battery_pct:.1f}% (topic: {b_topic})")
                print(f"  * Legacy Fill & Weight published.")

            time.sleep(interval)
    except KeyboardInterrupt:
        pass

    print("[Mock Sensors] Disconnecting from broker...")
    client.loop_stop()
    client.disconnect()
    print("[Mock Sensors] Terminated successfully.")

def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )

if __name__ == "__main__":
    main()