#!/usr/bin/env python
#encoding:utf8

'''
API Web: http://www.caiyunapp.com/map
API Ref: http://wiki.swarma.net/index.php/%E5%BD%A9%E4%BA%91%E5%A4%A9%E6%B0%94API/v2
YAML Example:
sensor:
  - platform: caiyun
    #name: CaiYun
    #latitude: 30.000
    #longitude: 120.000
    #scan_interval: 1200
    monitored_conditions: # Optional
      - weather
      - temperature
      - humidity
      - cloud_rate
      - pressure
      - wind_direction
      - wind_speed
      - local_precipitation
      - nearest_precipitation
      - precipitation_distance
      - aqi
      - pm25
      - pm10
      - o3
      - co
      - no2
      - so2
'''

import logging, time
import requests, json

# Const
USER_AGENT = 'ColorfulCloudsPro/3.2.0 (iPhone; iOS 11.2.2; Scale/2.00)'
LOGGER = logging.getLogger(__name__)
WEATHER_ICONS = {
    'CLEAR_DAY': ('晴天','sunny'),
    'CLEAR_NIGHT': ('晴夜','night'),
    'PARTLY_CLOUDY_DAY': ('多云','partlycloudy'),
    'PARTLY_CLOUDY_NIGHT': ('多云','windy-variant'),
    'CLOUDY': ('阴','cloudy'),
    'RAIN': ('雨','rainy'),
    'SNOW': ('雪','snowy'),
    'WIND': ('风','windy'),
    'FOG': ('雾','fog'),
    'HAZE': ('霾','hail'),
    'SLEET': ('冻雨','snowy-rainy')
}

#
def getWeatherData(longitude, latitude, metricv2=False):
    data = {}
    try:
        headers = {'User-Agent': USER_AGENT}
        url = 'http://api.caiyunapp.com/v2/UR8ASaplvIwavDfR/' + longitude + ',' + latitude + '/realtime.json'
        if metricv2:
            url += '?unit=metric:v2'
        #LOGGER.debug('getWeatherData: %s', url)
        response = requests.get(url, headers=headers).json()
        #LOGGER.info('gotWeatherData: %s', response)
        result = response['result']
        if result['status'] != 'ok':
            raise

        weather,icon = WEATHER_ICONS[result['skycon']]
        data['weather'] = weather
        if icon:
            data['skycon'] = icon

        data['temperature'] = result['temperature']
        data['humidity'] = int(result['humidity'] * 100)

        data['aqi'] = int(result['aqi'])
        data['pm25'] = int(result['pm25'])

        # Optional action
        data['cloud_rate'] = result['cloudrate']
        data['pressure'] = int(result['pres'])
        data['nearest_precipitation'] = result['precipitation']['nearest']['intensity']
        data['precipitation_distance'] = result['precipitation']['nearest']['distance']
        data['local_precipitation'] = result['precipitation']['local']['intensity']
        data['wind_direction'] = result['wind']['direction']
        data['wind_speed'] = result['wind']['speed']
        data['pm10'] = result['pm10']
        data['o3'] = result['o3']
        data['co'] = result['co']
        data['no2'] = result['no2']
        data['so2'] = result['so2']
    except:
        import traceback
        LOGGER.error('exception: %s', traceback.format_exc())
    return data

if __name__ == '__main__':
    # For local call
    import sys
    LOGGER.addHandler(logging.StreamHandler(sys.stderr))
    LOGGER.setLevel(logging.DEBUG)
    print(getWeatherData('120.00', '30.00', True))
    exit(0)

# Import homeassistant
from homeassistant.helpers.entity import Entity
from homeassistant.const import (CONF_NAME, CONF_LONGITUDE, CONF_LATITUDE, CONF_MONITORED_CONDITIONS)
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from datetime import timedelta
SCAN_INTERVAL = timedelta(seconds=1200)

SENSOR_TYPES = {
    'weather': ('Weather', None, 'help-circle-outline'),
    'temperature': ('Temperature', '°C', 'thermometer'),
    'humidity': ('Humidity', '%', 'water-percent'),

    'cloud_rate': ('Cloud Rate', None, 'cloud-outline'),
    'pressure': ('Pressure', 'Pa', 'download'),
    'wind_direction': ('Wind Direction', None, 'weather-windy'),
    'wind_speed': ('Wind Speed', 'm/s', 'weather-windy'),

    'local_precipitation': ('Local Precipitation', None, 'weather-pouring'),
    'nearest_precipitation': ('Nearest Precipitation', None, 'mixcloud'),
    'precipitation_distance': ('Precipitation Distance', None, 'mixcloud'),

    'aqi': ('AQI', None, 'leaf'),
    'pm25': ('PM2.5', 'μg/m³', 'blur'),
    'pm10': ('PM10', 'μg/m³', 'blur-linear'),
    'o3': ('O3', None, 'blur-radial'),
    'co': ('CO', None, 'blur-radial'),
    'no2': ('NO2', None, 'blur-radial'),
    'so2': ('SO2', None, 'blur-radial')
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default='CaiYun'): cv.string,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=['weather', 'temperature', 'humidity', 'pm25']): vol.All(cv.ensure_list, vol.Length(min=1), [vol.In(SENSOR_TYPES)]),
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    name = config.get(CONF_NAME)
    longitude = str(config.get(CONF_LONGITUDE, hass.config.longitude))
    latitude = str(config.get(CONF_LATITUDE, hass.config.latitude))
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    LOGGER.debug('setup_platform: name=%s, longitude=%s, latitude=%s', name, longitude, latitude)

    CaiYunSensor._data = {}
    CaiYunSensor._update_index = 0
    CaiYunSensor._conditions_count = len(monitored_conditions)
    CaiYunSensor._longitude = longitude
    CaiYunSensor._latitude = latitude

    devices = []
    for type in monitored_conditions:
        devices.append(CaiYunSensor(name, type))
    add_devices(devices, True)

class CaiYunSensor(Entity):

    def __init__(self, name, type):
        tname,unit,icon = SENSOR_TYPES[type]
        self._name = name + ' ' + tname
        self._type = type
        self._unit = unit
        self._icon = icon

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        icon = self._icon
        if self._type == 'weather' and 'skycon' in CaiYunSensor._data:
            icon = 'weather-' + CaiYunSensor._data['skycon']
        return 'mdi:' + icon

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def available(self):
        return self._type in CaiYunSensor._data

    @property
    def state(self):
        return CaiYunSensor._data[self._type] if self._type in CaiYunSensor._data else None

    @property
    def state_attributes(self):
        return CaiYunSensor._data if self._type == 'weather' else None

    def update(self):
        #LOGGER.debug('update: name=%s', self._name)
        if CaiYunSensor._update_index % CaiYunSensor._conditions_count == 0:
            CaiYunSensor._data = getWeatherData(CaiYunSensor._longitude, CaiYunSensor._latitude)
        CaiYunSensor._update_index += 1
        #LOGGER.info('End update: name=%s', self._name)
 