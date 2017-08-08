import os
os.environ['S3_ICAL2SLACKSTATUS_PRD_CONFIGBUCKET_BUCKET_NAME'] = "MyFakeNonexistentBucket"

from unittest.mock import patch, MagicMock

from ical2slackstatus.index import handler

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