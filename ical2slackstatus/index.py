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
import re
import fire
import yaml
import json
import pytz
import boto3
import random
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
bucketname = os.environ.get('S3_ICAL2SLACKSTATUS_PRD_CONFIGBUCKET_BUCKET_NAME')


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
    _today_events = clean_recurring_occurances(_today_events)
    return _today_events


def clean_recurring_occurances(events):
    """
    Takes all events for a day and splits them into two lists recurring and not recurring
    if duplicate UID exists in not_recur and recur it is removed from recur
    """
    recur = [event for event in events if event['recur']]
    not_recur = [event for event in events if not event['recur']]

    for x in not_recur:
        recur[:] = [event for event in recur if event['uid'] != x['uid']]
    return recur + not_recur


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
    now = pytz.utc.localize(datetime.datetime.utcnow())
    yesterday = now - one_day
    duration = event.get('dtstart').dt - event.get('dtend').dt
    rule = get_rrule(event)
    _next = rule.after(yesterday)
    if _next and _next.date() == now.date():
        dtend = _next - duration
        return parse_event(event, _next, dtend, True)


def parse_event(event, dtstart=None, dtend=None, recur=False):
    """
    helper function to parse an event into simple form
    """
    emoji, summary = emoji_from_summary(event.decoded('summary').decode('UTF-8'))

    return {
        'summary': summary,
        'dtstart': dtstart or event.decoded('dtstart'),
        'dtend': dtend or event.decoded('dtend'),
        'location': parse_location(event),
        'status': event.decoded('X-MICROSOFT-CDO-BUSYSTATUS').decode('UTF-8'),
        'emoji': emoji,
        'uid': event.decoded('uid').decode('UTF-8'),
        'recur': recur
    }


def emoji_from_summary(summary):
    m = re.match(r"^(.*)(:[a-z_]+:)(.*)$", summary, re.IGNORECASE)
    if m:
        new_summary = (m.group(1).strip() + ' ' + m.group(3).strip()).strip()
        return m.group(2), new_summary
    else:
        return None, summary


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


def get_new_status(calendar_url):
    events = get_today_events(calendar_url)
    now = pytz.utc.localize(datetime.datetime.now())
    return get_status_for_time(events, now)


def default_emoji():
    """
    Randomly pick between a set of default emojis
    """
    default_emojis = [':calendar:', ':date:', ':spiral_calendar_pod:',
    ':man_in_business_suit_levitating:', ':post_office:',
    ':european_post_office:', ':computer:', ':watch:', ':keyboard:',
    ':desktop_computer:']
    return random.choice(default_emojis)


def get_status_for_time(events, now):
    for event in events:
        if now >= event['dtstart'] and now < event['dtend']:
            logger.debug(f"{event} matched")
            if not event['location'].strip():
                if event['status'] == "OOF":
                    location = 'out of office'
                else:
                    location = 'likely at my desk'
            else:
                location = 'in ' + event['location']
            return {
                # need to truncate the status to at most 100 characters as that's the max the users.profile.set API allows
                'status_text': "{} {}".format(textwrap.shorten(event['summary'], 100-1-len(location)), location),
                'status_emoji': event['emoji'] or default_emoji()
            }
        else:
            logger.debug(f"{event} did not match")
    if now >= today_at(9) and now < today_at(17):
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
        if event['loglevel'].upper() in ['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            logger.setLevel(event['loglevel'].upper())
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
            logger.error("Exeption raised while trying to set {}'s status.  Exeption was {}".format(config['net_id'], repr(e)))


if __name__ == '__main__':
    fire.Fire()
