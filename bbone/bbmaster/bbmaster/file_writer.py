import os
import boto3
from botocore.exceptions import ClientError
from six.moves.configparser import ConfigParser
from bbcommon import constants

class FileWriter:
    """ Implementation of interfaces to do file upload """
    def __init__(self, log):
        """
        Constructor
        :param log: Logger to be used
        """
        self.log = log


class FileWriterS3(FileWriter):
    """ Implementation of interfaces to do file upload to S3 buckets"""
    def __init__(self, log=None):
        """
        Constructor
        :param log: Logger to be used
        """

        FileWriter.__init__(self, log=log)
        self.aws_info_available, self.bucket, self.region, self.access_key, self.secret_key = self._get_aws_info()

    def _get_aws_info(self):
        config = ConfigParser()
        bbmaster_conf = os.environ.get('BBMASTER_CONFIG_FILE',
                                       constants.BBMASTER_CONFIG_FILE)
        config.read(bbmaster_conf)
        bucket_name = ""
        region_name = ""
        aws_key_id = ""
        aws_secret_key = ""
        try:
            bucket_name = config.get('aws', 's3_bucket_name')
            region_name = config.get('aws', 's3_region_name')
            aws_key_id = config.get('aws', 'aws_access_key_id')
            aws_secret_key = config.get('aws', 'aws_secret_access_key')
            aws_info_available = True
        except Exception:
            aws_info_available = False

        return aws_info_available, bucket_name, region_name, aws_key_id, aws_secret_key


    def upload(self, file_to_upload, dst_path=None):
        """
        :param file_to_upload : File to be backed up.
        :param dst_path       : Destination path in S3
        """

        if not self.aws_info_available:
            self.log.info('AWS info is not available, File upload failed !')
            return

        # Upload the file with same name if destination path is not available.
        if dst_path is None:
            dst_path = file_to_upload

        s3_client = boto3.client('s3', aws_access_key_id=self.access_key,
             aws_secret_access_key=self.secret_key, region_name=self.region)
        try:
            response = s3_client.upload_file(file_to_upload, self.bucket, dst_path)
        except ClientError as e:
            self.log.error('Error Code: %s, Error Msg: %s',
                           e.errorCode, e.errorMsg)
        self.log.info('File %s uploaded to S3 bucket %s region %s. S3 destination path %s',
                       file_to_upload, self.bucket, self.region, dst_path)
