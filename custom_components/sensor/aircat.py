#!/usr/bin/env python
#encoding:utf8

'''
YAML Example:
sensors:
  - platform: aircat
    #name: AirCat
    username: 139********
    password: ********
    #sensors: 1
    #scan_interval: 60
    #monitored_conditions: [pm25,hcho,temperature,humidity]
'''

import logging, os
import requests, json

# Const
TOKEN_PATH = '.aircat.token'
AUTH_CODE = 'feixun.SH_1'
USER_AGENT = 'zhilian/5.7.0 (iPhone; iOS 10.0.2; Scale/3.00)'
#AUTH_CODE = 'feixun*123.SH_7316142'
#USER_AGENT = 'ICode7Phone/3.0.0 (iPhone; iOS 11.2.2; Scale/2.00)'
LOGGER = logging.getLogger(__name__)

# Get homeassistant configuration path to store token
TOKEN_PATH = os.path.split(os.path.split(os.path.split(os.path.realpath(__file__))[0])[0])[0] + '/' + TOKEN_PATH

class AirCatData():
    def __init__(self, username, password):
        self._devs = None
        self._username = username
        self._password = password
        try:
            with open(TOKEN_PATH) as f:
                self._token = f.read()
                LOGGER.debug('load: path=%s, token=%s', TOKEN_PATH, self._token)
        except:
            self._token = None
            pass

    def update(self):
        data = {}
        try:
            result = self.fetch()
            if ('error' in result) and (result['error'] != '0'):
                LOGGER.debug('resetToken: error=%s', result['error'])
                self._token = None
                result = self.fetch()
            self._devs = result['data']['devs']
            LOGGER.debug('getIndexData: devs=%s, len=%d', self._devs, len(self._devs))


            if len(self._devs) > 0:
                data['temperature'] = self._devs[0]['catDev']['temperature']
                data['humidity'] = self._devs[0]['catDev']['humidity']
                data['pm25'] = self._devs[0]['catDev']['pm25']
                data['hcho'] = self._devs[0]['catDev']['hcho']
                if self._devs[0]['cleanerDev']:
                    data['mode'] = self._devs[0]['cleanerDev']['mode']
                    data['speed'] = self._devs[0]['cleanerDev']['speed']
                    data['online'] = self._devs[0]['cleanerDev']['online']
                    data['filterstatus'] = self._devs[0]['cleanerDev']['filterStatus']
                    data['childlock'] = self._devs[0]['cleanerDev']['childLock']
                    data['deviceid'] = self._devs[0]['cleanerDev']['deviceId']

            if len(self._devs) > 1:
                data['temperature_1'] = self._devs[1]['catDev']['temperature']
                data['humidity_1'] = self._devs[1]['catDev']['humidity']
                data['pm25_1'] = self._devs[1]['catDev']['pm25']
                data['hcho_1'] = self._devs[1]['catDev']['hcho']
                if self._devs[1]['cleanerDev']:
                    data['mode_1'] = self._devs[1]['cleanerDev']['mode']
                    data['speed_1'] = self._devs[1]['cleanerDev']['speed']
                    data['online_1'] = self._devs[1]['cleanerDev']['online']
                    data['filterstatus_1'] = self._devs[1]['cleanerDev']['filterStatus']
                    data['childlock_1'] = self._devs[1]['cleanerDev']['childLock']
                    data['deviceid_1'] = self._devs[1]['cleanerDev']['deviceId']

            if len(self._devs) > 2:
                data['temperature_2'] = self._devs[2]['catDev']['temperature']
                data['humidity_2'] = self._devs[2]['catDev']['humidity']
                data['pm25_2'] = self._devs[2]['catDev']['pm25']
                data['hcho_2'] = self._devs[2]['catDev']['hcho']
                if self._devs[2]['cleanerDev']:
                    data['mode_2'] = self._devs[2]['cleanerDev']['mode']
                    data['speed_2'] = self._devs[2]['cleanerDev']['speed']
                    data['online_2'] = self._devs[2]['cleanerDev']['online']
                    data['filterstatus_2'] = self._devs[2]['cleanerDev']['filterStatus']
                    data['childlock_2'] = self._devs[2]['cleanerDev']['childLock']
                    data['deviceid_2'] = self._devs[2]['cleanerDev']['deviceId']

            if len(self._devs) > 3:
                data['temperature_3'] = self._devs[3]['catDev']['temperature']
                data['humidity_3'] = self._devs[3]['catDev']['humidity']
                data['pm25_3'] = self._devs[3]['catDev']['pm25']
                data['hcho_3'] = self._devs[3]['catDev']['hcho']
                if self._devs[3]['cleanerDev']:
                    data['mode_3'] = self._devs[3]['cleanerDev']['mode']
                    data['speed_3'] = self._devs[3]['cleanerDev']['speed']
                    data['online_3'] = self._devs[3]['cleanerDev']['online']
                    data['filterstatus_3'] = self._devs[3]['cleanerDev']['filterStatus']
                    data['childlock_3'] = self._devs[3]['cleanerDev']['childLock']
                    data['deviceid_3'] = self._devs[3]['cleanerDev']['deviceId']

            return data
        except:
            import traceback
            LOGGER.error('exception: %s', traceback.format_exc())

    def login(self):
        import hashlib
        md5 = hashlib.md5()
        md5.update(self._password.encode("utf8"))
        headers = {'User-Agent': USER_AGENT}
        data = {'authorizationcode': AUTH_CODE, 'password': md5.hexdigest().upper(), 'phonenumber': self._username}
        result = requests.post('https://accountsym.phicomm.com/v1/login', headers=headers, data=data).json()
        LOGGER.debug('getToken: result=%s', result)
        if 'access_token' in result:
            self._token = result['access_token']
            with open(TOKEN_PATH, 'w') as f:
                f.write(self._token)
            return result
        else:
            LOGGER.error('phicommcleaner login error:' + result['msg'])
            return None

    def fetch(self):
        if self._token == None:
            if self.login() == None:
                return None
        headers = {'User-Agent': USER_AGENT, 'Authorization': self._token}
        return requests.get('https://aircleaner.phicomm.com/aircleaner/getIndexData', headers=headers).json()


