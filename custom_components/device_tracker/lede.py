"""
Support for OpenWRT (luci) routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.luci/
"""
import json
import logging
import re

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


class InvalidLuciTokenError(HomeAssistantError):
    """When an invalid token is detected."""

    pass


def get_scanner(hass, config):
    """Validate the configuration and return a Luci scanner."""
    scanner = LuciDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class LuciDeviceScanner(DeviceScanner):
    """This class queries a wireless router running OpenWrt firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.parse_api_pattern = re.compile(r"(?P<param>\w*) = (?P<value>.*);")

        self.last_results = {}
        self.refresh_token()
        self.mac2name = None
        self.success_init = self.token is not None

    def refresh_token(self):
        """Get a new token."""
        self.token = _get_token(self.host, self.username, self.password)

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if self.mac2name is None:
            url = 'http://{}/cgi-bin/luci/admin/status/overview?status=1'.format(self.host)
            result = self.token.get(url).json()['leases']
            _LOGGER.warning('sta [%s]', result)
            if result:
                hosts = [x for x in result
                         if 'macaddr' in x and 'hostname' in x]
                mac2name_list = [
                    (x['macaddr'].upper(), x['hostname']) for x in hosts]
                self.mac2name = dict(mac2name_list)
            else:
                # Error, handled in the _req_json_rpc
                return
        return self.mac2name.get(device.upper(), None)

    def _update_info(self):
        """Ensure the information from the Luci router is up to date.

        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return False

        #_LOGGER.info("Checking ARP")

        # url = 'http://{}/cgi-bin/luci/rpc/sys'.format(self.host)
        url = 'http://{}/cgi-bin/luci/admin/status/overview?status=1'.format(self.host)

        try:
            result = self.token.get(url).json()['wifinets'][0]['networks'][0]['assoclist']
        except InvalidLuciTokenError:
            _LOGGER.info("Refreshing token")
            self.refresh_token()
            return False

        if result:
            #_LOGGER.info('%s', result)
            self.last_results = []
            for device_entry in result:
                _LOGGER.info(device_entry)
                self.last_results.append(device_entry)

            return True

        return False


def _req_json_rpc(url, method, *args, **kwargs):
    """Perform one JSON RPC operation."""
    data = 'luci_username={}&luci_password={}'.format(args[0], args[1])
    try:
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        s = requests.Session();
        res = s.post(url, data=data, headers=headers)
    except requests.exceptions.Timeout:
        _LOGGER.exception("Connection to the router timed out")
        return
    if res.status_code == 200:
        return s;
    elif res.status_code == 401:
        # Authentication error
        _LOGGER.exception(
            "Failed to authenticate, check your username and password")
        return
    elif res.status_code == 403:
        _LOGGER.exception("Luci responded with a 403 Invalid token")
        raise InvalidLuciTokenError

    else:
        _LOGGER.exception('Invalid response from luci: %s', res)


def _get_token(host, username, password):
    """Get authentication token for the given host+username+password."""
    url = 'http://{}/cgi-bin/luci/'.format(host)
    return _req_json_rpc(url, 'login', username, password)

