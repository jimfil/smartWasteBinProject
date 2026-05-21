#!/usr/bin/env python3
import json
import os
import sys
import time
import signal
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

# Default MQTT broker settings
BROKER_HOST = os.environ.get("BROKER_HOST", "localhost")
BROKER_PORT = int(os.environ.get("BROKER_PORT", 1883))

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "..", "data"))
ALERTS_LOG = os.path.join(DATA_DIR, "nodered_alerts.log")

stop_flag = False

def handle_sigint(sig, frame):
    global stop_flag
    print("\n[Node-RED Bridge] Terminating bridge...", flush=True)
    stop_flag = True

def on_connect(client, userdata, flags, rc, properties=None):
    """Callback for when the client connects to the broker."""
    if rc == 0:
        print(f"[Node-RED Bridge] Connected to MQTT broker at {BROKER_HOST}:{BROKER_PORT}", flush=True)
        # Subscribe to Node-RED outputs and bridge control topics
        client.subscribe("smartbin/nodered/#", qos=1)
        print("[Node-RED Bridge] Subscribed to smartbin/nodered/#", flush=True)
    else:
        print(f"[Node-RED Bridge] Connection failed with code {rc}", flush=True)

def on_message(client, userdata, msg):
    """Callback for incoming MQTT messages."""
    topic = msg.topic
    payload_str = msg.payload.decode("utf-8", errors="replace")
    
    print(f"[Node-RED Bridge] Message received on {topic}: {payload_str[:100]}", flush=True)
    
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    # 1. Alert Log handler (Flow D forwards alerts to smartbin/nodered/alert_log)
    if topic == "smartbin/nodered/alert_log":
        try:
            # Attempt to parse payload as JSON
            try:
                alert_data = json.loads(payload_str)
            except json.JSONDecodeError:
                alert_data = {"raw_payload": payload_str}
                
            alert_record = {
                "topic": topic,
                "alert": alert_data,
                "timestamp": timestamp,
                "acknowledged": False
            }
            
            # Append to nodered_alerts.log
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(ALERTS_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert_record) + "\n")
            print(f"[Node-RED Bridge] Logged alert to {ALERTS_LOG}", flush=True)
            
        except Exception as e:
            print(f"[Node-RED Bridge] Error saving alert: {e}", file=sys.stderr, flush=True)
            
    # 2. Alert Acknowledgement handler (e.g. from Dashboard click or bridge command)
    elif topic == "smartbin/nodered/alert_ack":
        try:
            ack_data = json.loads(payload_str)
            print(f"[Node-RED Bridge] Acknowledging alert: {ack_data}", flush=True)
            
            # Forward acknowledgment into main pipeline
            client.publish("smartbin/alerts/ack", json.dumps({
                "bin_id": ack_data.get("bin_id", "unknown"),
                "level": ack_data.get("level", "unknown"),
                "ack_at": timestamp,
                "ack_by": ack_data.get("operator", "Node-RED Dashboard")
            }), qos=1, retain=True)
            
            # Update local log file to mark matching alert as acknowledged
            if os.path.exists(ALERTS_LOG):
                updated_lines = []
                with open(ALERTS_LOG, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            record = json.loads(line)
                            alert_payload = record.get("alert", {})
                            if (alert_payload.get("bin_id") == ack_data.get("bin_id") and 
                                    alert_payload.get("level") == ack_data.get("level")):
                                record["acknowledged"] = True
                                record["ack_timestamp"] = timestamp
                            updated_lines.append(json.dumps(record) + "\n")
                        except Exception:
                            updated_lines.append(line)
                
                with open(ALERTS_LOG, "w", encoding="utf-8") as f:
                    f.writelines(updated_lines)
                    
        except Exception as e:
            print(f"[Node-RED Bridge] Error acknowledging alert: {e}", file=sys.stderr, flush=True)

def main():
    global stop_flag
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)
    
    # Automatic bootstrap logic for fresh clones
    nodered_data_dir = os.path.join(BASE_DIR, "..", "nodered_data")
    nodered_flows_path = os.path.join(nodered_data_dir, "flows.json")
    src_flows_path = os.path.join(BASE_DIR, "flows.json")
    
    if os.path.exists(src_flows_path) and not os.path.exists(nodered_flows_path):
        try:
            print(f"[Node-RED Bridge] Bootstrapping {nodered_flows_path} from {src_flows_path}...", flush=True)
            os.makedirs(nodered_data_dir, exist_ok=True)
            import shutil
            shutil.copy(src_flows_path, nodered_flows_path)
            print("[Node-RED Bridge] Bootstrapped Node-RED flows successfully!", flush=True)
        except Exception as e:
            print(f"[Node-RED Bridge] Failed to bootstrap flows: {e}", file=sys.stderr, flush=True)

    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Setup MQTT Client
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="nodered-bridge", clean_session=False)
    except AttributeError:
        client = mqtt.Client(client_id="nodered-bridge", clean_session=False)
        
    client.on_connect = on_connect
    client.on_message = on_message
    
    print(f"[Node-RED Bridge] Connecting to MQTT broker {BROKER_HOST}:{BROKER_PORT}...", flush=True)
    
    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    except Exception as e:
        print(f"[Node-RED Bridge] Error connecting to broker: {e}. Exiting.", file=sys.stderr, flush=True)
        sys.exit(1)
        
    client.loop_start()
    
    print("[Node-RED Bridge] Bridge is active and listening. Press Ctrl+C to stop.", flush=True)
    
    try:
        while not stop_flag:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
        
    print("[Node-RED Bridge] Disconnecting client...", flush=True)
    client.loop_stop()
    client.disconnect()
    print("[Node-RED Bridge] Exited cleanly.", flush=True)

if __name__ == "__main__":
    main()
