import datetime
import dateutil.rrule
import os
import pytz
import pytest
from ical2slackstatus import index
from icalendar import Event, vRecur, vDatetime
from unittest.mock import patch, MagicMock

os.environ['S3_ICAL2SLACKSTATUS_PRD_CONFIGBUCKET_BUCKET_NAME'] = "MyFakeNonexistentBucket"


@pytest.fixture
def recur_event():
    event = Event()
    LOCAL = pytz.timezone('America/Denver')
    _now = LOCAL.localize(datetime.datetime.now())
    _then = _now - datetime.timedelta(hours=1)
    event.add('RRULE', vRecur.from_ical('FREQ=DAILY;UNTIL=20190810T153000Z;INTERVAL=1'))
    event.add('dtstart', _now)
    event.add('dtend', _then)
    event.add('summary', 'FakeEvent')
    event.add('location', 'FakeLocation')
    return event

@pytest.mark.skip
@patch('ical2slackstatus.index.boto3')
def test_handler(boto3_mock):
    mock_s3_client = boto3_mock.client.return_value = MagicMock()
    mock_s3_resource = boto3_mock.resource.return_value = MagicMock()

    list_bucket_mock = MagicMock(objects={

    })
    mock_s3_resource.Bucket.side_effect = [list_bucket_mock]

    get_object_mock = MagicMock(body="")
    mock_s3_client.get_object.side_effect = [get_object_mock]
    index.handler({}, {})
    del os.environ['S3_ICAL2SLACKSTATUS_PRD_CONFIGBUCKET_BUCKET_NAME']


def test_today_at():
    seven_am = index.today_at(7)
    assert seven_am.tzinfo
    assert seven_am.tzinfo == pytz.utc
    assert seven_am.hour > 7


def test_parse_location(recur_event):
    assert index.parse_location(recur_event) == 'FakeLocation'


def test_get_rrule(recur_event):
    rule = index.get_rrule(recur_event)
    assert rule.__class__ == dateutil.rrule.rrule


def test_recurring_parser(recur_event):
    result = index.recurring_parser(recur_event)
    assert result['summary'] == 'FakeEvent'


def test_parse_event(recur_event):
    result = index.parse_event(recur_event)
    assert result['summary'] == 'FakeEvent'


def test_simple_builder():
    _now = datetime.datetime.now()
    test = {
        'summary': "FakeSummary",
        'dtstart': _now,
        'dtend': _now,
        'location': "FakeLocation"
    }

    result = index.simple_builder(test['summary'], test['dtstart'], test['dtend'], test['location'])
    assert result == test


def test_date_to_datetime():
    to_convert = datetime.datetime.utcnow().date()
    expected_result = pytz.utc.localize(datetime.datetime(to_convert.year, to_convert.month, to_convert.day, 14, 00))
    result = index.date_to_datetime(to_convert)
    assert result == expected_result
