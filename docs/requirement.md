# AeroGuard — Requirements Specification

| | |
| --- | --- |
| Project | AeroGuard: An Explainable Multi-Sensor System for Gas and Smoke Event Screening |
| Course | SCSE3103 Cognitive Computing, Semester I 2026/2027 |
| Group | DNF — Gan Rui En, Lee Ming Da, Tan Choon Da |
| Version | 0.1 (draft for Phase 2 design) |
| Date | 16 November 2026 |
| Source documents | Project Proposal (Phase 1); SCSE3103 Project Instruction ver 1.0 |

**How to read this document.** Each requirement has an ID, a priority and a verification method. Priority uses **M** (must have: needed to meet the course minimum or a proposal commitment), **S** (should have) and **C** (could have, only if time allows). Verification uses **T** (automated test), **D** (demonstration), **I** (inspection of code, logs or documents) and **A** (analysis of evaluation results).

Values marked *(provisional)* are starting defaults taken from the proposal or chosen for this draft. They must be configurable and will be confirmed after the hardware pilot on 23 November 2026. Section 12 lists every open decision.

---

## 1. Purpose and scope

### 1.1 Purpose

AeroGuard is a supplementary screening prototype. It reads a low-cost gas sensor together with temperature and humidity, classifies what is happening, assigns an alert priority, and tells the user why. Its purpose is to test whether combining machine learning, fuzzy inference and explicit rules reduces nuisance alerts compared with a fixed threshold, without losing sensitivity to gas and smoke events.

### 1.2 In scope

- A stationary, USB-powered ESP32 sensor node with MQ-2 and DHT22 sensors, an LED indicator and a buzzer.
- A Python backend that ingests, validates, stores and processes sensor data.
- Temporal feature extraction, an ML classifier, a Mamdani fuzzy inference system and a rule-based decision layer.
- A dashboard for live status, trends, explanations, muting and event review.
- A replay mode that feeds recorded sensor data through the same pipeline.
- Data collection, labelling and evaluation tooling for comparing three configurations.

### 1.3 Out of scope

- Replacing or certifying against any gas or smoke alarm standard.
- Autonomous emergency actions such as closing gas valves or calling emergency services.
- Calibrated gas-concentration measurement (ppm).
- Mobile robotics, battery operation, multi-node networks and industrial deployment.
- Automatic retraining from user feedback.
- Cloud hosting or any paid external service.

### 1.4 Intended and excluded use

The system is for controlled bench experiments and classroom demonstration. It must never be presented, installed or relied on as a life-safety device. Every user-facing surface that shows a status must also make this limitation visible (see RAI-01).

---

## 2. Stakeholders and user roles

| Role | Description | Main needs |
| --- | --- | --- |
| Operator | Household occupant or laboratory user who sees alerts and responds | Clear status, an understandable reason, the ability to mute and to mark false alarms |
| Supervisor | Facility or laboratory supervisor who reviews events afterwards | Event history, audit trail of actions, device health |
| Maintainer | Team member who runs, configures and debugs the system | Logs, configuration, fault states, reproducible setup |
| Experimenter | Team member who collects and labels data and runs evaluation | Recording controls, labelling, replay, evaluation reports |
| Assessor | Course lecturer | Evidence that minimum prototype requirements are met |

For the prototype, Operator and Supervisor share one dashboard login. Experimenter and Maintainer functions are command-line tools or a separate dashboard page.

---

## 3. System overview

### 3.1 Pipeline

```
Sensor node (perception)
   │  telemetry messages
   ▼
Ingestion and validation ──► raw data store
   │
   ▼
Device-health monitor
   │
   ▼
Feature extraction (sliding window)
   │
   ├──► ML classifier ───────┐
   │                         ▼
   └──► Fuzzy inference ──► Decision rules ──► Explanation generator
                                 │
                 ┌───────────────┼────────────────┐
                 ▼               ▼                ▼
            Dashboard      LED and buzzer     Event and audit log
                 │
                 ▼
            Human review (confirm, mute, mark false alarm)
```

### 3.2 Components

| ID | Component | Technology | Responsibility |
| --- | --- | --- | --- |
| CMP-1 | Sensor node firmware | Arduino C++ on ESP32 | Sample sensors, send telemetry, drive LED and buzzer |
| CMP-2 | Backend service | Python, FastAPI, Pydantic | Ingest, validate, store, run the reasoning pipeline, expose an API |
| CMP-3 | Reasoning pipeline | scikit-learn, scikit-fuzzy | Features, classifier, fuzzy inference, decision rules, explanations |
| CMP-4 | Dashboard | Streamlit | Status, trends, explanations, review actions, event history |
| CMP-5 | Data and evaluation tools | Python CLI, pytest | Recording, labelling, replay, training, evaluation, fault tests |

### 3.3 Definitions

