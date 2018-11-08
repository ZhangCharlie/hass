"""
PhicommA1空气净化器插件
@author:  hzcoolwind
@created: 2018-05-11
@updated: 2018-05-11
@version: 0.01
@yaml example:
fan:
  - platform: phicomm
    name: phicomma1
    username: 139xxxxxxxx
    password: xxxxxxxx
    deviceid: xx-xx:xx:xx:xx:xx:xx
"""
import logging, os

import requests
import time
import datetime

from homeassistant.components.fan import (FanEntity)
from homeassistant.util import Throttle


# Const
TOKEN_PATH = '.aircat.token'
AUTH_CODE = 'feixun.SH_1'
USER_AGENT = 'zhilian/5.7.0 (iPhone; iOS 10.0.2; Scale/3.00)'

# Get homeassistant configuration path to store token
TOKEN_PATH = os.path.split(os.path.split(os.path.split(os.path.realpath(__file__))[0])[0])[0] + '/' + TOKEN_PATH

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(seconds=15)

DEFAULT_NAME = 'phicomm'

ATTR_PM25 = 'pm25'
ATTR_HCHO = 'hcho'
ATTR_FILTER_REMAIN = 'filter_status'
ATTR_CHILDREN_LOCK = 'children_lock'

SPEED_OFF = '关闭'
SPEED_AUTO = '自动'
SPEED_SILENT = '静音'
SPEED_HAND = '手动'
SPEED_EFFIECT = '高效'


