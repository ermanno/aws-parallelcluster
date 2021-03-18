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
import logging
import os

from packaging import version

from common.aws.aws_api import AWSApi
from pcluster.cli_commands.compute_fleet_status_manager import ComputeFleetStatus
from pcluster.models.cluster import Cluster, ClusterActionError, ClusterStack
from pcluster.models.imagebuilder import ImageBuilder, ImageBuilderActionError
from pcluster.utils import get_installed_version, get_region
from pcluster.validators.common import FailureLevel

LOGGER = logging.getLogger(__name__)


class ApiFailure:
    """Represent a generic api error."""

    def __init__(self, message: str = None, validation_failures: list = None):
        self.message = message or "Something went wrong."
        self.validation_failures = validation_failures or []


class ClusterInfo:
    """Representation of a running cluster."""

    def __init__(self, stack: ClusterStack, cluster: Cluster = None):
        # Cluster info
        self.name = stack.cluster_name
        self.region = get_region()
        self.version = stack.version
        self.scheduler = stack.scheduler
        self.status = stack.status  # FIXME cluster status should be different from stack status

        # Stack info
        self.stack_arn = stack.id
        self.stack_name = stack.name
        self.stack_status = stack.status
        self.stack_outputs = stack.outputs
        if stack.is_working_status:
            self.head_node_ip = stack.head_node_ip
            self.user = stack.head_node_user

        # Add information from running resources. Config file is required.
        self.head_node = None
        self.compute_instances = None
        if cluster:
            if stack.is_working_status:
                self.head_node = cluster.head_node_instance
            self.compute_instances = cluster.compute_instances

    def __repr__(self):
        return json.dumps(self.__dict__)


class ImageInfo:
    """Minimal representation of a building image."""

    def __init__(self, imagebuilder: ImageBuilder):
        self.image_name = imagebuilder.stack.name
        self.imagebuild_status = imagebuilder.imagebuild_status
        self.stack_status = imagebuilder.stack.status
        self.stack_arn = imagebuilder.stack.id
        self.region = get_region()
        self.version = imagebuilder.stack.version

    def __repr__(self):
        return json.dumps(self.__dict__)


class PclusterApi:
    """Proxy class for all Pcluster API commands used in the CLI."""

    def __init__(self):
        pass

    @staticmethod
    def create_cluster(
        cluster_config: dict,
        cluster_name: str,
        region: str,
        disable_rollback: bool = False,
        suppress_validators: bool = False,
        validation_failure_level: FailureLevel = None,
    ):
        """
        Load cluster model from cluster_config and create stack.

        :param cluster_config: cluster configuration (yaml dict)
        :param cluster_name: the name to assign to the cluster
        :param region: AWS region
        :param disable_rollback: Disable rollback in case of failures
        :param suppress_validators: Disable validator execution
        :param validation_failure_level: Min validation level that will cause the creation to fail
        """
        try:
            # Generate model from config dict and validate
            if region:
                os.environ["AWS_DEFAULT_REGION"] = region
            cluster = Cluster(cluster_name, cluster_config)
            cluster.create(disable_rollback, suppress_validators, validation_failure_level)
            return ClusterInfo(cluster.stack)
        except ClusterActionError as e:
            return ApiFailure(str(e), e.validation_failures)
        except Exception as e:
            return ApiFailure(str(e))

    @staticmethod
    def delete_cluster(cluster_name: str, region: str, keep_logs: bool = True):
        """Delete cluster."""
        try:
            if region:
                os.environ["AWS_DEFAULT_REGION"] = region
            # retrieve cluster config and generate model
            cluster = Cluster(cluster_name)
            cluster.delete(keep_logs)
            return ClusterInfo(cluster.stack, cluster)
        except Exception as e:
            return ApiFailure(str(e))

    @staticmethod
    def describe_cluster(cluster_name: str, region: str):
        """Get cluster information."""
        try:
            if region:
                os.environ["AWS_DEFAULT_REGION"] = region

            cluster = Cluster(cluster_name)
            return ClusterInfo(cluster.stack, cluster)
        except Exception as e:
            return ApiFailure(str(e))

    @staticmethod
    def update_cluster(cluster_name: str, region: str):
        """Update existing cluster."""
        try:
            if region:
                os.environ["AWS_DEFAULT_REGION"] = region
            # Check if stack version matches with running version.
            cluster = Cluster(cluster_name)

            installed_version = get_installed_version()
            if cluster.stack.version != installed_version:
                raise ClusterActionError(
                    "The cluster was created with a different version of "
                    f"ParallelCluster: {cluster.stack.version}. Installed version is {installed_version}. "
                    "This operation may only be performed using the same ParallelCluster "
                    "version used to create the cluster."
                )
            return ClusterInfo(cluster.stack, cluster)
        except Exception as e:
            return ApiFailure(str(e))

    @staticmethod
    def list_clusters(region: str):
        """List existing clusters."""
        try:
            if region:
                os.environ["AWS_DEFAULT_REGION"] = region

            stacks = AWSApi.instance().cfn.list_pcluster_stacks()
            return [ClusterInfo(ClusterStack(stack)) for stack in stacks]

        except Exception as e:
            return ApiFailure(str(e))

    @staticmethod
    def update_compute_fleet_status(cluster_name: str, region: str, status: ComputeFleetStatus):
        """Update existing compute fleet status."""
        try:
            if region:
                os.environ["AWS_DEFAULT_REGION"] = region

            cluster = Cluster(cluster_name)
            if PclusterApi._is_version_2(cluster):
                raise ClusterActionError(
                    f"The cluster {cluster.name} was created with ParallelCluster {cluster.stack.version}. "
                    "This operation may only be performed using the same version used to create the cluster."
                )
            if status == ComputeFleetStatus.START_REQUESTED:
                cluster.start()
            elif status == ComputeFleetStatus.STOP_REQUESTED:
                cluster.stop()
            else:
                return ApiFailure(f"Unable to update the compute fleet to status {status}. Not supported.")

        except Exception as e:
            return ApiFailure(str(e))

    @staticmethod
    def _is_version_2(cluster):
        return version.parse(cluster.stack.version) < version.parse("3.0.0")

    @staticmethod
    def build_image(imagebuilder_config: dict, image_name: str, region: str, disable_rollback: bool = True):
        """
        Load imagebuilder model from imagebuilder_config and create stack.

        :param imagebuilder_config: imagebuilder configuration (yaml dict)
        :param image_name: the image name(the same as cfn stack name)
        :param region: AWS region
        :param disable_rollback: Disable rollback in case of failures
        """
        try:
            # Generate model from imagebuilder config dict
            if region:
                os.environ["AWS_DEFAULT_REGION"] = region
            imagebuilder = ImageBuilder(image_name, imagebuilder_config)
            imagebuilder.create(disable_rollback)
            return ImageInfo(imagebuilder)
        except ImageBuilderActionError as e:
            return ApiFailure(str(e), e.validation_failures)
        except Exception as e:
            return ApiFailure(str(e))