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
import yaml
import tarfile
import tempfile
from subprocess import CalledProcessError, check_call
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

sensitive_patterns = [
    re.compile(r'(password\s*=\s*".*?")', re.IGNORECASE),
    re.compile(r'(password\s*=\s*\'.*?\')', re.IGNORECASE),
    re.compile(r'(password\s*=\s*[^;\n]*)', re.IGNORECASE),
    re.compile(r'(ca_chain\s*=\s*".*?")', re.IGNORECASE),
    re.compile(r'(certificate\s*=\s*".*?")', re.IGNORECASE),
    re.compile(r'(issuing_ca\s*=\s*".*?")', re.IGNORECASE),
    re.compile(r'(service_account_key\s*=\s*".*?")', re.IGNORECASE),
    re.compile(r'(client-certificate-data\s*:\s*".*?")', re.IGNORECASE),
    re.compile(r'(client-key-data\s*:\s*".*?")', re.IGNORECASE),
    re.compile(r'(certificate-authority-data\s*:\s*".*?")', re.IGNORECASE),
    re.compile(r'(ETCD_INITIAL_CLUSTER_TOKEN\s*=\s*".*?")', re.IGNORECASE),
    re.compile(r'(DOCKERHUB_PASSWORD\s*=\s*".*?")', re.IGNORECASE),
    re.compile(r'(OS_PASSWORD\s*=\s*".*?")', re.IGNORECASE),
    re.compile(r'(VAULT_TOKEN\s*=\s*(?:"[^"]*"|[^;\n]*))', re.IGNORECASE),
    re.compile(r'(CUSTOM_REGISTRY_PASSWORD\s*:\s*".*?")', re.IGNORECASE),
    re.compile(r'(certificate-authority-data\s*:\s*[A-Za-z0-9+/=]+)', re.IGNORECASE),
    re.compile(r'(client-certificate-data\s*:\s*[A-Za-z0-9+/=]+)', re.IGNORECASE),
    re.compile(r'(client-key-data\s*:\s*[A-Za-z0-9+/=]+)', re.IGNORECASE),
    re.compile(r'(hashed certificate data:\s*[A-Za-z0-9+/=]+)', re.IGNORECASE),
]

sensitive_patterns_for_yaml_json = [
    re.compile(r'client-key-data', re.IGNORECASE),
    re.compile(r'client-certificate-data', re.IGNORECASE),
    re.compile(r'certificate-authority-data', re.IGNORECASE),

    re.compile(r'ca_chain', re.IGNORECASE),
    re.compile(r'certificate', re.IGNORECASE),
    re.compile(r'issuing_ca', re.IGNORECASE),
    re.compile(r'service_account_key', re.IGNORECASE),
    re.compile(r'client-certificate-data', re.IGNORECASE),
    re.compile(r'client-key-data', re.IGNORECASE),
    re.compile(r'certificate-authority-data', re.IGNORECASE),

    re.compile(r'VAULT_TOKEN', re.IGNORECASE),
    re.compile(r'ETCD_INITIAL_CLUSTER_TOKEN', re.IGNORECASE),
]

sensitive_keys_within_strings = {
    "ETCD_INITIAL_CLUSTER_TOKEN": re.compile(r'(ETCD_INITIAL_CLUSTER_TOKEN\s*=\s*)[^\n\\]+', re.IGNORECASE)
}

def redact_cert_requests(log_file_path):
    cert_request_pattern = re.compile(
        r'(-----BEGIN CERTIFICATE REQUEST-----.*?-----END CERTIFICATE REQUEST-----)',
        re.DOTALL
    )
    try:
        with open(log_file_path, 'r') as file:
            content = file.read()

        redacted_content = cert_request_pattern.sub(
            '-----BEGIN REDACTED REQUEST-----\nREDACTED\n-----END REDACTED REQUEST-----',
            content
        )

        redacted_file_path = f"{log_file_path}.redacted"
        with open(redacted_file_path, 'w') as file:
            file.write(redacted_content)
        return redacted_file_path
    except Exception:
        return None

def redact_sensitive_key_values(content):
    """
    Redact values of sensitive keys in the configuration file content.
    """
    redacted_content = content
    for pattern in sensitive_patterns:
        redacted_content = pattern.sub(lambda m: m.group(1).split('=')[0] + '=REDACTED', redacted_content)

    def redact_line(line):
        for key, pattern in sensitive_keys_within_strings.items():
            if pattern.search(line):
                line = pattern.sub(r'\1REDACTED', line)
        return line

    redacted_lines = []
    in_multiline_string = False
    multiline_buffer = []

    for line in redacted_content.split('\n'):
        if '="' in line and not in_multiline_string:
            in_multiline_string = True
            multiline_buffer.append(line)
        elif in_multiline_string:
            multiline_buffer.append(line)
            if line.endswith('"'):
                in_multiline_string = False
                multiline_content = '\n'.join(multiline_buffer)
                redacted_multiline_content = redact_line(multiline_content)
                redacted_lines.append(redacted_multiline_content)
                multiline_buffer = []
        else:
            redacted_lines.append(redact_line(line))

    return '\n'.join(redacted_lines)

def redact_yaml_content(content):
    """
    Redact sensitive information from YAML content with multiple documents.
    """
    documents = yaml.safe_load_all(content)
    redacted_docs = []
    for doc in documents:
        if doc is None:
            continue
        redacted_doc = redact_sensitive(doc)
        redacted_docs.append(redacted_doc)
    return redacted_docs