| Term | Meaning |
| --- | --- |
| G | MQ-2 sensor response as a raw ADC value. Not a gas concentration. |
| T, H | Temperature (°C) and relative humidity (%RH) from the DHT22. |
| Clean-air reference | A slowly updated estimate of G in normal conditions, used to compute deviation. |
| Window | A fixed-length slice of recent samples over which features are computed. |
| Event class | One of `normal`, `interference`, `gas`, `smoke`. Interference has sub-labels `steam` and `ethanol`. |
| Hazard | The `gas` and `smoke` classes together. |
| APS | Alert Priority Score, 0–100, from fuzzy inference. A relative decision priority, not a measured severity. |
| System status | One of the seven values in Section 4.7. |
| Alert episode | A continuous run of `ALERT` windows counted as one event (FR-DR-08). |
| Session | One continuous data-collection sitting with its own setup; the unit used for grouped validation. |
| Configuration | One of the three compared systems: fixed threshold, ML-only, hybrid. |

---

## 4. Functional requirements

### 4.1 Sensor node (CMP-1)

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| FR-SN-01 | The node shall read the MQ-2 analogue output through a voltage divider that keeps the ADC input at or below 3.3 V. The divider (10 kΩ series, 15 kΩ to ground *(provisional)*) shall be verified by measurement before first connection. | M | I |
| FR-SN-02 | The node shall sample G at 1 Hz *(provisional)*. | M | T |
| FR-SN-03 | The node shall sample T and H at 0.5 Hz, the DHT22 limit. | M | T |
| FR-SN-04 | The node shall send one telemetry message per G sample using the schema in Section 5.1. | M | T |
| FR-SN-05 | Each message shall carry a monotonically increasing sequence number and the device uptime in milliseconds. | M | T |
| FR-SN-06 | When a DHT22 read fails, the node shall still send the message with T and H set to null and `dht_ok` set to false. It shall not resend old values as if they were new. | M | T |
| FR-SN-07 | The node shall drive the LED and buzzer according to the status last received from the backend (Section 4.9). | M | D |
| FR-SN-08 | If the node receives no status from the backend for 10 s *(provisional)*, it shall show the "connection lost" indication and shall not show "normal". | M | D |
| FR-SN-09 | On power-up the node shall report `uptime_ms` from zero so that the backend can enforce the warm-up period. | M | T |
| FR-SN-10 | The node shall reconnect automatically after a transport failure, without a manual reset. | S | D |
| FR-SN-11 | Firmware shall include a version string that is sent in every message. | S | I |

### 4.2 Ingestion, validation and storage (CMP-2)

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| FR-BE-01 | The backend shall accept telemetry through a documented interface and validate every message against the schema with Pydantic. | M | T |
| FR-BE-02 | A message shall be rejected, logged and counted when it fails validation: missing fields, wrong types, G outside 0–4095, T outside −40 to 80 °C, or H outside 0–100 %RH. A rejected message shall never reach the reasoning pipeline. | M | T |
| FR-BE-03 | The backend shall timestamp each accepted message on receipt in UTC. | M | T |
| FR-BE-04 | Duplicate sequence numbers shall be discarded. Out-of-order messages shall be discarded and counted. | M | T |
| FR-BE-05 | The backend shall detect a node restart from a drop in `uptime_ms` or sequence number and shall re-enter warm-up. | M | T |
| FR-BE-06 | All accepted telemetry shall be stored with its receipt timestamp, device ID and session ID where one is active. | M | I |
| FR-BE-07 | The backend shall require a shared device key on the telemetry interface and reject messages without it. | M | T |
| FR-BE-08 | The backend shall expose the current status, latest readings, APS, predicted class and explanation through an API used by the dashboard and the node. | M | T |
| FR-BE-09 | The backend shall expose a health endpoint reporting uptime, last message time, and counts of rejected messages. | S | T |
| FR-BE-10 | The backend shall start in a safe state: status `UNAVAILABLE` until valid telemetry arrives. | M | T |

### 4.3 Device health

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| FR-DH-01 | The system shall hold status `WARMING_UP` for a configurable period after node power-up. The default shall be set from the MQ-2 manual and pilot measurements. | M | T |
| FR-DH-02 | The system shall set status `UNAVAILABLE` when no valid telemetry has arrived for 5 s *(provisional)*. | M | T |
| FR-DH-03 | The system shall set status `FAULT` when G is pinned at 0 or 4095 for 5 consecutive samples *(provisional)*, or when T/H have been null for 10 s *(provisional)*. | M | T |
| FR-DH-04 | T and H values shall be reused for at most 10 s *(provisional)* after the last valid read. After that they are stale and FR-DH-03 applies. | M | T |
| FR-DH-05 | Device-health status shall take precedence over every reasoning output. A window that contains invalid or stale data shall never produce `NORMAL`. | M | T |
| FR-DH-06 | When a health condition clears, the system shall return to normal operation without a restart, and shall log the fault start, end and cause. | M | T |

