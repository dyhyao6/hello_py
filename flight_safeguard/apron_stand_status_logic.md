# 停机坪机位状态 (Apron Stand Status) 推断逻辑文档

本逻辑用于根据航班信息 (FIS) 和保障节点 (Safeguard) 数据，实时推断机位的占用情况及当前停靠的飞机实体。

## 1. 核心标识字段

在最终结果中，以下字段用于标识“哪架飞机”：

- **`registration`**: 飞机注册号（机尾号），区分物理飞机的唯一标识。
- **`flight_uid`**: 航班唯一标识，关联具体的航司、航班号和日期。

## 2. 航班信息 (FIS) 推断字段

系统根据以下四类事件（PA, PD, FA, FD）及其对应的时间字段进行优先级排序和逻辑推断。

### 2.1 过去到达 (PA - Past Arrival)

- **判定字段 (取最大值/最晚时间)**:
    - `actual_on_block_date_time` (实际入位时间)
    - `actual_landing_date_time` (实际落地时间)
- **用途**: 判定上一架进入该机位的飞机。

### 2.2 过去起飞 (PD - Past Departure)

- **判定字段 (取最大值/最晚时间)**:
    - `actual_off_block_date_time` (实际撤轮挡时间)
    - `actual_take_off_date_time` (实际起飞时间)
- **用途**: 判定上一架离开该机位的飞机。

### 2.3 将来到达 (FA - Future Arrival)

- **判定字段 (取最小值/最早时间)**:
    - `estimated_on_block_date_time` (预计入位时间)
    - `estimated_landing_date_time` (预计落地时间)
- **用途**: 预警即将有飞机进入机位。

### 2.4 将来起飞 (FD - Future Departure)

- **判定字段 (优先级从高到低，取最小值)**:
    1. `estimated_off_block_date_time` / `estimated_take_off_date_time` (预计起飞)
    2. `scheduled_off_block_date_time` / `scheduled_take_off_date_time` (计划起飞)
- **用途**: 判定已经在机位上准备起飞的飞机（如拖车进位的飞机）。

---

## 3. 推断决策树 (优先级排序)

| 优先级       | 逻辑条件 (满足即终止)                                              | 判定结果 (Status & Aircraft)  |
|:----------|:----------------------------------------------------------|:--------------------------|
| **1 (高)** | 当前时间处于 **FD** 窗口内 (即 `now < FD_time < now + 45min`)       | **占用**: 使用 `FD_row` 的飞机信息 |
| **2**     | `PA_time > PD_time` 且距离落地已过 1 分钟 (`now > PA_time + 1min`) | **占用**: 使用 `PA_row` 的飞机信息 |
| **3**     | `now < FA_time < now + 15min`                             | **空闲**: 预留机位给即将落地的飞机      |
| **4**     | `PD_time > PA_time`                                       | **空闲**: 最后一架飞机已离开         |
| **5 (低)** | 以上均不满足                                                    | **空闲**                    |

---

## 4. 保障节点 (Safeguard)(虹桥) 融合字段

当 FIS 数据与保障节点数据不一致时，使用以下字段进行校准：

### 不一致解释

1. 比如： stand_id = 221 机位 , 对应的最新一条航班信息 (FIS) 与最新的一条保障节点 (Safeguard) 数据不一致。

```sql
--(Safeguard)
select *
from safeguard
where status = 'in progress'
  and stand_id = '221'
order by created_at desc limit 1;
--(FIS)
select flight_uid, flight_identity, base_airport_iata_code
from history_flight_info_refined
where stand_id = '221'
  and index_name = 'saafis*'
order by created_at desc limit 1;

```

- **`status`**: 必须为 `in progress` 才认为保障正在进行。
- **`events`**: 保障事件列表，通过遍历提取 `time` 字段的最大值，定义为 `events_max_time`。
- **`start_time`**: 保障任务开始时间。
- **校准逻辑**:
    - 如果 `Safeguard.events_max_time > FIS.message_time`，则放弃 FIS 结论，改用 Safeguard 里的 `registration` 和
      `flight_uid`。

---

## 5. 环境阈值 (配置参数)

逻辑行为受以下环境变量控制：

- `FLIGHT_TO_OCCUPY_STAND_DURATION`: 提前占用窗口 (默认 45m)。
- `FLIGHT_TO_FREE_STAND_DURATION`: 预警空闲窗口 (默认 15m)。
- `LANDING_TO_OCCUPY_STAND_GAP`: 滑行缓冲时间 (默认 1m)。

