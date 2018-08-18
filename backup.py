#!/usr/bin/env python3

import io, re, requests, sys, time
import json
from kython import json_dump_pretty
from os import listdir
from os.path import join, lexists

TOKEN = "$2y$10$REMOVED."
BPATH = '/L/backups/emfit/'

def get_logger():
    import logging
    logger = logging.getLogger('emfit-backup')
    return logger


def get_device():
    r = get("/api/v1/user/get")
    device = r.json()["user"]["devices"]
    return device

def get_presences(device):
    # TODO eh,is that all of them??
    r = get("/v4/presence/{0}/latest".format(device))
    presences = [presence["id"] for presence in r.json()["navigation_data"] ]
    # mm, date is returned in funny format, without year
    return presences

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
            json_dump_pretty(fo, js)

    if errors:
        sys.exit(1)

def main():
    backup()

if __name__ == '__main__':
    import logging
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    logging.basicConfig(level=logging.INFO)
    main()
