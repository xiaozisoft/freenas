#!/usr/local/bin/python
#-
# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from collections import defaultdict
from subprocess import Popen, PIPE
import json
import os
import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI',
])

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

import django
django.setup()


def main():
    FAILOVER_JSON = "/tmp/failover.json"
    try:
        os.unlink(FAILOVER_JSON)
    except OSError:
        pass

    from freenasUI.failover.models import Failover
    from freenasUI.network.models import Interfaces, Alias
    from freenasUI.services.models import SSH
    from freenasUI.storage.models import Volume
    from freenasUI.system.models import Settings
    from freenasUI.middleware.notifier import notifier

    if Failover.objects.all().exists():
        fobj = Failover.objects.all()[0]
    else:
        sys.exit()

    data = {
        'disabled': fobj.disabled,
        'master': fobj.master,
        'timeout': fobj.timeout,
        'groups': defaultdict(list),
        'volumes': [
            vol.vol_name for vol in Volume.objects.filter(vol_encrypt__lt=2)
        ],
        'phrasedvolumes': [
            vol.vol_name for vol in Volume.objects.filter(vol_encrypt__exact=2)
        ],
        'non_crit_interfaces': [
            (i.int_interface) for i in Interfaces.objects.exclude(int_vip=None).exclude(int_vip='').exclude(int_critical=True)
        ],
        'ips': [
            str(i.int_vip) for i in Interfaces.objects.exclude(int_vip=None).exclude(int_vip='')
        ],
        'internal_interfaces': notifier().failover_internal_interfaces(),
    }

    for i in Alias.objects.exclude(alias_vip=None).exclude(alias_vip=''):
        data['ips'].append(str(i.alias_vip))

    for item in Interfaces.objects.filter(int_critical=True):
        data['groups'][item.int_group].append(item.int_interface)

    with open(FAILOVER_JSON, "w+") as fh:
        fh.write(json.dumps(data))

    try:
        ssh = SSH.objects.order_by('-id')[0]
    except IndexError:
        ssh = SSH.objects.create()

    try:
        settings = Settings.objects.order_by('-id')[0]
    except IndexError:
        settings = Settings.objects.create()

    # Cook data['ips'] which will be empty in the single
    # head case.  Bug #16116
    if not data['ips']:
        data['ips'] = ['0.0.0.0']

    with open('/etc/pf.conf.block', 'w+') as f:
        f.write('set block-policy drop\n')
        f.write('''
ips = '{ %(ips)s }'
ports = '{ %(ssh)s, %(http)s, %(https)s }'
pass in quick proto tcp from any to any port $ports
block drop in quick proto tcp from any to $ips
block drop in quick proto udp from any to $ips\n''' % {
            'ssh': ssh.ssh_tcpport,
            'http': settings.stg_guiport,
            'https': settings.stg_guihttpsport,
            'ips': ', '.join(data['ips']),
        })

    Popen(["pfctl", "-f", "/etc/pf.conf.block"], stderr=PIPE, stdout=PIPE).wait()


if __name__ == "__main__":
    main()