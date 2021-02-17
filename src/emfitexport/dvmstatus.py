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
def grab(ip: str) -> None:
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


import click
@click.command()
@click.option('--ip', type=str, required=True)
@click.option('--to', type=Path, required=True)
def main(ip: str, to: Path) -> None:
    capture(ip=ip, to=to)


if __name__ == '__main__':
    main()