SPEED_MAP = {
    '0': SPEED_OFF,
    '3': SPEED_AUTO,
    '4': SPEED_SILENT,
    '2': SPEED_HAND,
    '5': SPEED_EFFIECT
}
CONTROL_MAP = {
    SPEED_AUTO: [3, 30],
    SPEED_SILENT: [4, 30],
    SPEED_HAND: [2, 60],
    SPEED_EFFIECT: [5, 85]
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    name = config.get('name') or DEFAULT_NAME
    password = config.get('password')
    user_id = config.get('username')
    device_id = config.get('deviceid')

    _LOGGER.debug('============= phicommcleaner setup -> name: %s =============', name)
    add_devices([
        PhicommFan(hass, name, password, user_id, device_id)
    ])


class PhicommController(object):
    lock = None

    def __init__(self, hass, password, user_id, device_id) -> None:
        self._username = user_id
        self._password = password
        self._deviceid = device_id
        try:
            with open(TOKEN_PATH) as f:
                self._token = f.read()
                _LOGGER.debug('load: path=%s, token=%s', TOKEN_PATH, self._token)
        except:
            self._token = None
            pass

    def login(self):
        import hashlib
        md5 = hashlib.md5()
        md5.update(self._password.encode("utf8"))
        headers = {'User-Agent': USER_AGENT}
        data = {'authorizationcode': AUTH_CODE, 'password': md5.hexdigest().upper(), 'phonenumber': self._username}
        _LOGGER.warning('post dataa [%s]', data)
        result = requests.post('https://accountsym.phicomm.com/v1/login', headers=headers, data=data).json()
        _LOGGER.warning('getToken: result=%s', result)
        if 'access_token' in result:
            self._token = result['access_token']
            with open(TOKEN_PATH, 'w') as f:
                f.write(self._token)
            return result
        else:
            _LOGGER.error('phicommcleaner login error:' + result['msg'])
            return None

    def getDeviceData(self, device_id):
        if self._token == None:
            if self.login() == None:
                return None
        data = {'deviceID': device_id}
        headers = {'User-Agent': USER_AGENT, 'Authorization': self._token}
        return requests.get('https://aircleaner.phicomm.com/aircleaner/getDeviceData', headers=headers,
                            params=data).json()

    # 0 OFF  1 ON  2 HAND  3 AUTO  4 SLEEP  5  EFFIECT
    def setDeviceMode(self, device_id, mode):
        if self._token == None:
            if self.login() == None:
                return None
        data = {'deviceID': device_id, 'mode': mode}
        headers = {'User-Agent': USER_AGENT, 'Authorization': self._token}
        return requests.post('https://aircleaner.phicomm.com/aircleaner/setDeviceMode', headers=headers,
                             data=data).json()

    def setWindSpeed(self, device_id, speed):
        if self._token == None:
            if self.login() == None:
                return None
        data = {'deviceID': device_id, 'windSpeed': speed}
        headers = {'User-Agent': USER_AGENT, 'Authorization': self._token}
        return requests.post('https://aircleaner.phicomm.com/aircleaner/windSpeed', headers=headers,
                             data=data).json()

    def open(self) -> bool:
        _LOGGER.debug('============= phicommcleaner open =============')
        self.lock = time.time()
        try:
            res = self.setDeviceMode(self._deviceid, 1)
            if res['error'] == '0':
                return True
        except BaseException:
            pass
        return False

    def close(self):
        _LOGGER.debug('============= phicommcleaner close =============')
        self.lock = time.time()
        try:
            res = self.setDeviceMode(self._deviceid, 0)
            if res['error'] == '0':
                return True
        except BaseException:
            pass
        return False

    def set_speed(self, speed):
        _LOGGER.debug('============= phicommcleaner set speed: %s =============', speed)
        self.lock = time.time()
        try:
            if speed == SPEED_HAND:
                res = self.setWindSpeed(self._deviceid, 65)
            else:
                res = self.setDeviceMode(self._deviceid, CONTROL_MAP[speed][0])

            if res['error'] == '0':
                return True
        except BaseException:
            pass
        return False

    @property
    def status(self) -> dict:
        _LOGGER.debug('============= phicommcleaner status =============')
        if (self.lock is not None) and (time.time() - self.lock < 5):
            _LOGGER.debug('============= phicommcleaner status return =============')
            return None
        try:
            speed = None
            res = self.getDeviceData(self._deviceid)
            if res['error'] == '0':
                if res['data']['cleanerDev']['online'] == '1':
                   speed = SPEED_MAP[res['data']['cleanerDev']['mode']]

                return {
                    'available': res['data']['cleanerDev']['online'],
                    'speed': speed,
                    'state_remain': res['data']['cleanerDev']['filterStatus'],
                    'state_pm25': res['data']['cleanerDev']['pm25'],
                    'state_hcho': res['data']['cleanerDev']['hcho'],
                    'state_lock': res['data']['cleanerDev']['childLock']
                }
        except BaseException:
            raise
        return {
            'available': False,
            'speed': None,
            'state_remain': None,
            'state_pm25': None,
            'state_hcho': None,
            'state_lock': None
        }


class PhicommFan(FanEntity):
    def __init__(self, hass, name: str, password: str, user_id: str,
                 device_id: str) -> None:
        self._hass = hass
        self._available = True
        self._name = name
        self._controller = PhicommController(hass, password, user_id, device_id)

        self._speed = SPEED_OFF
        self._updatetime = None
        self._state_pm25 = None
        self._state_remain = None
        self._state_hcho = None
        self._state_lock = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def available(self) -> bool:
        return self._available

    @property
    def should_poll(self):
        return True

    @property
    def speed(self) -> str:
        return self._speed

    @property
    def speed_list(self) -> list:
        return [ SPEED_OFF, SPEED_AUTO, SPEED_SILENT, SPEED_HAND, SPEED_EFFIECT ]

    def turn_on(self, speed: str, **kwargs) -> None:
        if speed == SPEED_OFF:
            self.turn_off()
            return
        if speed is None:
            speed = SPEED_AUTO
        if self._speed == SPEED_OFF:
            self._controller.open()
        if self._controller.set_speed(speed) is True:
            self._speed = speed
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs) -> None:
        if self._controller.close() is True:
            self._speed = SPEED_OFF
        self.schedule_update_ha_state()

    @property
    def is_on(self) -> bool:
        return SPEED_OFF != self._speed

    @Throttle(SCAN_INTERVAL)
    def update(self) -> None:

        data = self._controller.status

        if data is None:
            return
        self._available = data['available']
        self._speed = data['speed']
        self._state_remain = data['state_remain']
        self._state_hcho = data['state_hcho']
        self._state_pm25 = data['state_pm25']
        self._state_lock = data['state_lock']

    @property
    def device_state_attributes(self):
        return {
            ATTR_PM25: self._state_pm25,
            ATTR_HCHO: self._state_hcho,
            ATTR_FILTER_REMAIN: self._state_remain,
            ATTR_CHILDREN_LOCK: self._state_lock
        }
