import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from ..dal import AWAKE, DAL, Emfit
from ..exporthelpers.dal_helper import Json


class FakeData:
    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

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
        # todo ok, mimesize seems pretty useless for now?
        # from mimesis.schema import Field, Schema
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

            _count = int((sleep_end - sleep_start) / self.frequency)

            # todo decide on periods when woken up first (sort of poisson distribution?), then fit the rest
            # todo instead, arange and assume sample every 5 secs or something?
            tss = np.arange(T(bed_start), T(bed_end), self.frequency.total_seconds())

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
            }  # fmt: skip

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
        for _i in range(count):
            j = self.generate()
            (path / f'{j["id"]}.json').write_text(json.dumps(j))


def test(tmp_path: Path) -> None:
    f = FakeData()
    f.fill(tmp_path, count=5)
    res = list(DAL(tmp_path).sleeps())
    for r in res:
        assert isinstance(r, Emfit)
    assert len(res) == 5