### 4.4 Feature extraction

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| FR-FE-01 | Features shall be computed over a sliding window of 10 s with a hop of 1 s *(both provisional, both configurable)*. | M | T |
| FR-FE-02 | For G, the feature set shall include mean, standard deviation, maximum, deviation of the mean from the clean-air reference, and rate of change ΔG/Δt. | M | T |
| FR-FE-03 | For T and H, the feature set shall include mean, deviation from the window start, and rates of change ΔT/Δt and ΔH/Δt. | M | T |
| FR-FE-04 | Gas deviation shall be expressed as a percentage of ADC full scale so that fuzzy inputs do not depend on the raw scale. | M | T |
| FR-FE-05 | The clean-air reference shall be an average of G that updates only while status is `NORMAL`. It shall be frozen in every other status. | M | T |
| FR-FE-06 | The same feature code shall be used for live operation, replay, training and evaluation. | M | I |
| FR-FE-07 | A window with fewer than 80 % *(provisional)* of expected G samples shall be marked incomplete and handled by FR-DH-05. | M | T |
| FR-FE-08 | The feature list, units and formulas shall be documented in a data dictionary. | M | I |

### 4.5 Machine-learning classifier

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| FR-ML-01 | The classifier shall predict one of four classes (`normal`, `interference`, `gas`, `smoke`) for each complete window. | M | T |
| FR-ML-02 | The primary candidate shall be Random Forest, with Logistic Regression as the reference model and SVM as the alternative. The selected model shall be recorded with its rationale. | M | I |
| FR-ML-03 | Model selection and tuning shall use GroupKFold with the session as the group, so that no session appears in both training and validation folds. | M | I |
| FR-ML-04 | Two complete sessions *(provisional)* shall be held out before any model selection and used only for the final comparison. | M | I |
| FR-ML-05 | All preprocessing (for example scaling) shall be fitted on training folds only and stored inside the model pipeline. | M | I |
| FR-ML-06 | The classifier shall output a per-class score alongside the predicted class. Scores shall be labelled as model scores and never as a probability of danger. | M | I |
| FR-ML-07 | The trained model shall be saved as a versioned artefact with its training date, data version, feature list, hyperparameters and validation metrics (a model card). | M | I |
| FR-ML-08 | Training shall be reproducible from a single command with a fixed random seed. | M | T |
| FR-ML-09 | Training and inference shall run on a laptop CPU without a GPU. | M | D |
| FR-ML-10 | If the pilot shows that four classes cannot be separated, the class set may be reduced. The change and its evidence shall be documented. | S | I |

### 4.6 Fuzzy inference

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| FR-FZ-01 | The system shall implement Mamdani inference with centroid defuzzification, producing an APS from 0 to 100 for each complete window. | M | T |
| FR-FZ-02 | Inputs shall be gas deviation (% of full scale), gas rate (% of full scale per second), humidity rate (%RH per second) and temperature rate (°C per minute). | M | T |
| FR-FZ-03 | The initial rule base shall contain the six rules below. Each rule shall have a stable ID that is used in explanations. | M | T |
| FR-FZ-04 | Membership-function parameters shall be held in a configuration file under version control, not hard-coded. | M | I |
| FR-FZ-05 | Membership parameters shall be re-fitted from pilot and training data only. Held-out sessions shall not be used. | M | I |
| FR-FZ-06 | The fuzzy system shall report which rules fired and their firing strengths for every evaluation. | M | T |
| FR-FZ-07 | APS shall be mapped to bands: low below 35, moderate from 35 to below 65, high from 65 *(provisional cut-offs)*. | M | T |
| FR-FZ-08 | The scenarios S1–S5 of `fuzzy_rule_simulation.py` shall be kept as regression tests and re-baselined whenever parameters change. | M | T |

Initial rule base:

| Rule | IF | THEN APS |
| --- | --- | --- |
| R1 | gas deviation low AND gas rate slow AND humidity rate stable | low |
| R2 | gas deviation low AND humidity rate rapid AND temperature rate stable | low |
| R3 | gas rate rapid AND gas deviation moderate or high AND temperature rate stable | high |
| R4 | gas deviation moderate or high AND temperature rate rising | high |
| R5 | gas deviation moderate AND gas rate slow AND temperature rate stable | moderate |
| R6 | gas deviation high | high |

### 4.7 Decision rules and system status

The system has seven statuses, listed in order of precedence.

| Status | Meaning |
| --- | --- |
| `UNAVAILABLE` | No valid telemetry. |
| `FAULT` | Sensor data is invalid or stale. |
| `WARMING_UP` | Sensor is pre-heating; readings are not yet trusted. |
| `ALERT` | Evidence of a gas or smoke event. Investigate now. |
| `REVIEW_REQUIRED` | Evidence is mixed or unusual. A person should look. |
| `MONITORING` | Probable interference. No action needed, but the system keeps watching. |
| `NORMAL` | Nothing of note. |

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| FR-DR-01 | The decision layer shall apply rules in this order: device health (Section 4.3), safety override (FR-DR-03), then the fusion table (FR-DR-02). | M | T |
| FR-DR-02 | In the hybrid configuration, status shall be taken from the fusion table below. | M | T |
| FR-DR-03 | When gas deviation exceeds an override threshold (60 % of full scale *(provisional)*), status shall be `ALERT` whatever the classifier predicts. | M | T |
| FR-DR-04 | A prediction of interference shall apply to the current window only. It shall not suppress, delay or lower any later alert. | M | T |
| FR-DR-05 | The decision table shall be held as data (configuration), so that the same table drives the logic, the tests and the explanations. | M | I |
| FR-DR-06 | The system shall support three selectable configurations: fixed threshold, ML-only and hybrid. All three shall share ingestion, health and feature code. | M | T |
| FR-DR-07 | The fixed-threshold configuration shall raise `ALERT` when G deviation exceeds a threshold for a set number of consecutive windows. Both values shall be tuned on training data only. | M | T |
| FR-DR-08 | An alert episode shall start at the first `ALERT` window and end after 3 consecutive non-`ALERT` windows *(provisional)*. Episodes, not windows, are counted in false-alarm metrics. | M | T |
| FR-DR-09 | The ML-only configuration shall raise `ALERT` when the predicted class is `gas` or `smoke`, using the same episode rule. | M | T |
| FR-DR-10 | Every status change shall be written to the event log with the inputs that caused it (Section 5.3). | M | T |

