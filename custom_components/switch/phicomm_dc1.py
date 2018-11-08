#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import socket
import select
import queue as Queue
import json
import re
import logging
import sys

ATTR_I = "I"
ATTR_V = "V"
ATTR_P = "P"
ATTR_STATUS = "status"
ATTR_RESULT = "result"

# 忽略kWh+ 指令 不知道是干嘛的
IGNORE_ACTION = ['kWh+']

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)
# format = logging.Formatter("%(asctime)s - %(message)s")    # output format 
# sh = logging.StreamHandler(stream=sys.stdout)    # output to standard output
# sh.setFormatter(format)
# _LOGGER.addHandler(sh)

class PhicommDC1():
    """Class for handling the data retrieval."""

    def __init__(self):
        self.serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.serversocket.bind(("0.0.0.0", 8000))
        self.serversocket.listen(10)
        self.serversocket.setblocking(False)
        self.epoll = select.epoll()
        self.epoll.register(self.serversocket.fileno(), select.EPOLLIN)
        self.message_queues = {}
        self.fd_to_socket = {self.serversocket.fileno(): self.serversocket, }
        # 设置状态
        self.status_dict = {}
        self.change_status = {}

    def loop(self):
        while True:
            try:
                self.update(10)
            except Exception as e:
                _LOGGER.error(e)

    def update(self, timeout=10):
        _LOGGER.debug("等待活动连接......")
        events = self.epoll.poll(timeout)
        if not events:
            _LOGGER.debug("epoll超时无活动连接，重新轮询......")
            return
        _LOGGER.debug("有"+ str(len(events))+ "个新事件，开始处理......")

        for fd, event in events:
            socket = self.fd_to_socket[fd]
            # _LOGGER.debug(socket)
            if socket == self.serversocket:
                connection, address = self.serversocket.accept()
                # _LOGGER.debug("新连接：" + address)
                connection.setblocking(False)
                self.epoll.register(connection.fileno(), select.EPOLLIN)
                self.fd_to_socket[connection.fileno()] = connection
                self.message_queues[connection] = Queue.Queue()
            elif event & select.EPOLLHUP:
                _LOGGER.debug('client close')
                self.epoll.unregister(fd)
                self.fd_to_socket[fd].close()
                del self.fd_to_socket[fd]
            elif event & select.EPOLLIN:
                data = socket.recv(1024)
                if data:
                    _LOGGER.debug("收到数据："+str(data) +", client:"+ socket.getpeername()[0])
                    data = self.parseJsonData(data)
                    # 忽略不识别的指令
                    if "action" in data and data['action'] in IGNORE_ACTION :continue

                    uuid = data['params']['mac'] if "params" in data and "mac" in data['params'] else data['uuid'] 
                    #与斐讯服务器正常配网的反馈的是 device_id 
                    deviceid = data['params']['device_id'] if "params" in data and "device_id" in data['params'] else None
                    if  deviceid is not None:
                        _LOGGER.error("您的device_id为："+deviceid)
                    # deviceid优先
                    uuid = uuid if deviceid is None else deviceid
                    # uuid = uuid.replace(":","")
                    # device_status 不为空即传过来的是设备状态
                    # 判断反馈的指令类型 如果在hass端更新了状态， 即change_status中有对应设备 此处返回datapoint=指令 反之 反馈 datapoint指令 并更新状态为设备反馈值

                    # if uuid in self.status_dict and device_status and self.status_dict[uuid] != device_status :
                    if uuid in self.change_status:
                        _LOGGER.debug("更新设备状态")
                        _LOGGER.debug(self.change_status)
                        # 更新设备状态
                        data = bytes(
                            '{"action":"datapoint=","params":{"status":' + str(
                                self.change_status[uuid]) + '},"uuid":"' + str(uuid) + '","auth":""}\n',
                            encoding="utf8")
                        del self.change_status[uuid]
                    else:
                        _LOGGER.debug("无更新")
                        if ATTR_RESULT in data and ATTR_STATUS in data[ATTR_RESULT]:
                            if uuid not in  self.status_dict : self.status_dict[uuid] = {}
                            self.status_dict[uuid][ATTR_STATUS] = int(str(data[ATTR_RESULT][ATTR_STATUS]),2)
                            self.status_dict[uuid][ATTR_I] = data[ATTR_RESULT][ATTR_I] if ATTR_I in data[ATTR_RESULT] else None
                            self.status_dict[uuid][ATTR_P] = data[ATTR_RESULT][ATTR_P] if ATTR_P in data[ATTR_RESULT] else None
                            self.status_dict[uuid][ATTR_V] = data[ATTR_RESULT][ATTR_V] if ATTR_V in data[ATTR_RESULT] else None

                        data = bytes('{"uuid":"' + uuid + '","params":{},"auth":"","action":"datapoint"}\n',
                                     encoding="utf8")

                    # _LOGGER.debug(device_status)
                    # _LOGGER.debug(self.status_dict)
                    _LOGGER.debug(self.status_dict)
                    self.message_queues[socket].put(data)
                    self.epoll.modify(fd, select.EPOLLOUT)
            elif event & select.EPOLLOUT:
                try:
                    msg = self.message_queues[socket].get_nowait()
                except Queue.Empty:
                    _LOGGER.debug(socket.getpeername()[0] + " queue empty")
                    self.epoll.modify(fd, select.EPOLLIN)
                else:
                    _LOGGER.debug("发送数据："+ str(msg))
                    socket.send(msg)

    def shutdown(self):
        """Shutdown."""
        if self.serversocket is not None:
            self.epoll.unregister(self.serversocket.fileno())
            self.epoll.close()
            self.serversocket.close()
            self.serversocket = None

    def parseJsonData(self, data):
        # 解决data中包含多个json的情况
        pattern = r"(\{.*\})"
        jsonStr = re.findall(pattern, str(data).split('\n')[0], re.M)
        l = len(jsonStr)
        if l > 0:
            return json.loads(jsonStr[l - 1])
        else:
            return None


