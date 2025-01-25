from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator
from pathlib import Path

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .exporthelpers.export_helper import Json, Parser, setup_parser
from .exporthelpers.logging_helper import make_logger

logger = make_logger(__name__)


# ugh. it's a mess https://github.com/samuelmr/emfit-qs/pull/1/files
QS_API = 'https://qs-api.emfit.com'
API_QS = 'https://api-qs.emfit.com'


class RetryMe(Exception):
    pass


retryme = retry(
    retry=retry_if_exception_type(RetryMe),
    wait=wait_exponential(max=10),
    stop=stop_after_attempt(5),
)


class Exporter:
    def __init__(self, token: str, export_dir: Path) -> None:
        self.token = token
        self.export_dir = export_dir

    def api(self, path: str, base=QS_API, **kwargs):
        r = requests.get(
            base + path,
            headers={'Authorization': f'Bearer {self.token}'},
            **kwargs,
        )
        r.raise_for_status()
        return r

    @retryme
    def fetch_device_id(self) -> str:
        r = self.api('/api/v1/user/get')
        jj = r.json()
        u = jj.get('user', None)
        if u is None:
            # sometimes it just happens for no apparent reason...
            logger.error('"no user" error: %s', jj)
            raise RetryMe
        return u['devices']

    @retryme
    def fetch_sleeps(self, device_id: str) -> list[str]:
        r = self.api(f'/api/v1/presence/{device_id}/latest')
        jj = r.json()
        nd = jj.get('navigation_data', None)
        if nd is None:
            logger.error('no "navigation_data", probably means somethign is broken: %s', jj)
            raise RetryMe
        # mm, date is returned in funny format, without the year
        return sorted(sleep['id'] for sleep in nd)

    # @backoff.on_exception(backoff.expo, Retry, max_tries=5)
    @retryme
    def fetch_sleep(self, device: str, sleep_id: str) -> Json:
        # NOTE: for some reason, sleep session is called 'presence' in emfit
        js = self.api(f'/api/v1/presence/{device}/{sleep_id}').json()
        # todo don't remember if this happened often?
        sid = js.get('id', None)
        if sid is None:
            logger.warning(f'Bad json: {js}')
            raise RetryMe

        # todo use some direct way to check?
        datapoints = js['sleep_epoch_datapoints']
        if datapoints is None:
            logger.warning(f'Sleep session {sid} has no datapoints, likely incomplete sleep. Running the export later should resolve this.')
            raise RetryMe

        return js

    def load_existing(self) -> list[str]:
        return sorted(p.stem for p in self.export_dir.glob('*.json'))

    def update_sleeps(self) -> Iterator[Exception]:
        device_id = self.fetch_device_id()
        logger.info('Fetching data for device %s', device_id)

        api_ids = self.fetch_sleeps(device_id)

        logger.info('Fetched %d sleep sessions from api', len(api_ids))

        for sid in api_ids:
            ppath = self.export_dir / (sid + '.json')
            if ppath.exists():
                # todo special mode that force overwrites?
                logger.info('skipping %s, already downloaded', ppath)
                continue

            try:
                js = self.fetch_sleep(device_id, sleep_id=sid)
            except Exception as e:
                logging.error('error while fetching sleep %s', sid)
                logging.exception(e)
                yield e
                continue

            logger.info('fetched sleep %s, saving to %s', sid, ppath)
            ppath.write_text(json.dumps(js, ensure_ascii=False, indent=2, sort_keys=True))

        # next, clean up turds
        # IIRC, turds might happen if export happened to run during the sleep.. then you might end up with a partial sleep
        existing = self.load_existing()
        diff = set(existing).difference(set(api_ids))
        if len(diff) > 5:  # todo kinda arbitrary
            yield RuntimeError(f'Too many differences {diff}')

        for d in diff:
            logger.info(f'Archiving turd {d}')
            old = self.export_dir / (d + '.json')
            new = self.export_dir / (d + '.json.old')
            old.rename(new)

    def run(self) -> None:
        errors = list(self.update_sleeps())
        if len(errors) > 0:
            # todo not sure? more defensive?
            logger.error(f'Had {len(errors)} errors during the export')
            sys.exit(1)


Token = str


def login(username: str, password: str) -> Token:
    res = requests.post(
        'https://qs-api.emfit.com/api/v1/login',
        data={'username': username, 'password': password},
    )
    return res.json()['token']


def main() -> None:
    # todo tenacity logging?
    parser = make_parser()
    args = parser.parse_args()

    params = args.params

    token = login(
        username=params['username'],
        password=params['password'],
    )

    ex = Exporter(
        token=token,
        export_dir=args.export_dir,
    )
    ex.run()


def make_parser():
    p = Parser('Export/takeout for your personal Emfit QS sleep data')
    setup_parser(
        parser=p,
        params=['username', 'password'],
    )
    p.add_argument('--export-dir', type=Path, required=True, help='Output directory for JSON sleep sessions')
    return p


if __name__ == '__main__':
    main()