def redact_files(file, common_base_dir, logger=logging):
    try:
        if file.endswith('.log'):
            redacted_file = redact_cert_requests(file, logger)
            if redacted_file:
                return redacted_file

        redacted_file = f"{file}.redacted"
        sensitive_found = False

        with open(file, 'r') as f:
            if file.endswith('.json'):
                content = json.load(f)
                redacted_content = redact_sensitive(content)
                if redacted_content:
                    sensitive_found = True
                    with open(os.path.join(common_base_dir, redacted_file), 'w') as fw:
                        json.dump(redacted_content, fw, indent=2)
            elif file.endswith('.yaml') or file.endswith('.yml'):
                content = f.read()
                redacted_content = redact_yaml_content(content)
                if redacted_content:
                    sensitive_found = True
                    with open(os.path.join(common_base_dir, redacted_file), 'w') as fw:
                        yaml.safe_dump(redacted_content, fw, default_flow_style=False)
            else:
                content = f.read()
                redacted_content = redact_sensitive_key_values(content)
                if redacted_content != content:
                    sensitive_found = True
                    with open(os.path.join(common_base_dir, redacted_file), 'w') as fw:
                        fw.write(redacted_content)

        if sensitive_found:
            return redacted_file
        else:
            return file
    except Exception:
        return None

def redact_sensitive(content):
    if isinstance(content, dict):
        redacted_content = {}
        for key, value in content.items():
            if any(pattern.search(key) for pattern in sensitive_patterns_for_yaml_json):
                redacted_content[key] = 'REDACTED'
            else:
                redacted_content[key] = redact_sensitive(value)
        return redacted_content
    elif isinstance(content, list):
        return [redact_sensitive(item) for item in content]
    elif isinstance(content, str):
        lines = content.split('\n')
        redacted_lines = []
        for line in lines:
            for pattern in sensitive_patterns_for_yaml_json:
                if pattern.search(line):
                    key, sep, val = line.partition('=')
                    if sep:  # Ensure we have a key=value pair
                        line = f"{key}=REDACTED"
            redacted_lines.append(line)
        return '\n'.join(redacted_lines)
    else:
        return content

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
    except subprocess.CalledProcessError:
        return None, None

def generate_cert_dates(cert_path):
    try:
        start_date, end_date = extract_certificate_dates(cert_path)
        cert_info = f"start_date={start_date}, end_date={end_date}\n"
        cert_info_file = f"{cert_path}.hash"

        with open(cert_info_file, 'w') as f:
            f.write(cert_info)

        return cert_info_file
    except Exception:
        pass

def should_exclude(file):
    if os.path.isdir(file):
        return True

    # Exclude etcd-backup directory
    if 'etcd-backup' in file:
        return True

    # Exclude files named key.pem, key.pem.0, key.pem.1, etc.
    if re.match(r'.*key\.pem(\.\d+)?$', file):
        return True

    # Exclude .key and .csr files anywhere in /etc/pf9
    if file.startswith('/etc/pf9/') and (file.endswith('.key') or file.endswith('.csr')):
        return True

    # Include only .json, .log, and .crt files in the kube.d/certs* directory
    if '/etc/pf9/kube.d/certs' in file and not (file.endswith('.json') or file.endswith('.log') or file.endswith('.crt')):
        return True

    # Exclude files named cert.pem, cert.pem.0, cert.pem.1, etc.
    if re.match(r'.*cert\.pem(\.\d+)?$', file):
        return True

    # Exclude .crt files but allow .crt.hash files
    if file.endswith('.crt'):
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

    try:
        with tarfile.open(out_tgz_file, 'w:gz') as tgzfile:
            for pattern in file_list:
                expanded_pattern = os.path.expandvars(os.path.expanduser(pattern))

                for file in glob.iglob(expanded_pattern, recursive=True):
                    if os.path.isfile(file) and (file.endswith('.crt') or file.startswith('cert.pem') or re.match(r'cert\.pem(\.\d+)?$', os.path.basename(file))):
                        cert_info_file = generate_cert_dates(file)
                        if cert_info_file:
                            with tempfile.NamedTemporaryFile(delete=False) as temp_cert_file:
                                temp_cert_filename = temp_cert_file.name
                                with open(cert_info_file, 'r') as src, open(temp_cert_filename, 'w') as dst:
                                    dst.write(src.read())
                            os.remove(cert_info_file)
                            tgzfile.add(temp_cert_filename, arcname=os.path.relpath(file, start='/'))
                            os.remove(temp_cert_filename)

                    if should_exclude(file):
                        continue
                    try:
                        if os.path.isfile(file):
                            redacted_file = redact_files(file, '/')
                            if redacted_file:
                                with tempfile.NamedTemporaryFile(delete=False) as temp_redact_file:
                                    temp_redact_filename = temp_redact_file.name
                                    with open(redacted_file, 'r') as src, open(temp_redact_filename, 'w') as dst:
                                        dst.write(src.read())
                                os.remove(redacted_file)
                                tgzfile.add(temp_redact_filename, arcname=os.path.relpath(file, start='/'))
                                os.remove(temp_redact_filename)
                            else:
                                tgzfile.add(file, arcname=os.path.relpath(file, start='/'))

                    except (IOError, OSError) as e:
                        pass
                    except Exception as e:
                        pass
            logger.info(f"Support bundle created successfully: {out_tgz_file}")

    except Exception as e:
        logger.exception(f"Failed to generate support bundle: {e}")

if __name__ == '__main__':
    file_list = []

    # Prompt the user for each entry in the default file list
    for item in default_file_list:
        confirm = input(f"Do you want to include {item} in the support bundle? (yes/no): ").strip().lower()
        if confirm in ['yes', 'y', 'ye', '']:
            file_list.append(item)
        elif confirm in ['no', 'n']:
            continue
        else:
            print(f"Invalid response '{confirm}' received. Defaulting to 'no'.")

    output_file = '/tmp/pf9-support.tgz'
    generate_support_bundle(output_file)
