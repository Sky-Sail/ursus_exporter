""" ursus engine prometheus exporter """
#! /usr/bin/env python3

import logging
import time
import argparse

import os
import sys

from w1thermsensor import W1ThermSensor

from prometheus_client import start_http_server
from prometheus_client import Gauge

import yaml
from yaml.loader import SafeLoader

sensors_friendly_names = {}

temp_sensors = Gauge(
        'ursus_temperature',
        'Temperature same parts engine in Celsius degrees',
        ["sensor_id", "friendly_name"]
)

def process_request(scrape_interval):
    """ function to parsing sensors """
    for sensor in W1ThermSensor.get_available_sensors():
        temerature = sensor.get_temperature()

        if sensor.id in sensors_friendly_names:
            friendly_name = sensors_friendly_names[sensor.id]
        else:
            logging.debug('sensor %s hasnt friendly name :(', sensor.id )
            friendly_name = ''

        temp_sensors.labels(
            sensor_id=sensor.id,
            friendly_name=friendly_name
        ).set( temerature )

        logging.debug('Sensor %s return %s', sensor.id, temerature)
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

        # temp sensors
        for config_sensor in data['sensors']:
            sensors_friendly_names[ config_sensor['sensor_id'] ] = config_sensor[ 'name' ]
            logging.info(
                    'sensor: %s has friendly_names: %s',
                    config_sensor['sensor_id'], config_sensor['name']
                    )


    # Start up the server to expose the metrics.
    logging.info('Start http server')

    start_http_server( LISTEN_PORT )

    while True:
        process_request( SCRAPE_INTERVAL )
