from flask import Flask, request
from flask_restx import Api, Resource, fields, reqparse
from apiFunc import load_events, EVENTS_FILE, find_sensor, get_sensor_for_bin, find_bin, load_bins, load_sensors, get_sensors_for_bin
import json
import paho.mqtt.client as mqtt
import threading
from datetime import datetime, timezone
import os

try:
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="wastebin-api", clean_session=False)
except AttributeError:
    mqtt_client = mqtt.Client(client_id="wastebin-api", clean_session=False)

topic_store = {}
topic_lock = threading.Lock()

def on_message(client, userdata, msg):
    with topic_lock:
        print("1")
        topic_store[msg.topic] = {
            "topic": msg.topic,
            "payload": msg.payload.decode("utf-8", errors="replace"),
            "qos": msg.qos,
            "retain": msg.retain,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

def on_connect(client, userdata, flags, rc, *args):
    if rc == 0:
        print("Successfully connected to MQTT broker!")
        client.subscribe("smartbin/#", qos=1)
        print("Subscribed to smartbin/#")
    else:
        print(f"Failed to connect, return code {rc}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

broker_host = os.environ.get("BROKER_HOST", "localhost")
broker_port = int(os.environ.get("BROKER_PORT", 1883))

try:
    mqtt_client.connect_async(broker_host, broker_port, keepalive=60)
except Exception as e:
    print(f"Warning: MQTT connection failed: {e}")

mqtt_client.loop_start()

app = Flask(__name__)
api = Api(
    app,
    version="1.0",
    title="Smart Wastebin API",
    description="REST API for querying Smart Wastebin sensor data and bin status",
)

ns_bins = api.namespace("bins", description="Wastebin operations")
ns_sensors = api.namespace("sensors", description="Sensor operations")
ns_mqtt = api.namespace("mqtt", description="MQTT broker interaction")
ns_events = api.namespace("events", description="Motion events from pipeline")

bin_model = api.model("Bin", {
    "id": fields.String(required=True, description="Bin unique identifier"),
    "name": fields.String(description="Human-readable name"),
    "location": fields.String(description="Deployment location"),
    "status": fields.String(description="Current status"),
})

allbins_model = api.model("bins", {
    "bins": fields.List(fields.Nested(bin_model))
})

event_model = api.model("Event", {
    "resultTime": fields.String(description="ISO timestamp of the event"),
    "madeBySensor": fields.String(description="Sensor ID that produced this event"),
    "hasSimpleResult": fields.String(description="Motion state (detected/clear)"),
    "pipeline_latency_ms": fields.Float(description="Pipeline latency in ms"),
})

emptied_model = api.model("EmptiedRecord", {
    "bin_id": fields.String(description="Bin identifier"),
    "emptied_at": fields.String(description="ISO timestamp of when the bin was emptied"),
    "emptied_by": fields.String(description="Who emptied the bin"),
})

mqtt_message_model = api.model("MqttMessage", {
    "topic": fields.String(required=True, description="MQTT topic to publish to"),
    "message": fields.String(required=True, description="Message payload"),
})

sensor_model = api.model("Sensor", {
    "id": fields.String(required=True, description="Sensor unique identifier (URN)"),
    "type": fields.String(description="Sensor type (e.g. PIR)"),
    "model": fields.String(description="Hardware model"),
    "mounted_on": fields.String(description="ID of the bin this sensor is mounted on"),
    "status": fields.String(description="Current status"),
})

bin_sensors_response = api.model("BinSensorsResponse", {
    "bin_id": fields.String(description="Bin identifier"),
    "sensors": fields.List(fields.Nested(sensor_model))
})

publish_model = api.model("MQTTPublish", {
    "topic": fields.String(required=True, description="MQTT topic to publish to"),
    "payload": fields.String(required=True, description="Message payload"),
    "qos": fields.Integer(description="Quality of Service (0, 1, or 2)", default=1),
    "retain": fields.Boolean(description="Retain this message on the broker", default=False),
})

usage_intensity_model = api.model("UsageIntensity", {
    "state": fields.String(description="Usage state (e.g., low, medium, high)"),
    "count": fields.Integer(description="Number of events in the window"),
    "window_minutes": fields.Integer(description="Evaluation window size in minutes"),
    "timestamp": fields.Float(description="Unix timestamp of the evaluation"),
})

usage_prediction_model = api.model("UsagePrediction", {
    "prediction": fields.List(fields.String, description="Predicted usage state"),
    "confidence": fields.Float(description="Confidence of the prediction"),
    "predicted_hour": fields.Integer(description="The hour being predicted"),
    "utc_prediction_timestamp": fields.Float(description="Unix timestamp when prediction was made"),
    "model_name": fields.String(description="Name of the model used"),
    "features_used": fields.Raw(description="Features used for the prediction")
})

events_parser = reqparse.RequestParser()
events_parser.add_argument("limit", type=int, default=50, help="Max events to return")
events_parser.add_argument("start", type=str, help="Start datetime (ISO format)")
events_parser.add_argument("end", type=str, help="End datetime (ISO format)")

bin_parser = reqparse.RequestParser()
bin_parser.add_argument("bin_id", type=str, required=True, help="Bin unique identifier")

allbins_parser = reqparse.RequestParser()
allbins_parser.add_argument("limit", type=int, default=50, help="Max bins to return")
allbins_parser.add_argument("offset", type=int, default=0, help="Offset")

mqtt_parser = reqparse.RequestParser()
mqtt_parser.add_argument("topic", type=str, required=True, help="MQTT topic to publish to")
mqtt_parser.add_argument("message", type=str, required=True, help="Message payload")


@ns_bins.route("/")
@ns_bins.expect(allbins_parser)
class BinList(Resource):
    @ns_bins.marshal_with(allbins_model)
    def get(self):
        """List all bins"""
        args = allbins_parser.parse_args()
        limit=args.get("limit")
        offset=args.get("offset")
        bin_list = load_bins()
        if offset != None:
            bin_list = bin_list[offset:offset+limit]
        else:
            bin_list = bin_list[:limit]
        return {"bins": bin_list}, 200


@ns_bins.route("/<string:bin_id>")
@ns_bins.expect(bin_parser)
class BinItem(Resource):
    @ns_bins.marshal_with(bin_model)
    def get(self, bin_id):
        """Get details for a specific bin"""
        bin_data = find_bin(bin_id)
        if not bin_data:
            ns_bins.abort(404, f"Bin {bin_id} not found")
        return bin_data


@ns_bins.route("/<string:bin_id>/sensors")
@ns_bins.param("bin_id", "The bin identifier")
class BinSensors(Resource):
    @ns_bins.marshal_with(bin_sensors_response)
    def get(self, bin_id):
        """List sensors on a specific bin"""
        sensors = get_sensors_for_bin(bin_id)
        return {"bin_id": bin_id, "sensors": sensors}, 200


@ns_bins.route("/<string:bin_id>/events")
@ns_bins.expect(events_parser)
class BinEvents(Resource):
    @ns_bins.marshal_list_with(event_model)
    def get(self, bin_id):
        """Get motion events for a specific bin"""
        args = events_parser.parse_args()
        events = load_events(
            EVENTS_FILE,
            limit=args.get("limit"),
            sensor_id=get_sensor_for_bin(bin_id),
            start_time=args.get("start"),
            end_time=args.get("end")
        )
        return events


@ns_bins.route("/<string:bin_id>/emptied")
@ns_bins.param("bin_id", "The bin identifier")
class BinEmptied(Resource):
    @ns_bins.expect(emptied_model)
    @ns_bins.response(201, "Bin marked as emptied")
    @ns_bins.response(404, "Bin not found")
    @ns_bins.marshal_with(emptied_model, code=201)
    def post(self, bin_id):
        """Record that a bin was emptied"""
        bin_data = find_bin(bin_id)
        if not bin_data:
            ns_bins.abort(404, f"Bin {bin_id} not found")
            
        data = request.get_json(silent=True) or {}
        
        record = {
            "bin_id": bin_id,
            "emptied_at": data.get("emptied_at") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "emptied_by": data.get("emptied_by", "unknown")
        }
        
        # Save record to file
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, "emptied.log"), "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        # Publish an MQTT message
        mqtt_payload = {
            "state": "emptied",
            "emptied_at": record["emptied_at"]
        }
        mqtt_client.publish(
            topic=f"smartbin/{bin_id}/status",
            payload=json.dumps(mqtt_payload),
            qos=1,
            retain=True
        )
        
        return record, 201


@ns_bins.route("/<string:bin_id>/usage_intensity")
@ns_bins.param("bin_id", "The bin identifier")
class BinUsageIntensity(Resource):
    @ns_bins.response(404, "No usage intensity data found")
    @ns_bins.marshal_with(usage_intensity_model)
    def get(self, bin_id):
        """Get the latest rule-based usage intensity evaluation for a bin"""
        topic = f"smartbin/{bin_id}/usage_intensity"
        with topic_lock:
            if topic not in topic_store:
                ns_bins.abort(404, f"No usage intensity data available for bin {bin_id}")
            
            try:
                payload = json.loads(topic_store[topic]["payload"])
                return payload
            except json.JSONDecodeError:
                ns_bins.abort(500, "Failed to parse usage intensity data")


@ns_bins.route("/<string:bin_id>/usage_prediction")
@ns_bins.param("bin_id", "The bin identifier")
class BinUsagePrediction(Resource):
    @ns_bins.response(404, "No usage prediction data found")
    @ns_bins.marshal_with(usage_prediction_model)
    def get(self, bin_id):
        """Get the latest ML-based usage prediction for a bin"""
        topic = f"smartbin/{bin_id}/usage_prediction"
        with topic_lock:
            if topic not in topic_store:
                ns_bins.abort(404, f"No usage prediction data available for bin {bin_id}")
            
            try:
                payload = json.loads(topic_store[topic]["payload"])
                return payload
            except json.JSONDecodeError:
                ns_bins.abort(500, "Failed to parse usage prediction data")


@ns_sensors.route("/")
class SensorList(Resource):
    @ns_sensors.marshal_list_with(sensor_model)
    def get(self):
        """List all sensors"""
        return load_sensors()


@ns_sensors.route("/<string:sensor_id>")
@ns_sensors.param("sensor_id", "The sensor identifier")
@ns_sensors.response(404, "Sensor not found")
class Sensor(Resource):
    @ns_sensors.marshal_with(sensor_model)
    def get(self, sensor_id):
        """Get details for a specific sensor"""
        sensor = find_sensor(sensor_id)
        if not sensor:
            api.abort(404, f"Sensor {sensor_id} not found")
        return sensor


@ns_mqtt.route("/topics")
class MQTTTopics(Resource):
    def get(self):
        """List all known MQTT topics and their last received message"""
        with topic_lock:
            return {
                "topic_count": len(topic_store),
                "topics": list(topic_store.values())
            }, 200


@ns_mqtt.route("/topics/<path:topic>")
@ns_mqtt.param("topic", "MQTT topic path, for example smartbin/bin-01/pir-01/motion")
class MQTTTopicDetail(Resource):
    @ns_mqtt.response(404, "Topic not found or no message received yet")
    def get(self, topic):
        """GET the last received message for a specific MQTT topic"""
        with topic_lock:
            if topic not in topic_store:
                ns_mqtt.abort(404, f"No message received on topic '{topic}'")
            return topic_store[topic], 200


@ns_mqtt.route("/publish")
class MqttPublish(Resource):
    @ns_mqtt.expect(publish_model)
    @ns_mqtt.response(200, "Message published")
    @ns_mqtt.response(400, "Invalid request")
    def post(self):
        """Publish a message to an MQTT topic"""
        try:
            data = request.get_json() or {}
            
            topic = data.get("topic")
            payload = data.get("payload")
            qos = data.get("qos", 1)
            retain = data.get("retain", False)

            if not topic or payload is None:
                return {"message": "Both 'topic' and 'payload' are required"}, 400

            if qos not in (0, 1, 2):
                return {"message": "QoS must be 0, 1, or 2"}, 400

            result = mqtt_client.publish(topic, payload, qos=qos, retain=retain)
            
            return {
                "status": "published",
                "topic": topic,
                "payload": payload,
                "qos": qos,
                "retain": retain,
                "mqtt_rc": result.rc
            }, 200
        except Exception as e:
            return {"message": str(e)}, 500
        

@ns_events.route("/")
class EventList(Resource):
    @ns_events.expect(events_parser)
    @ns_events.marshal_list_with(event_model)
    def get(self):
        """List all motion events produced by the pipeline"""
        args = events_parser.parse_args()
        events = load_events(
            EVENTS_FILE,
            limit=args.get("limit"),
            start_time=args.get("start"),
            end_time=args.get("end")
        )
        return events


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)
