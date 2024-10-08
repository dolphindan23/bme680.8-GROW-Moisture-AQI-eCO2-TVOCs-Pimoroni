#!/usr/bin/env python

import time
import bme680
from datetime import datetime

print("""read-all.py - Displays temperature, pressure, humidity, gas resistance, and estimates air quality.

Press Ctrl+C to exit!

""")

# Initialize BME680 sensor
try:
    sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
except (RuntimeError, IOError):
    sensor = bme680.BME680(bme680.I2C_ADDR_SECONDARY)

# Set BME680 sensor settings
sensor.set_humidity_oversample(bme680.OS_2X)
sensor.set_pressure_oversample(bme680.OS_4X)
sensor.set_temperature_oversample(bme680.OS_8X)
sensor.set_filter(bme680.FILTER_SIZE_3)
sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)
sensor.set_gas_heater_temperature(320)
sensor.set_gas_heater_duration(150)
sensor.select_gas_heater_profile(0)

# Helper functions for air quality calculation
def gas_resistance_to_aqi(gas_resistance):
    min_gas_resistance = 10
    max_gas_resistance = 1400000
    gas_resistance = max(min_gas_resistance, min(gas_resistance, max_gas_resistance))
    aqi = 500 - int((gas_resistance - min_gas_resistance) / (max_gas_resistance - min_gas_resistance) * 499)
    return aqi

def aqi_to_co2(aqi):
    base_co2 = 400   # ppm for AQI 50 (typical outdoor clean air)
    max_co2 = 2500   # ppm for AQI 500 (potentially unhealthy levels)
    estimated_co2 = base_co2 + (max_co2 - base_co2) * (aqi / 500)
    return estimated_co2

def gas_resistance_to_tvoc(gas_resistance):
    min_gas_resistance = 10
    max_gas_resistance = 1400000
    gas_resistance = max(min_gas_resistance, min(gas_resistance, max_gas_resistance))
    max_tvoc_ppb = 1000
    min_tvoc_ppb = 0
    tvoc = max_tvoc_ppb - ((gas_resistance - min_gas_resistance) / (max_gas_resistance - min_gas_resistance)) * max_tvoc_ppb
    return tvoc

# Collect burn-in data
start_time = time.time()
curr_time = time.time()
burn_in_time = 300
burn_in_data = []

try:
    print('Collecting gas resistance burn-in data for 5 mins\n')
    while curr_time - start_time < burn_in_time:
        curr_time = time.time()
        if sensor.get_sensor_data() and sensor.data.heat_stable:
            gas = sensor.data.gas_resistance
            burn_in_data.append(gas)
            print('Gas: {0} Ohms'.format(gas))
            time.sleep(1)

    gas_baseline = sum(burn_in_data[-50:]) / 50.0
    hum_baseline = 40.0
    hum_weighting = 0.25

    print('Gas baseline: {0} Ohms, humidity baseline: {1:.2f} %RH\n'.format(
        gas_baseline,
        hum_baseline))

    while True:
        if sensor.get_sensor_data() and sensor.data.heat_stable:
            gas = sensor.data.gas_resistance
            gas_offset = gas_baseline - gas
            hum = sensor.data.humidity
            hum_offset = hum - hum_baseline

            if hum_offset > 0:
                hum_score = (100 - hum_baseline - hum_offset)
                hum_score /= (100 - hum_baseline)
                hum_score *= (hum_weighting * 100)
            else:
                hum_score = (hum_baseline + hum_offset)
                hum_score /= hum_baseline
                hum_score *= (hum_weighting * 100)

            if gas_offset > 0:
                gas_score = (gas / gas_baseline)
                gas_score *= (100 - (hum_weighting * 100))
            else:
                gas_score = 100 - (hum_weighting * 100)

            air_quality_score = hum_score + gas_score

            # Convert gas resistance to AQI
            aqi_value = gas_resistance_to_aqi(gas)

            # Estimate CO2 and TVOC based on AQI
            estimated_co2 = aqi_to_co2(aqi_value)
            estimated_tvoc = gas_resistance_to_tvoc(gas)

            # Print the combined data
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\nTime: {current_time}")
            print(f"Temperature: {sensor.data.temperature:.2f} °C")
            print(f"Pressure: {sensor.data.pressure:.2f} hPa")
            print(f"Humidity: {sensor.data.humidity:.2f} %")
            print(f"Gas Resistance: {sensor.data.gas_resistance} Ohms -> AQI: {aqi_value}")
            print(f"Estimated CO2: {estimated_co2:.2f} ppm")
            print(f"Estimated TVOC: {estimated_tvoc:.2f} ppb")
            print("-" * 40)

        time.sleep(5)

except KeyboardInterrupt:
    print("Exiting...")
