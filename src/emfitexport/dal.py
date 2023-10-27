#!/usr/bin/env python3
from dataclasses import dataclass
from datetime import date as datetime_date, datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Iterator, List, Tuple

from .exporthelpers.dal_helper import Res, Json, datetime_aware
from .exporthelpers.logging_helper import make_logger


logger = make_logger(__name__)
log = logger  # legacy name, was used at HPI at some point, so keeping for backwards compat


def _hhmm(minutes) -> str:
    return '{:02d}:{:02d}'.format(*divmod(minutes, 60))


# def important on the sleep plot to have consistent local time
# todo hmm, emfit has time_user_gmt_offset?? how it is determined?
# seems that datapoints are in UTC though
def fromts(ts) -> datetime_aware:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
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
    def epochs(self) -> List[Tuple[int, int]]:
        # pairs of timestamp/epoch 'id'
        # these seems to be utc (can double check last epoch against to_utc field in export)
        return self.raw['sleep_epoch_datapoints']

    @property
    def epoch_series(self) -> Tuple[List[int], List[int]]:
        tss = []
        eps = []
        for [ts, e] in self.epochs:
            tss.append(ts)
            eps.append(e)
        return tss, eps

    @property
    def sleep_start(self) -> datetime_aware:
        for [ts, e] in self.epochs:
            if e == AWAKE:
                continue
            return fromts(ts)
        raise RuntimeError

    @property
    def sleep_end(self) -> datetime_aware:
        for [ts, e] in reversed(self.epochs):
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
        for i, [ts, e] in enumerate(self.epochs):
            if e != AWAKE:
                ff = i
                break
        for i in range(len(self.epochs) - 1, -1, -1):
            [ts, e] = self.epochs[i]
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
            [ts, pulse, br, activity] = ll
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
            [ts, rmssd, _, _, almost_always_zero, _] = ll
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
        tss, hrs = self.sleep_hr
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
    def from_json(cls, j: Json) -> 'Emfit':
        sid = j['id']
        em = EmfitParse(sid, raw=j)

        # todo meh
        return cls(**{k: getattr(em, k) for k in Emfit.__annotations__})


def sleeps(path: Path) -> Iterator[Res[Emfit]]:
    assert path.exists(), path  # ugh glob will just return empty sequence if dir doesn't exist
    # NOTE: ids seems to be consistent with ascending date order
    paths = sorted(path.glob('*.json'))
    for i, f in enumerate(paths):
        logger.info(f'processing {f} ({i}/{len(paths)})')
        try:
            j = json.loads(f.read_text())
            e = Emfit.from_json(j)
            yield e
        except Exception as ex:
            yield ex


