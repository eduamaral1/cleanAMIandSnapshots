import boto3
from datetime import timedelta, datetime, timezone
import logging
import botocore

# Intialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    '''Clean AMIs and its associated SnapShots which are older than 90 Days and without "Retention=Y" tag in a AWS Region
    Exempt AMI which is currently being used in AWS Launch Config'''

    ec2 = boto3.client('ec2')
    autoscaling = boto3.client('autoscaling')
    ami_response = ec2.describe_images(Owners=['self'])
    snapshot_response = ec2.describe_snapshots(OwnerIds=['self'])
    lc_response = autoscaling.describe_launch_configurations()
    amis = {}
    amidnd = []
    for i in ami_response['Images']:
        for tag in i.get('Tags', ''):
            if tag['Key'] == 'Retention' and tag['Value'] == 'Y' in tag.values():
                amidnd.append(i.get('ImageId'))
                break

    for ami in lc_response['LaunchConfigurations']:
        if ami['ImageId'] not in amidnd:
            amidnd.append(ami['ImageId'])
    for i in ami_response['Images']:
        if i.get('Tags') == None or i['ImageId'] not in amidnd:
            amis[i.get('ImageId')] = i.get('CreationDate')
    if not amis:
        logger.info('No AMIs and SnapShots found to be deregister')
    else:
        for ami, cdate in amis.items():
            if cdate < (datetime.now(timezone.utc)-timedelta(minutes=0)).isoformat():
                logger.info('De-registering...'+ami)
                ec2.deregister_image(ImageId=ami)
                for snapshot in snapshot_response['Snapshots']:
                    if ami in snapshot.get('Description', ''):
                        logger.info(
                            'Deleting '+snapshot.get('SnapshotId') + "of "+ami)
                        ec2.delete_snapshot(
                            SnapshotId=snapshot.get('SnapshotId'))
            continue

    abandon_snap_clean(ami_response, snapshot_response)


def abandon_snap_clean(ami_response, snapshot_response):
    '''Clean abandon ebs snapshots of which no AMI has been found'''
    ec2 = boto3.client('ec2')
    snapdndids = []
    for i in ami_response['Images']:
        for snap in i['BlockDeviceMappings']:
            if 'Ebs' in snap.keys():
                snapdndids.append(snap['Ebs']['SnapshotId'])
    for snapid in snapshot_response['Snapshots']:
        if snapid['SnapshotId'] not in snapdndids:
            try:
                logger.info('Deleting abandon snapshots '+snapid['SnapshotId'])
                ec2.delete_snapshot(SnapshotId=snapid['SnapshotId'])
            except botocore.exceptions.ClientError as error:
                if error.response['Error']['Code'] == 'InvalidSnapshot.InUse':
                    logger.info(
                        'SnapshotId '+snapid['SnapshotId']+' is already being used by an AMI')
                else:
                    raise error
        else:
            logger.info('No abandon EBS SnapShots found to clean up')
            continue
    else:
        logger.info('No SnapShots found')