## 6. 数据库和表信息

- **数据库连接信息**:

```shell
SOURCE_DB_HOST = "10.143.36.7"
SOURCE_DB_PORT = "31647"
SOURCE_DB_NAME = "edi_data"
SOURCE_DB_USER = "readonly"
SOURCE_DB_PASSWORD = "88UM6Joj7BhBPKjN0E1B"
```

- **history_flight_info_refined表信息**:

```sql
CREATE TABLE public.history_flight_info_refined
(
    id                                             serial4     NOT NULL,
    flight_uid                                     text        NOT NULL,
    es_time                                        timestamptz NOT NULL,
    flight_identity                                text NULL,
    base_airport_iata_code                         text NULL,
    base_airport_icao_code                         text NULL,
    flight_scheduled_date                          timestamp NULL,
    flight_direction                               text NULL,
    message_type                                   text NULL,
    message_time                                   timestamp NULL,
    airline_iata_code                              text NULL,
    airline_icao_code                              text NULL,
    flight_status                                  text NULL,
    flight_status_cn                               text NULL,
    estimated_previous_airport_departure_date_time timestamptz NULL,
    actual_on_bridge_date_time                     timestamptz NULL,
    estimated_off_block_date_time                  timestamptz NULL,
    actual_door_close_date_time                    timestamptz NULL,
    actual_cargo_door_close_date_time              timestamptz NULL,
    baggage_reclaims                               text NULL,
    call_sign                                      text NULL,
    actual_landing_date_time                       timestamptz NULL,
    actual_on_block_date_time                      timestamptz NULL,
    estimated_landing_date_time                    timestamptz NULL,
    minimum_turn_around_time                       text NULL,
    estimated_on_block_date_time                   timestamptz NULL,
    actual_previous_airport_departure_date_time    timestamptz NULL,
    gates                                          text NULL,
    stand_id                                       text NULL,
    aircraft_iata_code                             text NULL,
    aircraft_icao_code                             text NULL,
    registration                                   text NULL,
    operation_status_cn                            text NULL,
    operation_status                               text NULL,
    total_passengers                               text NULL,
    baggage_weight                                 text NULL,
    baggage_number                                 text NULL,
    cargo_weight                                   text NULL,
    mail_weight                                    text NULL,
    link_flight_direction                          text NULL,
    link_flight_identity                           text NULL,
    link_flight_scheduled_date                     text NULL,
    first_baggage_date_time                        timestamptz NULL,
    last_baggage_date_time                         timestamptz NULL,
    actual_off_bridge_date_time                    timestamptz NULL,
    boarding_start_date_time                       timestamptz NULL,
    last_call_date_time                            timestamptz NULL,
    boarding_end_date_time                         timestamptz NULL,
    actual_off_block_date_time                     timestamptz NULL,
    actual_take_off_date_time                      timestamptz NULL,
    counters                                       text NULL,
    check_in_open_date_time                        timestamptz NULL,
    check_in_close_date_time                       timestamptz NULL,
    estimated_take_off_date_time                   timestamptz NULL,
    estimated_taxi_out_time                        text NULL,
    flight_scheduled_date_time                     timestamptz NULL,
    scheduled_on_block_date_time                   timestamptz NULL,
    flight_route                                   text NULL,
    concourse                                      text NULL,
    flight_terminal_id                             text NULL,
    cancel_reason                                  text NULL,
    iata_full_route                                text NULL,
    flight_country_type                            text NULL,
    is_over_night_flight                           text NULL,
    flight_iata_service_type                       text NULL,
    operative_comment                              text NULL,
    flight_caac_service_type                       text NULL,
    icao_full_route                                text NULL,
    iata_previous_airport                          text NULL,
    iata_origin_airport                            text NULL,
    icao_origin_airport                            text NULL,
    icao_previous_airport                          text NULL,
    slave_flight                                   text NULL,
    baggage_makeups                                text NULL,
    scheduled_next_airport_arrival_date_time       timestamptz NULL,
    scheduled_off_block_date_time                  timestamptz NULL,
    icao_destination_airport                       text NULL,
    icao_next_airport                              text NULL,
    iata_next_airport                              text NULL,
    iata_destination_airport                       text NULL,
    runway_id                                      text NULL,
    index_name                                     text NULL,
    is_primary                                     bool        DEFAULT true NULL,
    created_at                                     timestamptz DEFAULT CURRENT_TIMESTAMP NULL,
    total_weight                                   text NULL,
    total_adult_passengers_number                  text NULL,
    latest_take_off_time                           text NULL,
    total_infant_passengers_number                 text NULL,
    total_child_passengers_number                  text NULL,
    decision_off_block_date_time                   timestamptz NULL,
    calculated_take_off_date_time                  timestamptz NULL,
    estimated_off_block_date_time_atc              text NULL,
    target_off_block_date_time                     timestamptz NULL,
    is_blocked                                     text NULL,
    actual_startup_request_date_time               timestamptz NULL,
    actual_startup_approved_date_time              timestamptz NULL,
    fuuid                                          text NULL,
    internal_id                                    text NULL,
    security_check_passenger_count                 text NULL,
    check_in_passenger_count                       text NULL,
    onboard_passenger_count                        text NULL,
    is_transit_flight                              text NULL,
    airline_cn                                     text NULL,
    airline_en                                     text NULL,
    best_known_on_block_date_time                  timestamptz NULL,
    ten_miles_date_time                            timestamptz NULL,
    current_stand_id                               text NULL,
    scheduled_previous_airport_departure_date_time timestamptz NULL,
    estimated_fly_time                             text NULL,
    scheduled_landing_date_time                    timestamptz NULL,
    ramp_agent                                     text NULL,
    cn_full_route                                  text NULL,
    cn_previous_airport                            text NULL,
    en_origin_airport                              text NULL,
    cn_origin_airport                              text NULL,
    scheduled_fly_time                             text NULL,
    en_previous_airport                            text NULL,
    actual_next_airport_arrival_date_time          timestamptz NULL,
    estimated_next_airport_arrival_date_time       timestamptz NULL,
    best_known_off_block_date_time                 timestamptz NULL,
    counter_areas                                  text NULL,
    scheduled_take_off_date_time                   timestamptz NULL,
    cn_next_airport                                text NULL,
    en_next_airport                                text NULL,
    en_destination_airport                         text NULL,
    cn_destination_airport                         text NULL,
    create_reason                                  text NULL,
    diversion_airport_icao_code                    text NULL,
    diversion_airport_en                           text NULL,
    diversion_airport_cn                           text NULL,
    diversion_airport_iata_code                    text NULL,
    target_startup_approved_date_time              timestamptz NULL,
    deboarding_start_date_time                     timestamptz NULL,
    cdm_control_comment                            text NULL,
    cdm_control_point                              text NULL,
    cdm_control_reason                             text NULL,
    e_strip_status                                 text NULL,
    taxiing_start_date_time                        timestamptz NULL,
    dispatch_ticket_write_date_time                timestamptz NULL,
    in_stand_datetime                              text NULL,
    out_stand_datetime                             text NULL,
    actual_cargo_door_open_date_time               timestamptz NULL,
    actual_door_open_date_time                     timestamptz NULL,
    deboarding_end_date_time                       timestamptz NULL,
    dispatch_ticket_accept_date_time               timestamptz NULL,
    pilot_ready_date_time                          timestamptz NULL,
    manifest_finish_date_time                      timestamptz NULL,
    on_brake_date_time                             timestamptz NULL,
    off_brake_date_time                            timestamptz NULL,
    aircraft_dispatch_date_time                    timestamptz NULL,
    external_delay_reason                          text NULL,
    crew_enter_date_time                           timestamptz NULL,
    update_time                                    timestamptz DEFAULT CURRENT_TIMESTAMP NULL,
    is_deleted                                     bool        DEFAULT false NULL,
    estimated_flight_terminal_id                   text NULL,
    actual_deicing_start_date_time                 text NULL,
    actual_deicing_end_date_time                   text NULL,
    estimated_taxi_in_time                         text NULL,
    actual_taxi_in_time                            text NULL,
    base_airportght_scheduled_date_time            text NULL,
    generic_resource                               text NULL,
    target_landing_date_time                       text NULL,
    actual_taxi_out_time                           text NULL,
    basirport_icao_code                            text NULL,
    CONSTRAINT history_flight_info_refined_flight_uid_key UNIQUE (flight_uid),
    CONSTRAINT history_flight_info_refined_pkey PRIMARY KEY (id)
);
```

- **safeguard 表信息**:

```sql
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
```

## safeguard 表数据示例：
flight_safeguard/safeguard.json

## 需求：
1、根据stand_id, 推断机位的占用情况及当前停靠的飞机实体
2、推断所有机位的占用情况及当前停靠的飞机实体
