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

import boto3
import os


def get_parameters(app, stage, parameter_names):
    parameters = {}
    client = boto3.client('ssm')
    names = ['{}.{}.{}'.format(app, stage, param) for param in parameter_names]
    response = client.get_parameters(Names=names, WithDecryption=True)
    if response['InvalidParameters']:
        print('Invalid parameters: {}'.format(response['InvalidParameters']))
        raise KeyError()
    trim_length = len('{}.{}.'.format(app, stage))
    return {parameter['Name'][trim_length:]: parameter['Value']
        for parameter in response['Parameters']}

app_name = os.environ['HANDEL_APP_NAME']
app_stage = os.environ['HANDEL_ENVIRONMENT_NAME']
parameters = get_parameters(app_name, app_stage, [
    'client_id',
    'client_secret'])