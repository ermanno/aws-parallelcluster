# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance
# with the License. A copy of the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "LICENSE.txt" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES
# OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and
# limitations under the License.

import yaml

from pcluster.templates.cdk_builder import CDKTemplateBuilder
from tests.common.dummy_aws_api import mock_aws_api

from ..models.cluster_dummy_model import dummy_awsbatch_cluster_config, dummy_bucket, dummy_slurm_cluster_config


def test_slurm_cluster_builder(mocker):
    mock_aws_api()
    generated_template = CDKTemplateBuilder().build_cluster_template(
        cluster_config=dummy_slurm_cluster_config(mocker),
        bucket=dummy_bucket(),
        stack_name="parallelcluster-dummyname",
    )
    print(yaml.dump(generated_template))
    # TODO assert content of the template by matching expected template


def test_awsbatch_cluster_builder(mocker):
    mock_aws_api()
    generated_template = CDKTemplateBuilder().build_cluster_template(
        cluster_config=dummy_awsbatch_cluster_config(mocker),
        bucket=dummy_bucket(),
        stack_name="parallelcluster-dummyname",
    )
    print(yaml.dump(generated_template))
    # TODO assert content of the template by matching expected template