if __name__ == '__main__':
    phicomm = PhicommDC1()
    try:
        phicomm.loop()
    except KeyboardInterrupt:
        pass
    phicomm.shutdown()
    exit(0)


import threading
import datetime
import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_NAME, CONF_MAC)
import homeassistant.helpers.config_validation as cv

_INTERVAL = 3

SCAN_INTERVAL = datetime.timedelta(seconds=_INTERVAL)
# DEFAULT_NAME = 'dc1'
# CONF_PORTS = 'ports'

ATTR_STATE = "switchstate"
ATTR_NAME = "switchname"

CONNECTION_LISTS = []

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    # vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_MAC): dict
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Phicomm DC1 switch."""

    macs = config[CONF_MAC]
    phicomm = PhicommDC1()
    threading.Thread(target=phicomm.loop).start()

    devs = []
    index = 0
    for mac in macs:
        index+=1
        for i in range(0, 4):
            name = "dc%s_s%s"%(index,i)
            devs.append(PhicommDC1Port(hass, phicomm,name, mac, i))

    add_devices(devs)


class PhicommDC1Port(SwitchDevice):
    """Representation of a port of DC1 Smart Plug switch."""

    def __init__(self, hass, phicomm,name, mac, port):
        """Initialize the switch."""
        self._hass = hass
        # self._name = "%s-%s" % (port, mac)
        self._name = name
        self._phicomm = phicomm
        self._mac = mac
        self._port = port
        self._state = False
        self._state_attrs = {
            ATTR_STATE: False,
            ATTR_I: None,
            ATTR_P: None,
            ATTR_V: None,
        }

    @property
    def name(self):
        """Return the name of the Smart Plug, if any."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def current_power_watt(self):
        """Return the current power usage in Watt."""
        return None

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state_attrs[ATTR_STATE]

    def turn_on(self, **kwargs):
        """Turn the switch on."""

        current_status = self._phicomm.status_dict[self._mac][ATTR_STATUS]

        _LOGGER.debug("更新前"+str(current_status))

        current_status |= 1 << self._port

        # 开启总开关
        current_status |= 1 

        _LOGGER.debug("更新後"+str(current_status))

        strT = bin(int(current_status))
        strT = strT[2:len(strT)]

        self._state_attrs[ATTR_STATE] = True
        self._phicomm.change_status[self._mac] = strT
        self._phicomm.status_dict[self._mac][ATTR_STATUS] = current_status

        _LOGGER.debug("更新後"+strT)

    def turn_off(self):

        current_status = self._phicomm.status_dict[self._mac][ATTR_STATUS]
        _LOGGER.debug("更新前"+str(current_status))
        
        current_status &= ~(1 << self._port)

        _LOGGER.debug("更新後"+str(current_status))

        strT = bin(int(current_status))
        strT = strT[2:len(strT)]

        self._state_attrs[ATTR_STATE] = False
        self._phicomm.change_status[self._mac] = strT
        self._phicomm.status_dict[self._mac][ATTR_STATUS] = current_status

        _LOGGER.debug("更新後"+strT)


    def update(self):
        # self._state_attrs
        # _LOGGER.debug("hass--update")
        if self._mac in  self._phicomm.status_dict :
            self._state_attrs[ATTR_STATE] = True if self._phicomm.status_dict[self._mac][ATTR_STATUS] & (1 << self._port) > 0  else False
            self._state_attrs[ATTR_V] = self._phicomm.status_dict[self._mac][ATTR_V]
            self._state_attrs[ATTR_I] = self._phicomm.status_dict[self._mac][ATTR_I]
            self._state_attrs[ATTR_P] = self._phicomm.status_dict[self._mac][ATTR_P]
        else:
            self._state_attrs[ATTR_V] = "未知" 
            #self._mac
            self._state_attrs[ATTR_I] = "未知" 
            #self._mac
            self._state_attrs[ATTR_P] = "未知" 
            #self._mac