Fusion table for the hybrid configuration *(provisional)*:

| Classifier prediction | APS low | APS moderate | APS high |
| --- | --- | --- | --- |
| `normal` | `NORMAL` | `REVIEW_REQUIRED` | `REVIEW_REQUIRED` |
| `interference` | `MONITORING` | `REVIEW_REQUIRED` | `REVIEW_REQUIRED` |
| `gas` or `smoke` | `REVIEW_REQUIRED` | `ALERT` | `ALERT` |

The table is deliberately conservative. The only cells that produce no prompt to the user are those where the classifier and the fuzzy score agree that nothing hazardous is happening.

### 4.8 Explanations

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| FR-EX-01 | Every status other than `NORMAL` shall be accompanied by a plain-language explanation. | M | T |
| FR-EX-02 | An explanation shall state: the measurements that mattered and their direction, the classifier's predicted class, the fuzzy rules that fired (by ID and description), and the recommended human action. | M | T |
| FR-EX-03 | Explanations shall be generated from the actual fired rules, feature values and fusion-table cell of that decision. No text shall be produced that is not backed by a logged value. | M | T |
| FR-EX-04 | An automated test shall confirm, for every logged decision in the evaluation set, that the explanation's rule IDs and measurement directions match the log (criterion C6). | M | T |
| FR-EX-05 | Explanations shall describe the decision process and shall not state a physical cause as fact. Wording such as "possible" and "predicted" shall be used. | M | I |
| FR-EX-06 | Health statuses shall be explained by cause, for example "No data from the sensor node for 8 seconds". | M | T |
| FR-EX-07 | When the override (FR-DR-03) triggers, the explanation shall say so and shall show the classifier's prediction separately. | M | T |

Example: "Gas-sensor response increased rapidly while temperature remained stable (rule R3). The classifier predicted a gas-related event. Further investigation is required."

### 4.9 Local indicators

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| FR-LI-01 | The node shall give a distinct indication for each of: normal, monitoring or review required, alert, warming up, and fault or connection lost. | M | D |
| FR-LI-02 | The buzzer shall sound only in `ALERT`. | M | D |
| FR-LI-03 | While muted, the buzzer shall be silent and the LED shall continue to show the true status. | M | D |
| FR-LI-04 | The mapping of status to LED colour or blink pattern shall be documented in the user guide. | S | I |

### 4.10 Dashboard (CMP-4)

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| FR-UI-01 | The dashboard shall show the current status prominently, with text as well as colour. | M | D |
| FR-UI-02 | The dashboard shall show live trend charts of G, T and H covering at least the last 5 minutes. | M | D |
| FR-UI-03 | The dashboard shall show the predicted class, model scores, APS and its band, and the current explanation. | M | D |
| FR-UI-04 | The dashboard shall show device health: connection state, time since last message, warm-up time remaining and any fault cause. | M | D |
| FR-UI-05 | The dashboard shall provide Confirm, Mute Buzzer and Mark False Alarm actions for the current alert episode. | M | D |
| FR-UI-06 | The dashboard shall show mute state and time remaining whenever a mute is active. | M | D |
| FR-UI-07 | The dashboard shall provide an event history listing past episodes with time, status, explanation and any review action. | M | D |
| FR-UI-08 | The dashboard shall display a permanent notice that the system is a supplementary prototype and not a certified alarm. | M | I |
| FR-UI-09 | The dashboard shall indicate clearly when it is showing replayed data rather than live data. | M | D |
| FR-UI-10 | The dashboard shall require a login before any status or action is available. | M | T |
| FR-UI-11 | The dashboard shall remain usable when the backend is unreachable, showing a clear "backend unavailable" state instead of the last known status. | M | T |
| FR-UI-12 | The dashboard should refresh at least once per second. | S | D |

