# ha-linux-mqtt-dhtxx

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![Dependabot Status](https://img.shields.io/badge/Dependabot-enabled-025e8c?logo=dependabot)](https://dependabot.com)
[![GitHub repo](https://img.shields.io/badge/github-repo-000)](https://github.com/AnthonyWrather/ha-linux-mqtt-dhtxx)

A Python service that automatically creates Linux sensor devices in Home Assistant to publish temperature and humidity data via MQTT. This project enables seamless integration of DHT-11 and DHT-22 sensors with Home Assistant using the MQTT Discovery protocol.

This has been tested on the following hardware with generic DHT sensors.

- Raspberry Pi 2B running Trixie
- Raspberry Pi 3B running Buster
- Raspberry Pi 5B running Trixie

Other versions of Linux should also work so long as they run Python 3.X

## Features

- **DHT Sensor Reading**: Read temperature and humidity from DHT-11 and DHT-22 sensors
- **MQTT Discovery**: Automatic device discovery in Home Assistant (no manual configuration needed)
- **Auto-Reconnection**: Robust MQTT reconnection handling with exponential backoff
- **Availability Tracking**: Reports online/offline status to Home Assistant
- **Configurable**: Fully configurable via `config.ini` (broker, credentials, GPIO pins, sensor types, topics)
- **Service Support**: Can run as a systemd service for persistent operation
- **Multi-Sensor Support**: Support for multiple DHT sensors connected to different GPIO pins

## Prerequisites

- Raspberry Pi or compatible Linux device with GPIO support
- Python 3.7+
- MQTT broker (e.g., Home Assistant with MQTT addon, Mosquitto)
- DHT-11 or DHT-22 sensor(s) connected to GPIO pin(s)
- Adafruit CircuitPython DHT library support

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/AnthonyWrather/ha-linux-mqtt-dhtxx.git
cd ha-linux-mqtt-dhtxx
```

### 2. Create Python Virtual Environment

```bash
python -m venv .ha-linux-mqtt-dhtxx
source .ha-linux-mqtt-dhtxx/bin/activate
pip install -r requirements.txt
```

### 3. Create Helper Script

Create `~/bin/ha-linux-mqtt-dhtxx.sh` (create the `~/bin` directory if it doesn't exist):

```bash
#!/bin/bash
cd "$(dirname "$0")/../Projects/Home Assistant/Remote Dev/ha-linux-mqtt-dhtxx" || exit
source .ha-linux-mqtt-dhtxx/bin/activate
while true; do python ha-linux-mqtt-dhtxx.py; done
deactivate
```

Make it executable:

```bash
chmod +x ~/bin/ha-linux-mqtt-dhtxx.sh
```

## Configuration

Copy `config.ini.EXAMPLE` to `config.ini` and update the following settings:

```bash
cp config.ini.EXAMPLE config.ini
nano config.ini
```

### Configuration Parameters

#### [mqtt] Section

```conf
[mqtt]
broker = homeassistant.lan          # MQTT broker hostname or IP
username = mqtt_user                # MQTT username
password = your_secure_password     # MQTT password
port = 1883                         # MQTT port (default: 1883)
timeout = 60                        # Reconnection timeout in seconds
topic_config = /config              # MQTT discovery config topic suffix
topic_state = /state                # State publication topic suffix
topic_set = /set                    # Command subscription topic suffix (not used for sensors)
topic_availability = /availability  # Availability status topic suffix
```

#### [sensor] Section

```conf
[sensor]
pins = ["D4"]              # GPIO pin names (board numbering) in the same order as device_names and types
types = ["DHT-11"]         # Sensor types (DHT-11 or DHT-22) in the same order as device_names and pins
```

#### [homeassistant] Section

```conf
[homeassistant]
device_names = ["main_cabin"]       # Device identifiers used in MQTT topics
topic_base = homeassistant/sensor   # Base topic for MQTT discovery
```

### Example Configuration

Here's a typical setup example with two sensors:

```conf
[mqtt]
broker = homeassistant.local
username = controlpi_mqtt
password = CHANGE_ME
port = 1883
timeout = 60

[sensor]
pins = ["D4", "D5"]
types = ["DHT-11", "DHT-22"]

[homeassistant]
device_names = ["main_cabin", "basement"]
topic_base = homeassistant/sensor
topic_config = /config
topic_state = /state
topic_set = /set
topic_availability = /availability
```

## Running the Service

### Option 1: Manual Execution (Development/Testing)

```bash
# Activate the virtual environment
source .ha-linux-mqtt-dhtxx/bin/activate

# Run the script
python ha-linux-mqtt-dhtxx.py
```

### Option 2: Screen Session

```bash
# Start a detached screen session
screen -dmS ha-linux-mqtt-dhtxx ~/bin/ha-linux-mqtt-dhtxx.sh

# View logs
screen -S ha-linux-mqtt-dhtxx -X hardcopy -h -S - | tail -50

# Attach to the session
screen -r ha-linux-mqtt-dhtxx

# Detach from the session (press Ctrl+A, then D)
```

### Option 3: Systemd Service (Recommended for Production)

#### Create the Service File

```bash
sudo systemctl edit --force --full ha-linux-mqtt-dhtxx.service
```

Paste the following configuration:

```ini
[Unit]
Description=ha-linux-mqtt-dhtxx MQTT Sensor Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=controlpi
Group=controlpi
WorkingDirectory=/home/controlpi/Projects/Home Assistant/Remote Dev/ha-linux-mqtt-dhtxx
ExecStart=/home/controlpi/bin/ha-linux-mqtt-dhtxx.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ha-linux-mqtt-dhtxx

[Install]
WantedBy=multi-user.target
```

#### Enable and Start the Service

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable ha-linux-mqtt-dhtxx.service

# Start the service
sudo systemctl start ha-linux-mqtt-dhtxx.service

# Check service status
sudo systemctl status ha-linux-mqtt-dhtxx.service

# View service logs
journalctl -u ha-linux-mqtt-dhtxx.service -f
```

## Home Assistant Integration

Once the service is running, Home Assistant will automatically discover the sensor devices via MQTT Discovery. Each configured sensor will appear as two entities in Home Assistant: a temperature sensor and a humidity sensor.

### MQTT Topics

The service publishes to the following MQTT topics:

- **Config Topics**: Used for Home Assistant auto-discovery (sends device configuration for temperature and humidity sensors)
- **State Topic**: Publishes the current sensor state (temperature and humidity as JSON)
- **Availability Topic**: Publishes availability status (`online` or `offline`)

All topics are dynamically generated based on `config.ini` settings and each device name:

```
{topic_base}/dhtxx/{device_name}/config
{topic_base}/dhtxx/{device_name}T/config
{topic_base}/dhtxx/{device_name}H/config
{topic_base}/dhtxx/{device_name}/state
{topic_base}/dhtxx/{device_name}/availability
```

## Troubleshooting

### Service Won't Start

Check the service logs:

```bash
journalctl -u ha-linux-mqtt-dhtxx.service -n 50 -e
```

### MQTT Connection Issues

1. **Verify MQTT Broker**: Check that your MQTT broker is running and accessible
   ```bash
   # Test connection from your device
   mosquitto_sub -h homeassistant.local -u mqtt_user -P your_password -t '#'
   ```

2. **Check Credentials**: Ensure username and password in `config.ini` are correct

3. **Verify Broker Address**: Ensure `config.ini` has the correct broker hostname/IP

### Sensor Reading Issues

1. **Check GPIO Pin Numbers**: Verify the `pins` list in `config.ini` matches your sensor GPIO pins and is in the same order as `device_names` and `types`
2. **Check Sensor Types**: Ensure `types` array matches your actual sensor types (DHT-11 or DHT-22)
3. **GPIO Permissions**: Ensure the user running the service has GPIO permissions
4. **Sensor Connection**: Verify sensor wiring and power supply
5. **Sensor Errors**: DHT sensors can be unreliable; the service retries up to 5 times per reading cycle

### Device Not Appearing in Home Assistant

1. Check that MQTT integration is enabled in Home Assistant
2. Verify the service is running: `systemctl status ha-linux-mqtt-dhtxx.service`
3. Check the device availability topic for `online` status
4. Check Home Assistant logs for MQTT-related errors

### Debugging

To see detailed debug output:

```bash
# Run the script directly (not as a service)
source .ha-linux-mqtt-dhtxx/bin/activate
python ha-linux-mqtt-dhtxx.py
```

This will display logging output to the console for troubleshooting.

## Development Notes

- The code uses Python 3 with the `paho-mqtt` library for MQTT communication and `adafruit-circuitpython-dht` for sensor reading
- GPIO control is handled by the Adafruit DHT library
- Configuration is read from `config.ini` using Python's `configparser`
- The service maintains automatic reconnection to the MQTT broker with exponential backoff
- Home Assistant discovery is done via the MQTT Discovery protocol with separate entities for temperature and humidity
- Sensor readings are taken every 30 seconds

## Resources

- [Home Assistant MQTT Documentation](https://www.home-assistant.io/integrations/mqtt/)
- [Home Assistant MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery)
- [Paho MQTT Python Client](https://github.com/eclipse/paho.mqtt.python)
- [Adafruit CircuitPython DHT](https://github.com/adafruit/Adafruit_CircuitPython_DHT)
- [DHT Sensor Documentation](https://learn.adafruit.com/dht/overview)

## License

See [LICENSE](LICENSE) file for details.

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community guidelines.

