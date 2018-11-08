"""
Support for the GPSLogger platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.gpslogger/
"""
import logging
import time
import json
from hmac import compare_digest
import qrcode
import asyncio
from aiohttp import web
from io import BytesIO
#pip install pillow
#pip install qrcode
import asyncws
#pip3 install asyncws
import requests
import datetime
import threading
import hashlib
import gzip
from io import StringIO
from requests.exceptions import ReadTimeout,ConnectionError,RequestException
import paho.mqtt.client as mqtt
#pip3 install paho-mqtt
# from Crypto.Cipher import AES
# wget https://ftp.dlitz.net/pub/dlitz/crypto/pycrypto/pycrypto-2.6.1.tar.gz
# tar zxvf pycrypto-2.6.1.tar.gz
# cd pycrypto-2.6.1
# sudo python3 setup.py install
# 如果还是报错，就修改/usr/local/lib/python3.7/site-packages下的crypto为Crypto

from aiohttp.web import Request, HTTPUnauthorized
import voluptuous as vol
from homeassistant.core import callback

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_PASSWORD, HTTP_UNPROCESSABLE_ENTITY, EVENT_HOMEASSISTANT_START
)
from homeassistant.components.http import (
    CONF_API_PASSWORD, HomeAssistantView
)
# pylint: disable=unused-import
from homeassistant.components.device_tracker import (  # NOQA
    DOMAIN, PLATFORM_SCHEMA
)
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

DOMAIN = 'ihass_mqtt'

CONF_MQTT_HOST = 'mqtt_host'
CONF_MQTT_PORT = 'mqtt_port'
CONF_MQTT_USER = 'mqtt_user'
CONF_MQTT_PWD =  'mqtt_pwd'
CONF_TOPIC_SERVER = 'topic_server'
CONF_TOPIC_EVENT = 'topic_event'
CONF_AES_KEY = 'aes_key'
CONF_AES_IV = "aes_iv"
CONF_INTERVAL = 'event_interval'
CONF_HIDE_QR = 'hide_qr'
CONF_API_TOKEN = 'api_token'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_MQTT_HOST): cv.string,
        vol.Optional(CONF_MQTT_PORT, default = 1883): cv.string,
        vol.Optional(CONF_MQTT_USER): cv.string,
        vol.Optional(CONF_MQTT_PWD): cv.string,
        vol.Optional(CONF_TOPIC_SERVER, default = '/hass/server'): cv.string,
        vol.Optional(CONF_TOPIC_EVENT, default = '/hass/event'): cv.string,
        vol.Optional(CONF_AES_KEY): cv.string,
        vol.Optional(CONF_AES_IV): cv.string,
        vol.Optional(CONF_INTERVAL, default = 10): cv.string,
        vol.Optional(CONF_HIDE_QR, default = False): cv.boolean,
        vol.Optional(CONF_API_PASSWORD): cv.string,
        vol.Optional(CONF_API_TOKEN): cv.string,
        }),
    }, extra=vol.ALLOW_EXTRA)
    