### 4.11 Human review and audit

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| FR-HR-01 | An operator shall be able to confirm an alert, which records that a person has seen it. | M | T |
| FR-HR-02 | An operator shall be able to mute the buzzer for a fixed period (5 minutes *(provisional)*). The mute shall expire automatically. | M | T |
| FR-HR-03 | A mute shall apply to the current alert episode only. A new episode after the mute expires shall sound the buzzer again. | M | T |
| FR-HR-04 | Muting shall never change the status, hide it on the dashboard, or stop logging. | M | T |
| FR-HR-05 | An operator shall be able to mark an episode as a suspected false alarm with an optional note. | M | T |
| FR-HR-06 | Every review action shall be written to an append-only audit log with time, action, episode ID and operator role (Section 5.4). | M | T |
| FR-HR-07 | User annotations shall not change the model, the rules or any threshold automatically. They are stored for manual review only. | M | I |
| FR-HR-08 | No dashboard action shall be able to disable detection or suppress future alerts. | M | I |

### 4.12 Data collection and labelling (CMP-5)

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| FR-DC-01 | The experimenter shall be able to start and stop a recording session. Each session shall receive a unique ID and a setup record (date, location, ventilation, sensor warm-up time, notes). | M | D |
| FR-DC-02 | Within a session, the experimenter shall be able to mark the start and end of each trial with its class and, for interference, its sub-label. | M | D |
| FR-DC-03 | Recordings shall be saved as CSV with the columns in Section 5.2. | M | I |
| FR-DC-04 | A clean-air recovery interval shall be recorded between trials. The next trial shall not start until G has returned to within a set tolerance of the reference. | M | I |
| FR-DC-05 | The dataset shall contain 150–160 labelled sequences, balanced across classes, from at least 8 sessions on at least 4 days. | M | I |
| FR-DC-06 | A dataset log shall record, for each session, the number of sequences per class and any anomalies. | M | I |
| FR-DC-07 | A data sheet shall document provenance, collection procedure, label definitions, known limitations and permitted use. | M | I |
| FR-DC-08 | Raw recordings shall never be edited. Corrections are made in a separate label file and recorded in the dataset log. | M | I |

### 4.13 Replay

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| FR-RP-01 | The system shall replay a recorded CSV through the same validation, feature, reasoning and decision code as live data. | M | T |
| FR-RP-02 | Replay shall run at real-time speed for demonstration and at maximum speed for evaluation. | M | T |
| FR-RP-03 | A replay file with missing columns or invalid values shall be rejected with a clear message. | M | T |
| FR-RP-04 | Events produced during replay shall be tagged as replay in the event log and on the dashboard. | M | T |
| FR-RP-05 | The repository shall include sample recordings so that the system can be demonstrated without hardware. | M | I |

### 4.14 Evaluation tooling

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| FR-EV-01 | A single command shall run all three configurations over the held-out sessions and write a results report. | M | T |
| FR-EV-02 | The report shall include per-class precision, recall and F1, macro F1, a confusion matrix, and overall hazard recall with a 95 % confidence interval. | M | A |
| FR-EV-03 | The report shall include event-level false alarms on interference trials for each configuration, broken down by sub-label. | M | A |
| FR-EV-04 | The report shall include software latency (median and 95th percentile) and, where onset is logged, stimulus-to-alert time. | M | A |
| FR-EV-05 | The report shall list every false negative and every false alarm with its session, trial and explanation, for error analysis. | M | A |
| FR-EV-06 | Cross-validation estimates and held-out estimates shall be reported separately. | M | A |
| FR-EV-07 | The evaluation shall include one ablation: fuzzy inference and rules without the classifier. | S | A |
| FR-EV-08 | A fault-test suite shall run the cases in Section 9.2 and report pass or fail for each. | M | T |

---

## 5. Data requirements

### 5.1 Telemetry message (node to backend)

| Field | Type | Unit or range | Notes |
| --- | --- | --- | --- |
| `device_id` | string | — | Fixed per node |
| `fw_version` | string | — | Firmware version |
| `seq` | integer | ≥ 0 | Increases by 1 per message; resets on reboot |
| `uptime_ms` | integer | ms | Since power-up |
| `g_raw` | integer | 0–4095 | MQ-2 ADC reading after the divider |
| `t_c` | float or null | −40 to 80 °C | Null when the read failed |
| `h_rh` | float or null | 0–100 %RH | Null when the read failed |
| `dht_ok` | boolean | — | False when T/H are null |

### 5.2 Recording file (CSV)

Columns: `received_at_utc`, `session_id`, `trial_id`, `device_id`, `seq`, `uptime_ms`, `g_raw`, `t_c`, `h_rh`, `dht_ok`, `label`, `sub_label`, `stimulus_onset` (boolean marker).

### 5.3 Event log

One record per status change: `event_id`, `episode_id`, `time_utc`, `source` (live or replay), `configuration`, `previous_status`, `new_status`, `predicted_class`, `class_scores`, `aps`, `aps_band`, `fired_rules` with strengths, `feature_values`, `fusion_cell`, `override_applied`, `health_cause`, `explanation_text`, `model_version`, `rule_config_version`.

### 5.4 Audit log

One record per human action: `audit_id`, `time_utc`, `action` (confirm, mute, mute_expired, mark_false_alarm, login, config_change), `episode_id`, `operator_role`, `note`. The log is append-only.

