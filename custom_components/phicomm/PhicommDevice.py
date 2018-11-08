import os
import requests
import json
import logging
import yaml
from homeassistant.helpers.entity import Entity

AUTH_CODE = 'feixun.SH_1'
USER_AGENT = 'zhilian/5.7.0 (iPhone; iOS 10.0.2; Scale/3.00)'

# Get homeassistant configuration path to store token
TOKEN_PATH = '.phicomm.token'
TOKEN_PATH = os.path.split(os.path.split(os.path.split(
    os.path.realpath(__file__))[0])[0])[0] + '/' + TOKEN_PATH

_LOGGER = logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG)


class PhicommDevice(Entity):
    """Representation a base Xiaomi device."""

    def __init__(self, username, password):
        """Initialize the Xiaomi device."""
        self._state = None
        self._is_available = True
        self._name = ''
        self._device_state_attributes = {}
        self._username = str(username)
        self._password = password
        self._token = self.config_get('_token')
        self._access_token = self.config_get('_access_token')
        self._refresh_token = self.config_get('_refresh_token')
        self._user_id = self.config_get('_user_id')

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._is_available

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._device_state_attributes

    def login(self):
        # _LOGGER.error('phicomm login  :'+ self._name )
        import hashlib
        md5 = hashlib.md5()
        md5.update(self._password.encode("utf8"))
        headers = {'User-Agent': USER_AGENT}
        data = {'authorizationcode': AUTH_CODE, 'password': md5.hexdigest(
        ).upper(), 'phonenumber': self._username}
        result = requests.post(
            'https://accountsym.phicomm.com/v1/login', headers=headers, data=data).json()
        _LOGGER.debug('getToken: result=%s', result)
        if 'access_token' in result:
            # _LOGGER.error('phicomm login success:' + json.dumps(result))
            self._token = result['access_token']
            self._access_token = result['access_token']
            self._refresh_token = result['refresh_token']
            self._user_id = result['uid']
            self.config_set("_token", result['access_token'])
            self.config_set("_access_token", result['access_token'])
            self.config_set("_refresh_token", result['refresh_token'])
            self.config_set("_user_id", result['uid'])
            return result
        else:
            _LOGGER.error('phicomm login error:' + json.dumps(result))
            return None

    def verifyToken(self):
        if self._token is not None:
            # return True
            # if need to verifyToken before actions
            # _LOGGER.error('phicomm verifyToken  :'+ self._name )
            try:
                headers = {'User-Agent': USER_AGENT, 'Authorization': self._token}
                result = requests.get(
                    'https://accountsym.phicomm.com/v1/verifyToken',
                    headers=headers).json()
                if result['error'] == '0':
                    return True
                else:
                    _LOGGER.error('phicomm verifyToken error:' + self._name + json.dumps(result))
            except Exception as e:
                _LOGGER.error(e)
        return False

    def config_set(self, key, value):
        fdd = None
        try:
            fdd = os.open(TOKEN_PATH, os.O_RDWR | os.O_CREAT)
            load_config = os.read(fdd, 65535)
            os.close(fdd)
            try:
                load_config = yaml.load(load_config.decode())
            except Exception as e:
                _LOGGER.error(e)
                load_config = {}

            load_config = {} if load_config is None else load_config

            if self._username not in load_config:
                load_config[self._username] = {}

            load_config[self._username][key] = value
            s = yaml.dump(load_config, indent=4, default_flow_style=False)

            fdd = os.open(TOKEN_PATH, os.O_RDWR | os.O_TRUNC | os.O_CREAT)
            os.write(fdd, str.encode(s))
            return True
        except Exception as e:
            _LOGGER.error(e)
        finally:
            if fdd is not None:
                os.close(fdd)
        return False

    def config_get(self, key=None, default=None):
        fdd = None
        try:
            fdd = os.open(TOKEN_PATH, os.O_RDONLY | os.O_CREAT)
            load_config = os.read(fdd, 65535)
            try:
                load_config = yaml.load(load_config.decode())
            except Exception as e:
                _LOGGER.error(e)
                load_config = {}
            load_config = {} if load_config == None else load_config
            if (self._username in load_config):
                load_dict = load_config[self._username]
            else:
                return None
            if key != None:
                return load_dict[key] if key in load_dict else None
            else:
                return load_dict
        except Exception as e:
            _LOGGER.error(e)
            if key != None:
                return default
            else:
                return {}
        finally:
            if fdd != None:
                os.close(fdd)
