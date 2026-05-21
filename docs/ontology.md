# Smart Wastebin — Custom Ontology Terms

Base namespace: `https://github.com/jimfil/smartWasteBinProject/blob/main/docs/ontology.md#`
Prefix used in JSON-LD: `pipeline`

## Entity Types

The JSON-LD model files (`sensor.jsonld`, `wastebin.jsonld`, `environment.jsonld`) describe the physical entities in the system. The RDF types for each entity are defined here.

### urn:dev:team05:pir-01
- **Model File:** `sensor.jsonld`
- **RDF Type:** `sosa:Sensor`
- **Description:** HC-SR501 PIR motion sensor

### urn:wastebin:bin-01
- **Model File:** `wastebin.jsonld`
- **RDF Type:** `saref:Appliance`
- **Description:** Smart wastebin unit

### urn:env:kypes-02
- **Model File:** `environment.jsonld`
- **RDF Type:** `bot:Space`
- **Description:** Deployment environment (room/space)

### Detection stimulus (nested in sensor)
- **RDF Type:** `ssn:Stimulus`
- **Description:** Changes in infrared radiation from warm bodies detected by the PIR sensor

### University (nested in environment)
- **RDF Type:** `schema:Organization`
- **Description:** The university where the system is deployed

### Department (nested in environment)
- **RDF Type:** `schema:Organization`
- **Description:** The department within the university

### Address (nested in environment)
- **RDF Type:** `schema:PostalAddress`
- **Description:** Postal address of the university

---

## Event / Observation Context Terms

The following terms are aliased in `context.jsonld` for pipeline observation events. Their expected datatypes are defined here.

### event_time
- **Type:** `xsd:dateTime`
- **Mapped to:** `sosa:resultTime`
- **Description:** The UTC timestamp at which the sensor observation was produced by the pipeline producer. Represents the instant the sensor reading was taken, **not** when it was ingested or processed.

### device_id
- **Type:** `@id` (IRI reference)
- **Mapped to:** `sosa:madeBySensor`
- **Description:** The IRI of the sensor entity that generated the observation. Resolves to the full sensor description in `sensor.jsonld`.

### event_type
- **Mapped to:** `@type`
- **Description:** The RDF type of the observation record (e.g. `sosa:Observation`). Also used as a human-readable short label such as `"motion"`.

### motionState
- **Type:** `xsd:string`
- **Description:** Describes whether motion was detected or cleared. Values: `"detected"` (movement sensed), `"cleared"` (sensor returned to idle).

### sequenceNumber
- **Type:** `xsd:integer`
- **Description:** A monotonically increasing counter for events within a single pipeline run. Resets to 0 when the pipeline restarts.

### runId
- **Type:** `xsd:string`
- **Description:** A UUID v4 identifier that uniquely identifies a single execution (run) of the pipeline. All events in the same run share this value.

### ingestTime
- **Type:** `xsd:dateTime`
- **Description:** The UTC timestamp at which the consumer thread received and processed the event from the queue.

### pipelineLatencyMs
- **Type:** `xsd:float`
- **Description:** Time in milliseconds between `event_time` (producer creation) and `ingest_time` (consumer ingestion). Measures how long a record spent in the queue.

### sensorRef
- **Type:** `@id` (IRI reference)
- **Description:** The IRI of the sensor entity associated with the observation. Resolves to `sensor.jsonld`.

### wastebinRef
- **Type:** `@id` (IRI reference)
- **Description:** The IRI of the wastebin entity associated with the observation. Resolves to `wastebin.jsonld`.

### environmentRef
- **Type:** `@id` (IRI reference)
- **Description:** The IRI of the environment entity associated with the observation. Resolves to `environment.jsonld`.

---

## Sensor Terms

### gpioPin
- **Type:** `xsd:integer`
- **Description:** The GPIO pin number on the Raspberry Pi that the sensor is connected to.

### operatingVoltage
- **Type:** `xsd:string`
- **Description:** The required voltage for the sensor to operate (e.g. `"5V DC"`).

### detectionRange
- **Type:** `xsd:string`
- **Description:** The physical range within which the sensor can successfully trigger (e.g. `"up to 7 metres"`).

### cooldownSeconds
- **Type:** `xsd:float`
- **Description:** The hardware cooldown period (in seconds) before the sensor can detect another event.

### detectionAngle
- **Type:** `xsd:string`
- **Description:** The angle of the cone of detection for the sensor (e.g. `"less than 120 degrees cone"`).

### minHighSeconds
- **Type:** `xsd:float`
- **Description:** The minimum number of seconds the signal must stay HIGH before the pipeline emits an event.

### operatingTemperature
- **Type:** `xsd:string`
- **Description:** The safe temperature range for sensor operation (e.g. `"-15°C to +70°C"`).

### indoorOutdoor
- **Type:** `xsd:string`
- **Description:** Indicates whether the deployment is suited for `"indoor"`, `"outdoor"`, or `"both"`.