class HassInvoker:
    def __init__(self, config, mq):
        conf = config.get(DOMAIN, {})    
        self._password = conf.get(CONF_API_PASSWORD)
        self._token = conf.get(CONF_API_TOKEN)
        self.websocket = None
        self.msgIndex = 1
        self.mq = mq
    def index(self):
        self.msgIndex = self.msgIndex + 1
        return self.msgIndex
    def handle(self, msg):
        try:
            message = json.loads(msg)
            if 'type' in message:
                type = message['type']
                if type == 'auth_required':
                    if self._token:
                        yield from self.websocket.send(json.dumps({"type": "auth", "access_token": self._token}))
                    else:
                        yield from self.websocket.send(json.dumps({"type": "auth", "api_password": self._password}))
                elif type == 'auth_ok':
                    yield from self.websocket.send(json.dumps({'id': self.index(), 'type': 'subscribe_events', 'event_type': 'state_changed'}))
                elif type == "event":
                    self.handle_event(message)
        except Exception as ex:
            _LOGGER.error(ex)
    def handle_event(self, message):
        self.mq.publish(message)
    def handle_request(self, request):
        path = request["path"]
        index = request.get("index")
        body = request.get("body")
        if isinstance(body, dict):
            body = json.dumps(body)
        method = request.get("method", "GET")
        result, reason = self.call_hass(method, path, body)
        if "topic" in request:
            topic = request.get("topic")
            response = {"index": index, "result": result, "reason": reason}
            response = json.dumps(response)
            self.mq.response(response, topic)

    def call_hass(self, method, path, body):
        headers = {
            "Content-Type": "application/json"
        }
        if self._token:
            headers["Authorization"] = "Bearer " + str(self._token) 
        elif self._password:
            headers["x-ha-access"] = self._password            
        url = 'http://{}:{}{}'.format("localhost", 8123, path)
        result = None
        reason = None
        try:
            if method == "POST":
                response = requests.post(url, headers=headers, data=body, timeout=1)
            else:
                response = requests.get(url, headers=headers, timeout=1)
            if (response.status_code != 200):
                reason = response.content.decode()
            else:
                result = response.content.decode()
        except ReadTimeout:
            reason = "连接超时"
        except ConnectionError:
            reason = "连接错误"
        except RequestException:
            reason = "发生未知错误"
        return result, reason

    @asyncio.coroutine
    def run(self):
        self.websocket = yield from asyncws.connect('ws://localhost:8123/api/websocket')
        while True:
            message = yield from self.websocket.recv()
            if message is None:
                break
            yield from self.handle(message)


def on_message(client, mq, msg):
    mq.on_message(client, msg)

def on_connected(client, mq, flags, rc):
    client.on_disconnect = on_disconnected
    print(str(datetime.datetime.now()) + ":mqtt connected, rc=" + str(rc))
    if rc == 0:
        mq.subscribe()

def on_disconnected(client, mq, rc):
    print(str(datetime.datetime.now()) + ":mqtt disconnected")

def on_timer(mq):
    mq.on_timer()

class Mosquitto:
    def __init__(self, config):          
        conf = config.get(DOMAIN, {})
        self.host = conf.get(CONF_MQTT_HOST)
        self.port = int(conf.get(CONF_MQTT_PORT, 1883))
        self.user = conf.get(CONF_MQTT_USER) 
        self.pwd = conf.get(CONF_MQTT_PWD)  
        self.server = conf.get(CONF_TOPIC_SERVER, '/hass/server')
        self.event = conf.get(CONF_TOPIC_EVENT, '/hass/event')  
        self.aes_key = conf.get(CONF_AES_KEY) 
        self.aes_iv = conf.get(CONF_AES_IV) 
        self.interval = int(conf.get(CONF_INTERVAL, 10))
        
        self.mqtt = mqtt.Client(userdata = self)
        if self.user:
            self.mqtt.username_pw_set(self.user, self.pwd)
        self.mqtt.on_connect = on_connected
        self.hass = None
        self.events = []
        if self.aes_key and len(self.aes_key) > 0:
            self.key = self.generate_key(self.aes_key).encode()
            self.iv = self.generate_key(self.aes_iv).encode()
        else:
            self.key = None
            self.iv = None
        if self.interval > 0:    
            threading.Timer(self.interval, on_timer, (self,)).start()
    def set_hass(self, hass):
        self.hass = hass
    def connect(self):
        self.mqtt.connect(self.host, self.port, 60)
        self.mqtt.loop_start()
    def subscribe(self, qos = 1):
        self.mqtt.subscribe(self.server, qos)
        self.mqtt.on_message = on_message
    def response(self, payload, topic, qos = 1):
        try:
            compressed = gzip.compress(payload.encode())
            aes = self.encrypt(compressed)
            self.mqtt.publish(topic, aes, qos)
        except Exception as ex:
            print(ex)
    def publish(self, message):
        self.events.append(message)
        if self.interval < 1 or len(self.events) > 30:
            print("send " + str(len(self.events)) + " events")
            text = json.dumps(self.events)
            self.response(text, self.event)
            self.events.clear()

    def on_timer(self):
        threading.Timer(self.interval, on_timer, (self,)).start()
        if len(self.events) > 0:
            print("send " + str(len(self.events)) + " events")
            text = json.dumps(self.events)
            self.response(text, self.event)
            self.events.clear()

    def generate_key(self, key):
        if self.user:
            key = self.user + key
        hl = hashlib.md5()
        hl.update(key.encode(encoding='utf-8'))
        key = hl.hexdigest()
        key = key[0:16]
        return key

    def on_message(self, client, message):
        try:
            msg = self.decrypt(message.payload)
            decompressed = gzip.decompress(msg)
            if isinstance(decompressed, bytes):
                msg = bytes.decode(decompressed)
            request = json.loads(msg)
            if "path" not in request or not self.hass:
                return
            self.hass.handle_request(request)
        except Exception as ex:
            print(ex)

    def compress(self,buf):
        return gzip.compress(buf)

    def decompress(self,buf):
        obj = StringIO(buf)
        with gzip.GzipFile(fileobj=obj) as f:
            result = f.read()
        return result

    def pad(self, datas):
        from Crypto.Cipher import AES
        block_size = AES.block_size
        ext = (block_size - len(datas) % block_size)
        result = bytearray(datas)
        for i in range(0, ext):
            result.append(ext)
        return bytes(result)

    def unpad(self, datas):
        if datas[-1] <= 16:
            return datas[0: - datas[-1]]
        return datas

    def encrypt(self, datas):
        if self.key:
            from Crypto.Cipher import AES
            cipher = AES.new(self.key, AES.MODE_CBC, IV = self.iv)
            aes = cipher.encrypt(self.pad(datas))
            return aes
        else:
            return datas

    def decrypt(self, datas):
        if self.key:
            from Crypto.Cipher import AES
            cipher = AES.new(self.key, AES.MODE_CBC, IV = self.iv)
            msg = cipher.decrypt(datas)
            return self.unpad(msg)
        else:
            return datas    
  
   
