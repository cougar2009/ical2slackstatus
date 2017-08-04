import os
os.environ['S3_ICAL2SLACKSTATUS_PRD_CONFIGBUCKET_BUCKET_NAME'] = "MyFakeNonexistentBucket"

from unittest.mock import patch, MagicMock

from ical2slackstatus.index import handler

@patch('ical2slackstatus.index.boto3')
def test_handler(boto3_mock):
    boto3_mock.client.return_value = MagicMock()
    handler({}, {})
    del os.environ['S3_ICAL2SLACKSTATUS_PRD_CONFIGBUCKET_BUCKET_NAME']