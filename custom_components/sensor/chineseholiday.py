#! usr/bin/python
#coding=utf-8
"""
中国节假日
版本：0.0.5
"""
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import datetime
from datetime import timedelta
import requests
import time
import logging
from homeassistant.util import Throttle
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
     CONF_NAME)
from homeassistant.helpers.entity import generate_entity_id
from . import lunar

_Log=logging.getLogger(__name__)



DEFAULT_NAME = 'chinese_holiday'
CONF_UPDATE_INTERVAL = 'update_interval'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(minutes=360)): (vol.All(cv.time_period, cv.positive_timedelta)),
})
FESTIVAL_TYPE= {
    'new_years_day' : '元旦',
    'spring_festival' : '春节',
    'tomb_sweeping_day' : '清明节',
    'labour_day' : '国际劳动节',
    'dragon_boat_festival' : '端午节',
    'national_day' : '国庆节',
    'mid_autumn_festival' : '中秋节',
    'day_off' : '调休日需上班'
}
HOLIDAY = {
    datetime.date(year=2018, month=1, day=1): FESTIVAL_TYPE['new_years_day'],
    datetime.date(year=2018, month=2, day=11): FESTIVAL_TYPE['day_off'],
    datetime.date(year=2018, month=2, day=15): FESTIVAL_TYPE['spring_festival'],
    datetime.date(year=2018, month=2, day=16): FESTIVAL_TYPE['spring_festival'],
    datetime.date(year=2018, month=2, day=17): FESTIVAL_TYPE['spring_festival'],
    datetime.date(year=2018, month=2, day=18): FESTIVAL_TYPE['spring_festival'],
    datetime.date(year=2018, month=2, day=19): FESTIVAL_TYPE['spring_festival'],
    datetime.date(year=2018, month=2, day=20): FESTIVAL_TYPE['spring_festival'],
    datetime.date(year=2018, month=2, day=21): FESTIVAL_TYPE['spring_festival'],
    datetime.date(year=2018, month=2, day=24): FESTIVAL_TYPE['day_off'],
    datetime.date(year=2018, month=4, day=5): FESTIVAL_TYPE['tomb_sweeping_day'],
    datetime.date(year=2018, month=4, day=6): FESTIVAL_TYPE['tomb_sweeping_day'],
    datetime.date(year=2018, month=4, day=7): FESTIVAL_TYPE['tomb_sweeping_day'],
    datetime.date(year=2018, month=4, day=8): FESTIVAL_TYPE['day_off'],
    datetime.date(year=2018, month=4, day=28): FESTIVAL_TYPE['day_off'],
    datetime.date(year=2018, month=4, day=29): FESTIVAL_TYPE['labour_day'],
    datetime.date(year=2018, month=4, day=30): FESTIVAL_TYPE['labour_day'],
    datetime.date(year=2018, month=5, day=1): FESTIVAL_TYPE['labour_day'],
    datetime.date(year=2018, month=6, day=16): FESTIVAL_TYPE['dragon_boat_festival'],
    datetime.date(year=2018, month=6, day=17): FESTIVAL_TYPE['dragon_boat_festival'],
    datetime.date(year=2018, month=6, day=18): FESTIVAL_TYPE['dragon_boat_festival'],
    datetime.date(year=2018, month=9, day=22): FESTIVAL_TYPE['mid_autumn_festival'],
    datetime.date(year=2018, month=9, day=23): FESTIVAL_TYPE['mid_autumn_festival'],
    datetime.date(year=2018, month=9, day=24): FESTIVAL_TYPE['mid_autumn_festival'],
    datetime.date(year=2018, month=9, day=29): FESTIVAL_TYPE['day_off'],
    datetime.date(year=2018, month=9, day=30): FESTIVAL_TYPE['day_off'],
    datetime.date(year=2018, month=10, day=1): FESTIVAL_TYPE['national_day'],
    datetime.date(year=2018, month=10, day=2): FESTIVAL_TYPE['national_day'],
    datetime.date(year=2018, month=10, day=3): FESTIVAL_TYPE['national_day'],
    datetime.date(year=2018, month=10, day=4): FESTIVAL_TYPE['national_day'],
    datetime.date(year=2018, month=10, day=5): FESTIVAL_TYPE['national_day'],
    datetime.date(year=2018, month=10, day=6): FESTIVAL_TYPE['national_day'],
    datetime.date(year=2018, month=10, day=7): FESTIVAL_TYPE['national_day'],
}
ANNIVERSARY = {
    datetime.date(year=2018, month=6, day=9): 'Timi生日',
    datetime.date(year=2018, month=11, day=7):'Diamond生日',
}
CALCULATEAGE= {
    datetime.datetime(year=2014, month=6, day=9, hour=13, minute=32, second=54): '小Timi出生',
    datetime.datetime(year=2032, month=6, day=9, hour=13, minute=32, second=54): '小Timi成年',
}

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the movie sensor."""
    name = config[CONF_NAME]
    interval = config.get(CONF_UPDATE_INTERVAL)

    sensors = [ChineseHolidaySensor(hass, name, interval)]
    add_devices(sensors, True)

class ChineseHolidaySensor(Entity):
    def __init__(self, hass, name, interval):
        """Initialize the sensor."""
        self.client_name = name
        self._state = None
        self._hass = hass
        self.attributes = {}
        self.entity_id = generate_entity_id(
            'sensor.{}', self.client_name, hass=self._hass)
        self.update = Throttle(interval)(self._update)

    def nearest_holiday(self):
        '''查找离今天最近的法定节假日，并显示天数'''
        now_day = datetime.date.today()
        count_dict = {}
        for key in HOLIDAY.keys():
            if (key - now_day).days > 0:
                count_dict[key] = (key - now_day).days
        nearest_holiday_dict = {}
        nearest_holiday_dict['name'] = HOLIDAY[min(count_dict)]
        nearest_holiday_dict['date'] = min(count_dict).isoformat()
        nearest_holiday_dict['day'] = str((min(count_dict)-now_day).days)+'天'
        return nearest_holiday_dict

    def nearest_anniversary(self):
        '''查找离今天最近的纪念日，并显示天数'''
        now_day = datetime.date.today()
        count_dict = {}
        for key in ANNIVERSARY.keys():
            if (key - now_day).days > 0:
                count_dict[key] = (key - now_day).days
        nearest_anniversary_dict = {}
        nearest_anniversary_dict['name'] = ANNIVERSARY[min(count_dict)]
        nearest_anniversary_dict['date'] = min(count_dict).isoformat()
        nearest_anniversary_dict['day'] = str((min(count_dict)-now_day).days)+'天'
        return nearest_anniversary_dict


    def is_holiday(self,day):
        """
        判断是否节假日, api 来自百度 apistore: [url]http://apistore.baidu.com/apiworks/servicedetail/1116.html[/url]
        :param day: 日期， 格式为 '20160404'
        :return: bool
        api = 'http://tool.bitefu.net/jiari/'
        params = {'d': day, 'apiserviceid': 1116}
        rep = requests.get(api, params)
        if rep.status_code != 200:
            return '无法获取节日数据'
        res = rep.text
        return "法定节日" if res != "0" else "非法定节日"
        """
        holiday_api = 'https://api.goseek.cn/Tools/holiday?date={0}'.format(day)
        rep =requests.get(holiday_api)
        if rep.status_code != 200:
            return '无法获取节日数据'
        holiday_date = rep.json()
        get_day = holiday_date['data']
        result = ''
        if get_day == 0:
            result = '工作日'
        elif get_day == 1:
            result = '休息日'
        elif get_day == 2:
            result = '节假日'
        else:
            result = '出错了呀！'
        return result

    def is_holiday_today(self):
        """
        判断今天是否时节假日
        :return: bool
        """
        today = datetime.date.today().strftime('%Y%m%d')
        return self.is_holiday(today)

    @property
    def name(self):
        """Return the name of the sensor."""
        return '节假日'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:calendar-today'



    @property
    def device_state_attributes(self):
        """Return the state attributes."""

        return self.attributes


    def _update(self):

        self._state = self.is_holiday_today()
        self.attributes['今天日期'] = datetime.date.today().strftime('%Y{y}%m{m}%d{d}').format(y='年', m='月', d='日')
        self.attributes['农历'] = lunar.getCalendar_today()['lunar']
        if 'festival' in lunar.getCalendar_today().keys():
            self.attributes['节日'] = lunar.getCalendar_today()['festival']
        self.attributes['离今天最近的法定节日'] = self.nearest_holiday()['name']
        self.attributes['法定节日日期'] = self.nearest_holiday()['date']
        self.attributes['还有'] = self.nearest_holiday()['day']
        self.attributes['最近的纪念日'] = self.nearest_anniversary()['name']
        self.attributes['纪念日日期'] = self.nearest_anniversary()['date']
        self.attributes['相隔'] = self.nearest_anniversary()['day']
        if CALCULATEAGE:
            now_day = datetime.datetime.now()
            count_dict = {}
            for key, value in CALCULATEAGE.items():
                if (now_day - key).total_seconds() > 0:
                    total_seconds = int((now_day - key).total_seconds())
                    year, remainder = divmod(total_seconds,60*60*24*365)
                    day, remainder = divmod(remainder,60*60*24)
                    hour, remainder = divmod(remainder,60*60)
                    minute, second = divmod(remainder,60)
                    self.attributes['离'+value+'过去'] = '{}年 {} 天 {} 小时 {} 分钟 {} 秒'.format(year,day,hour,minute,second)
                if (now_day - key).total_seconds() < 0:
                    total_seconds = int((key - now_day ).total_seconds())
                    year, remainder = divmod(total_seconds,60*60*24*365)
                    day, remainder = divmod(remainder,60*60*24)
                    hour, remainder = divmod(remainder,60*60)
                    minute, second = divmod(remainder,60)
                    self.attributes['离'+value+'还差']  = '{}年 {} 天 {} 小时 {} 分钟 {} 秒'.format(year,day,hour,minute,second)




        '''计算给定日期与今天日期相差的天数
        if CALCULATEAGE:
            now_day = datetime.date.today()
            count_dict = {}
            for key in CALCULATEAGE.keys():
                if (now_day - key).days > 0:
                    self.attributes[key] = str((now_day - key).days)+'天'
                if (now_day - key).days < 0:
                    self.attributes[key]  = (key - now_day).days'''