### 5.5 Storage, retention and access

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| DR-01 | Telemetry, events and audit records shall be stored locally on the laptop running the backend. | M | I |
| DR-02 | The dataset and logs shall be kept in the team's private repository or local storage until the course ends, then deleted or archived as the lecturer directs. | M | I |
| DR-03 | Access shall be limited to team members and the lecturer. | M | I |
| DR-04 | No names, images, audio or other personal data shall be collected. Operators are recorded by role only. | M | I |
| DR-05 | Model artefacts, rule configuration and dataset versions shall be identifiable so that any logged decision can be traced to the versions that produced it. | M | I |
| DR-06 | The UCI Gas Sensor Array Drift Dataset (CC BY 4.0) shall be used only as a methodological reference and shall be cited wherever it is mentioned. | M | I |

---

## 6. Non-functional requirements

### 6.1 Performance

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| NFR-P-01 | Software latency from a complete input window to alert output shall be at most 1 s at the 95th percentile (criterion C4). | M | A |
| NFR-P-02 | Stimulus-to-alert time shall be at most 30 s where onset is reliably logged *(provisional)*. | S | A |
| NFR-P-03 | The system shall run continuously for at least 2 hours without restart or unbounded memory growth. | M | T |
| NFR-P-04 | The whole system shall run on one laptop CPU with no GPU. | M | D |

### 6.2 Reliability and safety

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| NFR-R-01 | The system shall fail safe: on any internal error in the reasoning pipeline, status shall become `FAULT`, never `NORMAL`. | M | T |
| NFR-R-02 | An exception while processing one message shall not stop the backend. | M | T |
| NFR-R-03 | After a backend restart, the system shall resume without manual steps and shall re-enter warm-up if node continuity cannot be confirmed. | M | T |
| NFR-R-04 | All fault and recovery cases in Section 9.2 shall pass (criterion C5). | M | T |
| NFR-R-05 | Uncertain outputs shall be presented as uncertain. No screen shall show a gas concentration, a probability of danger or a statement of physical cause. | M | I |

### 6.3 Security and privacy

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| NFR-S-01 | Dashboard access shall require authentication. | M | T |
| NFR-S-02 | The telemetry interface shall require a device key (FR-BE-07). | M | T |
| NFR-S-03 | Keys and passwords shall be supplied through environment variables or an untracked file. None shall be committed to the repository. | M | I |
| NFR-S-04 | The backend shall listen on the local machine or local network only. | M | I |
| NFR-S-05 | All external input (telemetry, replay files, dashboard forms) shall be validated before use. | M | T |
| NFR-S-06 | Free-text notes shall be length-limited and escaped when displayed. | M | T |
| NFR-S-07 | Configuration changes that affect detection (thresholds, rules, model) shall be possible only through files under version control, not through the dashboard. | M | I |

### 6.4 Usability

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| NFR-U-01 | Status shall be understandable without colour vision: every colour is paired with text or an icon. | M | I |
| NFR-U-02 | Explanations shall use plain language and avoid internal variable names. | M | I |
| NFR-U-03 | A first-time user shall be able to identify the current status and the reason for it within 10 seconds, checked informally with at least 3 people outside the team. | S | D |
| NFR-U-04 | A short user guide shall describe statuses, indicators, actions and limitations. | M | I |

### 6.5 Maintainability and reproducibility

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| NFR-M-01 | The repository shall contain setup instructions, a pinned dependency file and sample inputs, so that a new machine can run the replay demonstration from a clean checkout. | M | T |
| NFR-M-02 | Feature extraction, fuzzy inference, decision rules and explanation generation shall each have unit tests run by pytest. | M | T |
| NFR-M-03 | Development shall use feature branches and peer-reviewed pull requests, with tasks tracked as GitHub Issues. | M | I |
| NFR-M-04 | Each member shall keep a contribution log referencing commits, issues, tests and documents. | M | I |
| NFR-M-05 | The final submission shall be an immutable tagged release. | M | I |
| NFR-M-06 | Tunable values shall live in configuration files, not in code. | M | I |
| NFR-M-07 | Components shall communicate through the documented interfaces in Section 5, so that the node, backend and dashboard can be developed and tested separately. | S | I |

### 6.6 Resource awareness

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| NFR-E-01 | The system shall not depend on any external or paid service at run time. | M | I |
| NFR-E-02 | The final report shall state training time, inference time and hardware used. | M | I |

---

## 7. Responsible-AI requirements

These map to Section 8 of the Project Instruction.

