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
import hashlib
from OpenSSL import crypto
from subprocess import check_call

"""
Want to be able to do the following eventually:
1. Allow apps to provide their own manifest in a directory and this gatherer
captures it at run time for the app.
2. Run a command on the host and capture its output in a file in the bundle.
"""

file_list = [
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

def redact_files(file, logger=logging):
    try:
        with open(file, 'r') as f:
            if file.endswith('.json'):
                content = json.load(f)
                redact_sensitive(content)
                with open(file, 'w') as fw:
                    json.dump(content, fw, indent=2)
            else:
                lines = f.readlines()
                redacted_lines = []
                for line in lines:
                    redacted_line = line
                    for pattern in sensitive_patterns:
                        if isinstance(pattern, re.Pattern):
                            redacted_line = pattern.sub('REDACTED', redacted_line)
                        else:
                            redacted_line = re.sub(pattern, 'REDACTED', redacted_line, flags=re.IGNORECASE | re.MULTILINE)
                    redacted_lines.append(redacted_line)

                with open(file, 'w') as fw:
                    fw.writelines(redacted_lines)

        logger.debug(f"Redacted sensitive information in: {file}")
    except Exception as e:
        logger.warning(f"Failed to redact file: {file}, Error: {e}")

def redact_sensitive(content):
    if isinstance(content, dict):
        for key, value in content.items():
            for pattern in sensitive_patterns:
                if pattern.search(key):
                    if isinstance(value, str):
                        content[key] = "REDACTED"
                    elif isinstance(value, list):
                        content[key] = ["REDACTED" for _ in value]
            if isinstance(value, (dict, list)):
                redact_sensitive(value)
    elif isinstance(content, list):
        for index, item in enumerate(content):
            if isinstance(item, str):
                for pattern in sensitive_patterns:
                    if pattern.search(item):
                        content[index] = "REDACTED"
            else:
                redact_sensitive(item)

def hash_content(content):
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def extract_certificate_dates(cert_path):
    cert = crypto.load_certificate(crypto.FILETYPE_PEM, open(cert_path).read())
    start_date = cert.get_notBefore().decode('utf-8')
    end_date = cert.get_notAfter().decode('utf-8')
    return start_date, end_date

def generate_cert_dates(cert_path, logger):
    try:
        start_date, end_date = extract_certificate_dates(cert_path)
        cert_info = f"start_date={start_date}, end_date={end_date}\n"
        hashed_cert_info = hash_content(cert_info)
        cert_info_file = f"{cert_path}.hash"

        with open(cert_info_file, 'w') as f:
            f.write(hashed_cert_info)

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

    # Exclude .crt files anywhere
    if file.endswith('.crt'):
        logger.debug(f"Excluding because of file extension: {file}")
        return True

    return False

def generate_support_bundle(out_tgz_file, logger=logging):
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

    tgzfile = tarfile.open(out_tgz_file, 'w:gz')
    # cert_dates_collected = set()
    for pattern in file_list:
        expanded_pattern = os.path.expandvars(os.path.expanduser(pattern))

        for file in glob.iglob(expanded_pattern, recursive=True):
            logger.debug(f"Current File/Dir is: {file}")

            if should_exclude(file, logger):
                logger.debug(f"Excluding file: {file}")
                continue
            try:
                if os.path.isfile(file):
                    if file.endswith('.crt') or file.startswith('cert.pem'):
                        cert_info_file = generate_cert_dates(file, logger)
                        if cert_info_file:
                            tgzfile.add(cert_info_file, arcname=os.path.basename(cert_info_file))
                    else:
                        redact_files(file)

                logger.debug(f"Adding file: {file}")
                tgzfile.add(file)

            except (IOError, OSError) as e:
                logger.warning(f"Failed to add file: {file}, Error: {e}")
            except Exception as e:
                logger.warning(f"Failed to process file: {file}, Error: {e}")
    tgzfile.close()

if __name__ == '__main__':
    tmp_file = '/tmp/pf9-support.tgz'
    generate_support_bundle(tmp_file)