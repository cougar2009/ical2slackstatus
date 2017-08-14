import datetime
import dateutil.rrule
import pytz
import pytest
from ical2slackstatus import index
from icalendar import Event, vRecur
from unittest.mock import patch, MagicMock


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
    event.add('X-MICROSOFT-CDO-BUSYSTATUS', 'OOF')
    return event


@pytest.fixture
def simple_event():
    _now = pytz.utc.localize(datetime.datetime.utcnow())
    _later = _now + datetime.timedelta(hours=1)
    return {
        'summary': 'FakeEvent',
        'dtstart': _now,
        'dtend': _later,
        'location': '',
        'status': 'OOF',
        'emoji': None
    }


@patch('ical2slackstatus.index.boto3')
def test_handler(boto3_mock):
    index.bucketname = "MyFakeNonexistentBucket"
    mock_s3_client = boto3_mock.client.return_value = MagicMock()
    mock_s3_resource = boto3_mock.resource.return_value = MagicMock()

    list_bucket_mock = MagicMock()
    mock_s3_resource.Bucket.side_effect = [list_bucket_mock]

    get_object_mock = MagicMock(body="")
    mock_s3_client.get_object.side_effect = [get_object_mock]
    index.handler({}, {})


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
        'location': "FakeLocation",
        'status': 'OOF',
        'emoji': None
    }

    result = index.simple_builder(test['summary'], test['dtstart'], test['dtend'], test['location'], test['status'])
    assert result == test

def test_emoji_at_start_of_summary():
    emoji, summary = index.emoji_from_summary(":some_emoji: Some Summary")
    assert emoji == ":some_emoji:"
    assert summary == "Some Summary"

def test_emoji_at_middle_of_summary():
    emoji, summary = index.emoji_from_summary("Some :some_emoji: Summary")
    assert emoji == ":some_emoji:"
    assert summary == "Some Summary"

def test_emoji_at_end_of_summary():
    emoji, summary = index.emoji_from_summary("Some Summary :some_emoji:")
    assert emoji == ":some_emoji:"
    assert summary == "Some Summary"

def test_no_emoji_in_summary():
    emoji, summary = index.emoji_from_summary("Some Summary")
    assert emoji == None
    assert summary == "Some Summary"

def test_date_to_datetime():
    to_convert = datetime.datetime.utcnow().date()
    expected_result = pytz.utc.localize(datetime.datetime(to_convert.year, to_convert.month, to_convert.day, 14, 00))
    result = index.date_to_datetime(to_convert)
    assert result == expected_result


def test_get_status_for_time_out_of_office_no_location(simple_event):
    now = pytz.utc.localize(datetime.datetime.utcnow())
    result = index.get_status_for_time([simple_event], now)
    assert result['status_text'] == 'FakeEvent out of office'


def test_get_status_for_time_out_of_office_location(simple_event):
    now = pytz.utc.localize(datetime.datetime.utcnow())
    simple_event['location'] = 'FakeLocation'
    result = index.get_status_for_time([simple_event], now)
    assert result['status_text'] == 'FakeEvent in FakeLocation'


def test_get_status_for_time_not_out_of_office_no_location(simple_event):
    now = pytz.utc.localize(datetime.datetime.utcnow())
    simple_event['status'] = 'BUSY'
    result = index.get_status_for_time([simple_event], now)
    assert result['status_text'] == 'FakeEvent likely at my desk'


def test_get_status_for_time_not_out_of_office_location(simple_event):
    now = pytz.utc.localize(datetime.datetime.utcnow())
    simple_event['status'] = 'BUSY'
    simple_event['location'] = 'FakeLocation'
    result = index.get_status_for_time([simple_event], now)
    assert result['status_text'] == 'FakeEvent in FakeLocation'


def test_get_status_default_emoji(simple_event):
    now = pytz.utc.localize(datetime.datetime.utcnow())
    result = index.get_status_for_time([simple_event], now)
    assert result['status_emoji'] == ':calendar:'


def test_get_status_manual_emoji(simple_event):
    now = pytz.utc.localize(datetime.datetime.utcnow())
    simple_event['emoji'] = ':test:'
    result = index.get_status_for_time([simple_event], now)
    assert result['status_emoji'] == ':test:'