### end of main DAL, rest is test & supplementary code
class FakeData:
    def __init__(self, seed: int = 0) -> None:
        self.seed = seed
        import numpy as np

        self.gen = np.random.default_rng(seed=self.seed)
        self.id = 0

        # hr is sort of a random walk?? probably not very accurate, but whatever
        # also keep within certain boundaries?
        # fmt: off
        self.cur_avg_hr  = 60.0
        self.rr_avg      = 13.0
        self.hrv_morning = 45.0
        self.hrv_evening = 55.0
        # fmt: on

        # todo would be nice to separate parameters and the state
        self.frequency = timedelta(seconds=30)  # NOTE: it better be aligned to minute boundaries..
        self.device_id = '1234'
        self.tz = timezone(offset=timedelta(hours=-4))  # kinda new york?
        self.first_day = datetime.strptime('20100101', '%Y%m%d')
        self.avg_sleep_minutes = 7 * 60
        # todo gaussian distribution??

    @property
    def today(self) -> datetime:
        return self.first_day + timedelta(days=self.id)

    def generate(self) -> Json:
        import numpy as np

        # todo ok, mimesize seems pretty useless for now?
        # from mimesis.schema import Field, Schema # type: ignore
        # mark fields I didn't bother filling for now
        # F = Field('en')
        todo = None
        G = self.gen

        def make_sleep():
            D = timedelta

            def ntd(mean, sigma):
                # 'normal' timedelta minutes
                val = G.normal(mean, sigma)
                val = max(0, val)
                return D(minutes=int(val))

            sleep_minutes = ntd(self.avg_sleep_minutes, 60)

            T = lambda d: int(d.timestamp())  # assume it's aligned by seconds for simplicity
            # fmt: off
            bed_start   = self.today + D(hours=23)  # todo randomize
            bed_end     = bed_start + sleep_minutes
            sleep_start = bed_start + ntd(30, 10)
            sleep_end   = bed_end   - ntd(20, 10)
            # fmt: on

            gmt_offset = self.tz.utcoffset(self.today) / D(minutes=1)

            sleep_duration = (sleep_end - sleep_start) / D(seconds=1)

            count = int((sleep_end - sleep_start) / self.frequency)

            # todo decide on periods when woken up first (sort of poisson distribution?), then fit the rest
            # todo instead, arange and assume sample every 5 secs or something?
            tss = np.arange(T(bed_start), T(bed_end), self.frequency.total_seconds())

            arange = np.arange
            # fmt: off
            return {
                "bed_exit_count"            : todo,
                "bed_exit_duration"         : todo,
                "bed_exit_periods"          : todo,
                "device_id"                 : self.device_id,
                "from_utc"                  : todo,
                "hrv_hf"                    : todo,
                "hrv_lf"                    : todo,
                "hrv_recovery_integrated"   : todo,
                "hrv_recovery_rate"         : todo,
                "hrv_recovery_ratio"        : todo,
                "hrv_recovery_total"        : todo,
                "hrv_rmssd_datapoints"      : [(
                    ts,
                    0,  # TODO HRV
                    todo,
                    todo,
                    todo,
                    todo
                ) for ts in tss],
                "hrv_rmssd_evening"         : self.hrv_evening,
                "hrv_rmssd_morning"         : self.hrv_morning,
                "id"                        : f'{self.id:06}',
                "measured_activity_avg"     : todo,
                "measured_datapoints"       : [(
                    ts,
                    G.normal(60, 5),  # TODO vary it throughout the night & have a global trend
                    G.normal(12, 2),
                    todo, # activity??
                ) for ts in tss],
                "measured_hr_avg"           : self.cur_avg_hr,  # todo simulate nightly HR via this
                "measured_hr_max"           : todo,
                "measured_hr_min"           : todo,
                # todo this should also be inferred instead from raw data
                "measured_rr_avg"           : self.rr_avg,
                "measured_rr_max"           : todo,
                "measured_rr_min"           : todo,
                "nodata_periods"            : todo,
                "note"                      : todo,
                "sleep_awakenings"          : todo,
                "sleep_class_awake_duration": todo,
                "sleep_class_awake_percent" : todo,
                "sleep_class_deep_duration" : todo,
                "sleep_class_deep_percent"  : todo,
                "sleep_class_light_duration": todo,
                "sleep_class_light_percent" : todo,
                "sleep_class_rem_duration"  : todo,
                "sleep_class_rem_percent"   : todo,
                "sleep_duration"            : sleep_duration,
                "sleep_efficiency"          : todo,
                "sleep_epoch_datapoints"    : [(t, AWAKE) for t in range(T(bed_start)  , T(sleep_start), 60)] + \
                                              [(t, 3    ) for t in range(T(sleep_start), T(sleep_end  ), 60)] + \
                                              [(t, AWAKE) for t in range(T(sleep_end)  , T(bed_end)    , 60)],
                "sleep_onset_duration"      : todo,
                "sleep_score"               : todo,
                "sleep_score_2"             : todo,
                "snoring_data"              : todo,
                "system_nodata_periods"     : todo,
                "time_duration"             : todo,
                "time_end"                  : T(bed_start),
                "time_end_string"           : todo,
                "time_in_bed_duration"      : todo,
                "time_start"                : T(bed_end),
                "time_start_gmt_offset"     : gmt_offset,
                "time_user_gmt_offset"      : todo,
                "to_utc"                    : todo,
                "tossnturn_count"           : todo,  # todo derive
                "tossnturn_datapoints"      : todo,
            }
            # fmt: on

        j = make_sleep()
        # fmt: off
        self.hrv_morning += G.normal(0, 0.9)
        self.hrv_evening += G.normal(0, 0.9)
        self.cur_avg_hr  += G.normal(0, 0.5)
        self.rr_avg      += G.normal(0, 0.1)
        # fmt: on
        self.id += 1
        return j

    def fill(self, path: Path, *, count: int) -> None:
        for i in range(count):
            j = self.generate()
            (path / f'{j["id"]}.json').write_text(json.dumps(j))


def test(tmp_path: Path) -> None:
    f = FakeData()
    f.fill(tmp_path, count=5)
    res = list(sleeps(tmp_path))
    for r in res:
        assert isinstance(r, Emfit)
    assert len(res) == 5


# todo use proper dal_helper.main?
def main() -> None:
    for x in sleeps(Path('/tmp/emfit')):
        print(x)


if __name__ == '__main__':
    main()
