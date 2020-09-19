#!/usr/bin/env python3
import json
import logging
from pathlib import Path
from typing import Iterator, List, Set


import requests
from tenacity import retry, retry_if_exception_type, wait_exponential, stop_after_attempt # type: ignore


# ugh. it's a mess https://github.com/samuelmr/emfit-qs/pull/1/files
QS_API = 'https://qs-api.emfit.com'
API_QS = 'https://api-qs.emfit.com'


def get_logger():
    return logging.getLogger('emfitexport')


class RetryMe(Exception):
    pass


retryme = retry(
    retry=retry_if_exception_type(RetryMe),
    wait=wait_exponential(max=10),
    stop=stop_after_attempt(5),
)


from .exporthelpers.export_helper import Json, setup_logger


class Exporter:
    def __init__(self, token: str, export_dir: Path) -> None:
        self.logger = get_logger()
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
            self.logger.error('"no user" error: %s', jj)
            raise RetryMe
        return u['devices']


    @retryme
    def fetch_sleeps(self, device_id: str) -> List[str]:
        r = self.api(f'/api/v1/presence/{device_id}/latest')
        jj = r.json()
        nd = jj.get('navigation_data', None)
        if nd is None:
            self.logger.error('no "navigation_data", probably means somethign is broken: %s', jj)
            raise RetryMe
        # mm, date is returned in funny format, without the year
        return list(sorted(sleep['id'] for sleep in nd))


    # @backoff.on_exception(backoff.expo, Retry, max_tries=5)
    @retryme
    def fetch_sleep(self, device: str, sleep_id: str) -> Json:
        # NOTE: for some reason, sleep session is called 'presence' in emfit
        js = self.api(f'/api/v1/presence/{device}/{sleep_id}').json()
        # todo don't remember if this happened often?
        sid = js.get('id', None)
        if sid is None:
            self.logger.warning(f'Bad json: {js}')
            raise RetryMe

        # todo use some direct way to check?
        datapoints = js['sleep_epoch_datapoints']
        if datapoints is None:
            self.logger.warning('Sleep session %s has no datapoints, likely incomplete sleep. Running the export later should resolve this.', sid)
            raise RetryMe

        return js


    def load_existing(self) -> List[str]:
        return list(sorted(p.stem for p in self.export_dir.glob('*.json')))


    def update_sleeps(self) -> Iterator[Exception]:
        logger = get_logger()

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
        if len(diff) > 5: # todo kinda arbitrary
            yield RuntimeError(f'Too many differences {diff}')

        from os import rename
        for d in diff:
            logger.info(f'Archiving turd {d}')
            old = self.export_dir / (d + '.json')
            new = self.export_dir / (d + '.json.old')
            rename(old, new)


    def run(self) -> None:
        errors = list(self.update_sleeps())
        if len(errors) > 0:
            # todo not sure? more defensive?
            self.logger.error(f'Had %d errors during the export', len(errors))
            import sys
            sys.exit(1)


Token = str
def login(username: str, password: str) -> Token:
    res = requests.post(
        'https://qs-api.emfit.com/api/v1/login',
        data=dict(username=username, password=password),
    )
    return res.json()['token']


def main():
    setup_logger(get_logger(), level='INFO')
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
    from .exporthelpers.export_helper import setup_parser, Parser
    p = Parser('Export/takeout for your personal Emfit QS sleep data')
    setup_parser(
        parser=p,
        params=['username', 'password'],
    )
    p.add_argument('--export-dir', type=Path, required=True, help='Output directory for JSON sleep sessions')
    return p


if __name__ == '__main__':
    main()
