from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from concurrent.futures import Executor
from dataclasses import dataclass
from datetime import UTC, datetime
from datetime import date as datetime_date
from pathlib import Path
from typing import TYPE_CHECKING

from .exporthelpers import dal_helper
from .exporthelpers.dal_helper import Json, Res, datetime_aware, pathify
from .exporthelpers.logging_helper import make_logger
from .utils import DummyFuture

logger = make_logger(__name__)


def _hhmm(minutes) -> str:
    return '{:02d}:{:02d}'.format(*divmod(minutes, 60))


# def important on the sleep plot to have consistent local time
# todo hmm, emfit has time_user_gmt_offset?? how it is determined?
# seems that datapoints are in UTC though
def fromts(ts) -> datetime_aware:
    dt = datetime.fromtimestamp(ts, tz=UTC)
    return dt


# todo tossnturn_count, tossnturn_datapoints (array of timestamps)
# todo use sleep class percents?

AWAKE = 4


# todo use multiple threads for that?
class EmfitParse:
    # todo could get rid of sid parameter? it's in the json so don't really need anymore
    def __init__(self, sid: str, raw: Json) -> None:
        self.sid = sid
        self.raw = raw

    # TODO what was that for???
    def __hash__(self):
        return hash(self.sid)

    @property
    def measured_rr_avg(self) -> float:
        # todo "measured_rr_max", "measured_rr_min"
        return self.raw['measured_rr_avg']

    # todo derive from hrv datapoints?
    @property
    def hrv_morning(self) -> float:
        return self.raw['hrv_rmssd_morning']

    @property
    def hrv_evening(self) -> float:
        return self.raw['hrv_rmssd_evening']

    @property
    def start(self) -> datetime_aware:
        """
        Bed enter time, not necessarily sleep start
        """
        return fromts(self.raw['time_start'])

    @property
    def end(self) -> datetime_aware:
        """
        Bed exit time, not necessarily sleep end
        """
        return fromts(self.raw['time_end'])

    @property
    def epochs(self) -> list[tuple[int, int]]:
        # pairs of timestamp/epoch 'id'
        # these seems to be utc (can double check last epoch against to_utc field in export)
        return self.raw['sleep_epoch_datapoints']

    @property
    def epoch_series(self) -> tuple[list[int], list[int]]:
        tss = []
        eps = []
        for ts, e in self.epochs:
            tss.append(ts)
            eps.append(e)
        return tss, eps

    @property
    def sleep_start(self) -> datetime_aware:
        for ts, e in self.epochs:
            if e == AWAKE:
                continue
            return fromts(ts)
        raise RuntimeError

    @property
    def sleep_end(self) -> datetime_aware:
        for ts, e in reversed(self.epochs):
            if e == AWAKE:
                continue
            return fromts(ts)
        raise RuntimeError

    # so it's actual sleep, without awake
    # ok, so I need time_asleep
    @property
    def sleep_minutes_emfit(self) -> float:
        # ugh.. really need to figure out what I want to rely on?
        return self.raw['sleep_duration'] // 60

    @property
    def hrv_lf(self) -> float:
        return self.raw['hrv_lf']

    @property
    def hrv_hf(self) -> float:
        return self.raw['hrv_hf']

    @property
    def strip_awakes(self):
        ff = None
        ll = None
        for i, [_ts, e] in enumerate(self.epochs):
            if e != AWAKE:
                ff = i
                break
        for i in range(len(self.epochs) - 1, -1, -1):
            [_ts, e] = self.epochs[i]
            if e != AWAKE:
                ll = i
                break
        return self.epochs[ff:ll]

    # # TODO epochs with implicit sleeps? not sure... e.g. night wakeups.
    # # I guess I could input intervals/correct data/exclude days manually?
    # @property
    # def pulse_percentage(self):

    #     # TODO pulse intervals are 4 seconds?
    #     # TODO ok, how to compute that?...
    #     # TODO cut ff start and end?
    #     # TODO remove awakes from both sides
    #     sp = self.strip_awakes
    #     present = {ep[0] for ep in sp}
    #     start = min(present)
    #     end = max(present)
    #     # TODO get start and end in one go?

    #     for p in self.iter_points():
    #         p.ts

    #     INT = 30

    #     missing = 0
    #     total = 0
    #     for tt in range(start, end + INT, INT):
    #         total += 1
    #         if tt not in present:
    #             missing += 1
    #     # TODO get hr instead!
    #     import ipdb; ipdb.set_trace()
    #     return missing

    #     st = st[0][0]
    #     INT = 30
    #     for [ts, e] in sp:
    #         if e == AWAKE:
    #             continue
    #         return fromts(ts)
    #     raise RuntimeError
    #     pass

    def __str__(self) -> str:
        return f"from {self.sleep_start} to {self.sleep_end}"

    # measured_datapoints
    # [[timestamp, pulse, breath?, ??? hrv?]] # every 4 seconds?

    def iter_points(self):
        for ll in self.raw['measured_datapoints']:
            [ts, pulse, _br, _activity] = ll
            # TODO what the fuck is whaat?? It can't be HRV, it's about 500 ms on average
            # act in csv.. so it must be activity? wonder how is it measured.
            # but I guess makes sense. yeah,  "measured_activity_avg": 595, about that
            # makes even more sense given tossturn datapoints only have timestamp
            yield ts, pulse

    @property
    def sleep_hr(self):
        tss = []
        res = []
        for ts, pulse in self.iter_points():
            if self.sleep_start < fromts(ts) < self.sleep_end:
                tss.append(ts)
                res.append(pulse)
        return tss, res

    @property
    def sleep_hr_series(self):
        return self.sleep_hr

    @property
    def hrv(self):
        tss = []
        res = []
        for ll in self.raw['hrv_rmssd_datapoints']:
            [ts, rmssd, _, _, _almost_always_zero, _] = ll
            # timestamp,rmssd,tp,lfn,hfn,r_hrv
            # TP is total_power??
            # erm. looks like there is a discrepancy between csv and json data.
            # right, so web is using api v 1. what if i use v1??
            # definitely a discrepancy between v1 and v4. have no idea how to resolve it :(
            # also if one of them is indeed tp value, it must have been rounded.
            # TODO what is the meaning of the rest???
            # they don't look like HR data.
            tss.append(ts)
            res.append(rmssd)
        return tss, res

    @property
    def measured_hr_avg(self) -> float:
        return self.raw['measured_hr_avg']

    @property
    def sleep_hr_coverage(self) -> float:
        _tss, hrs = self.sleep_hr
        covered = len([h for h in hrs if h is not None])
        expected = len(hrs)
        return covered / expected * 100


