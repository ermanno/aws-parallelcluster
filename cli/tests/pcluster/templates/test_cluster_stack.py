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

import json

import pytest
import yaml
from assertpy import assert_that
from freezegun import freeze_time

from pcluster.schemas.cluster_schema import ClusterSchema
from pcluster.templates.cdk_builder import CDKTemplateBuilder
from pcluster.utils import load_json_dict, load_yaml_dict
from tests.pcluster.aws.dummy_aws_api import mock_aws_api
from tests.pcluster.models.dummy_s3_bucket import dummy_cluster_bucket, mock_bucket
from tests.pcluster.utils import load_cluster_model_from_yaml


@pytest.mark.parametrize(
    "config_file_name",
    [
        "slurm.required.yaml",
        "slurm.full.yaml",
        "awsbatch.simple.yaml",
        "awsbatch.full.yaml",
        "byos.required.yaml",
        "byos.full.yaml",
    ],
)
def test_cluster_builder_from_configuration_file(mocker, config_file_name):
    mock_aws_api(mocker)
    # mock bucket initialization parameters
    mock_bucket(mocker)
    input_yaml, cluster = load_cluster_model_from_yaml(config_file_name)
    generated_template = CDKTemplateBuilder().build_cluster_template(
        cluster_config=cluster, bucket=dummy_cluster_bucket(), stack_name="clustername"
    )
    print(yaml.dump(generated_template))


def test_byos_substack(mocker):
    mock_aws_api(mocker)
    # mock bucket initialization parameters
    mock_bucket(mocker)
    input_yaml, cluster = load_cluster_model_from_yaml("byos.full.yaml")
    generated_template = CDKTemplateBuilder().build_cluster_template(
        cluster_config=cluster, bucket=dummy_cluster_bucket(), stack_name="clustername"
    )
    print(yaml.dump(generated_template))
    assert_that(generated_template["Resources"]["ByosStack"]).is_equal_to(
        {
            "Type": "AWS::CloudFormation::Stack",
            "Properties": {
                "TemplateURL": "https://parallelcluster-a69601b5ee1fc2f2-v1-do-not-delete.s3.fake-region.amazonaws.com"
                "/parallelcluster/clusters/dummy-cluster-randomstring123/templates/byos-substack.cfn",
                "Parameters": {
                    "ClusterName": "clustername",
                    "ParallelClusterStackId": {"Ref": "AWS::StackId"},
                    "VpcId": "vpc-123",
                    "HeadNodeRoleName": "",
                    "ComputeFleetRoleNames": {"Fn::Join": ["", [{"Ref": "Role15b342af42246b70"}, ","]]},
                    "queue1-compute-resource-1-LTVersion": {
                        "Fn::GetAtt": ["ComputeFleetLaunchTemplate396a2157454c4981E9D46761", "LatestVersionNumber"]
                    },
                    "queue1-compute-resource-2-LTVersion": {
                        "Fn::GetAtt": ["ComputeFleetLaunchTemplate5275f50b77308d66FBA4CCEB", "LatestVersionNumber"]
                    },
                    "queue2-compute-resource-1-LTVersion": {
                        "Fn::GetAtt": ["ComputeFleetLaunchTemplate73e56110dc1f92a468DDBA65", "LatestVersionNumber"]
                    },
                    "queue2-compute-resource-2-LTVersion": {
                        "Fn::GetAtt": ["ComputeFleetLaunchTemplate4e6f582fd35bda115FD3E5B9", "LatestVersionNumber"]
                    },
                },
            },
        }
    )


@pytest.mark.parametrize(
    "config_file_name, expected_head_node_dna_json_file_name",
    [
        ("slurm-imds-secured-true.yaml", "slurm-imds-secured-true.head-node.dna.json"),
        ("slurm-imds-secured-false.yaml", "slurm-imds-secured-false.head-node.dna.json"),
        ("awsbatch-imds-secured-false.yaml", "awsbatch-imds-secured-false.head-node.dna.json"),
        ("byos-imds-secured-true.yaml", "byos-imds-secured-true.head-node.dna.json"),
    ],
)
# Datetime mocking is required because some template values depend on the current datetime value
@freeze_time("2021-01-01T01:01:01")
def test_head_node_dna_json(mocker, test_datadir, config_file_name, expected_head_node_dna_json_file_name):
    mock_aws_api(mocker)

    input_yaml = load_yaml_dict(test_datadir / config_file_name)

    cluster_config = ClusterSchema(cluster_name="clustername").load(input_yaml)

    generated_template = CDKTemplateBuilder().build_cluster_template(
        cluster_config=cluster_config, bucket=dummy_cluster_bucket(), stack_name="clustername"
    )

    generated_head_node_dna_json = json.loads(
        _get_cfn_init_file_content(template=generated_template, resource="HeadNodeLaunchTemplate", file="/tmp/dna.json")
    )
    expected_head_node_dna_json = load_json_dict(test_datadir / expected_head_node_dna_json_file_name)

    assert_that(generated_head_node_dna_json).is_equal_to(expected_head_node_dna_json)


def _get_cfn_init_file_content(template, resource, file):
    cfn_init = template["Resources"][resource]["Metadata"]["AWS::CloudFormation::Init"]
    content_join = cfn_init["deployConfigFiles"]["files"][file]["content"]["Fn::Join"]
    content_separator = content_join[0]
    content_elements = content_join[1]
    return content_separator.join(str(elem) for elem in content_elements)
