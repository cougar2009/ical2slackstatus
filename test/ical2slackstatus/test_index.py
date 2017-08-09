import os
import pytz
from unittest.mock import patch, MagicMock
os.environ['S3_ICAL2SLACKSTATUS_PRD_CONFIGBUCKET_BUCKET_NAME'] = "MyFakeNonexistentBucket"
from ical2slackstatus.index import handler, today_at

@patch('ical2slackstatus.index.boto3')
def test_handler(boto3_mock):
    mock_s3_client = boto3_mock.client.return_value = MagicMock()
    mock_s3_resource = boto3_mock.resource.return_value = MagicMock()

    list_bucket_mock = MagicMock(objects={

    })
    mock_s3_resource.Bucket.side_effect = [list_bucket_mock]

    get_object_mock = MagicMock(body="")
    mock_s3_client.get_object.side_effect = [get_object_mock]
    handler({}, {})
    del os.environ['S3_ICAL2SLACKSTATUS_PRD_CONFIGBUCKET_BUCKET_NAME']

def test_today_at():
    seven_am = today_at(7)
    import datetime
    assert seven_am.tzinfo
    assert seven_am.tzinfo == pytz.utc
    assert seven_am.hour > 7