| ID | Area | Requirement | Pri | Ver |
| --- | --- | --- | :---: | :---: |
| RAI-01 | Purpose and stakeholders | Intended use, excluded use and the accountable person (the operator) shall be stated in the dashboard, the user guide and the final report. | M | I |
| RAI-02 | Data governance | Data source, ownership, minimisation, retention and access shall be documented (Section 5.5 and the data sheet). | M | I |
| RAI-03 | Fairness | The report shall justify why demographic fairness analysis does not apply (no data about people or groups) and shall instead report performance per interference sub-label, per session and per humidity range. | M | A |
| RAI-04 | Transparency | The dashboard shall explain what the system is for, what each output means, and its known limitations, in language suited to the operator. | M | I |
| RAI-05 | Human oversight | Confirm, mute and false-alarm actions shall be available and logged; the human decides the response (Section 4.11). | M | D |
| RAI-06 | Security and privacy | Requirements in Section 6.3 and DR-04 shall be met. The report shall discuss misuse, including muting abuse and tampering with the sensor. | M | I |
| RAI-07 | Reliability | Representative, edge, invalid and failure cases shall be tested (Section 9). Proxy stimuli shall be described as proxies. | M | T |
| RAI-08 | Resource awareness | NFR-E-01 and NFR-E-02 shall be met. | M | I |
| RAI-09 | Residual risk | The report shall list residual risks, including missed events, ethanol and gas confusion, and sensor drift. | M | I |
| RAI-10 | AI-use disclosure | Each assessed document shall include an AI-use statement naming tools, purpose, material, verification and the responsible member. | M | I |

---

## 8. Constraints and assumptions

### 8.1 Constraints

- Hardware budget: about RM40 for the core parts (ESP32, MQ-2, DHT22, LED, buzzer).
- One gas sensor. A second (for example MQ-3) is a fallback, not a baseline assumption.
- No ignition and no open flame in any test or demonstration. Smoke is shown by replay unless a suitable facility is approved.
- Physical tests follow a procedure approved by the lecturer or laboratory staff: small fixed releases, ventilation, and no direct spray onto the sensor.
- Team of three. Deadlines: design 21 December 2026; prototype, report and presentation 21 January 2027.
- Technology stack: Arduino C++, Python, scikit-learn, scikit-fuzzy, FastAPI, Pydantic, Streamlit, pytest, GitHub.

### 8.2 Assumptions

- A laptop is available to power the node and run the backend and dashboard.
- The node and laptop can communicate over the chosen transport in the demonstration room.
- The MQ-2 gives a repeatable response after warm-up, to be confirmed in the pilot.
- At least 8 collection sessions can be completed by 7 December 2026.
- Butane, ethanol mist, steam and incense smoke are acceptable proxies for the purposes of this prototype.

---

## 9. Acceptance

### 9.1 Success criteria (from the proposal)

| ID | Measure | Provisional target | Verified by |
| --- | --- | --- | --- |
| C1 | Overall hazard recall (gas and smoke combined) | ≥ 90 %, with a 95 % confidence interval | FR-EV-02 |
| C2 | Macro F1 across four classes | ≥ 0.85 | FR-EV-02 |
| C3 | Event-level false alarms on interference trials | ≥ 75 % relative reduction against the tuned threshold baseline, with hazard recall within 5 percentage points | FR-EV-03 |
| C4 | Latency | Software 95th percentile ≤ 1 s; stimulus-to-alert ≤ 30 s where onset is logged | FR-EV-04 |
| C5 | Reliability and auditability | All fault and recovery tests pass; every review and mute action logged | FR-EV-08, FR-HR-06 |
| C6 | Explanation faithfulness | Every displayed explanation matches the fired rules and logged measurements | FR-EX-04 |

Missing a provisional target does not fail the project. It must be reported honestly with an error analysis.

### 9.2 Fault and recovery test cases

| ID | Case | Expected behaviour |
| --- | --- | --- |
| FT-01 | Node powered on | `WARMING_UP` for the configured period, then normal operation |
| FT-02 | Node unplugged during operation | `UNAVAILABLE` within the stale limit; dashboard shows the cause |
| FT-03 | Node reconnected | Warm-up re-entered, then normal operation without a backend restart |
| FT-04 | DHT22 disconnected | T/H null; `FAULT` after the stale limit; never `NORMAL` |
| FT-05 | G pinned at 0 or 4095 | `FAULT` with cause shown |
| FT-06 | Malformed or out-of-range message | Rejected, counted, pipeline unaffected |
| FT-07 | Message without a valid device key | Rejected |
| FT-08 | Duplicate and out-of-order sequence numbers | Discarded and counted |
| FT-09 | Backend restarted during operation | Resumes automatically; node shows connection lost meanwhile |
| FT-10 | Dashboard open while backend is down | "Backend unavailable" shown, not the last status |
| FT-11 | Mute during an alert | Buzzer silent; status, LED and logging unchanged; mute expires on time |
| FT-12 | New alert episode after mute expiry | Buzzer sounds again |
| FT-13 | Alert immediately after an interference window | Alert is raised without delay (FR-DR-04) |
| FT-14 | Gas deviation above override while classifier predicts normal | `ALERT` with override explanation |
| FT-15 | Replay file with missing columns | Rejected with a clear message |
| FT-16 | Exception injected into the reasoning pipeline | `FAULT`; backend keeps running |
| FT-17 | Unauthenticated dashboard access | No status or action available |

### 9.3 Demonstration scenarios

