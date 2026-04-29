###############################################################################
#
# python -m pip install -r requirements.txt
#
import board
import adafruit_dht

# from time import sleep             # lets us have a delay
import sys
import json
import logging
import random
import time
import threading        # Is this needed or causing an issue?
import re
import datetime as dt
from collections import defaultdict

from paho.mqtt import client as mqtt_client
from configparser import ConfigParser

###############################################################################
# Set up the config options.
config = ConfigParser(delimiters=('=', ))
config.read('config.ini')
###############################################################################

BROKER = config['mqtt'].get('broker', 'homeassistant.local')
PORT = int(config['mqtt'].get('port', '1883'))
# generate client ID with pub prefix randomly
CLIENT_ID = f'python-mqtt-tcp-pub-sub-{random.randint(0, 1000)}'
USERNAME = config['mqtt'].get('username', 'CONFIG_ME')
PASSWORD = config['mqtt'].get('password', 'CONFIG_ME')

FIRST_RECONNECT_DELAY = 1
RECONNECT_RATE = 2
MAX_RECONNECT_COUNT = 12
MAX_RECONNECT_DELAY = int(config['mqtt'].get('timeout', '60'))

all_devices = defaultdict(list)
devices = json.loads(config.get("homeassistant","device_names"))
for device in devices:
    TOPIC_BASE = config['homeassistant'].get('topic_base', 'default/homeassistant/sensor')  \
        + '/dhtxx/' + device + '/'
    TOPIC_BASE_T = config['homeassistant'].get('topic_base', 'default/homeassistant/sensor')  \
        + '/dhtxx/' + device + 'T/'
    TOPIC_BASE_H = config['homeassistant'].get('topic_base', 'default/homeassistant/sensor')  \
        + '/dhtxx/' + device + 'H/'

    # This needs to support a T and H config option but with only one State channel.
    devices_config = {
        "topic_config_t": TOPIC_BASE_T + config['mqtt'].get('topic_config', 'config'),
        "topic_config_h": TOPIC_BASE_H + config['mqtt'].get('topic_config', 'config'),
        "topic_set": TOPIC_BASE + config['mqtt'].get('topic_set', 'set'),
        "topic_state": TOPIC_BASE + config['mqtt'].get('topic_state', 'state'),
        "topic_availability": TOPIC_BASE + config['mqtt'].get('topic_availability', 'availability'),
        "pin": "D4",
        "type": "DHT11"
    }
    all_devices[device].append(devices_config)

logging.basicConfig(format='%(asctime)s - %(levelname)s: %(message)s',
                    level=logging.DEBUG)

logging.info('===================================================================')
logging.info("Starting....")

# =============================================================================

# Create/Update device and set the temperature sensor.
ENVIRONMENT_T_PAYLOAD = {
  "device_class":"temperature",
  "name": "Temperature",
  "unique_id":"envtemp01ae",
  "state_topic":"",
  "unit_of_measurement":"°C",
  "value_template":"{{value_json.temperature}}",
  "optimistic": "false",
  "qos": "0",
  "retain": "true",
  "device":{
    "identifiers":["env01_01ae"],
    "name":"Sensor",
    "manufacturer": "Example sensors Ltd.",
    "model": "Example Sensor",
    "model_id": "DHT-XX",
    "hw_version": "Linux-0.01a",
    "sw_version": "2026.4.0",
    "configuration_url": "https://github.com/AnthonyWrather/ha-linux-mqtt-dhtxx"
  }
}

# And add the humidity sensor.
ENVIRONMENT_H_PAYLOAD = {
    "device_class":"humidity",
    "name": "Humidity",
    "unique_id":"envhum01ae",
    "state_topic":"",
    "unit_of_measurement":"%",
    "value_template":"{{value_json.humidity}}",
    "device":{
      "identifiers":["env01_01ae"]
  }
}

###############################################################################

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0 and client.is_connected():
        logging.info("Connected to MQTT Broker!")
    else:
        logging.info(f'Failed to connect, return code {rc}')


def on_disconnect(client, userdata, flags, rc, properties):
    logging.info("Disconnected with result code: %s", rc)
    reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
    while reconnect_count < MAX_RECONNECT_COUNT:
        logging.info("Reconnecting MQTT in %d seconds...", reconnect_delay)
        time.sleep(reconnect_delay)

        try:
            client.reconnect()
            logging.info("Reconnected successfully!")
            # If there are any scenarios where I need to resubscribe here is the place to do it.
            return
        except Exception as err:
            logging.error("%s. Reconnect failed. Retrying...", err)

        reconnect_delay *= RECONNECT_RATE
        reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
        reconnect_count += 1

    logging.info("Reconnect failed after %s attempts. Exiting...", reconnect_count)


