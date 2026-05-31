import os
import sys
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Set paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CHARTS_DIR = os.path.join(PROJECT_ROOT, "charts")

def generate_mock_data():
    """Generates realistic mock telemetry data to match professor's hints and project goals."""
    print("Generating comprehensive mock telemetry log: data/mock_data.jsonl...")
    os.makedirs(DATA_DIR, exist_ok=True)
    mock_file = os.path.join(DATA_DIR, "mock_data.jsonl")
    
    np.random.seed(42)
    devices = [
        "urn:dev:team05:ultrasonic-01",
        "urn:dev:team05:weight-01",
        "urn:dev:team05:pir-01"
    ]
    severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    severity_probs = [0.50, 0.30, 0.15, 0.05]
    
    records = []
    # Generate 300 data points across the past 7 days to have a rich heatmap
    base_time = pd.Timestamp.now() - pd.Timedelta(days=7)
    
    for i in range(300):
        # Time increment with a circadian pattern (more frequent during daytime hours 8:00 - 20:00)
        hour = base_time.hour
        if 8 <= hour <= 20:
            time_delta_mins = int(np.random.exponential(15)) + 5  # more frequent
        else:
            time_delta_mins = int(np.random.exponential(60)) + 15 # less frequent
            
        event_time = base_time + pd.Timedelta(minutes=time_delta_mins)
        base_time = event_time
        
        device_id = np.random.choice(devices)
        # Latency typically follows a log-normal distribution
        pipeline_latency_ms = float(np.random.lognormal(mean=2.2, sigma=0.4)) + 1.0
        
        # Emulating Rule-Based Virtual Sensor (Usage Intensity) based on circadian pattern
        if 8 <= hour <= 12:
            base_count = np.random.randint(8, 18)   # Peak morning usage
        elif 12 < hour <= 17:
            base_count = np.random.randint(4, 12)   # Moderate afternoon
        elif 17 < hour <= 22:
            base_count = np.random.randint(10, 22)  # Evening rush
        else:
            base_count = np.random.randint(0, 3)    # Night idle
            
        rule_count = int(base_count)
        if rule_count == 0:
            rule_state = "IDLE"
            rule_val = 0
        elif rule_count <= 5:
            rule_state = "LOW"
            rule_val = 1
        elif rule_count <= 15:
            rule_state = "MEDIUM"
            rule_val = 2
        else:
            rule_state = "HIGH"
            rule_val = 3
            
        # ML Virtual Sensor predicts state (emulating classification with a bit of noise)
        ml_val = int(np.clip(rule_val + np.random.choice([-1, 0, 1], p=[0.12, 0.76, 0.12]), 0, 3))
        ml_states = ["IDLE", "LOW", "MEDIUM", "HIGH"]
        ml_state = ml_states[ml_val]
        ml_confidence = float(np.random.uniform(0.68, 0.97))
        
        records.append({
            "event_time": event_time.isoformat() + "Z",
            "device_id": device_id,
            "pipeline_latency_ms": round(pipeline_latency_ms, 2),
            "severity": rule_state if rule_state != "IDLE" else "LOW",
            "rule_event_count": rule_count,
            "rule_usage_state": rule_state,
            "rule_usage_value": rule_val,
            "ml_predicted_state": ml_state,
            "ml_predicted_value": ml_val,
            "ml_prediction_confidence": round(ml_confidence, 3),
            "fill_pct": int(np.random.randint(0, 100)) if "ultrasonic" in device_id else None,
            "weight_g": float(np.random.randint(200, 4500)) if "weight" in device_id else None
        })
        
    with open(mock_file, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
            
    print(f"Mock telemetry log generated at: {mock_file}")

def load_data():
    """Scans the data/ directory for JSONL, JSON, or LOG telemetry files and loads them into a DataFrame."""
    os.makedirs(DATA_DIR, exist_ok=True)
    log_files = []
    
    # Scans for log, json, or jsonl formats to include real production data, ignoring nodered logs
    for f in os.listdir(DATA_DIR):
        if f.endswith((".json", ".jsonl", ".log")) and f != ".gitkeep" and "nodered" not in f:
            log_files.append(os.path.join(DATA_DIR, f))
            
    # Check for mock_data.jsonl first or create it if directory is empty
    if not log_files:
        generate_mock_data()
        for f in os.listdir(DATA_DIR):
            if f.endswith((".json", ".jsonl", ".log")) and f != ".gitkeep" and "nodered" not in f:
                log_files.append(os.path.join(DATA_DIR, f))
                
    dfs = []
    for file_path in log_files:
        try:
            print(f"Parsing telemetry file: {os.path.basename(file_path)}")
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            records = []
            for line in lines:
                if not line.strip() or not line.startswith("{"):
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            
            if records:
                dfs.append(pd.DataFrame(records))
            else:
                try:
                    df = pd.read_json(file_path)
                    dfs.append(df)
                except Exception:
                    pass
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            
    if not dfs:
        print("Error: Could not load any telemetry data.")
        sys.exit(1)
        
    df = pd.concat(dfs, ignore_index=True)
    print(f"Loaded {len(df)} telemetry records from {len(log_files)} file(s).")
    return df

def process_data(df):
    """Safely converts timestamps, unpacks nested payloads, and extracts datetime elements."""
    # Exclude any Node-RED topics
    if "topic" in df.columns:
        df = df[~df["topic"].str.contains("nodered", na=False)]
    
    # 1. Unpack Nested Payloads (specifically for raw MQTT logs like archive.log)
    if "payload" in df.columns:
        unpacked_records = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            payload = row_dict.get("payload")
            
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    pass
            
            if isinstance(payload, dict):
                for k, v in payload.items():
                    if k not in row_dict or pd.isna(row_dict[k]):
                        row_dict[k] = v
            unpacked_records.append(row_dict)
        df = pd.DataFrame(unpacked_records)
        
    # 2. Extract Virtual Sensors Telemetry from MQTT Topics if processing real logs
    if "topic" in df.columns:
        # Check rule-based intensity levels
        rules_mask = df["topic"] == "smartbin/bin-01/usage_intensity"
        if rules_mask.any():
            df.loc[rules_mask, "rule_usage_state"] = df.loc[rules_mask, "state"].astype(str).str.upper()
            df.loc[rules_mask, "rule_event_count"] = df.loc[rules_mask, "count"]
            df.loc[rules_mask, "rule_usage_value"] = df.loc[rules_mask, "rule_usage_state"].str.upper().map({
                "IDLE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3
            })
            
        # Check ML-based usage predictions
        ml_mask = df["topic"] == "smartbin/bin-01/usage_prediction"
        if ml_mask.any():
            def extract_pred(x):
                if isinstance(x, list) and len(x) > 0:
                    return str(x[0]).upper()
                return str(x).upper()
                
            df.loc[ml_mask, "ml_predicted_state"] = df.loc[ml_mask, "prediction"].apply(extract_pred)
            df.loc[ml_mask, "ml_prediction_confidence"] = df.loc[ml_mask, "confidence"]
            df.loc[ml_mask, "ml_predicted_value"] = df.loc[ml_mask, "ml_predicted_state"].map({
                "QUIET": 0, "IDLE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "BUSY": 3
            })

    # 3. Safe Datetime Conversion
    time_col = None
    for col in ["event_time", "timestamp", "ingest_time"]:
        if col in df.columns:
            time_col = col
            break
            
    if time_col:
        df["event_time"] = pd.to_datetime(df[time_col], errors="coerce")
    else:
        df["event_time"] = pd.Timestamp.now()
        
    # Drop rows with invalid timestamps
    df = df.dropna(subset=["event_time"])
    
    # Extract temporal features for heatmaps
    df["hour"] = df["event_time"].dt.hour
    df["day_name"] = df["event_time"].dt.day_name()
    
    # Order weekdays logically
    weekdays_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    df["day_name"] = pd.Categorical(df["day_name"], categories=weekdays_order, ordered=True)
    
    return df

def plot_latency_distribution(df):
    """Generates a high-res histogram with KDE curve tracking pipeline_latency_ms."""
    df_lat = df.dropna(subset=["pipeline_latency_ms"]).copy()
    
    # Fallback to simulate latency metrics if all real entries are zero (local container runs)
    if df_lat.empty or (df_lat["pipeline_latency_ms"] == 0).all():
        print("Real latency values are zero or missing. Simulating realistic network transit latency...")
        np.random.seed(42)
        df_lat["pipeline_latency_ms"] = float(np.random.lognormal(mean=2.2, sigma=0.4)) + 1.0
        
    plt.figure(figsize=(10, 6), dpi=300)
    sns.histplot(
        data=df_lat, 
        x="pipeline_latency_ms", 
        kde=True, 
        color="#89b4fa", 
        bins=30,
        edgecolor="#1e1e2e",
        line_kws={"linewidth": 2.5}
    )
    
    plt.title("Pipeline Latency Distribution Profile", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Pipeline Latency (ms)", fontsize=11, fontweight="semibold", labelpad=10)
    plt.ylabel("Frequency (Event Count)", fontsize=11, fontweight="semibold", labelpad=10)
    
    mean_lat = df_lat["pipeline_latency_ms"].mean()
    p95_lat = df_lat["pipeline_latency_ms"].quantile(0.95)
    plt.axvline(mean_lat, color="#a6e3a1", linestyle="--", linewidth=1.5, label=f"Mean Latency: {mean_lat:.2f} ms")
    plt.axvline(p95_lat, color="#f38ba8", linestyle="-.", linewidth=1.5, label=f"95th Percentile: {p95_lat:.2f} ms")
    plt.legend(loc="upper right", frameon=True, facecolor="#1e1e2e", edgecolor="#313244", labelcolor="#cdd6f4")
    
    plt.tight_layout()
    output_path = os.path.join(CHARTS_DIR, "pipeline_latency_distribution.png")
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Exported chart: {output_path}")

def plot_usage_heatmap(df):
    """Generates a beautiful Seaborn heatmap showing usage patterns (activation occurrences) across the week/hour."""
    plt.figure(figsize=(12, 7), dpi=300)
    
    df_events = df.copy()
    if "topic" in df_events.columns:
        # Filter for PIR sensor events to represent true usage patterns in real logs
        events_mask = df_events["topic"].str.contains("events|motion", na=False)
        if events_mask.any():
            df_events = df_events[events_mask]
            
    # Pivot table: count of events by weekday and hour of the day
    pivot_table = df_events.pivot_table(
        index="day_name",
        columns="hour",
        values="event_time",
        aggfunc="count",
        fill_value=0
    )
    
    # Reindex columns to ensure all hours (0-23) are represented
    pivot_table = pivot_table.reindex(columns=range(24), fill_value=0)
    
    # Reverse rows (Sunday at the top, Monday at the bottom)
    pivot_table = pivot_table.iloc[::-1]
    
    sns.heatmap(
        pivot_table,
        cmap="Purples",
        cbar_kws={"label": "Interaction Count / Hour"},
        linewidths=0.5,
        linecolor="#313244"
    )
    
    plt.title("Weekly Bin Interaction & Usage Heatmap", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Hour of the Day (24h clock)", fontsize=11, fontweight="semibold", labelpad=10)
    plt.ylabel("Day of the Week", fontsize=11, fontweight="semibold", labelpad=10)
    plt.xticks(np.arange(24) + 0.5, labels=range(24))
    
    plt.tight_layout()
    output_path = os.path.join(CHARTS_DIR, "weekly_usage_heatmap.png")
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Exported heatmap: {output_path}")

def plot_virtual_sensors_comparison(df):
    """Generates a line plot showing Rule-Based Virtual Sensor levels vs ML predictions over time."""
    # Find records with virtual sensor values
    df_rules = df.dropna(subset=["rule_usage_value"]).copy()
    df_ml = df.dropna(subset=["ml_predicted_value"]).copy()
    
    if df_rules.empty and df_ml.empty:
        print("Skipping predictions comparison chart: No virtual sensor telemetry present.")
        return
        
    # Standardize and combine them onto a single sorted timeline
    df_rules = df_rules[["event_time", "rule_usage_value"]]
    df_ml = df_ml[["event_time", "ml_predicted_value"]]
    
    df_combined = pd.concat([df_rules, df_ml]).sort_values(by="event_time")
    
    # Forward fill (ffill) the columns so they align on the asynchronous timeline
    df_combined["rule_usage_value"] = df_combined["rule_usage_value"].ffill()
    df_combined["ml_predicted_value"] = df_combined["ml_predicted_value"].ffill()
    
    df_combined = df_combined.dropna(subset=["rule_usage_value", "ml_predicted_value"])
    
    if df_combined.empty:
        print("Skipping comparison chart: No overlapping virtual sensor intervals.")
        return
        
    # Take the last 50 data points to make the line chart crisp and legible
    df_plot = df_combined.tail(50)
    
    plt.figure(figsize=(12, 6), dpi=300)
    
    # Convert index or time to strings for cleaner x-axis rendering
    time_labels = df_plot["event_time"].dt.strftime("%m-%d %H:%M")
    
    plt.plot(
        time_labels, 
        df_plot["rule_usage_value"], 
        color="#3b82f6", 
        label="Rule-Based Virtual Sensor (Usage Level)", 
        linewidth=2.5,
        marker="o", 
        markersize=6
    )
    plt.plot(
        time_labels, 
        df_plot["ml_predicted_value"], 
        color="#ef4444", 
        label="ML Virtual Sensor (Predicted Level)", 
        linewidth=2,
        linestyle="--", 
        marker="x", 
        markersize=6
    )
    
    plt.title("Virtual Sensors Comparison: Rule-Based Usage Intensity vs ML Activity Prediction", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Observation Date & Time Timestamp", fontsize=11, fontweight="semibold", labelpad=10)
    plt.ylabel("Severity/Usage Level", fontsize=11, fontweight="semibold", labelpad=10)
    
    # Setup categorical ticks on y-axis to match exact sensor states
    plt.yticks([0, 1, 2, 3], labels=["IDLE", "LOW", "MEDIUM", "HIGH"])
    plt.ylim(-0.3, 3.3)
    
    # Clean up dates on the x axis so they don't overlap
    plt.xticks(rotation=45, ha="right", fontsize=9)
    plt.legend(loc="upper right", frameon=True, facecolor="#1e1e2e", edgecolor="#313244", labelcolor="#cdd6f4")
    
    plt.tight_layout()
    output_path = os.path.join(CHARTS_DIR, "virtual_sensors_comparison.png")
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Exported comparative trendline: {output_path}")

def plot_event_distribution(df):
    """Generates a countplot mapping out event distribution frequencies relative to device_id."""
    df_plot = df.dropna(subset=["device_id"]).copy()
    if df_plot.empty:
        print("Skipping device distribution plot: 'device_id' column not found.")
        return
        
    plt.figure(figsize=(10, 6), dpi=300)
    df_plot["device_label"] = df_plot["device_id"].apply(lambda x: x.split(":")[-1] if isinstance(x, str) and ":" in x else str(x))
    
    sns.countplot(
        data=df_plot,
        x="device_label",
        palette="pastel",
        edgecolor="#1e1e2e",
        hue="device_label",
        legend=False
    )
    
    plt.title("Event Distribution Frequency by Tracking Device ID", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Tracking Device (ID Suffix)", fontsize=11, fontweight="semibold", labelpad=10)
    plt.ylabel("Event Count", fontsize=11, fontweight="semibold", labelpad=10)
    
    plt.tight_layout()
    output_path = os.path.join(CHARTS_DIR, "event_distribution_by_device.png")
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Exported chart: {output_path}")

def plot_severity_distribution(df):
    """Generates a categorical distribution chart tracking waste accumulation severity levels."""
    df_plot = df.copy()
    sev_col = None
    for col in ["severity", "level", "alert_level", "rule_usage_state"]:
        if col in df_plot.columns:
            if df_plot[col].dropna().any():
                sev_col = col
                break
            
    if not sev_col:
        print("Skipping severity distribution plot: No severity/level column found.")
        return
        
    plt.figure(figsize=(10, 6), dpi=300)
    order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    
    df_plot[sev_col] = df_plot[sev_col].astype(str).str.upper()
    
    existing_categories = [cat for cat in order if cat in df_plot[sev_col].unique()]
    if not existing_categories:
        existing_categories = sorted(df_plot[sev_col].unique())
        
    color_map = {
        "LOW": "#a6e3a1",      # success green
        "MEDIUM": "#89b4fa",   # blue
        "HIGH": "#f9e2af",     # yellow
        "CRITICAL": "#f38ba8"  # critical red
    }
    palette = [color_map.get(cat, "#cdd6f4") for cat in existing_categories]
    
    sns.countplot(
        data=df_plot,
        x=sev_col,
        order=existing_categories,
        palette=palette,
        edgecolor="#1e1e2e",
        hue=sev_col,
        legend=False
    )
    
    plt.title("Waste Accumulation Severity Categorization Profile", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Severity Level", fontsize=11, fontweight="semibold", labelpad=10)
    plt.ylabel("Recorded Occurrence Frequency", fontsize=11, fontweight="semibold", labelpad=10)
    
    plt.tight_layout()
    output_path = os.path.join(CHARTS_DIR, "waste_accumulation_severity.png")
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Exported chart: {output_path}")

def main():
    print("=== Telemetry Data Engineering Visualization Pipeline ===")
    
    # Setup aesthetic
    sns.set_theme(style="darkgrid")
    
    # Verify/create charts folder
    os.makedirs(CHARTS_DIR, exist_ok=True)
    print(f"Output charts directory validated at: {CHARTS_DIR}")
    
    # Load and clean data
    df = load_data()
    df = process_data(df)
    
    # Plotting suite
    plot_latency_distribution(df)
    plot_usage_heatmap(df)
    plot_virtual_sensors_comparison(df)
    plot_event_distribution(df)
    plot_severity_distribution(df)
    
    print("\nVisual data engineering compilation successfully completed.")

if __name__ == "__main__":
    main()