### statusSensor
- **Type:** `xsd:string`
- **Description:** Administrative tracking of the sensor status. Values: `"active"`, `"inactive"`, `"maintenance"`.

---

## Relationship Terms

### mountedOn
- **Type:** `owl:ObjectProperty`
- **Domain:** Sensor → Physical object
- **Description:** A relationship indicating what physical object (e.g. a wastebin) a sensor is attached to.

### deployedIn
- **Type:** `owl:ObjectProperty`
- **Domain:** Sensor → Environment
- **Description:** A relationship indicating the environment in which the sensor is deployed.

### locatedIn
- **Type:** `owl:ObjectProperty`
- **Domain:** Wastebin → Environment
- **Description:** A relationship indicating that a physical object is located in a certain environment/space.

### contains
- **Type:** `owl:ObjectProperty`
- **Domain:** Environment → Wastebin / Sensor
- **Description:** A relationship indicating that an environment contains a device or physical object.

---

## Wastebin Terms

### capacityLt
- **Type:** `xsd:float`
- **Description:** The capacity of the wastebin in liters.

### material
- **Type:** `xsd:string`
- **Description:** The material of the wastebin (e.g. `"HDPE plastic"`).

### color
- **Type:** `xsd:string`
- **Description:** The color(s) of the wastebin (e.g. `"grey,blue"`).

### lengthCm
- **Type:** `xsd:float`
- **Description:** The length of the wastebin in centimeters.

### widthCm
- **Type:** `xsd:float`
- **Description:** The width of the wastebin in centimeters.

### heightCm
- **Type:** `xsd:float`
- **Description:** The height of the wastebin in centimeters.

### wasteType
- **Type:** `xsd:string`
- **Description:** The type of waste the wastebin is designed to collect (e.g. `"general"`, `"recyclable"`, `"organic"`).

### collectionZone
- **Type:** `xsd:string`
- **Description:** The geographic or organizational zone the wastebin belongs to for collection logistics.

### collectionRoute
- **Type:** `xsd:string`
- **Description:** The route designation for waste collection that covers this bin.

### statusBin
- **Type:** `xsd:string`
- **Description:** Administrative tracking of the wastebin status. Values: `"active"`, `"full"`, `"maintenance"`.

---

## Environment / Location Terms

### university
- **Type:** `xsd:string`
- **Description:** The name of the university where the system is deployed.

### department
- **Type:** `xsd:string`
- **Description:** The department within the university.

### roomName
- **Type:** `xsd:string`
- **Description:** The human-readable name of the room.

### roomNumber
- **Type:** `xsd:integer`
- **Description:** The numeric identifier for the room.

### buildingName
- **Type:** `xsd:string`
- **Description:** The name of the building where the deployment exists.

### floorNumber
- **Type:** `xsd:integer`
- **Description:** The floor number within the building (ground = 0).

### trafficLevel
- **Type:** `xsd:string`
- **Description:** Qualitative indicator of foot traffic in the environment. Values: `"low"`, `"medium"`, `"high"`.

---

## Virtual Telemetry & Virtual Sensor Terms

### fill_pct (or fill_level)
- **Type:** `xsd:integer`
- **Description:** The current fill level percentage of the wastebin, ranging from `0` (completely empty) to `100` (completely full). Used by Flow A, Flow B, and the Node-RED dashboard gauges.

### weight_g
- **Type:** `xsd:float`
- **Description:** The current weight of the wastebin in grams. Used by Flow A, Flow B, and dashboard indicators to monitor load.

### motion_state (or motionState)
- **Type:** `xsd:string`
- **Description:** Simple state representation of PIR motion telemetry. Values: `"detected"` (sensed movement), `"clear"` (no movement).

---

## Machine Learning & Prediction Terms

### prediction
- **Type:** `xsd:string` (or array of `xsd:string`)
- **Description:** The predicted usage state of the wastebin for a future time window (e.g., `"busy"`, `"quiet"`).

### confidence
- **Type:** `xsd:float`
- **Description:** A value between `0.0` and `1.0` representing the confidence or probability score of the ML prediction.

### predicted_hour
- **Type:** `xsd:integer`
- **Description:** The hour of the day (in 24-hour format, `0` to `23`) for which the usage prediction is applicable.

### model_name
- **Type:** `xsd:string`
- **Description:** The name or identifier of the machine learning model used to generate the prediction (e.g., `"random_forest_v1"`).

---

## Alerting & Orchestration Terms

### level
- **Type:** `xsd:string`
- **Description:** The severity level of a rule-based or virtual sensor alert. Values: `"LOW"`, `"MEDIUM"`, `"HIGH"`, `"CRITICAL"`.

### acknowledged
- **Type:** `xsd:boolean`
- **Description:** Indicates whether a generated alert has been reviewed and acknowledged by an operator.

### ack_timestamp
- **Type:** `xsd:dateTime`
- **Description:** The UTC timestamp recording when an alert was acknowledged by an operator.

### ack_by (or operator)
- **Type:** `xsd:string`
- **Description:** The name or role of the operator or dashboard client instance that acknowledged the alert.