if __name__ == '__main__':

    import sys
    LOGGER.addHandler(logging.StreamHandler(sys.stderr))
    LOGGER.setLevel(logging.DEBUG)
    if len(sys.argv) != 3:
        print('Usage: %s <username> <password>' % sys.argv[0])
        exit(0)
    aircatData = AirCatData(sys.argv[1], sys.argv[2])
    data = aircatData.update()
    print(data)
    exit(0)

# Import homeassistant
from homeassistant.helpers.entity import Entity
from homeassistant.const import (CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_SENSORS, CONF_MONITORED_CONDITIONS)
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from datetime import timedelta
SCAN_INTERVAL = timedelta(seconds=60)

SENSOR_TYPES = {
    'pm25': ('pm25', 'μg/m³', 'blur'),
    'hcho': ('hcho', 'mg/m³', 'biohazard'),
    'temperature': ('temperature', '°C', 'thermometer'),
    'humidity': ('humidity', '%', 'water-percent'),
    'mode': ('mode', '', 'blur'),
    'speed': ('speed', '', 'fan'),
    'online': ('online', '', 'fan'),
    'filterstatus': ('filterStatus', '%', 'fan'),
    'childlock': ('childLock', '', 'fan'),
    'deviceid': ('deviceid', '', 'fan'),
    'pm25_1': ('pm25_1', 'μg/m³', 'blur'),
    'hcho_1': ('hcho_1', 'mg/m³', 'biohazard'),
    'temperature_1': ('temperature_1', '°C', 'thermometer'),
    'humidity_1': ('humidity_1', '%', 'water-percent'),
    'mode_1': ('mode_1', '', 'blur'),
    'speed_1': ('speed_1', '', 'fan'),
    'online_1': ('online_1', '', 'fan'),
    'filterstatus_1': ('filterStatus_1', '%', 'fan'),
    'childlock_1': ('childLock_1', '', 'fan'),
    'deviceid_1': ('deviceid_1', '', 'fan'),
    'pm25_2': ('pm25_2', 'μg/m³', 'blur'),
    'hcho_2': ('hcho_2', 'mg/m³', 'biohazard'),
    'temperature_2': ('temperature_2', '°C', 'thermometer'),
    'humidity_2': ('humidity_2', '%', 'water-percent'),
    'mode_2': ('mode_2', '', 'blur'),
    'speed_2': ('speed_2', '', 'fan'),
    'online_2': ('online_2', '', 'fan'),
    'filterstatus_2': ('filterStatus_2', '%', 'fan'),
    'childlock_2': ('childLock_2', '', 'fan'),
    'deviceid_2': ('deviceid_2', '', 'fan'),
    'pm25_3': ('pm25_3', 'μg/m³', 'blur'),
    'hcho_3': ('hcho_3', 'mg/m³', 'biohazard'),
    'temperature_3': ('temperature_3', '°C', 'thermometer'),
    'humidity_3': ('humidity_3', '%', 'water-percent'),
    'mode_3': ('mode_3', '', 'blur'),
    'speed_3': ('speed_3', '', 'fan'),
    'online_3': ('online_3', '', 'fan'),
    'filterstatus_3': ('filterStatus_3', '%', 'fan'),
    'childlock_3': ('childLock_3', '', 'fan'),
    'deviceid_3': ('deviceid_3', '', 'fan')
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default='AirCat'): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SENSORS, default=1): cv.positive_int,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=['pm25', 'hcho', 'temperature', 'humidity']): vol.All(cv.ensure_list, vol.Length(min=1), [vol.In(SENSOR_TYPES)]),
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    sensors = config.get(CONF_SENSORS)
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]

    LOGGER.info('setup_platform: name=%s, username=%s, password=%s, sensors=%d', name, username, password, sensors)

    AirCatSensor._airCatData = AirCatData(username, password)
    AirCatSensor._update_index = 0
    AirCatSensor._conditions_count = len(monitored_conditions)

    i = 0
    devices = []
    while i < sensors:
        for type in monitored_conditions:
            devices.append(AirCatSensor(name, i, type))
        i += 1
    add_devices(devices, True)

class AirCatSensor(Entity):

    def __init__(self, name, index, type):
        tname,unit,icon = SENSOR_TYPES[type]
        if index:
            name += str(index + 1)
        self._name = name + ' ' + tname
        self._index = index
        self._type = type
        self._unit = unit
        self._icon = 'mdi:' + icon

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return self._icon

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def available(self):
        attributes = self.attributes
        return attributes #and attributes['online'] == '1'

    @property
    def state(self):
        attributes = self.attributes
        return attributes[self._type] if attributes else None

    @property
    def state_attributes(self):
        return self.attributes if self._type == 'pm25' else None

    @property
    def attributes(self):
        if AirCatSensor._airCatData._devs and self._index < len(AirCatSensor._airCatData._devs):
            return AirCatSensor._data
        return None

    def update(self):
        LOGGER.debug('update: name=%s', self._name)
        if AirCatSensor._update_index % AirCatSensor._conditions_count == 0:
            AirCatSensor._data = AirCatSensor._airCatData.update()
        AirCatSensor._update_index += 1
        LOGGER.info('End update: name=%s', self._name)