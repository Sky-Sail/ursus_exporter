""" ursus engine prometheus exporter """
#! /usr/bin/env python3

import logging
import time
import argparse

import os
import sys
import time

from w1thermsensor import W1ThermSensor
from w1thermsensor.errors import W1ThermSensorError,SensorNotReadyError

from prometheus_client import start_http_server
from prometheus_client import Gauge

import yaml
from yaml.loader import SafeLoader

import board
from adafruit_ina219 import ADCResolution, BusVoltageRange, INA219

temp_sensors_friendly_names = {}
voltage_bus_names = {}
voltage_bus = []

temp_sensors = Gauge(
        'ursus_temperature',
        'Temperature same parts engine [ in Celsius degrees ]',
        ["sensor_id", "friendly_name"]
)

voltage_sensor = Gauge(
        'ursus_voltage',
        'voltage on one of tree sensor [ in volts ]',
        ["voltage_bus", "friendly_name"]
)

def process_request(scrape_interval):
    """ function to parsing sensors """
    
    # try read temp sensors
    try:
        for sensor in W1ThermSensor.get_available_sensors():
            temerature = sensor.get_temperature()

            if sensor.id in temp_sensors_friendly_names:
                friendly_name = temp_sensors_friendly_names[sensor.id]
            else:
                logging.debug('sensor %s hasnt friendly name :(', sensor.id )
                friendly_name = ''

            temp_sensors.labels(
                sensor_id=sensor.id,
                friendly_name=friendly_name
            ).set( temerature )

            logging.debug('Sensor %s return %s', sensor.id, temerature)
    except SensorNotReadyError:
        logging.warning('Failed to read sensor state. Sensor not ready yet.')
    except W1ThermSensorError:
        logging.warning('Fail to read sensor strate.')


    # try read voltage sensors
    for idx, sensor in enumerate(voltage_bus):
        name = voltage_bus_names[ idx ]
        if name == '':
            name = 'voltage_bus_%i' % idx

        voltage = sensor.bus_voltage
        voltage_sensor.labels(
            voltage_bus='voltage_bus_%i' % idx,
            friendly_name=name
        ).set( voltage )
        logging.info('voltage on %s sensor', name)


    time.sleep(scrape_interval)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config.file', type=str, required=False,
            dest='config_file', default='./config.yaml',
            help='Path to config file (default is "./config.yaml")'
    )
    parser.add_argument('--debug', action="store_true",
            dest='is_debug', help='use this option to enable debug log'
    )
    args = parser.parse_args()

    LISTEN_PORT = 0
    SCRAPE_INTERVAL = -1

    logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(levelname)s: %(message)s')


    i2c_bus = board.I2C()

    voltage_bus.append( INA219(i2c_bus,addr=0x40) )
    voltage_bus.append( INA219(i2c_bus,addr=0x41) )
    voltage_bus.append( INA219(i2c_bus,addr=0x42) )

    for bus in voltage_bus:
        bus.bus_voltage_range = BusVoltageRange.RANGE_16V

    # pare config
    with open(args.config_file, encoding="utf-8") as f:
        # check file permission. Correct is
        if oct(os.stat(args.config_file).st_mode) != oct(0o100600):
            logging.critical('Config file permission is wrong. Correct is 0600 (-rw-------).')
            sys.exit(1)

        # load yaml config
        data = yaml.load(f, Loader=SafeLoader)

        # configure logging
        if args.is_debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logging.info('Set debug log level')
        else:
            if 'global' in data:
                logging.getLogger().setLevel(data['global']['log_level'].upper())

        # listen port
        try:
            LISTEN_PORT = data['global']['listen_port']
            logging.info('Use %s TCP port.', LISTEN_PORT )
        except KeyError:
            LISTEN_PORT = 9271

        # scrape_interval
        try:
            tmp_scrape_interval = data['global']['scrape_interval']
            logging.debug('parse scrape_interval option: %s', tmp_scrape_interval )

            suffix     = tmp_scrape_interval[-1].lower()
            value      = int(tmp_scrape_interval[:-1])

            logging.debug('scrape_interval suffix: %s, value: %s', suffix, value )

            if suffix == 's':
                SCRAPE_INTERVAL = value
            if suffix == 'm':
                SCRAPE_INTERVAL = value * 60
            if suffix == 'h':
                SCRAPE_INTERVAL = value * 60 * 60

        except KeyError:
            SCRAPE_INTERVAL = 60

        logging.info('set scrape_interval to: %ss', SCRAPE_INTERVAL )

        # configure sensors
        if 'sensors' in data:
            # temp sensors
            if 'temperature' in data['sensors']:
                for config_sensor in data['sensors']['temperature']:
                    temp_sensors_friendly_names[ config_sensor['sensor_id'] ] = config_sensor[ 'name' ]
                    logging.info(
                            'temperature sensor: %s has friendly_names: %s',
                            config_sensor['sensor_id'], config_sensor['name']
                        )

            if 'voltage' in data['sensors']:
                voltage_bus_names[0] = voltage_bus_names[1] = voltage_bus_names[2] = ''

                for config_sensor in data['sensors']['voltage']:
                    if config_sensor['bus'] < 0 or config_sensor['bus'] > 2:
                        logging.critical('give incorrect voltage bus number (bus name: %s)' % config_sensor['name'] )
                        sys.exit(1)
                    
                    name = 'voltage_bus_%s' % config_sensor['bus']
                    if 'name' in config_sensor:
                        name = config_sensor['name']

                    voltage_bus_names[ int(config_sensor['bus']) ] =  name
                    logging.info(
                            'voltage sensor: on %s bus has friendly_names: %s',
                            config_sensor['bus'], name
                        )



    # Start up the server to expose the metrics.
    logging.info('Start http server')

    start_http_server( LISTEN_PORT )

    while True:
       process_request( SCRAPE_INTERVAL )
