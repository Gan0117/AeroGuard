"""AeroGuard - Phase 1 fuzzy-rule simulation (initial evidence).

Purpose
-------
Checks that the candidate Mamdani rule base in the proposal behaves as
intended on SYNTHETIC inputs. It tests rule behaviour only. It does not
validate physical detection: no sensor data is used, and every membership
parameter below is a provisional placeholder to be re-fitted from pilot and
training data.

Inputs (all computed over one feature window)
    gas_dev   MQ-2 response deviation from the clean-air reference, % of ADC full scale
    gas_rate  rate of change of the MQ-2 response, % of full scale per second
    hum_rate  rate of change of relative humidity, %RH per second
    temp_rate rate of change of temperature, degC per minute

Output
    Alert Priority Score (APS), 0-100. A relative decision priority, not a
    measured hazard severity.

Run
    pip install scikit-fuzzy numpy scipy networkx
    python fuzzy_rule_simulation.py
"""

from __future__ import annotations

import csv
import sys

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl


def build_system() -> ctrl.ControlSystem:
    gas_dev = ctrl.Antecedent(np.arange(0, 100.5, 0.5), "gas_dev")
    gas_rate = ctrl.Antecedent(np.arange(0, 10.05, 0.05), "gas_rate")
    hum_rate = ctrl.Antecedent(np.arange(0, 5.05, 0.05), "hum_rate")
    temp_rate = ctrl.Antecedent(np.arange(0, 6.05, 0.05), "temp_rate")
    aps = ctrl.Consequent(np.arange(0, 101, 1), "aps", defuzzify_method="centroid")

    # Provisional membership functions (placeholders pending pilot data).
    gas_dev["low"] = fuzz.trapmf(gas_dev.universe, [0, 0, 5, 15])
    gas_dev["moderate"] = fuzz.trimf(gas_dev.universe, [10, 25, 45])
    gas_dev["high"] = fuzz.trapmf(gas_dev.universe, [35, 55, 100, 100])

    gas_rate["slow"] = fuzz.trapmf(gas_rate.universe, [0, 0, 0.3, 1.0])
    gas_rate["rapid"] = fuzz.trapmf(gas_rate.universe, [0.5, 2.0, 10, 10])

    hum_rate["stable"] = fuzz.trapmf(hum_rate.universe, [0, 0, 0.2, 0.6])
    hum_rate["rapid"] = fuzz.trapmf(hum_rate.universe, [0.4, 1.0, 5, 5])

    temp_rate["stable"] = fuzz.trapmf(temp_rate.universe, [0, 0, 0.5, 1.5])
    temp_rate["rising"] = fuzz.trapmf(temp_rate.universe, [1.0, 2.5, 6, 6])

    aps["low"] = fuzz.trapmf(aps.universe, [0, 0, 15, 35])
    aps["moderate"] = fuzz.trimf(aps.universe, [30, 50, 70])
    aps["high"] = fuzz.trapmf(aps.universe, [65, 85, 100, 100])

    rules = [
        # R1 Normal: nothing is happening.
        ctrl.Rule(gas_dev["low"] & gas_rate["slow"] & hum_rate["stable"], aps["low"]),
        # R2 Small gas-response increase + rapid humidity rise + stable temperature
        #    -> possible humidity-related interference; continue monitoring.
        ctrl.Rule(gas_dev["low"] & hum_rate["rapid"] & temp_rate["stable"], aps["low"]),
        # R3 Rapid gas-response increase + stable temperature
        #    -> possible gas-related event requiring investigation.
        ctrl.Rule(
            gas_rate["rapid"] & (gas_dev["moderate"] | gas_dev["high"]) & temp_rate["stable"],
            aps["high"],
        ),
        # R4 Increasing gas response and temperature
        #    -> possible heat-associated abnormal event.
        ctrl.Rule((gas_dev["moderate"] | gas_dev["high"]) & temp_rate["rising"], aps["high"]),
        # R5 Persistent abnormal gas response without temperature rise
        #    -> continued investigation required.
        ctrl.Rule(
            gas_dev["moderate"] & gas_rate["slow"] & temp_rate["stable"], aps["moderate"]
        ),
        # R6 Safety override: a high gas response is never scored low.
        ctrl.Rule(gas_dev["high"], aps["high"]),
    ]
    return ctrl.ControlSystem(rules)


# Synthetic scenarios: (id, description, gas_dev, gas_rate, hum_rate, temp_rate, expected band)
SCENARIOS = [
    ("S1", "Clean air, steady state", 2, 0.05, 0.05, 0.1, "low"),
    ("S2", "Steam-like: small gas rise, rapid humidity rise", 8, 0.3, 2.0, 0.3, "low"),
    ("S3", "Gas-like: rapid gas rise, stable temperature", 50, 4.0, 0.1, 0.2, "high"),
    ("S4", "Heat-associated: gas response and temperature rising", 40, 1.5, 0.1, 3.5, "high"),
    ("S5", "Persistent moderate gas response, no temperature rise", 25, 0.1, 0.1, 0.2, "moderate"),
    ("S6", "Ethanol-mist-like: rapid gas rise, mild humidity rise", 45, 3.5, 0.5, 0.2, "?"),
    ("S7", "Steam with larger gas response (conflicting evidence)", 22, 0.8, 2.5, 0.3, "?"),
]


def band(score: float) -> str:
    """Report band used only for reading the table (provisional cut-offs)."""
    if score < 35:
        return "low"
    if score < 65:
        return "moderate"
    return "high"


def main() -> int:
    system = build_system()
    rows = []
    for sid, desc, g, gr, hr, tr, expected in SCENARIOS:
        sim = ctrl.ControlSystemSimulation(system)
        sim.input["gas_dev"] = g
        sim.input["gas_rate"] = gr
        sim.input["hum_rate"] = hr
        sim.input["temp_rate"] = tr
        sim.compute()
        score = float(sim.output["aps"])
        got = band(score)
        verdict = "n/a" if expected == "?" else ("pass" if got == expected else "FAIL")
        rows.append((sid, desc, g, gr, hr, tr, round(score, 1), got, expected, verdict))

    header = (
        "id", "scenario", "gas_dev_%FS", "gas_rate_%FS/s", "hum_rate_%RH/s",
        "temp_rate_C/min", "APS", "band", "expected", "check",
    )
    print(" | ".join(header))
    for r in rows:
        print(" | ".join(str(x) for x in r))

    with open("fuzzy_rule_simulation_results.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)

    failed = [r[0] for r in rows if r[-1] == "FAIL"]
    print("\nExpected-band checks failed:", failed if failed else "none")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
