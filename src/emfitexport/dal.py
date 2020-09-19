#!/usr/bin/env python3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from typing import Iterator

import pytz


from .exporthelpers.dal_helper import Res, Json, logger


log = logger(__name__)


def _hhmm(minutes) -> str:
    return '{:02d}:{:02d}'.format(*divmod(minutes, 60))


#
# def important on the sleep plot to have consistent local time
# todo hmm, emfit has time_user_gmt_offset?? how it is determined?
def fromts(ts) -> datetime:
    dt = datetime.fromtimestamp(ts, tz=pytz.utc)
    return dt


# todo tossnturn_count, tossnturn_datapoints (array of timestamps)
# todo use sleep class percents?

cproperty = property # todo?
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

    @property
    def hrv_morning(self) -> float:
        return self.raw['hrv_rmssd_morning']

    @property
    def hrv_evening(self) -> float:
        return self.raw['hrv_rmssd_evening']

    @property
    def start(self) -> datetime:
        """
        Bed enter time, not necessarily sleep start
        """
        return fromts(self.raw['time_start'])

    @property
    def end(self) -> datetime:
        """
        Bed exit time, not necessarily sleep end
        """
        return fromts(self.raw['time_end'])

    @property
    def epochs(self):
        # pairs of timestamp/epoch 'id'
        return self.raw['sleep_epoch_datapoints']

    @property
    def epoch_series(self):
        tss = []
        eps = []
        for [ts, e] in self.epochs:
            tss.append(ts)
            eps.append(e)
        return tss, eps

    @cproperty
    def sleep_start(self) -> datetime:
        for [ts, e] in self.epochs:
            if e == AWAKE:
                continue
            return fromts(ts)
        raise RuntimeError

    @cproperty
    def sleep_end(self) -> datetime:
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
        return self.epochs[ff: ll]


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

    @cproperty
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
    start: datetime
    end  : datetime
    sleep_start: datetime
    sleep_end  : datetime
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
    def date(self):
        return self.end.date()

    @cproperty
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
        return cls(**{
            # pylint: disable=no-member
            k: getattr(em, k) for k in Emfit.__annotations__
        })


# TODO FIXME handle this? not sure how common
# if em.epochs is None:
#     # TODO yield errors??
#     log.error('%s (on %s) got None in epochs! ignoring', em.sid, em.end)
#     return

def sleeps(path: Path) -> Iterator[Res[Emfit]]:
    # NOTE: ids seems to be consistent with ascending date order
    for f in list(sorted(path.glob('*.json'))):
        try:
            j = json.loads(f.read_text())
            e = Emfit.from_json(j)
            yield e
        except Exception as ex:
            raise ex
            # yield ex


### end of main DAL, rest is test & supplementary code

class FakeData:
    def __init__(self, seed: int=0) -> None:
        self.seed = seed
        import numpy as np # type: ignore
        self.gen = np.random.default_rng(seed=self.seed)
        self.id = 0
        # todo would be nice to separate parameters and the state
        self.frequency = timedelta(seconds=30) # NOTE: it better be aligned to minute boundaries..
        self.device_id = '1234'
        self.tz = pytz.timezone('America/New_York')
        self.first_day = datetime.strptime('20100101', '%Y%m%d')
        self.avg_sleep_minutes = 7 * 60
        # todo gaussian distribution??

    @property
    def today(self) -> datetime:
        return self.first_day + timedelta(days=self.id)

    def generate(self) -> Json:
        import numpy as np # type: ignore

        # todo ok, mimesize seems pretty useless for now?
        # from mimesis.schema import Field, Schema # type: ignore
        # mark fields I didn't bother filling for now
        # F = Field('en')
        todo = None

        def make_sleep():
            D = timedelta
            def ntd(mean, sigma):
                # 'normal' timedelta minutes
                val = self.gen.normal(mean, sigma)
                val = max(0, val)
                return D(minutes=int(val))

            sleep_minutes = ntd(self.avg_sleep_minutes, 60)

            T = lambda d: int(d.timestamp()) # assume it's aligned by seconds for simplicity
            bed_start = self.today + D(hours=23) # todo randomize
            bed_end   = bed_start + sleep_minutes
            gmt_offset = self.tz.utcoffset(self.today) / D(minutes=1) # type: ignore

            sleep_start = bed_start + ntd(30, 10)
            sleep_end   = bed_end   - ntd(20, 10)

            sleep_duration = (sleep_end - sleep_start) / D(seconds=1)

            count = int((sleep_end - sleep_start) / self.frequency)

            # todo decide on periods when woken up first (sort of poisson distribution?), then fit the rest
            # todo instead, arange and assume sample every 5 secs or something?
            tss = np.arange(T(bed_start), T(bed_end), self.frequency.total_seconds())

            arange = np.arange
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
                    0, # TODO HRV
                    todo,
                    todo,
                    todo,
                    todo
                ) for ts in tss],
                "hrv_rmssd_evening"         : todo,
                "hrv_rmssd_morning"         : todo,
                "id"                        : f'{self.id:06}',
                "measured_activity_avg"     : todo,
                "measured_datapoints"       : [(
                    ts,
                    self.gen.normal(60, 5), # TODO vary it throughout the night & have a global trend
                    self.gen.normal(12, 2),
                    todo, # activity??
                ) for ts in tss],
                "measured_hr_avg"           : todo,
                "measured_hr_max"           : todo,
                "measured_hr_min"           : todo,
                "measured_rr_avg"           : todo,
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
                "tossnturn_count"           : todo, # todo derive
                "tossnturn_datapoints"      : todo,
            }

        j = make_sleep()
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
def main():
    for x in sleeps(Path('/tmp/emfit')):
        print(x)


if __name__ == '__main__':
    main()
