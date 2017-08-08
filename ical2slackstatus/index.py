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
import datetime
import requests
import urllib.request
from icalendar import Calendar

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
        if event.decoded('dtstart').__class__ == datetime.date:
            if event.decoded('dtstart') == today:
                _today_events.append(event)
        elif event.decoded('dtstart').__class__ == datetime.datetime:
            if event.decoded('dtstart').date() == today:
                _today_events.append(event)
    return [parse_event(event) for event in _today_events]


def parse_event(event):
    location = ''
    if event.get('location'):
        location = event.decoded('location').decode('UTF-8')
    return {
        'summary': event.decoded('summary').decode('UTF-8'),
        'dtstart': event.decoded('dtstart'),
        'dtend': event.decoded('dtend'),
        'location': location
    }


def set_status(token, profile):
    params = {
        'token': token,
        'profile': json.dumps(profile)
    }
    response = requests.post("https://slack.com/api/users.profile.set", params=params)
    response.raise_for_status()
    return response.json()['ok'] == True


def test(verbose=False):
    import doctest
    doctest.testmod(verbose=verbose)

def get_new_status(calendar_url):
    events = get_today_events(calendar_url)
    now = pytz.utc.localize(datetime.datetime.now())
    for event in events:
        if now >= event['dtstart'] and now < event['dtend']:
            if not event['location'].strip():
                location = 'at my desk'
            else:
                location = 'in ' + event['location']
            return {
                'status_text': "{} {}".format(event['summary'], location),
                'status_emoji': ':calendar:'
            }
    return {
        'status_text': '',
        'status_emoji': ''
    }

def handler(event, context):
    configs = get_config_objects()
    for config in configs:
        profile = get_new_status(config['calendar_url'])
        set_status(config['token'], profile)


if __name__ == '__main__':
    fire.Fire()