# todo eh, I guess the reason for Emfit and EmfitParse was to make the latter cacheable?
# maybe I should have a protocol/dataclass base and overload in EmfitParse instead?

Sid = str


@dataclass(eq=True, frozen=True)
class Emfit:
    sid: Sid
    hrv_morning: float
    hrv_evening: float
    start: datetime_aware
    end: datetime_aware
    sleep_start: datetime_aware
    sleep_end: datetime_aware
    sleep_hr_coverage: float
    measured_hr_avg: float
    sleep_minutes_emfit: int
    hrv_lf: float
    hrv_hf: float
    measured_rr_avg: float

    @property
    def respiratory_rate_avg(self) -> float:
        # todo not sure about aliases? measured_rr is very cryptic.. on the other hand nice to be consistent with the raw field names?
        return self.measured_rr_avg

    @property
    # ok, I guess that's a reasonable way of defining sleep date
    def date(self) -> datetime_date:
        return self.end.date()

    @property
    def time_in_bed(self) -> int:
        return int((self.sleep_end - self.sleep_start).total_seconds()) // 60

    @property
    def recovery(self) -> float:
        return self.hrv_morning - self.hrv_evening

    @classmethod
    def from_json(cls, j: Json) -> Emfit:
        sid = j['id']
        em = EmfitParse(sid, raw=j)

        # todo meh
        return cls(**{k: getattr(em, k) for k in Emfit.__annotations__})


def _process_one(json_path: Path, i: int, total: int) -> Res[Emfit]:
    logger.info(f'processing {json_path} ({i}/{total})')
    try:
        j = json.loads(json_path.read_text())
        return Emfit.from_json(j)
    except Exception as ex:
        return ex


class DAL:
    def __init__(self, export_path: Path | Sequence[Path | str], *, cpu_pool: Executor | None = None) -> None:
        # TODO maybe rename to 'sources' (while preserving backwards compatibility?)
        if isinstance(export_path, Path):
            # legacy behaviour -- initially DAL was just taking export_path: Path here
            # ugh glob will just return empty sequence if dir doesn't exist
            assert export_path.exists(), export_path

            # NOTE: ids seems to be consistent with ascending date order
            self.sources = sorted(export_path.glob('*.json'))
        else:
            # it's better to allow passing input sources directly
            # - in case user wants to filter some out first or whatever
            # - in case they are compressed
            self.sources = list(map(pathify, export_path))

        self.cpu_pool = cpu_pool

    def sleeps(self) -> Iterator[Res[Emfit]]:
        paths = self.sources

        cpu_pool = self.cpu_pool

        futures = []
        for i, f in enumerate(paths):
            if cpu_pool is not None:
                future = cpu_pool.submit(_process_one, f, i, len(paths))
            else:
                future = DummyFuture(_process_one, f, i, len(paths))
            futures.append(future)

        for fut in futures:
            fres = fut.result()
            yield fres


if not TYPE_CHECKING:
    log = logger  # legacy name, was used at HPI at some point, so keeping for backwards compat

    # legacy function, used to be called from HPI. keeping for bwd compatibility
    def sleeps(path: Path, *, cpu_pool: Executor | None = None) -> Iterator[Res[Emfit]]:
        return DAL(export_path=path, cpu_pool=cpu_pool).sleeps()


def demo(dal: DAL) -> None:
    for sleep in dal.sleeps():
        logger.info(f'parsed {sleep}')


if __name__ == '__main__':
    dal_helper.main(DAL=DAL, demo=demo)
