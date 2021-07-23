from datetime import date
import os
import boto3
import json


def lambda_handler(event, context):
    terminationFlag = "N"
    current_day = date.today()
    formatted_date = date.strftime(current_day, "%m-%d-%Y")
    today = str(formatted_date)
    REGION = "us-east-1"
    # To filter the instances that are ready for retirement based on tags
    ec2 = boto3.client("ec2", region_name=REGION)
    retired_instances = ec2.describe_instances(
        Filters=[
            {"Name": "instance-state-name", "Values": ["stopped"]},
            {"Name": "tag:termination-reason", "Values": ["ec2-retire"]},
        ]
    )
    instance_ids = []
    volume_id_list = []
    # To change delete on termination on ebs volumes to True if the Termination date is today
    for reservation in retired_instances["Reservations"]:
        for instance in reservation["Instances"]:
            instance_ids.append(instance["InstanceId"])
    for instance in instance_ids:
        volume_detail = ec2.describe_instance_attribute(
            InstanceId=instance, Attribute="blockDeviceMapping"
        )
        InstanceTags = ec2.describe_tags(
            Filters=[
                {"Name": "resource-id", "Values": [instance]},
                {"Name": "tag:termination-date", "Values": ["*"]},
            ]
        )
        TerminationDate = InstanceTags["Tags"][0]["Value"]
        if TerminationDate == today:
            for volume in volume_detail["BlockDeviceMappings"]:
                device_name = volume["DeviceName"]
                vol_id = volume["Ebs"]["VolumeId"]
                terminationFlag = "Y"
                ec2.modify_instance_attribute(
                    InstanceId=instance,
                    Attribute='blockDeviceMapping',
                    BlockDeviceMappings=[
                        {
                            "DeviceName": device_name,
                            "Ebs": {"DeleteOnTermination": True, "VolumeId": vol_id},
                        },
                    ],
                )
        # Disabling in Termination protection and Terminating the instance
        if terminationFlag == "Y" and TerminationDate == today:
            ec2.modify_instance_attribute(
                    InstanceId=instance,
                    DisableApiTermination={
                        "Value": False
                    }
                )
            print("Terminating", instance)
            terminate_instance = ec2.terminate_instances(InstanceIds=[instance])

    # return
