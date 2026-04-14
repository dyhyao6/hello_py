-- public.safeguard definition

-- Drop table

-- DROP TABLE public.safeguard;

CREATE TABLE public.safeguard
(
    session_id        text NULL,
    status            text NULL,
    start_time        timestamptz NULL,
    events            json NULL,
    end_time          timestamptz NULL,
    stand_id          text NULL,
    station           text NULL,
    camera_id         text NULL,
    flight_uid        text NULL,
    call_sign         text NULL,
    created_at        timestamptz NULL,
    id                serial4 NOT NULL,
    registration      text NULL,
    taxi_time         text NULL,
    now_time          timestamptz NULL,
    "delete"          bool DEFAULT false NULL,
    mock              bool DEFAULT false NULL,
    merged_flight_uid varchar(255) NULL,
    CONSTRAINT pk_safeguard PRIMARY KEY (id)
);
CREATE INDEX ix_safeguard_created_at ON public.safeguard USING btree (created_at);
CREATE INDEX ix_safeguard_created_at_when_status_in_progress ON public.safeguard USING btree (created_at DESC) WHERE (status = 'in progress'::text);
CREATE INDEX ix_safeguard_end_time ON public.safeguard USING btree (end_time);
CREATE INDEX ix_safeguard_query ON public.safeguard USING btree (created_at, start_time DESC);
CREATE INDEX ix_safeguard_stand_id ON public.safeguard USING btree (stand_id);
CREATE INDEX ix_safeguard_start_time ON public.safeguard USING btree (start_time);
CREATE INDEX ix_safeguard_station ON public.safeguard USING btree (station);
CREATE INDEX safeguard_merged_flight_uid_index ON public.safeguard USING btree (merged_flight_uid);