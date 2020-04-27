import boto3
from botocore.exceptions import ClientError

class FileWriter:
    """ Implementation of interfaces to do file upload """
    def __init__(self, log):
        """
        Constructor
        :param log: Logger to be used
        """
        self.log = log


# TODO : Fill these up for testing. Will be removed once
# devops defines a way to fetch them.
BUCKET_NAME = ""
REGION_NAME = ""
AWS_KEY_ID = ""
AWS_SECRET_KEY = ""

class FileWriterS3(FileWriter):
    """ Implementation of interfaces to do file upload to S3 buckets"""
    def __init__(self, log=None):
        """
        Constructor
        :param log: Logger to be used
        """

        FileWriter.__init__(self, log=log)
        self.bucket, self.region = self._get_bucket_info()
        self.access_key, self.secret_key = self._get_keys()

    # TODO: Implement these once devops define a way to fetch bucket info
    def _get_bucket_info(self):
        return BUCKET_NAME, REGION_NAME

    # TODO: Implement these once devops define a way to fetch aws credentials
    def _get_keys(self):
        return AWS_KEY_ID, AWS_SECRET_KEY

    def upload(self, file_to_upload, dst_path=None):
        """
        :param file_to_upload : File to be backed up.
        :param dst_path       : Destination path in S3
        """

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