@asyncio.coroutine
def async_setup(hass, config):    
    mq = Mosquitto(config)
    ha = HassInvoker(config, mq)
    mq.set_hass(ha)
    mq.connect()  
    conf = config.get(DOMAIN, {})
    hideQr = conf.get(CONF_HIDE_QR, False)
    if not hideQr:
        hass.http.register_view(IHassMqttView(config))
    
    @callback
    def start_websocket(event):
        hass.async_add_job(ha.run())  
        
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_websocket)    
    return True    


class IHassMqttView(HomeAssistantView):
    """View to handle GPSLogger requests."""

    url = '/api/ihassmqtt'
    name = 'api:ihassmqtt'

    def __init__(self, config):
        """Initialize GPSLogger url endpoints."""        
        conf = config.get(DOMAIN, {})
        self.host = conf.get(CONF_MQTT_HOST)
        self.port = conf.get(CONF_MQTT_PORT, 1883)
        self.user = conf.get(CONF_MQTT_USER) 
        self.pwd = conf.get(CONF_MQTT_PWD)  
        self.server = conf.get(CONF_TOPIC_SERVER, '/hass/server')
        self.event = conf.get(CONF_TOPIC_EVENT, '/hass/event')  
        self.aes_key = conf.get(CONF_AES_KEY) 
        self.aes_iv = conf.get(CONF_AES_IV)  
        self.api_token = conf.get(CONF_API_TOKEN)  
        self.requires_auth = False

    async def get(self, request: Request):
        """Handle for GPSLogger message received as GET."""
        hass = request.app['hass']
        data = request.query    
        
        datas = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "pwd": self.pwd,
            "key": self.aes_key,
            "iv": self.aes_iv,
            "server": self.server,
            "event": self.event,
            "token": self.api_token
        }
        
        img = qrcode.make(json.dumps(datas))
        stream = BytesIO()
        img.save(stream, format='PNG')
        data = stream.getvalue()        
        response = web.StreamResponse()
        response.content_type = 'image/png'
        response.content_length = len(data)
        await response.prepare(request)
        await response.write(data)
        return response    