def on_message(client, userdata, msg):
    logging.info('==================================================================')
    logging.info(f'Message `{msg.payload.decode()}` from `{msg.topic}` topic')
    # now its regex time...
    pattern = r"(?<=/)[^/\n]+(?=/[^/\n]*$)"
    device = (re.search(pattern, msg.topic)).group(0)
    logging.info(f"Using device {device}")


def connect_mqtt():
    connect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
    while connect_count < MAX_RECONNECT_COUNT:
        logging.info("Connecting to MQTT in %d seconds...", reconnect_delay)
        time.sleep(reconnect_delay)
        try:
            client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2, CLIENT_ID)
            client.username_pw_set(USERNAME, PASSWORD)
            client.on_connect = on_connect
            client.on_message = on_message
            error = client.connect(BROKER, PORT, keepalive=120)
            client.on_disconnect = on_disconnect
            logging.info(f"connect_mqtt: {client}")
            return client
        except Exception as err:
            logging.error("%s. Connection failed...", err)
        except:
            # this catches ALL other exceptions including errors.
            # You won't get any error messages for debugging
            # so only use it once your code is working
            logging.info( "A general connection exception occurred!" )
        reconnect_delay *= RECONNECT_RATE
        reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
        connect_count += 1


def publish(client, topic, temperature_c, humidity):
    payload = {
        "temperature":temperature_c,
        "humidity":humidity
    }
    msg = json.dumps(payload)
    if not client.is_connected():
        logging.error("publish: MQTT client is not connected!")
        time.sleep(1)
    result = client.publish(topic, msg)
    status = result[0]
    if status == 0:
        logging.info(f'Sent `{msg}` to topic `{topic}`')
    else:
        logging.info(f'Failed to send message to topic {topic}')
    time.sleep(1)


def get_sensor_data(this_pin, this_type, temperature_c, humidity):
    # Connect to the server and get the data.
    temperature_c = 0.0
    humidity = 0.0

    logging.info(f"Connect to sensor {this_type} on pin {this_pin}")
    loop = 1
    count = 0
    status: bool = False
    # Let the sensor settle.
    time.sleep(2.0)

    temperature_c = 0.0
    humidity = 0.0
    while loop and loop < 6:
        try:
            # Get the temperature and humidity from the sensor.
            if this_type.find("11") != -1:
                logging.info("Trying DHT-11 sensor.")
                sensor = adafruit_dht.DHT11(pin=getattr(board, this_pin))
            elif this_type.find("22") != -1:
                logging.info("Trying DHT-22 sensor.")
                sensor = adafruit_dht.DHT22(pin=getattr(board, this_pin))
            else:
                logging.info(f"Unknown sensor type: {this_type}")
                return temperature_c, humidity
            temperature_c = sensor.temperature
            temperature_c += 1
            humidity = sensor.humidity
            logging.info("    Got Temp: {0:0.1f}ºC, Humidity: {1:0.1f}% from the sensor.".format(temperature_c, humidity))
            sensor.exit()
            status = True
            loop = 0

        except RuntimeError as error:
            # Errors happen fairly often, DHT's are hard to read, just keep going
            logging.info(f"RuntimeError: {error.args[0]}")
            if error.args[0].find("DHT sensor not found") != -1:
                loop = 0
            else:
                loop = 1
            sensor.exit()
            time.sleep(1.0)
            continue
        except Exception as error:
            logging.info(f"Exception: {error.args[0]}")
            sensor.exit()
            time.sleep(1.0)
            loop += 1
            # raise error
            continue

    logging.info("Disconnected from the sensor.")
    return status, temperature_c, humidity


def send_to_mqtt(topic, temperature_c, humidity):
    client = connect_mqtt()
    client.loop_start()
    time.sleep(1)
    if client.is_connected():
        publish(client, topic, temperature_c, humidity)
    client.loop_stop()
    logging.info("Disconnected from MQTT")
    return

