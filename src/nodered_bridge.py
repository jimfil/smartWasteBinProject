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
                "acknowledged": False,
                "acknowledged_at": None,
                "solved": False,
                "solved_at": None
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
            bin_id = ack_data.get("bin_id", "unknown")
            client.publish(f"smartbin/{bin_id}/alerts/ack", json.dumps({
                "bin_id": bin_id,
                "level": ack_data.get("level", "unknown"),
                "ack_at": timestamp,
                "ack_by": ack_data.get("operator", "Node-RED Dashboard")
            }), qos=1, retain=True)
            
            # Update local log file to mark the MOST RECENT matching alert as acknowledged
            if os.path.exists(ALERTS_LOG):
                lines = []
                with open(ALERTS_LOG, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                target_ts = ack_data.get("timestamp")
                
                # Find the target alert to acknowledge
                updated = False
                for i in range(len(lines) - 1, -1, -1):  # Iterate backwards (most recent first)
                    if not lines[i].strip():
                        continue
                    try:
                        record = json.loads(lines[i])
                        alert_payload = record.get("alert", {})
                        
                        # Match condition
                        if target_ts:
                            is_match = (alert_payload.get("timestamp") == target_ts or record.get("timestamp") == target_ts)
                        else:
                            is_match = (alert_payload.get("bin_id") == ack_data.get("bin_id") and 
                                        (ack_data.get("level") == "ACK" or alert_payload.get("level") == ack_data.get("level")))
                                        
                        if is_match and not record.get("acknowledged", False):  # Only unacknowledged
                            record["acknowledged"] = True
                            record["acknowledged_at"] = timestamp
                            lines[i] = json.dumps(record) + "\n"
                            updated = True
                            print(f"[Node-RED Bridge] Marked alert as acknowledged: {alert_payload.get('bin_id')} - {alert_payload.get('level')}", flush=True)
                            break  # Stop after updating
                    except Exception:
                        pass
            # Write back only if we updated something
            if updated:
                with open(ALERTS_LOG, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                print(f"[Node-RED Bridge] Alert log updated successfully", flush=True)
            else:
                print(f"[Node-RED Bridge] No matching unacknowledged alert found", flush=True)
                    
        except Exception as e:
            print(f"[Node-RED Bridge] Error acknowledging alert: {e}", file=sys.stderr, flush=True)

    # 3. Solved State handler (listening to usage intensity changes)
    elif topic == "smartbin/nodered/usage_intensity":
        try:
            usage_data = json.loads(payload_str)
            fill_pct = usage_data.get("fill_pct", 0)
            
            if fill_pct < 75:
                if os.path.exists(ALERTS_LOG):
                    updated_lines = []
                    with open(ALERTS_LOG, "r", encoding="utf-8") as f:
                        for line in f:
                            if not line.strip():
                                continue
                            try:
                                record = json.loads(line)
                                bin_id = usage_data.get("bin_id", "bin-01")
                                alert_payload = record.get("alert", {})
                                
                                if alert_payload.get("bin_id") == bin_id and record.get("solved", False) is False:
                                    record["solved"] = True
                                    record["solved_at"] = timestamp
                                    print(f"[Node-RED Bridge] Alert for {bin_id} marked as solved.", flush=True)
                                    
                                updated_lines.append(json.dumps(record) + "\n")
                            except Exception:
                                updated_lines.append(line)
                    
                    with open(ALERTS_LOG, "w", encoding="utf-8") as f:
                        f.writelines(updated_lines)
        except Exception as e:
            print(f"[Node-RED Bridge] Error processing usage intensity for solve state: {e}", file=sys.stderr, flush=True)
    

        # 4. Alert Solved handler (manual override from HA button)
    elif topic == "smartbin/nodered/alert_solved":
        try:
            solved_data = json.loads(payload_str)
            bin_id = solved_data.get("bin_id", "bin-01")
            print(f"[Node-RED Bridge] Marking all alerts for {bin_id} as solved", flush=True)
            
            # Publish solved confirmation
            client.publish(f"smartbin/{bin_id}/alerts/solved", json.dumps({
                "bin_id": bin_id,
                "solved_at": timestamp,
                "solved_by": solved_data.get("operator", "Manual")
            }), qos=1, retain=True)
            
            # Update log file to mark all unresolved alerts as solved
            if os.path.exists(ALERTS_LOG):
                lines = []
                with open(ALERTS_LOG, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                count = 0
                for i in range(len(lines)):
                    if not lines[i].strip():
                        continue
                    try:
                        record = json.loads(lines[i])
                        alert_payload = record.get("alert", {})
                        if (alert_payload.get("bin_id") == bin_id and 
                            not record.get("solved", False)):
                            record["solved"] = True
                            record["solved_at"] = timestamp
                            lines[i] = json.dumps(record) + "\n"
                            count += 1
                    except Exception:
                        pass
                
                with open(ALERTS_LOG, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                
                print(f"[Node-RED Bridge] Marked {count} alerts as solved for {bin_id}", flush=True)
                
        except Exception as e:
            print(f"[Node-RED Bridge] Error marking alerts as solved: {e}", file=sys.stderr, flush=True)

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
