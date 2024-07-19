# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
Module that builds a bundle of all support information from a host
"""

__author__ = 'Platform9'

import glob
import logging
import os
import re
import json
import tarfile
import argparse
from subprocess import check_call
import subprocess

"""
Want to be able to do the following eventually:
1. Allow apps to provide their own manifest in a directory and this gatherer
captures it at run time for the app.
2. Run a command on the host and capture its output in a file in the bundle.
"""

# Default file list
default_file_list = [
    '/etc/pf9/**',
    '/var/log/pf9/**',
    '/var/opt/pf9/hostagent/**',
    '/var/opt/pf9/hypervisor_details',
]

support_logging_dir = '/var/log/pf9/support'
support_script = '/opt/pf9/hostagent/bin/run_support_scripts.sh'

sensitive_patterns = [
    re.compile(r'password\s*=\s*".*?"', re.IGNORECASE),
    re.compile(r'password\s*=\s*\'.*?\'', re.IGNORECASE),
    re.compile(r'password\s*=\s*[^;\n]*', re.IGNORECASE),
    re.compile(r'ca_chain', re.IGNORECASE),
    re.compile(r'certificate', re.IGNORECASE),
    re.compile(r'issuing_ca', re.IGNORECASE),
    re.compile(r'service_account_key', re.IGNORECASE),
    re.compile(r'client-certificate-data', re.IGNORECASE),
    re.compile(r'client-key-data', re.IGNORECASE),
    re.compile(r'certificate-authority-data', re.IGNORECASE),
    re.compile(r'ETCD_INITIAL_CLUSTER_TOKEN\s*=\s*".*?"', re.IGNORECASE),
    re.compile(r'DOCKERHUB_PASSWORD\s*=\s*".*?"', re.IGNORECASE),
    re.compile(r'OS_PASSWORD\s*=\s*".*?"', re.IGNORECASE),
    re.compile(r'VAULT_TOKEN\s*=\s*".*?"', re.IGNORECASE),
    re.compile(r'CUSTOM_REGISTRY_PASSWORD\s*:\s*".*?"', re.IGNORECASE),
    re.compile(r'certificate-authority-data\s*:\s*[A-Za-z0-9+/=]+\s*', re.IGNORECASE),
    re.compile(r'client-certificate-data\s*:\s*[A-Za-z0-9+/=]+\s*', re.IGNORECASE),
    re.compile(r'client-key-data\s*:\s*[A-Za-z0-9+/=]+\s*', re.IGNORECASE),
    re.compile(r'hashed certificate data:\s*[A-Za-z0-9+/=]+\s*', re.IGNORECASE)
]

def setup_logger():
    logger = logging.getLogger('SupportBundleLogger')
    logger.setLevel(logging.DEBUG)
    # Create file handler which logs even debug messages
    fh = logging.FileHandler(os.path.join(support_logging_dir, 'support_bundle.log'))
    fh.setLevel(logging.DEBUG)
    # Create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # Create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # Add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

def redact_files(file, common_base_dir, logger=logging):
    try:
        redacted_file = f"{file}.redacted"
        sensitive_found = False
        with open(file, 'r') as f:
            if file.endswith('.json'):
                content = json.load(f)
                if redact_sensitive(content):
                    sensitive_found = True
                    with open(os.path.join(common_base_dir, redacted_file), 'w') as fw:
                        json.dump(content, fw, indent=2)
            else:
                lines = f.readlines()
                redacted_lines = []
                for line in lines:
                    redacted_line = line
                    for pattern in sensitive_patterns:
                        if pattern.search(line):
                            sensitive_found = True
                            redacted_line = pattern.sub('REDACTED', redacted_line)
                    redacted_lines.append(redacted_line)

                if sensitive_found:
                    with open(os.path.join(common_base_dir, redacted_file), 'w') as fw:
                        fw.writelines(redacted_lines)

        if sensitive_found:
            logger.debug(f"Redacted sensitive information in: {file}, created redacted copy: {redacted_file}")
            return redacted_file
        else:
            logger.debug(f"No sensitive information found in: {file}, including original file.")
            return file
    except Exception as e:
        logger.warning(f"Failed to redact file: {file}, Error: {e}")
        return None

def redact_sensitive(content):
    sensitive_found = False
    if isinstance(content, dict):
        for key, value in content.items():
            for pattern in sensitive_patterns:
                if pattern.search(key):
                    sensitive_found = True
                    if isinstance(value, str):
                        content[key] = "REDACTED"
                    elif isinstance(value, list):
                        content[key] = ["REDACTED" for _ in value]
            if isinstance(value, (dict, list)):
                if redact_sensitive(value):
                    sensitive_found = True
    elif isinstance(content, list):
        for index, item in enumerate(content):
            if isinstance(item, str):
                for pattern in sensitive_patterns:
                    if pattern.search(item):
                        sensitive_found = True
                        content[index] = "REDACTED"
            else:
                if redact_sensitive(item):
                    sensitive_found = True
    return sensitive_found

def extract_certificate_dates(cert_path):
    try:
        # Extract the start date
        start_date_command = ["openssl", "x509", "-in", cert_path, "-noout", "-startdate"]
        start_date_output = subprocess.check_output(start_date_command, text=True)
        start_date = start_date_output.strip().split('=')[1]

        # Extract the end date
        end_date_command = ["openssl", "x509", "-in", cert_path, "-noout", "-enddate"]
        end_date_output = subprocess.check_output(end_date_command, text=True)
        end_date = end_date_output.strip().split('=')[1]

        return start_date, end_date
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to extract certificate dates for {cert_path}: {e}")
        return None, None

def generate_cert_dates(cert_path, logger):
    try:
        start_date, end_date = extract_certificate_dates(cert_path)
        cert_info = f"start_date={start_date}, end_date={end_date}\n"
        cert_info_file = f"{cert_path}.hash"

        with open(cert_info_file, 'w') as f:
            f.write(cert_info)

        logger.debug(f"Generated hashed certificate info file: {cert_info_file}")
        return cert_info_file
    except Exception as e:
        logger.warning(f"Failed to update certificate {cert_path}: {e}")

def should_exclude(file, logger):
    logger.debug(f"Checking exclusion for file: {file}")

    if os.path.isdir(file):
        logger.debug(f"Skipping directory: {file}")
        return True

    # Exclude etcd-backup directory
    if 'etcd-backup' in file:
        logger.debug(f"Excluding because of etcd-backup: {file}")
        return True

    # Exclude files named key.pem, key.pem.0, key.pem.1, etc.
    if re.match(r'.*key\.pem(\.\d+)?$', file):
        logger.debug(f"Excluding because of file name: {file}")
        return True

    # Exclude .key and .csr files anywhere in /etc/pf9
    if file.startswith('/etc/pf9/') and (file.endswith('.key') or file.endswith('.csr')):
        logger.debug(f"Excluding because of file extension: {file}")
        return True


    # Include only .json, .log, and .crt files in the kube.d/certs* directory
    if '/etc/pf9/kube.d/certs' in file and not (file.endswith('.json') or file.endswith('.log') or file.endswith('.crt')):
        logger.debug(f"Excluding because of file type in kube.d/certs*: {file}")
        return True

    # Exclude files named cert.pem, cert.pem.0, cert.pem.1, etc.
    if re.match(r'.*cert\.pem(\.\d+)?$', file):
        logger.debug(f"Excluding because of file name: {file}")
        return True

    # Exclude .crt files but allow .crt.hash files
    if file.endswith('.crt') and not file.endswith('.crt.hash'):
        logger.debug(f"Excluding because of file extension: {file}")
        return True

    return False

def generate_support_bundle(out_tgz_file, logger):
    """
    Run the support scripts and generate a tgz file in
    /var/opt/pf9/hostagent. Overwrites the previously generated
    tgz file if it exists.
    """
    logger.info('Writing out support file %s', out_tgz_file)
    try:
        if not os.path.isdir(support_logging_dir):
            os.makedirs(support_logging_dir)

        support_logfile = os.path.join(support_logging_dir, 'support.txt')
        with open(support_logfile, 'w') as f:
            f.write("Support logs:\n")
            check_call([support_script, support_logging_dir], stdout=f, stderr=f)
    except Exception as e:
        logger.exception("Failed to run the support scripts: %s", e)

    try:
        with tarfile.open(out_tgz_file, 'w:gz') as tgzfile:
            for pattern in file_list:
                expanded_pattern = os.path.expandvars(os.path.expanduser(pattern))

                for file in glob.iglob(expanded_pattern, recursive=True):
                    logger.debug(f"Current File/Dir is: {file}")

                    if os.path.isfile(file) and (file.endswith('.crt') or file.startswith('cert.pem') or re.match(r'cert\.pem(\.\d+)?$', os.path.basename(file))):
                        cert_info_file = generate_cert_dates(file, logger)
                        if cert_info_file:
                            tgzfile.add(cert_info_file, arcname=os.path.relpath(cert_info_file, start='/'))
                            os.remove(cert_info_file)

                    if should_exclude(file, logger):
                        logger.debug(f"Excluding file: {file}")
                        continue
                    try:
                        if os.path.isfile(file):
                            redacted_file = redact_files(file, '/', logger)
                            if redacted_file:
                                tgzfile.add(redacted_file, arcname=os.path.relpath(redacted_file, start='/'))
                                os.remove(redacted_file)
                            else:
                                tgzfile.add(file, arcname=os.path.relpath(file, start='/'))

                        logger.debug(f"Adding file: {file}")

                    except (IOError, OSError) as e:
                        logger.warning(f"Failed to add file: {file}, Error: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to process file: {file}, Error: {e}")
            logger.info(f"Support bundle created successfully: {out_tgz_file}")

    except Exception as e:
        logger.exception(f"Failed to generate support bundle: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate Support Bundle')
    parser.add_argument('--file-list', type=str, nargs='+', default=None,
                        help='List of files or directories to include in the support bundle')
    parser.add_argument('--output', type=str, default='/tmp/pf9-support.tgz',
                        help='Output tar.gz file for the support bundle')

    args = parser.parse_args()

    file_list = []

    # Prompt the user for each entry in the default file list
    for item in default_file_list:
        confirm = input(f"Do you want to include {item} in the support bundle? (yes/no): ")
        if confirm.lower() == 'yes':
            file_list.append(item)

    # Append the provided file list from CLI arguments
    if args.file_list:
        # Ensure all file patterns end with '**'
        args.file_list = [pattern if pattern.endswith('/**') else pattern.rstrip('/') + '/**' for pattern in args.file_list]
        file_list.extend(args.file_list)

    logger = setup_logger()
    logger.info(f"Final file list: {file_list}")
    generate_support_bundle(args.output, logger)