def configure_mqtt_devices():
    # Need to send the config once on startup.
    logging.info('=========================== START CONFIG ==========================')
    logging.info("Connecting to MQTT")
    client = connect_mqtt()
    client.loop_start()
    time.sleep(1)
    if client.is_connected():
        logging.info("Sending config to MQTT")
        for this_one in all_devices:
            # Publish the Device config for auto discovery.
            logging.info(f"Processing device {this_one}")
            # Set the Temperature payload.
            logging.info(f"State topic: {all_devices[this_one][0]['topic_state']}")
            ENVIRONMENT_T_PAYLOAD["name"] = this_one + "_Temperature"
            ENVIRONMENT_T_PAYLOAD["unique_id"] = this_one + "_tmp01ae"
            ENVIRONMENT_T_PAYLOAD["state_topic"] = all_devices[this_one][0]['topic_state']
            ENVIRONMENT_T_PAYLOAD["device"]["identifiers"][0] = this_one + "_dev01ae"            
            ENVIRONMENT_T_PAYLOAD["device"]["name"] = "Sensor " + this_one            
            msg = json.dumps(ENVIRONMENT_T_PAYLOAD)

            result = client.publish(all_devices[this_one][0]['topic_config_t'], msg)
            status = result[0]
            if status != 0:
                logging.info(f'Failed to send SENSOR config to topic {all_devices[this_one][0]['topic_config_t']}')
            else:
                logging.info(f'Successfully sent SENSOR config to topic {all_devices[this_one][0]['topic_config_t']}')

            # Set the Humidity payload.
            logging.info(f"Processing additional device {this_one}")
            logging.info(f"State topic: {all_devices[this_one][0]['topic_state']}")
            ENVIRONMENT_H_PAYLOAD["name"] = this_one + "_Humidity"
            ENVIRONMENT_H_PAYLOAD["unique_id"] = this_one + "_hum01ae"
            ENVIRONMENT_H_PAYLOAD["state_topic"] = all_devices[this_one][0]['topic_state']
            ENVIRONMENT_H_PAYLOAD["device"]["identifiers"][0] = this_one + "_dev01ae"
            ENVIRONMENT_H_PAYLOAD["device"]["name"] = "Sensor " + this_one            
            msg = json.dumps(ENVIRONMENT_H_PAYLOAD)

            result = client.publish(all_devices[this_one][0]['topic_config_h'], msg)
            status = result[0]
            if status != 0:
                logging.info(f'Failed to send SENSOR config to topic {all_devices[this_one][0]['topic_config_h']}')
            else:
                logging.info(f'Successfully sent SENSOR config to topic {all_devices[this_one][0]['topic_config_h']}')

        
    client.loop_stop()
    logging.info("Disconnected from MQTT")
    logging.info('=========================== END CONFIG ==========================')
    return

###############################################################################
def run():
    try:
        # Main loop goes here.
        logging.basicConfig(format='%(asctime)s - %(levelname)s: %(message)s',
                            level=logging.DEBUG)

        # Setup the devices.
        configure_mqtt_devices()

        # TODO: Sort out the loop to avoid threading issues.
        loop_forever = 1
        while loop_forever:
            logging.info("")
            logging.info("==================================================================")
            start_time = dt.datetime.now()
            logging.info(start_time.strftime("%Y-%m-%d %H:%M:%S"))
            for device, config in all_devices.items():
                logging.info('==================================================================')
                this_pin = config[0]["pin"]
                this_type = config[0]["type"]
                topic = config[0]["topic_state"]
                temperature_c = 0
                humidity = 0
                status, temperature_c, humidity = get_sensor_data(this_pin, this_type, temperature_c, humidity)
                if status == True:
                    send_to_mqtt(topic, temperature_c, humidity)
                else:
                    logging.info(f"ERROR: Failed to read sensor {this_type} on pin {this_pin}")

            logging.info("==================================================================")
            time_now = dt.datetime.now()
            result = time_now - start_time
            sleep_time = 30 - result.seconds
            if sleep_time <= 0:
                sleep_time = 0
            else:
                sleep_time -= 1
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        # here you put any code you want to run before the program
        # exits when you press CTRL+C
        logging.info( "Keyboard interrupt\n" )


if __name__ == '__main__':
    # Get the pins
    pins = json.loads(config.get("sensor","pins"))
    types = json.loads(config.get("sensor","types"))
    count = 0
    # Set the pins in the main struct
    for this_one in all_devices:
        all_devices[this_one][0]['pin'] = pins[count]
        all_devices[this_one][0]['type'] = types[count]
        count += 1
    run()
