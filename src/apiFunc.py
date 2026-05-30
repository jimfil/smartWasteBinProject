import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "..", "data"))
EVENTS_FILE = os.path.join(DATA_DIR, "events.log")

def load_json(filepath):
    """Loads and parses a standard JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def load_events(filepath=EVENTS_FILE, limit=None, sensor_id=None, start_time=None, end_time=None):
    """Loads, filters, and sorts events from a JSONL file. Supports date range filtering."""
    events = []

    if not os.path.exists(filepath):
        return events

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)

                # Filter by sensor_id if provided
                if sensor_id is not None and record.get("device_id") != sensor_id:
                    continue

                event_time = record.get("event_time")
                
                # Filter by start_time if provided
                if start_time and event_time < start_time:
                    continue
                
                # Filter by end_time if provided
                if end_time and event_time > end_time:
                    continue

                # Map internal data to the format expected by the API models
                mapped_event = {
                    "resultTime": record.get("event_time"),
                    "madeBySensor": record.get("device_id"),
                    "hasSimpleResult": record.get("motion_state"),
                    "pipeline_latency_ms": record.get("pipeline_latency_ms")
                }

                events.append(mapped_event)

            except json.JSONDecodeError:
                continue

    events.reverse()

    if limit is not None:
        events = events[:limit]

    return events


def load_models():
    """Dynamically loads all .jsonld models from the models directory."""
    models_dir = os.path.join(BASE_DIR, "models")
    all_data = []
    if not os.path.exists(models_dir):
        return all_data
    
    for filename in os.listdir(models_dir):
        if filename.endswith(".jsonld"):
            filepath = os.path.join(models_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    all_data.append(data)
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    return all_data


def load_bins():
    """Returns a list of all bins mapped to the API format."""
    models = load_models()
    bins = []
    for m in models:
        if m.get("@type") == "saref:Appliance":
            bins.append({
                "id": m.get("@id"),  # Use full URN
                "name": m.get("name"),
                "location": m.get("pipeline:collectionZone", "Unknown"),
                "status": m.get("pipeline:statusBin", "active")
            })
    return bins


def load_sensors():
    """Returns a list of all sensors mapped to the API format."""
    models = load_models()
    sensors = []
    for m in models:
        if m.get("@type") == "sosa:Sensor":
            mounted_on = m.get("pipeline:mountedOn", {})
            bin_urn = ""
            if isinstance(mounted_on, dict) and "@id" in mounted_on:
                bin_urn = mounted_on["@id"]
            
            sensors.append({
                "id": m.get("@id"),  # Use full URN
                "type": m.get("@type", "").split(":")[-1],
                "model": m.get("model"),
                "mounted_on": bin_urn,
                "status": m.get("pipeline:statusSensor", "active")
            })
    return sensors


def find_bin(bin_id):
    """Finds a specific bin by its identifier or full URN."""
    for b in load_bins():
        if b["id"] == bin_id or b["id"].split(":")[-1] == bin_id:
            return b
    return None


def find_sensor(sensor_id):
    """Finds a specific sensor by its identifier or full URN."""
    for s in load_sensors():
        if s["id"] == sensor_id or s["id"].split(":")[-1] == sensor_id:
            return s
    return None


def get_sensors_for_bin(bin_id):
    """Returns all sensor objects mounted on a specific bin."""
    found_bin = find_bin(bin_id)
    if not found_bin:
        return []
    
    bin_urn = found_bin["id"]
    bin_sensors = []
    for s in load_sensors():
        if s.get("mounted_on") == bin_urn:
            bin_sensors.append(s)
    return bin_sensors


def get_sensor_for_bin(bin_id):
    """Returns the sensor ID (full URN) of the FIRST sensor mounted on a specific bin."""
    sensors = get_sensors_for_bin(bin_id)
    if sensors:
        return sensors[0]["id"]
    return None


def load_nodered_alerts(filepath=None, limit=None):
    """Loads and returns alert records from nodered_alerts.log."""
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "nodered_alerts.log")
        
    alerts = []
    if not os.path.exists(filepath):
        return alerts
        
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                alerts.append(record)
            except json.JSONDecodeError:
                continue
                
    # Sort chronologically, newest first
    alerts.reverse()
    
    if limit is not None:
        alerts = alerts[:limit]
        
    return alerts
