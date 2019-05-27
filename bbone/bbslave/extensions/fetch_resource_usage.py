#!/opt/pf9/hostagent/bin/python

import json

import cpuinfo
import psutil


def get_disk_usage():
    usage = psutil.disk_usage('/')
    used = usage.used
    total = usage.total
    percentage = float(used) / float(total) * 100
    return {
        'percent': round(percentage, 1),
        'total': total,
        'used': used
    }


def get_cpu_usage():
    cpu_info = cpuinfo.get_cpu_info()
    cpu_percent = psutil.cpu_percent(0.5)
    clock_rate = cpu_info['hz_actual_raw'][0]
    return {
        'percent': cpu_percent,
        'total': clock_rate,
        'used': clock_rate * cpu_percent / 100
    }


def main():
    mem = psutil.virtual_memory()

    usage = {
        'disk': get_disk_usage(),
        'memory': {
            'percent': mem.percent,
            'total': mem.total,
            'available': mem.available
        },
        'cpu': get_cpu_usage()
    }
    print(json.dumps(usage, indent=3))


if __name__ == '__main__':
    main()
