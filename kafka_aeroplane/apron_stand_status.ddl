CREATE TABLE public.apron_stand_status
(
    station                           text NULL,
    stand_id                          text NULL,
    registration                      text NULL,
    flight_uid                        text NULL,
    latest_actual_landing_time        timestamptz NULL,
    latest_actual_take_off_time       timestamptz NULL,
    "source"                          text NULL,
    safeguard_events_min_time         timestamp NULL,
    safeguard_events_max_time         timestamp NULL,
    created_at                        timestamptz NULL,
    reason                            text NULL,
    stand_occupation_start_time       timestamptz NULL,
    stand_occupation_end_time         timestamptz NULL,
    safeguard_start_time              timestamptz NULL,
    occupation_flight                 text NULL,
    message_time                      timestamptz NULL,
    earliest_estimated_landing_time   timestamptz NULL,
    earliest_estimated_take_off_time  timestamptz NULL,
    stand_occupation_probe_end_flight text NULL,
    stand_occupation_probe_end_time   timestamptz NULL,
    start_time                        timestamptz NULL,
    end_time                          text NULL,
    status                            text NULL,
    events                            text NULL,
    events_max_time                   timestamptz NULL
);

CREATE INDEX idx_apron_stand_status_station_created_at ON public.apron_stand_status USING btree (station, created_at DESC);
CREATE INDEX ix_apron_stand_status_created_at ON public.apron_stand_status USING btree (created_at);
CREATE INDEX ix_apron_stand_status_stand_id ON public.apron_stand_status USING btree (stand_id);
CREATE INDEX ix_apron_stand_status_station ON public.apron_stand_status USING btree (station);