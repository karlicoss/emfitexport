#!/usr/bin/env python3
from dataclasses import dataclass
from datetime import date, datetime
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
    # ok, I guess that's reasonable way of defining sleep date
    def date(self):
        return self.end.date() # type: ignore[attr-defined]

    @cproperty
    def time_in_bed(self):
        return int((self.sleep_end - self.sleep_start).total_seconds()) // 60  # type: ignore[attr-defined]

    @property
    def recovery(self):
        return self.hrv_morning - self.hrv_evening  # type: ignore[attr-defined]

    @property
    def summary(self):
        return f"""
in bed for {_hhmm(self.time_in_bed)}
emfit time: {_hhmm(self.sleep_minutes_emfit)}; covered: {self.sleep_hr_coverage:.0f}
hrv morning: {self.hrv_morning:.0f}
hrv evening: {self.hrv_evening:.0f}
avg hr: {self.measured_hr_avg:.0f}
recovery: {self.recovery:3.0f}
{self.hrv_lf}/{self.hrv_hf}
""".stip()  # type: ignore[attr-defined]

    @classmethod
    def make(cls, em: EmfitParse) -> Iterator[Res['Emfit']]:
        if em.epochs is None:
            # TODO yield errors??
            log.error('%s (on %s) got None in epochs! ignoring', em.sid, em.end)
            return

        # todo meh. not sure
        yield cls(**{
            # pylint: disable=no-member
            k: getattr(em, k) for k in Emfit.__annotations__
        })


def sleeps(path: Path) -> Iterator[Res[Emfit]]:
    # NOTE: ids seems to be consistent with ascending date order
    for f in list(sorted(path.glob('*.json'))):
        sid = f.stem
        em = EmfitParse(sid=sid, raw=json.loads(f.read_text()))
        yield from Emfit.make(em)
        # todo assert sorted??


def main():
    for x in sleeps(Path('/tmp/emfit')):
        print(x)


if __name__ == '__main__':
    main()
