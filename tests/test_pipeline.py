import sys
import os
import pytest
from datetime import datetime

# Add project root to Python path so it can find 'main'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import WeatherPayload, execute_ml_inference

def test_valid_payload():
    data = WeatherPayload(temperature=25.5, humidity=45.0, pressure=1010.0)
    assert data.temperature == 25.5
    assert data.humidity == 45.0
    assert data.pressure == 1010.0

def test_invalid_temperature_too_high():
    with pytest.raises(Exception):  # Pydantic raises ValidationError
        WeatherPayload(temperature=150.0, humidity=50.0, pressure=1010.0)

def test_invalid_temperature_too_low():
    with pytest.raises(Exception):
        WeatherPayload(temperature=-50.0, humidity=50.0, pressure=1010.0)

def test_anomaly_detection():
    payload = WeatherPayload(temperature=45.0, humidity=30.0, pressure=1000.0)
    anomaly, pred, conf = execute_ml_inference(payload)
    assert anomaly == 1, f"Expected anomaly for 45°C, but got {anomaly}"

def test_normal_condition():
    payload = WeatherPayload(temperature=22.0, humidity=50.0, pressure=1013.0)
    anomaly, pred, conf = execute_ml_inference(payload)
    assert anomaly == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])