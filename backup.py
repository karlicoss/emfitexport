#!/usr/bin/env python3
import io, re, requests, sys, time
import json
import logging
from os import listdir, rename
from os.path import join, lexists

from emfit_secrets import TOKEN # type: ignore

from kython import setup_logzero

import backoff # type: ignore

BPATH = '/L/backups/emfit/'

def get_logger():
    return logging.getLogger('emfit-backup')

class NoKey(Exception):
    pass

@backoff.on_exception(backoff.expo, NoKey, max_time=60 * 30)
def get_device():
    r = get("/api/v1/user/get")
    jj = r.json()
    u = jj.get('user', None)
    if u is None:
        # sometimes it just happens for no good reason...
        get_logger().error(f'"no user" error: {jj}')
        raise NoKey
    return u['devices']

@backoff.on_exception(backoff.expo, NoKey, max_time=60 * 30)
def get_presences(device):
    # TODO eh,is that all of them??
    r = get("/v4/presence/{0}/latest".format(device))
    jj = r.json()
    nd = jj.get('navigation_data', None)
    if nd is None:
        raise NoKey
    presences = [presence["id"] for presence in nd]
    # mm, date is returned in funny format, without year
    return set(presences)

def download_presence(device, pres):
    logger = get_logger()
    attempt = 0
    while attempt < 5:
        js = get(f"/v4/presence/{device}/{pres}").json()
        if 'id' not in js:
            logger.warning(f"Bad json: {js}")
            time.sleep(1)
            attempt += 1
            continue
        return js
    else:
        return None

def get(path):
    r = requests.get("https://api-qs.emfit.com" + path, params = { "remember_token" : TOKEN }, verify=False)
    r.raise_for_status()
    return r

def merge(records):
    assert len(records) > 1
    merged = records[0]
    for record in records[1:]:
        merged.append(record[1])
    return merged

def get_existing():
    res = set() 
    for p in listdir(BPATH):
        if p.endswith('.json'):
            res.add(p[:-len('.json')])
    return res


def backup():
    errors = False

    logger = get_logger()
    device = get_device()
    presences = get_presences(device)
    for presence in presences:
        ppath = join(BPATH, presence + '.json')
        if lexists(ppath):
            logger.info(f"Skipping {ppath}, already exists")
            continue
        js = download_presence(device, presence)
        if js is None:
            logging.error(f"Error while getting presence {presence}")
            errors = True
            continue

        logger.info(f"Downloaded {presence}, saving")
        with open(ppath, 'w') as fo:
            json.dump(js, fo, ensure_ascii=False, indent=2, sort_keys=True)

    existing = get_existing()
    # next, clean up turds
    diff = existing.difference(presences)
    if len(diff) > 5: # kinda arbitrary
        raise RuntimeError(f'Too many differences {diff}')

    for d in diff:
        logger.info(f"Archiving turd {d}")
        OLD = join(BPATH, d + ".json")
        NEW = join(BPATH, d + ".json.old")
        rename(OLD, NEW)

    if errors:
        sys.exit(1)

def main():
    import urllib3 # type: ignore
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    setup_logzero(get_logger(), level=logging.INFO)
    setup_logzero(logging.getLogger('backoff'), level=logging.DEBUG)
    backup()

if __name__ == '__main__':
    main()
