#!/opt/pf9/hostagent/bin/python

import json
import logging
import os
import sys
import re
import subprocess
import datetime

LOG = logging.getLogger(__name__)

CACHE_DIR = '/opt/pf9/cache'


def cache_mounted_nfs():
    try:
        process = subprocess.Popen(["mount", "-t", "nfs,nfs4"],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        out, err = process.communicate()
        if not process.returncode:
            groups = re.split('\n', out)
            groups = [x for x in groups if x]
            res = []
            for g in groups:
                m = re.match("(?P<first>.*) on (?P<second>.*) type (?P<third>.*) \((?P<fourth>\w+),.*", g)
                if m:
                    source = m.group('first')
                    dest = m.group('second')
                    fstype = m.group('third')
                    permissions = m.group('fourth')
                    item={
                        'source': source,
                        'destination': dest,
                        'destination_exist': str(os.path.exists(dest)),
                        'fstype': fstype,
                        'permissions': permissions
                    }
                    res.append(item)
            LOG.info(str(res))
            # write to cache file so it can be read from 'extensions' tasks
            cache_dir = CACHE_DIR
            if not os.path.exists(cache_dir):
                os.mkdir(cache_dir)
            mounted_nfs_cache_file = os.path.join(cache_dir, 'mounted_nfs')
            timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            data = {'mounted': res, 'last_updated': timestamp}
            with open(mounted_nfs_cache_file, 'w') as fp:
                json.dump(data, fp)
            return data
    except Exception:
        LOG.exception('unhandled exception when get mounted nfs info')
    return None


def get_mounted_nfs():
    timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    answer = {'mounted': [], 'last_updated': timestamp}
    try:
        cache_dir = CACHE_DIR
        mounted_nfs_cache_file = os.path.join(cache_dir, 'mounted_nfs')
        if not os.path.exists(mounted_nfs_cache_file):
            cached = cache_mounted_nfs()
            if cached:
                return cached
            else:
                return answer

        # get last modified time to see whether need to refresh it
        with open(mounted_nfs_cache_file, 'r') as fp:
            answer = json.load(fp)
            last_updated = datetime.datetime.strptime(answer['last_updated'], '%Y-%m-%d %H:%M:%S')
            if datetime.datetime.utcnow() - last_updated > datetime.timedelta(minutes=5):
                cached = cache_mounted_nfs()
                if cached:
                    answer = cached
        return answer
    except Exception:
        LOG.exception('unhandled exception when get mounted nfs info.')
    return answer


if __name__ == '__main__':
    out = get_mounted_nfs()
    sys.stdout.write(json.dumps(out))
