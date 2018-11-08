"""
PhicommTC1 
"""
import datetime
import json
import logging
import paho.mqtt.client as mqtt
import requests
import ssl
import voluptuous as vol
from custom_components.phicomm.PhicommDevice import *

import homeassistant.helpers.config_validation as cv
from homeassistant.components.mqtt import MQTT
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_MAC, CONF_NAME)
from homeassistant.core import callback

REQUIREMENTS = ['paho-mqtt==1.3.1']

_LOGGER = logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG)

SCAN_INTERVAL = datetime.timedelta(seconds=15)

MQTT_HOSTNAME = "home.phicomm.com"
MQTT_PORT = 8883
MQTT_USERNAME = "admin"
MQTT_PASSWORD = "password"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_MAC, default=""): cv.string
})

ATTR_STATE = "state"
ATTR_POWER = "power"
ATTR_DURATION = "duration"
ATTR_CONSUMPTION = "consumption"

SWITCHS = {
    'all': "_all",
    's1': "_s1",
    's2': "_s2",
    's3': "_s3",
    's4': "_s4",
    's5': "_s5",
    's6': "_s6"
}


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up a PhicommTC1  switch."""
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    mac = config.get(CONF_MAC)

    phicommController = PhicommController(hass, name, mac, username, password)
    await phicommController.subscribe()
    devices = []
    for (switch_id, switch_name) in SWITCHS.items():
        phicommTC1Switch = PhicommTC1Switch(
            hass,
            switch_id,
            name + switch_name,
            phicommController)
        devices.append(phicommTC1Switch)

    async_add_devices(devices)
    return True


class PhicommController(PhicommDevice):

    def __init__(self, hass, name, mac, username, password) -> None:
        PhicommDevice.__init__(self, username, password)
        self._username = username
        self._password = password
        self._hass = hass
        # self.switch_status = None
        self._name = name
        self._token = self.config_get("_token")
        self._deviceid = self.config_get(self.name + "_deviceid")
        self._mac = mac
        self._mqtt = None

        self.switch_status = {}

        for (switch_id, switch_name) in SWITCHS.items():
            self.switch_status[switch_id] = {ATTR_STATE: False}

    def get_device_id(self):

        headers = {'User-Agent': USER_AGENT, 'Authorization': self._token}
        device_id = None

        result = requests.get('https://home.phicomm.com/v1/user/config_message',
                              headers=headers).json()
        if result['status'] == 200:
            family_id = result['result']['selected_family']['family_id']

            data = {'fid': family_id, 'page': 1, 'page_size': 100}
            result = requests.get('https://home.phicomm.com/v1/user/devices', headers=headers,
                                  params=data).json()
            if result['status'] == 200 and len(result['result']['devices']) > 0:
                device_id = result['result']['devices'][0]['device_id']
                for device in result['result']['devices']:
                    if self._mac == device['device_mac']:
                        device_id = device['device_id']

        return device_id

    async def publish(self, topic, payload="") -> bool:
        if not self.verifyToken():
            if self.login() is None:
                return False
            await self.subscribe()

        if not self._deviceid:
            self._deviceid = self.get_device_id()
            self.config_set(self._name + "_deviceid", self._deviceid)
            await self.subscribe()
        try:
            await self._mqtt.async_publish(topic, payload, 0, False)
            return True
        except Exception as e:
            _LOGGER.error("phicommTC1 publish error")
            _LOGGER.error(e)
        return False

    async def _toggle(self, switch_id, status) -> bool:
        desired_topic = "device/%s/OutletStatus" % self._deviceid
        desired_payload = """{"state":{"desired":{"switch":{"%s":%s}}}}""" % (
            switch_id, status)

        if switch_id == "all":
            desired_payload = \
                '{"state":{"desired":{"switch":{"s1":"%s","s2":"%s","s3":"%s","s4":"%s","s5":"%s","s6":"%s"}}}}}' % (
                    status, status, status, status, status, status)

        reported_topic = "$phihome/shadow/outlet_tc1/%s/OutletStatus/update/accepted" % self._deviceid
        reported_payload = """{"state":{"reported":{"switch":{"%s":%s}}}}""" % (switch_id, status)
        if switch_id == "all":
            reported_payload = \
                '{"state":{"reported":{"switch":{"s1":"%s","s2":"%s","s3":"%s","s4":"%s","s5":"%s","s6":"%s"}}}}}' % (
                    status, status, status, status, status, status)

        return await self.publish(desired_topic, desired_payload) and await self.publish(reported_topic,
                                                                                         reported_payload)

    async def open(self, switch_id) -> bool:
        return await self._toggle(switch_id, 1)

    async def close(self, switch_id) -> bool:
        return await self._toggle(switch_id, 0)

    async def subscribe(self):

        if self._token is not None and self._deviceid is not None:
            self._mqtt = MQTT(
                self._hass, MQTT_HOSTNAME, MQTT_PORT, "Bearer " + self._token, 60, MQTT_USERNAME,
                MQTT_PASSWORD,
                requests.certs.where(), None, None, None, mqtt.MQTTv311,
                None, None, ssl.CERT_REQUIRED)

            # yield from self._mqtt.async_disconnect()  # type: bool
            await self._mqtt.async_connect()  # type: bool

            @callback
            def message_received(topic, payload, qos):
                payload = json.loads(payload)
                # update power
                if topic.endswith("/power/instant/response"):
                    self.switch_status['all'][ATTR_POWER] = payload['power']

                elif topic.endswith("/OutletStatus/get/accepted"):
                    all_state = True
                    for (switch_id, switch_name) in SWITCHS.items():
                        # update friendly_name

                        if switch_id in payload['state']['reported']['switchName']:
                            self.switch_status[switch_id]['friendly_name'] = \
                                payload['state']['reported']['switchName'][
                                    switch_id]
                        # update switch state
                        if switch_id in payload['state']['reported']['switch']:
                            self.switch_status[switch_id][ATTR_STATE] = True if (
                                    str(payload['state']['reported']['switch'][switch_id]) == "1") else False

                            all_state = all_state and self.switch_status[switch_id][ATTR_STATE]

                    self.switch_status['all'][ATTR_STATE] = all_state
                elif topic.endswith("/PowerConsumption/update/accepted"):
                    self.switch_status['all'][ATTR_DURATION] = \
                        payload['state']['reported']['power_consumption']['daily'][-1]['duration']
                    self.switch_status['all'][ATTR_CONSUMPTION] = \
                        payload['state']['reported']['power_consumption']['daily'][-1]['consumption']

            topics_list = [topic for topic in (
                "$phihome/shadow/outlet_tc1/%s/PowerConsumption/update/accepted" % self._deviceid,
                "device/%s/power/instant/response" % self._deviceid,
                "$phihome/shadow/outlet_tc1/%s/OutletStatus/get/accepted" % self._deviceid
            ) if topic]
            for topic in set(topics_list):
                await self._mqtt.async_subscribe(topic, message_received, 0, 'utf-8')


class PhicommTC1Switch(SwitchDevice):
    """Representation of a PhicommTC1 switch."""

    def __init__(self, hass, switch_id, switch_name, controller):
        """Initialize the PhicommTC1 switch."""
        self._hass = hass
        self._name = switch_name
        self._controller = controller
        self._switch_id = switch_id

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._controller.switch_status[self._switch_id][ATTR_STATE]

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._controller.open(self._switch_id)
        self._controller.switch_status[self._switch_id][ATTR_STATE] = True
        # self.asyn_schedule_update_ha_state(True)

    async def async_turn_off(self, **kwargs):
        """Turn the device off if an off action is present."""
        await self._controller.close(self._switch_id)
        self._controller.switch_status[self._switch_id][ATTR_STATE] = False
        # self.asyn_schedule_update_ha_state(True)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._controller.switch_status[self._switch_id]

    async def async_update(self):
        """Check if device is on and update the state."""
        if self._switch_id == "all":
            await self._controller.publish(
                "$phihome/shadow/outlet_tc1/%s/OutletStatus/get" % self._controller._deviceid)
            await self._controller.publish(
                "device/%s/power/instant/request" % self._controller._deviceid)
            await self._controller.publish(
                "device/%s/power/comsumption/request" % self._controller._deviceid)