| ID | Scenario | Mode | Expected result |
| --- | --- | --- | --- |
| DS-01 | Clean air | Live | `NORMAL` |
| DS-02 | Warm-water steam | Live | `MONITORING` or `NORMAL`; no buzzer |
| DS-03 | Brief 70 % ethanol mist | Live | `MONITORING` or `REVIEW_REQUIRED`, with explanation |
| DS-04 | Unignited butane release | Live | `ALERT`, buzzer, explanation |
| DS-05 | Mute and false-alarm marking | Live | Actions take effect and appear in the audit log |
| DS-06 | Smoke recording | Replay | `ALERT`, tagged as replay |
| DS-07 | Node unplugged (edge case) | Live | `UNAVAILABLE` shown |

---

## 10. Traceability

### 10.1 Project Instruction Section 4 (minimum prototype) to requirements

| Minimum requirement | Covered by |
| --- | --- |
| End-to-end operation | FR-SN-04, FR-BE-01, FR-DR-02, FR-UI-01, FR-RP-01, DS-01 to DS-07 |
| Cognitive component | FR-ML-01, FR-FZ-01, FR-DR-02, FR-EX-02 |
| Data or knowledge layer | FR-DC-05 to FR-DC-08, FR-FZ-03, FR-FZ-04, FR-FE-08, Section 5 |
| Software architecture | Section 3, Section 5, NFR-M-07 |
| Interface | Section 4.10, Section 4.9, FR-BE-08 |
| Evaluation | Section 4.14, Section 9 |
| Reliability and safety | Section 4.3, Section 6.2, FR-BE-02, Section 9.2 |
| Responsible AI controls | Section 7, Section 4.11, Section 6.3 |

### 10.2 Proposal objectives to requirements

| Objective | Covered by |
| --- | --- |
| O1 Integrated node, backend and dashboard | Sections 4.1, 4.2, 4.9, 4.10 |
| O2 Documented multi-session dataset | Section 4.12 |
| O3 ML classifier on temporal features | Sections 4.4, 4.5 |
| O4 Fuzzy inference, rules and explanations | Sections 4.6, 4.7, 4.8 |
| O5 Three-way comparison | FR-DR-06 to FR-DR-09, Section 4.14 |

### 10.3 Suggested ownership

| Area | Lead |
| --- | --- |
| Sections 4.1, 4.2, 4.3, 4.9, 6.2, 6.3 | Tan Choon Da |
| Sections 4.4, 4.5, 4.12, 4.14 | Lee Ming Da |
| Sections 4.6, 4.7, 4.8, 4.10, 4.11, 7 | Gan Rui En |
| Sections 4.13, 6.5, 9 | All |

---

## 11. Priorities for delivery

| Stage | Date | Minimum to have working |
| --- | --- | --- |
| Pilot | 23 November 2026 | FR-SN-01 to FR-SN-05, FR-BE-01 to FR-BE-06, FR-DC-01 to FR-DC-03 |
| Baseline | 30 November 2026 | FR-FE-01 to FR-FE-06, FR-DR-07, FR-DR-08 |
| Dataset complete | 7 December 2026 | FR-DC-05 to FR-DC-07 |
| Proof of concept | 14–21 December 2026 | First versions of 4.5, 4.6, 4.7, 4.8, 4.10 and 4.13 running end to end |
| Evaluation | 11 January 2027 | Sections 4.14 and 9.2 complete |
| Release | 21 January 2027 | All M requirements; tagged release |

---

## 12. Open items

| ID | Decision needed | Default in this draft | Decide by |
| --- | --- | --- | --- |
| OI-01 | Node-to-backend transport: Wi-Fi HTTP or USB serial | Not fixed; the message schema is the same either way | 23 November |
| OI-02 | MQ-2 warm-up period | Configurable; set from the manual and pilot | 23 November |
| OI-03 | Window length and hop | 10 s and 1 s | 30 November |
| OI-04 | Stale and fault time limits | 5 s for G, 10 s for T/H | 30 November |
| OI-05 | Whether temperature features carry signal with the DHT22 | Kept; review in pilot | 30 November |
| OI-06 | Whether ethanol and butane are separable with one sensor; add MQ-3 or merge classes | Single sensor, four classes | 30 November |
| OI-07 | Whether smoke data can be collected safely | Four classes; fall back to three | 30 November |
| OI-08 | Fuzzy membership parameters and APS band cut-offs | Values in `fuzzy_rule_simulation.py` | 14 December |
| OI-09 | Fusion table and override threshold | Table in Section 4.7; 60 % of full scale | 14 December |
| OI-10 | Number of held-out sessions | 2 | 7 December |
| OI-11 | Mute duration and episode end rule | 5 minutes; 3 non-alert windows | 14 December |
| OI-12 | LED hardware and status-to-indication mapping | Not fixed | 23 November |
| OI-13 | Storage format for telemetry and logs (CSV, SQLite) | Not fixed | 30 November |
| OI-14 | Final classifier | Random Forest primary | 21 December |

---

## 13. Revision history

| Version | Date | Change |
| --- | --- | --- |
| 0.1 | 16 November 2026 | First draft derived from the Phase 1 proposal and the Project Instruction |
