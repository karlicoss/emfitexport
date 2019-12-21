#!/usr/bin/env python3
import io
import json
import logging
import re
import sys
import time
from os import listdir, rename
from os.path import join, lexists
from pathlib import Path
from typing import Any, Dict, Iterator, List, Union

import backoff # type: ignore
import requests
from kython.klogging import setup_logzero

from emfit_secrets import TOKEN # type: ignore


# ugh. it's a mess https://github.com/samuelmr/emfit-qs/pull/1/files
QS_API = 'https://qs-api.emfit.com'
API_QS = 'https://api-qs.emfit.com'


BPATH = Path('/L/backups/emfit/')


def get_logger():
    return logging.getLogger('emfit-backup')


class NoKey(Exception):
    pass

@backoff.on_exception(backoff.expo, NoKey, max_time=60 * 30)
def get_device() -> str:
    # TODO ugh it's a mess
    # in browser, it uses https://qs-api.emfit.com/api/v1/user and bearer: in Authorisation field??
    r = get('/api/v1/user/get', timeout=1)
    jj = r.json()
    u = jj.get('user', None)
    if u is None:
        # sometimes it just happens for no good reason...
        get_logger().error('"no user" error: %s', jj)
        raise NoKey
    return u['devices']


@backoff.on_exception(backoff.expo, NoKey, max_time=60 * 30)
def get_presences(device):
    # TODO eh,is that all of them??
    r = get(f"/v4/presence/{device}/latest")
    jj = r.json()
    nd = jj.get('navigation_data', None)
    if nd is None:
        get_logger().error("no navigation data: %s", jj)
        raise NoKey
    presences = [presence["id"] for presence in nd]
    # mm, date is returned in funny format, without year
    return set(presences)


class Retry(Exception):
    pass


@backoff.on_exception(backoff.expo, Retry, max_tries=5)
def download_presence(device, presence):
    logger = get_logger()
    js = get(f"/v4/presence/{device}/{presence}").json()
    if 'id' not in js:
        logger.warning(f"Bad json: {js}")
        raise Retry
    else:
        return js


def get(path, base=API_QS, **kwargs):
    r = requests.get(
        base + path,
        params={
            'remember_token': TOKEN,
        }, verify=False, **kwargs)
    r.raise_for_status()
    return r


def get_existing():
    res = set()
    for p in listdir(BPATH):
        if p.endswith('.json'):
            res.add(p[:-len('.json')])
    return res


def fetch_presences() -> Iterator[Exception]:
    logger = get_logger()

    device = get_device()
    logger.info('Fetching data for device %s', device)
    presences = get_presences(device)

    for p in presences:
        ppath = BPATH / (p + '.json')
        if ppath.exists():
            logger.info('skipping %s, already exists', ppath)
            continue 

        try:
            js = download_presence(device, presence=p)
        except Exception as e:
            logging.error('error while getting presence %s', p)
            logging.exception(e)
            yield e
            continue

        logger.info('downloaded presence %s, saving', p)
        with ppath.open('w') as fo:
            json.dump(js, fo, ensure_ascii=False, indent=2, sort_keys=True)

    existing = get_existing()
    # next, clean up turds
    diff = existing.difference(presences)
    if len(diff) > 5: # kinda arbitrary
        yield RuntimeError(f'Too many differences {diff}')

    for d in diff:
        logger.info(f"Archiving turd {d}")
        OLD = BPATH / (d + ".json")
        NEW = BPATH / ( d + ".json.old")
        rename(OLD, NEW)


def backup():
    logger = get_logger()

    errors = list(fetch_presences())
    if len(errors) > 0:
        sys.exit(1)


def main():
    import urllib3 # type: ignore
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    setup_logzero(get_logger(), level=logging.DEBUG)
    setup_logzero(logging.getLogger('requests'), level=logging.DEBUG)
    setup_logzero(logging.getLogger('backoff'), level=logging.DEBUG)
    backup()


if __name__ == '__main__':
    main()


# TODO what was that for?
# def merge(records):
#     assert len(records) > 1
#     merged = records[0]
#     for record in records[1:]:
#         merged.append(record[1])
#     return merged
