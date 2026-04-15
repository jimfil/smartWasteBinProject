import os
import sys
import threading
import time

# Add root folder to sys.path to allow absolute imports from 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ["GPIOZERO_PIN_FACTORY"] = "mock"
from gpiozero import Device
from gpiozero.pins.mock import MockFactory

Device.pin_factory = MockFactory()

def simulate_motion(pin_num):
    pin = Device.pin_factory.pin(pin_num)
    time.sleep(1.0)
    print("\n[Mock] Simulating motion START...", file=sys.stderr)
    pin.drive_high()
    time.sleep(2.0)
    pin.drive_low()
    time.sleep(2.0)
    pin.drive_high()
    print("\n[Mock] Simulating motion END...", file=sys.stderr)
    pin.drive_low()
    time.sleep(1.0)

# Start the simulation thread in parallel
t = threading.Thread(target=simulate_motion, args=(18,), daemon=True)
t.start()

# Now import and run the pipeline
from src import pipeline
from click.testing import CliRunner

runner = CliRunner()
result = runner.invoke(pipeline.main, [
    "--device-id", "pir-01",
    "--pin", "18",
    "--sample-interval", "0.1",
    "--cooldown", "1.0",
    "--min-high", "0.2",
    "--queue-size", "100",
    "--consumer-delay", "0.0",
    "--duration", "5",
    "--out", "motion_pipeline.log",
    "--verbose"
])

print(result.output)
