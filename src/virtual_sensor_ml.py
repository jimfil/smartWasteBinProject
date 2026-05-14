import paho.mqtt.client as mqtt
import json
import time
import click
import joblib
import numpy as np
import pandas as pd
from datetime import datetime

def load_model(path):
    return joblib.load(path)

def predict_next_hour(model):
    now = datetime.now()
    next_hour = (now.hour + 1) % 24

    dayOfWeek = now.weekday()

    if dayOfWeek == 5 or dayOfWeek == 6: # saturday or sunday 
        isWeekend = 1
    else:
        isWeekend = 0

    features = pd.DataFrame([[dayOfWeek, next_hour, isWeekend]], 
                            columns=["day_of_week", "hour", "is_weekend"])

    prediction = model.predict(features)
    probabilities = model.predict_proba(features)
    confidence = np.max(probabilities[0])
    return prediction.tolist(), confidence.item(), next_hour, [next_hour, dayOfWeek, isWeekend]


def publish_discovery(client, publish_topic, bin_id):
    print(f"[Virtual Sensor ML] Publishing HA discovery for bin {bin_id}...")
    
    # Prediction Sensor
    prediction_config = {
        "name": f"Wastebin {bin_id} Activity Prediction",
        "state_topic": publish_topic,
        "value_template": "{{ value_json.prediction[0] }}",
        "unique_id": f"{bin_id}_usage_prediction",
        "device": {
            "identifiers": [bin_id],
            "name": f"Smart Wastebin {bin_id}",
            "model": "ML-based Virtual Sensor",
            "manufacturer": "IoT Lab"
        },
        "icon": "mdi:crystal-ball"
    }
    client.publish(f"homeassistant/sensor/{bin_id}_prediction/config", json.dumps(prediction_config), retain=True)

    # Confidence Sensor
    confidence_config = {
        "name": f"Wastebin {bin_id} Prediction Confidence",
        "state_topic": publish_topic,
        "value_template": "{{ (value_json.confidence * 100) | round(1) }}",
        "unique_id": f"{bin_id}_prediction_confidence",
        "device": {
            "identifiers": [bin_id],
            "name": f"Smart Wastebin {bin_id}"
        },
        "unit_of_measurement": "%",
        "icon": "mdi:shield-check"
    }
    client.publish(f"homeassistant/sensor/{bin_id}_confidence/config", json.dumps(confidence_config), retain=True)


@click.command()
@click.option("--model-path", default="models/busy_predictor.joblib", help="Path to the trained ML model")
@click.option("--broker", default="localhost", help="MQTT Broker address")
@click.option("--port", type=int, default=1883, help="MQTT Broker port")
@click.option("--publish-topic", default="smartbin/bin-01/usage_prediction", help="MQTT topic to publish to")
@click.option("--interval", type=int, default=30, help="Time between predictions in seconds")
@click.option("--bin-id", default="bin-01", help="Identifier for the smart bin")
def main(model_path, broker, port, publish_topic, interval, bin_id):
    model = load_model(model_path)
    client = mqtt.Client()
    client.connect(broker, port)
    client.loop_start()
    
    publish_discovery(client, publish_topic, bin_id)
    
    print(f"[Virtual Sensor ML] Monitoring {publish_topic} for usage prediction")
    try:
        while True:
            prediction, confidence, next_hour, features = predict_next_hour(model)
            timestamp = time.time()
            
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            dayName = day_names[features[1]]
            
            confidence_value = round(float(confidence), 3)
            is_weekend = features[2]
            payload = {
                "prediction": prediction,
                "confidence": confidence_value,
                "predicted_hour": next_hour,
                "utc_prediction_timestamp": timestamp,
                "model_name": "busy_predictor.joblib",
                "features_used": {
                    "day_of_week": dayName,
                    "hour": next_hour,
                    "is_weekend": is_weekend
                }
            }
            client.publish(publish_topic, json.dumps(payload), qos=1, retain=True)
            print(f"[Virtual Sensor ML] Predicted hour: {next_hour} Prediction: {prediction} Confidence Percentage: {confidence}")
            time.sleep(interval)
    except KeyboardInterrupt:
        client.disconnect()
        print("[Virtual Sensor ML] Disconnected from broker.")

if __name__ == "__main__":
    main()