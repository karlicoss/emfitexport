#!/usr/bin/env python3
# Captures dvmstatus Emfit page
# TODO: see  https://gist.github.com/karlicoss/3361f6a239048a451daa2a02982ee180#dvmstatushtm
# for actual parsing

from datetime import datetime
from pathlib import Path
import time
from typing import Dict, Any
import sys

import pytz

import urllib.request
def grab(ip: str) -> str:
    url = ip + '/dvmstatus.htm'
    try:
        return urllib.request.urlopen(url, timeout=1).read().decode('utf8')
    except Exception as e:
        return str(e)


import sqlite3
def capture(*, ip: str, to: Path) -> None:
    with sqlite3.connect(str(to)) as db:
        # todo not sure if need id?
        db.execute('CREATE TABLE IF NOT EXISTS data (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, payload TEXT)')
        total = 0
        # todo shold I use asyncio maybe?
        while True:
            data = grab(ip=ip)
            now = datetime.utcnow().isoformat()
            if total % 60 == 0:
                # log & commit every minute
                db.commit()
                total = next(db.execute('select COUNT(*) from data'))[0]
                print('capturing: ', total, now, repr(data), file=sys.stderr)
            db.execute('INSERT INTO data(timestamp, payload) VALUES (?, ?)', (now, data))
            total += 1
            time.sleep(1)


### copy pasted from promnesia
import subprocess
from typing import List

SYSTEMD_TEMPLATE = '''
[Unit]
Description=Emfit local capture

[Install]
WantedBy=default.target

[Service]
ExecStart={launcher} {extra_args}
Type=simple
Restart=always
'''

def systemd(*args, method=subprocess.check_call) -> None:
    method([
        'systemctl', '--no-pager', '--user', *args,
    ])


def _install_systemd(*, name: str, out: Path, launcher: str, largs: List[str]) -> None:
    unit_name = name

    import shlex
    extra_args = ' '.join(shlex.quote(str(a)) for a in largs)

    out.write_text(SYSTEMD_TEMPLATE.format(
        launcher=launcher,
        extra_args=extra_args,
    ))

    try:
        systemd('stop' , unit_name, method=subprocess.run) # ignore errors here if it wasn't running in the first place
        systemd('daemon-reload')
        systemd('enable', unit_name)
        systemd('start' , unit_name)
        systemd('status', unit_name)
    except Exception as e:
        print(f"Something has gone wrong... you might want to use 'journalctl --user -u {unit_name}' to investigate", file=sys.stderr)
        raise e
###


import click
@click.command()
@click.option('--ip', type=str, required=True)
@click.option('--to', type=Path, required=True)
@click.option('--install-systemd', type=bool, is_flag=True, default=False)
def main(*, ip: str, to: Path, install_systemd: bool) -> None:
    if install_systemd:
        name = 'emfit_capture'
        out = Path(f'~/.config/systemd/user/{name}.service').expanduser()
        _install_systemd(
            name=name,
            out=out, 
            launcher=str(Path(__file__).absolute()),
            largs=['--ip', ip, '--to', str(to)],
        )
        return
    capture(ip=ip, to=to)


if __name__ == '__main__':
    main()
