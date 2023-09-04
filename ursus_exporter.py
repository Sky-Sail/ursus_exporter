#! /usr/bin/env python3

from w1thermsensor import W1ThermSensor

from prometheus_client import start_http_server, Summary
from prometheus_client import Gauge

import yaml
from yaml.loader import SafeLoader

import logging
import time
import argparse

import os
import stat

sensors_friendly_names = {}
                
temp_sensors = Gauge('ursus_temperature', 'Temperature same parts engine in Celsius degrees', ["sensor_id", "friendly_name"])

def process_request(t):
  for sensor in W1ThermSensor.get_available_sensors():
    temerature = sensor.get_temperature()
    
    if sensor.id in sensors_friendly_names:
      friendly_name = sensors_friendly_names[sensor.id]
    else:
      logging.debug('sensor {} hasnt friendly name :('.format( sensor.id ))
      friendly_name = ''

    temp_sensors.labels(
      sensor_id=sensor.id, 
      friendly_name=friendly_name
    ).set( temerature )
    
    logging.debug('Sensor {} return {}'.format(sensor.id, temerature))
    time.sleep(t)


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--config.file', type=str, required=False, dest='config_file', default='./config.yaml', help='Path to config file (default is "./config.yaml")')
  parser.add_argument('--debug', action=argparse.BooleanOptionalAction, dest='is_debug', help='use this option to enable debug log')
  args = parser.parse_args()

  listen_port = 0
  scrape_interval = -1

  logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(levelname)s: %(message)s')
  
  # pare config
  with open(args.config_file) as f:
    data        = yaml.load(f, Loader=SafeLoader)

    # configure logging
    if args.is_debug:
      logging.getLogger().setLevel(logging.DEBUG)
      logging.info('Set debug log level')
    else:
      try:
        logging.getLogger().setLevel(data['global']['log_level'].upper())
      except:
        pass
      


    # listen port
    try:
      listen_port = data['global']['listen_port']
      logging.info('Use {} TCP port.'.format(listen_port))
    except:
      listen_port = 9271
    
    # scrape_interval
    try:
      tmp_scrape_interval = data['global']['scrape_interval']
      logging.debug('parse scrape_interval option: {}'.format(tmp_scrape_interval) )

      suffix  = tmp_scrape_interval[-1].lower()
      value   = int(tmp_scrape_interval[:-1])
    
      logging.debug('scrape_interval suffix: {}, value: {}'.format(suffix, value) )

      if suffix == 's': scrape_interval = value
      if suffix == 'm': scrape_interval = value * 60 
      if suffix == 'h': scrape_interval = value * 60 * 60
    except:
      scrape_interval = 60

    logging.info('set scrape_interval to: {}s'.format(scrape_interval))
        
    # temp sensors
    for sensor in data['sensors']:
      sensors_friendly_names[ sensor['sensor_id'] ] = sensor[ 'name' ]
      logging.info('sensor: {} has friendly_names: {}'.format(sensor['sensor_id'], sensor['name']))

    
  # Start up the server to expose the metrics.
  logging.info('Start http server')

  start_http_server( listen_port )

  while True:
    process_request( scrape_interval )
