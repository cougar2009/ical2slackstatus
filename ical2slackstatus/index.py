#!/usr/bin/env python3.6
# Copyright 2017 Brigham Young University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import fire
import yaml
import json
import pytz
import boto3
import logging
import textwrap
import datetime
import requests
import urllib.request
from icalendar import Calendar
from dateutil.rrule import rrulestr

logging.basicConfig() # necessary for anything to print
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
bucketname = os.environ['S3_ICAL2SLACKSTATUS_PRD_CONFIGBUCKET_BUCKET_NAME']


def get_s3_yaml_contents(filename):
    assert isinstance(bucketname, str)
    assert isinstance(filename, str)
    s3 = boto3.client('s3')
    obj = s3.get_object(Bucket=bucketname, Key=filename)
    return yaml.load(obj['Body'].read())


def get_bucket_filelist():
    assert isinstance(bucketname, str)
    s3 = boto3.resource('s3')
    my_bucket = s3.Bucket(bucketname)
    return [item.key for item in my_bucket.objects.all()]


def get_config_objects():
    config_objects = []
    for filename in get_bucket_filelist():
        config_object = get_s3_yaml_contents(filename)
        config_object['net_id'] = filename.split('.')[0] # netid for netid.yml
        config_objects.append(config_object)
    return config_objects


def get_cal(url):
    with urllib.request.urlopen(url) as cal:
        return Calendar.from_ical(cal.read())


def get_today_events(cal_url):
    today = datetime.date.today()
    cal = get_cal(cal_url)
    events = cal.walk('vevent')
    _today_events = []
    for event in events:
        if event.get('RRULE'):
            _event = recurring_parser(event)
            if _event:
                _today_events.append(_event)
            continue
        if event.decoded('dtstart').__class__ == datetime.date:
            if event.decoded('dtstart') == today:
                _today_events.append(parse_event(event))
            else:
                logger.debug(f"{event} is not for today")
        elif event.decoded('dtstart').__class__ == datetime.datetime:
            if event.decoded('dtstart').date() == today:
                _today_events.append(parse_event(event))
            else:
                logger.debug(f"{event} is not for today")
    return _today_events


def parse_location(event):
    """
    Helper function to return location if one is present
    """
    location = ''
    if event.get('location'):
        location = event.decoded('location').decode('UTF-8')
    return location


def get_rrule(event):
    """
    Function takes  an icalendar event and returns a dateutils.rrule
    """
    dtstart = event.get('dtstart').dt
    if dtstart.__class__ == datetime.date:
        dtstart = date_to_datetime(dtstart)
    _dtstart = dtstart.strftime('%Y%m%dT%H%M%S%z')
    rules_text = "DTSTART:{}\n".format(_dtstart)
    rules_text = rules_text + '\n'.join([line for line in event.content_lines() if line.startswith('RRULE')])
    return rrulestr(rules_text)


def recurring_parser(event):
    """
    function takes in an event and builds the recurring rules and checks if an
    occurance is set for today if it is returns simplified dictionary
    """
    one_day = datetime.timedelta(days=1)
    _now = pytz.utc.localize(datetime.datetime.utcnow())
    _yesterday = _now - one_day
    _duration = event.get('dtstart').dt - event.get('dtend').dt
    rule = get_rrule(event)
    _next = rule.after(_yesterday)
    if _next and _next.date() == _now.date():
        dtend = _next - _duration
        _summary = event.decoded('summary').decode('UTF-8')
        _location = parse_location(event)
        return simple_builder(_summary, _next, dtend, _location)


def parse_event(event):
    """
    helper function to parse an event into simple form
    """
    summary = event.decoded('summary').decode('UTF-8')
    start = event.decoded('dtstart')
    end = event.decoded('dtend')
    location = parse_location(event)
    return simple_builder(summary, start, end, location)


def simple_builder(summary, start, end, location):
    """
    helper function builds simple dictionary
    """
    return {
        'summary': summary,
        'dtstart': start,
        'dtend': end,
        'location': location
    }


def set_status(token, profile):
    params = {
        'token': token,
        'profile': json.dumps(profile)
    }
    response = requests.post("https://slack.com/api/users.profile.set", params=params)
    response.raise_for_status()
    return response.json()['ok'] == True, response.json()


def today_at(hour):
    """
    Creates a datetime object for today in UTC at hour (in military time) in the
    current timezone.
    For example today_at(17) would give you a datetime object in UTC
    that represents 5pm today in the current timezone.
    """
    result_naive = datetime.datetime.combine(datetime.date.today(), datetime.time(hour, 0))
    tz = pytz.timezone('America/Denver')
    utc_dt = tz.localize(result_naive, is_dst=None).astimezone(pytz.utc)
    return utc_dt


def date_to_datetime(date):
    """
    helper function to handle converting date to datetime with tzinfo
    default to 2pm utc time == 8 or 9 am mountain
    """
    _result = datetime.datetime(date.year, date.month, date.day, 14, 00)
    _result = pytz.utc.localize(_result)
    return _result


def test(verbose=False):
    import doctest
    doctest.testmod(verbose=verbose)


def get_new_status(calendar_url):
    events = get_today_events(calendar_url)
    now = pytz.utc.localize(datetime.datetime.now())
    for event in events:
        if now >= event['dtstart'] and now < event['dtend']:
            logger.debug(f"{event} matched")
            if not event['location'].strip():
                location = 'likely at my desk'
            else:
                location = 'in ' + event['location']
            return {
                # need to truncate the status to at most 100 characters as that's the max the users.profile.set API allows
                'status_text': "{} {}".format(textwrap.shorten(event['summary'], 100-1-len(location)), location),
                'status_emoji': ':calendar:'
            }
        else:
            logger.debug(f"{event} did not match")
    if now >= today_at(9) and now < today_at(17): # Everyone is generally here from 9am to 4pm
        working_default = {
            'status_text': 'Probably working hard at my desk',
            'status_emoji': ':computer_rage:'
        }
        logger.info(f"During working hours.  Using working default {working_default}")
        return working_default
    else:
        non_working_hours_default = {
            'status_text': '',
            'status_emoji': ''
        }
        logger.info(f"Not working hours.  Using the non working hours default {non_working_hours_default}")
        return non_working_hours_default


def handler(event, context):
    if 'loglevel' in event:
        if event['loglevel'] in ['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            logger.setLevel(event['loglevel'])
    configs = get_config_objects()
    for config in configs:
        try:
            profile = get_new_status(config['calendar_url'])
            logger.info("Setting {}'s status to {}".format(config['net_id'], profile))
            status_set, detail = set_status(config['token'], profile)
            if not status_set:
                logger.error("Error setting {}'s status.  Details are: {}".format(config['net_id'], detail))
            else:
                logger.info("Set {}'s status successfully".format(config['net_id']))
        except Exception as e:
            logger.error("Exception raised while trying to set {}'s status.  Exeption was {}".format(config['net_id'], repr(e)))


if __name__ == '__main__':
    fire.Fire()
