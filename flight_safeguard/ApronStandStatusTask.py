"""
停机坪机位数据任务模块
@Author: Eric Cao
@Date: 2024/08/27
"""
import datetime
import logging
import os
from typing import Optional, Tuple, Union, List, Literal

import pandas as pd
from sqlalchemy import select, or_, JSON

from core import Task, Data, DataType
from mining import utils


class ApronStandStatusProcessor:
    """机场停机坪数据处理类"""

    def __init__(self, flight_info_index_name: str, safeguard_table: str, station: str):
        self.safeguard_table_name = safeguard_table
        self.station = station
        self.flight_info_index_name = flight_info_index_name

        # 预计起飞的飞机，在其预计起飞多久前，就认为该机位已经被占用
        flight_to_occupy_stand_duration = os.getenv(
            "FLIGHT_TO_OCCUPY_STAND_DURATION", "45m"
        )
        self.flight_to_occupy_stand_duration = utils.duration_to_minutes(
            flight_to_occupy_stand_duration
        )

        # 预计降落的飞机，在其预计降落时间多久以内，才能认为该机位必然没有飞机
        flight_to_free_stand_duration = os.getenv(
            "FLIGHT_TO_FREE_STAND_DURATION", "15m"
        )
        self.flight_to_free_stand_duration = utils.duration_to_minutes(
            flight_to_free_stand_duration
        )

        # 飞机落地到其开始占用机位的时间差，即飞机的滑行时间
        landing_to_occupy_stand_duration = os.getenv(
            "LANDING_TO_OCCUPY_STAND_DURATION", "1m"
        )
        self.landing_to_occupy_stand_gap = pd.Timedelta(
            landing_to_occupy_stand_duration
        )

        # 机位结束占用时间，当无法找到时，寻找该机位未来多久内的飞机的预计起飞时间，作为该机位的结束占用时间
        stand_occupy_end_duration = os.getenv("STAND_OCCUPY_END_DURATION", "24h")
        self.stand_occupy_end_duration = utils.duration_to_minutes(
            stand_occupy_end_duration
        )

        self.to_occupy_time = None
        self.to_free_time = None
        self.max_data_source_time = None  # 最新的数据源时间
        self.max_stand_occupy_end_time = None
        self.pg_flight_info_source = Data(
            DataType.POSTGRESSQL, "history_flight_info_refined", 'es_time'
        )
        self.pg_safeguard_source = Data(
            DataType.POSTGRESSQL, self.safeguard_table_name, 'created_at'
        )

        self.pg_apron_stand_status_store = Data(
            DataType.POSTGRES, 'apron_stand_status', 'created_at'
        )
        self.pg_apron_stand_status_store.safe_create_index('created_at')
        self.pg_apron_stand_status_store.safe_create_index('stand_id')
        self.pg_apron_stand_status_store.safe_create_index('station')

        # TODO: drop this table, as it is just for testing
        self.pg_apron_full_stand_status_store = Data(
            DataType.POSTGRES, 'apron_full_stand_status', 'created_at'
        )
        self.pg_apron_full_stand_status_store.safe_create_index('created_at')
        self.pg_apron_full_stand_status_store.safe_create_index('stand_id')
        self.pg_apron_full_stand_status_store.safe_create_index('station')

    def process(self):
        """
        机位状态处理主逻辑
        """
        processing_start_time = utils.now()
        stand_status_by_safeguard = self._load_latest_in_progress_safeguard_data()
        flight_info_with_stand_id_df = (
            self._load_latest_flight_info_with_stand_id_data()
        )

        latest_flight_info_created_at = utils.safe_convert_datetime_with_tz(
            flight_info_with_stand_id_df['es_time'].max()
        )
        latest_safeguard_created_at = None
        if not stand_status_by_safeguard.empty:
            latest_safeguard_created_at = utils.safe_convert_datetime_with_tz(
                stand_status_by_safeguard['created_at'].max()
            )
        else:
            latest_safeguard_created_at = (
                latest_flight_info_created_at - datetime.timedelta(days=2)
            )

        if latest_safeguard_created_at > latest_flight_info_created_at:
            self.max_data_source_time = latest_safeguard_created_at
            latest_source_name = 'safeguard'
        else:
            self.max_data_source_time = latest_flight_info_created_at
            latest_source_name = 'flight_info'
        self.to_occupy_time = self.max_data_source_time + datetime.timedelta(
            minutes=self.flight_to_occupy_stand_duration
        )
        self.to_free_time = self.max_data_source_time + datetime.timedelta(
            minutes=self.flight_to_free_stand_duration
        )
        self.max_stand_occupy_end_time = self.max_data_source_time + datetime.timedelta(
            minutes=self.stand_occupy_end_duration
        )
        logging.warning(
            "latest safeguard created at: %s, latest flight info created at: %s, so the latest source is %s",
            utils.time_to_str(latest_safeguard_created_at),
            utils.time_to_str(latest_flight_info_created_at),
            latest_source_name,
        )

        # 从航班信息中获取机位状态
        flight_info_with_stand_id_df['message_time'] = flight_info_with_stand_id_df[
            'message_time'
        ].apply(utils.safe_convert_datetime_with_tz)
        stand_status_by_flight_info = self.get_stand_status_by_flight_info(
            flight_info_with_stand_id_df
        )
        stand_status_by_flight_info['safeguard_start_time'] = None
        stand_status_by_flight_info['safeguard_events_max_time'] = None

        # 从保障节点数据中获取机位状态
        stand_status_by_safeguard['source'] = 'safeguard'
        stand_status_by_safeguard['station'] = self.station
        stand_status_by_safeguard['events_max_time'] = stand_status_by_safeguard[
            'events'
        ].apply(ApronStandStatusProcessor._get_events_max_time)

        # 合并保障和航班信息的机位状态
        for stand_id in stand_status_by_safeguard['stand_id'].unique():
            stand_status = self._merge_safeguard_and_flight_info_stand_status(
                stand_id, stand_status_by_safeguard, stand_status_by_flight_info
            )
            if stand_status is None or stand_status.empty:
                logging.warning(
                    "cannot find stand %s in both safeguard and flight info data",
                    stand_id,
                )
                continue
            if stand_status['source'] == 'safeguard':
                idx = stand_status_by_flight_info[
                    stand_status_by_flight_info['stand_id'] == stand_id
                ].index
                if not idx.empty:
                    stand_status_by_flight_info.loc[idx, 'source'] = 'safeguard'
                    stand_status_by_flight_info.loc[
                        idx, 'occupation_flight'
                    ] = 'safeguard'
                    stand_status_by_flight_info.loc[idx, 'reason'] = stand_status[
                        'reason'
                    ]
                    stand_status_by_flight_info.loc[idx, 'flight_uid'] = stand_status[
                        'flight_uid'
                    ]
                    stand_status_by_flight_info.loc[idx, 'registration'] = stand_status[
                        'registration'
                    ]
                    stand_status_by_flight_info.loc[
                        idx, 'safeguard_start_time'
                    ] = stand_status['start_time']
                    stand_status_by_flight_info.loc[
                        idx, 'stand_occupation_start_time'
                    ] = stand_status['start_time']
                    stand_status_by_flight_info.loc[
                        idx, 'safeguard_events_max_time'
                    ] = stand_status['events_max_time']
                else:
                    logging.warning(
                        "find a stand %s in safeguard data, but not in flight info data",
                        stand_id,
                    )
                    new_row = pd.DataFrame([stand_status])
                    new_row['source'] = 'safeguard'
                    new_row['station'] = self.station
                    new_row['stand_id'] = stand_id
                    new_row['safeguard_start_time'] = stand_status['start_time']
                    new_row['stand_occupation_start_time'] = stand_status['start_time']
                    new_row['safeguard_events_max_time'] = stand_status[
                        'events_max_time'
                    ]
                    try:
                        stand_status_by_flight_info = pd.concat(
                            [stand_status_by_flight_info, new_row]
                        )
                    except Exception as e:
                        logging.error(e)

        stand_status_by_flight_info.drop(
            columns=['PA_row', 'PD_row', 'FA_row', 'FD_row'], inplace=True
        )
        stand_status_by_flight_info.rename(
            columns={
                'PA_time': 'latest_actual_landing_time',
                'PD_time': 'latest_actual_take_off_time',
                'FA_time': 'earliest_estimated_landing_time',
                'FD_time': 'earliest_estimated_take_off_time',
            },
            inplace=True,
        )
        all_stand_status = stand_status_by_flight_info.copy()
        stand_status_result = stand_status_by_flight_info.loc[
            (stand_status_by_flight_info['registration'].notnull())
            & (stand_status_by_flight_info['flight_uid'].notnull())
        ].copy()
        stand_status_result['stand_occupation_start_time'] = stand_status_result[
            'stand_occupation_start_time'
        ].apply(utils.safe_convert_datetime_with_tz)
        stand_status_result['stand_occupation_end_time'] = stand_status_result[
            'stand_occupation_end_time'
        ].apply(utils.safe_convert_datetime_with_tz)
        stand_status_result['stand_occupation_probe_end_time'] = stand_status_result[
            'stand_occupation_probe_end_time'
        ].apply(utils.safe_convert_datetime_with_tz)
        stand_status_result['safeguard_start_time'] = stand_status_result[
            'safeguard_start_time'
        ].apply(utils.safe_convert_datetime_with_tz)
        stand_status_result['safeguard_events_max_time'] = stand_status_result[
            'safeguard_events_max_time'
        ].apply(utils.safe_convert_datetime_with_tz)

        to_remove_stand_ids = self._get_out_date_stand_ids(stand_status_result)
        if len(to_remove_stand_ids) > 0:
            logging.warning(
                "remove %s stand occupied info from result that is actually not occupied",
                len(to_remove_stand_ids),
            )
            stand_status_result = stand_status_result[
                ~stand_status_result['stand_id'].isin(to_remove_stand_ids)
            ].copy()

        finished_time = utils.now()
        occupied_stand_ids = set(stand_status_result['stand_id'])
        total_stand_ids = set(stand_status_by_safeguard['stand_id']) | set(
            stand_status_by_flight_info['stand_id']
        )
        logging.warning(
            "Apron stand latest status computed at %s, "
            "occupied stand/total stand: %s/%s",
            utils.time_to_str(finished_time),
            len(occupied_stand_ids),
            len(total_stand_ids),
        )

        self.pg_apron_stand_status_store.save(
            stand_status_result, finished_time, index=False, dtype={'events': JSON}
        )
        self.pg_apron_stand_status_store.delete_before(
            keep_since_in_minutes=60 * 24 * 3
        )

        self.pg_apron_full_stand_status_store.save(
            all_stand_status, finished_time, index=False, dtype={'events': JSON}
        )
        self.pg_apron_full_stand_status_store.delete_before(
            keep_since_in_minutes=60 * 24 * 3
        )

        logging.info(
            "processed data successfully at %s, cost time: %f minutes",
            utils.time_to_str(utils.now()),
            ((utils.now() - processing_start_time).total_seconds() / 60),
        )
        return not stand_status_result.empty

    def _get_out_date_stand_ids(self, stand_status_result: pd.DataFrame):
        """
        获取实际上已经离开的飞机的机位信息
        """
        to_remove_stand_ids = set()
        for _, row in stand_status_result.iterrows():
            registration = row['registration']
            source = row['source']
            stand_id = row['stand_id']
            flight_str = self._get_flight_str(row)
            flight_date_str = row['flight_uid'][:8]
            today_str = utils.now().strftime('%Y%m%d')
            if flight_date_str != today_str and pd.notna(registration):
                if source == 'flight_info':
                    flight_row = self._get_latest_finished_flight_info_by_registration(
                        registration
                    )
                    if flight_row is not None:
                        latest_flight_date = utils.get_date_from_flight_uid(
                            flight_row['flight_uid']
                        )
                        row_flight_date = utils.get_date_from_flight_uid(
                            row['flight_uid']
                        )
                        if latest_flight_date > row_flight_date:
                            # 该注册号的飞机的最新信息在其他机位，说明该飞机已经离开了该机位，需要从结果中删除
                            to_remove_stand_ids.add(row['stand_id'])
                            logging.warning(
                                "result shows %s is at stand %s since %s,"
                                " but latest flight info shows that %s,"
                                " and the latest flight date is %s, newer than row flight's date %s,"
                                " so remove it from result",
                                flight_str,
                                stand_id,
                                utils.time_to_local_str(
                                    row.get(
                                        'stand_occupation_start_time',
                                        row.get('start_time', ''),
                                    )
                                ),
                                self._get_flight_info_log_str(flight_row),
                                flight_row['flight_uid'][:8],
                                row['flight_uid'][:8],
                            )
                            continue
                else:
                    # 如果 source 是 safeguard，那么需要检查该飞机的最新保障节点的信息
                    safeguard_row = self._get_latest_safeguard_info_by_registration(
                        registration
                    )
                    if safeguard_row is not None:
                        if (
                            safeguard_row['flight_uid'] == row['flight_uid']
                            and safeguard_row['stand_id'] == row['stand_id']
                            and safeguard_row['status'] == 'in progress'
                        ):
                            # 保障节点显示该飞机最新信息在该机位，说明该飞机还在该机位，不需要删除
                            continue
                        latest_safeguard_date = utils.get_date_from_flight_uid(
                            safeguard_row['flight_uid']
                        )
                        row_flight_date = utils.get_date_from_flight_uid(
                            row['flight_uid']
                        )
                        if (
                            safeguard_row['stand_id'] != row['stand_id']
                            and latest_safeguard_date > row_flight_date
                        ):
                            # 保障节点显示该飞机最新信息在其他机位，说明该飞机已经离开了该机位，需要从结果中删除
                            to_remove_stand_ids.add(row['stand_id'])
                            logging.warning(
                                "result shows %s is at stand %s since %s,"
                                " but latest safeguard info shows that %s,"
                                " and the latest safeguard date is %s, newer than row flight's date %s,"
                                " so remove it from result",
                                flight_str,
                                stand_id,
                                utils.time_to_local_str(
                                    row.get(
                                        'stand_occupation_start_time',
                                        row.get('start_time', ''),
                                    )
                                ),
                                self._get_safeguard_log_str(safeguard_row),
                                safeguard_row['flight_uid'][:8],
                                row['flight_uid'][:8],
                            )
                            continue
        return to_remove_stand_ids

    @staticmethod
    def _get_safeguard_log_str(safeguard_row: dict):
        flight_str = ApronStandStatusProcessor._get_flight_str(safeguard_row)
        start_time = utils.time_to_local_str(safeguard_row['start_time'])
        end_time = utils.time_to_local_str(safeguard_row['end_time'])
        station = safeguard_row['station']
        stand_id = safeguard_row['stand_id']
        return f"{flight_str} is at {station} stand {stand_id} since {start_time} to {end_time}"

    @staticmethod
    def _get_flight_info_log_str(flight_row: dict):
        flight_str = ApronStandStatusProcessor._get_flight_str(flight_row)
        direction_str = (
            'taken off'
            if pd.notna(flight_row['actual_take_off_date_time'])
            else 'landed'
        )
        station = flight_row['station']
        stand_id = flight_row['stand_id']
        if pd.notna(flight_row['actual_take_off_date_time']):
            time_str = utils.time_to_local_str(flight_row['actual_take_off_date_time'])
        else:
            time_str = utils.time_to_local_str(flight_row['actual_landing_date_time'])
        return f"{flight_str} has {direction_str} at {station} stand {stand_id} at {time_str}"

    def _get_fd_occupation_start_time(
        self, fd_row: pd.Series, pa_row: Optional[pd.Series]
    ):
        """
        计算即将起飞的飞机的开始占用机位的事件
        :param fd_row: 未来起飞的航班信息
        :param pa_row: 过去到达的航班信息
        """
        if pa_row is not None and pa_row['registration'] == fd_row['registration']:
            return pa_row['actual_landing_date_time']
        if pd.notna(fd_row['actual_landing_date_time']):
            return fd_row['actual_landing_date_time']
        fd_registration = fd_row['registration']
        fd_stand_id = fd_row['stand_id']
        flight_str = self._get_flight_str(fd_row)
        if fd_registration is None:
            logging.warning(
                "cannot find the registration of FD %s at stand %s",
                flight_str,
                fd_stand_id,
            )
            return None
        last_landing_flight = self._get_latest_flight_landing_record(fd_registration)
        if last_landing_flight is None:
            logging.warning(
                "cannot find last landing flight for FD %s at stand %s",
                flight_str,
                fd_stand_id,
            )
            return None
        if last_landing_flight['stand_id'] == fd_stand_id:
            return last_landing_flight['actual_landing_date_time']
        logging.warning(
            "cannot find last landing flight for FD %s at stand %s, as the last landing flight is %s at stand %s",
            flight_str,
            fd_stand_id,
            self._get_flight_str(last_landing_flight),
            last_landing_flight.get('stand_id', ''),
        )
        return None

    @staticmethod
    def _get_base_flight_str(row: pd.Series):
        return f"({row['flight_uid']}@{row['registration']})"

    @utils.retry_catch_exception
    def _get_latest_flight_landing_record(self, registration: str):
        flight_info_table = self.pg_flight_info_source.get_table()
        with self.pg_flight_info_source.pg.connect() as conn:
            query = (
                select(
                    flight_info_table.c.flight_uid,
                    flight_info_table.c.registration,
                    flight_info_table.c.stand_id,
                    flight_info_table.c.actual_take_off_date_time,
                    flight_info_table.c.actual_landing_date_time,
                    flight_info_table.c.created_at,
                )
                .where(flight_info_table.c.registration == registration)  # noqa
                .where(flight_info_table.c.is_primary.is_(True))
                .where(flight_info_table.c.base_airport_iata_code == self.station)
                .where(flight_info_table.c.actual_landing_date_time.isnot(None))
                .order_by(
                    flight_info_table.c.flight_uid.desc(),
                    flight_info_table.c.es_time.desc(),
                )
                .limit(1)
            )
            result = conn.execute(query).first()
            if result is None:
                return None
            return {
                'flight_uid': result[0],
                'registration': result[1],
                'stand_id': result[2],
                'actual_take_off_date_time': result[3],
                'actual_landing_date_time': result[4],
                'created_at': result[5],
            }

    @utils.retry_catch_exception
    def _get_latest_finished_flight_info_by_registration(self, registration: str):
        """
        get latest finished flight info by registration
        """
        flight_info_table = self.pg_flight_info_source.get_table()
        with self.pg_flight_info_source.pg.connect() as conn:
            query = (
                select(
                    flight_info_table.c.flight_uid,
                    flight_info_table.c.registration,
                    flight_info_table.c.stand_id,
                    flight_info_table.c.actual_take_off_date_time,
                    flight_info_table.c.actual_landing_date_time,
                    flight_info_table.c.base_airport_iata_code,
                    flight_info_table.c.created_at,
                )
                .where(flight_info_table.c.registration == registration)  # noqa
                .where(flight_info_table.c.is_primary.is_(True))
                .where(
                    or_(
                        flight_info_table.c.actual_take_off_date_time.isnot(None),
                        flight_info_table.c.actual_landing_date_time.isnot(None),
                    )
                )
                .order_by(
                    flight_info_table.c.flight_uid.desc(),
                    flight_info_table.c.es_time.desc(),
                )
                .limit(1)
            )
            result = conn.execute(query).first()
            if result is None:
                return None
            return {
                'flight_uid': result[0],
                'registration': result[1],
                'stand_id': result[2],
                'actual_take_off_date_time': result[3],
                'actual_landing_date_time': result[4],
                'station': result[5],
                'created_at': result[6],
            }

    @utils.retry_catch_exception
    def _get_latest_safeguard_info_by_registration(self, registration: str):
        """
        get latest safeguard info by registration
        """
        safeguard_table = self.pg_safeguard_source.get_table(self.safeguard_table_name)
        with self.pg_safeguard_source.pg.connect() as conn:
            query = (
                select(
                    safeguard_table.c.flight_uid,
                    safeguard_table.c.registration,
                    safeguard_table.c.stand_id,
                    safeguard_table.c.start_time,
                    safeguard_table.c.end_time,
                    safeguard_table.c.status,
                    safeguard_table.c.created_at,
                )
                .where(safeguard_table.c.registration == registration)
                .where(safeguard_table.c.status != 'error')
                .order_by(safeguard_table.c.created_at.desc())
                .limit(1)
            )
            result = conn.execute(query).first()
            if result is None:
                return None
            return {
                'flight_uid': result[0],
                'registration': result[1],
                'stand_id': result[2],
                'start_time': result[3],
                'end_time': result[4],
                'status': result[5],
                'created_at': result[6],
                'station': self.station,
            }

    @utils.retry_catch_exception(max_retries=3, retry_interval=2)
    def _load_latest_in_progress_safeguard_data(self):
        safeguard_query = """
            SELECT flight_uid,
                   registration,
                   stand_id,
                   start_time,
                   end_time,
                   status,
                   events,
                   created_at
            FROM {safeguard_table}
            WHERE created_at = (SELECT MAX(created_at) FROM {safeguard_table})
              AND status = 'in progress'
        """.format(
            safeguard_table=self.safeguard_table_name
        )
        df = self.pg_safeguard_source.load(query=safeguard_query)
        if df.empty:
            logging.error("Cannot get latest safeguard data, check the safeguard table")
        return df

    @utils.retry_catch_exception
    def _load_latest_flight_info_with_stand_id_data(self):
        flight_info_query = """
            SELECT * FROM history_flight_info_refined WHERE
                index_name='{flight_info_index_name}'
            AND
                stand_id IS NOT NULL
            AND 
                is_primary = TRUE
            AND
                stand_id != ''
            AND flight_scheduled_date > (now()-interval '7 day')
                """.format(
            flight_info_index_name=self.flight_info_index_name
        )

        df = self.pg_flight_info_source.load(query=flight_info_query)
        if df.empty:
            logging.error(
                "Cannot get latest flight info data, check the flight info table"
            )
            raise ValueError(
                "Cannot get latest flight info data, so cannot get stand status, please check the flight info table"
            )
        logging.info(
            "loaded %d flight info records in %s", len(df), self.flight_info_index_name
        )
        return df

    def get_stand_status_by_flight_info(
        self, flight_info_with_stand_id_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        从航班信息中获取机位状态
        约定
        P = Past
        F = Future
        A = Arrival
        D = Departure

        PA = Past Arrival 过去到达
        PD = Past Departure 过去出发
        FA = Future Arrival 将来到达
        FD = Future Departure 将来出发

        :param flight_info_with_stand_id_df: 带有机位信息的航班信息
        :return: 机位状态表
        """
        flight_stand_status_list = []
        for stand_id, group_df in flight_info_with_stand_id_df.groupby(
            'stand_id', dropna=True
        ):
            stand_id = str(stand_id)
            (
                flight_row,
                stand_other_flight_info_dict,
            ) = self._get_stand_current_flight_info(group_df)

            result_dict = {
                'station': self.station,
                'stand_id': stand_id,
                'registration': None,
                'flight_uid': None,
                'PA_time': stand_other_flight_info_dict['PA_time'],
                'PD_time': stand_other_flight_info_dict['PD_time'],
                'FA_time': stand_other_flight_info_dict['FA_time'],
                'FD_time': stand_other_flight_info_dict['FD_time'],
                'PA_row': self.transform_row_to_dict(
                    stand_other_flight_info_dict['PA_row']
                ),
                'PD_row': self.transform_row_to_dict(
                    stand_other_flight_info_dict['PD_row']
                ),
                'FA_row': self.transform_row_to_dict(
                    stand_other_flight_info_dict['FA_row']
                ),
                'FD_row': self.transform_row_to_dict(
                    stand_other_flight_info_dict['FD_row']
                ),
                'occupation_flight': stand_other_flight_info_dict['occupation_flight'],
                'message_time': stand_other_flight_info_dict['message_time'],
                'reason': '\n'.join(stand_other_flight_info_dict['reason_list']),
                'stand_occupation_start_time': stand_other_flight_info_dict[
                    'stand_occupation_start_time'
                ],
                'stand_occupation_end_time': stand_other_flight_info_dict[
                    'stand_occupation_end_time'
                ],
                'stand_occupation_probe_end_time': None,
                'source': 'flight_info',
            }
            if flight_row is not None:
                result_dict['registration'] = flight_row['registration']
                result_dict['flight_uid'] = flight_row['flight_uid']
                if result_dict['stand_occupation_end_time'] is None:
                    # 当没有找到结束时间时，尝试找到从未来该机位即将起飞的航班的预计起飞时间作为结束时间
                    departure_time = self._probe_departure_time(
                        flight_info_with_stand_id_df, flight_row['registration']
                    )
                    if departure_time is not None:
                        result_dict['stand_occupation_end_time'] = departure_time
                    else:
                        (
                            latest_take_off_time,
                            latest_take_off_row,
                        ) = self._get_earliest_departure_time_and_row(group_df)
                        if latest_take_off_time is not None:
                            take_off_flight_str = self._get_flight_str(
                                latest_take_off_row
                            )

                            # 暂时将这个值放入另一个字段中，以区分
                            result_dict[
                                'stand_occupation_probe_end_flight'
                            ] = take_off_flight_str
                            result_dict[
                                'stand_occupation_probe_end_time'
                            ] = latest_take_off_time

            flight_stand_status_list.append(result_dict)
        return pd.DataFrame(flight_stand_status_list)

    @staticmethod
    def _get_target_fields_extreme_value_and_row(
        df_in: pd.DataFrame,
        target_fields: List[str],
        extreme: Literal['max', 'min'] = 'max',
    ) -> Tuple[Optional[pd.Timestamp], Optional[pd.Series]]:
        """
        Get the extreme (max or min) value of the target field and the corresponding row.
        If there are multiple extreme values, return the row with a non-null registration.
        :param df_in: DataFrame to search
        :param target_fields: The fields to find the extreme value for
        :param extreme: 'max' or 'min' to specify which extreme to find
        :return: The extreme value and the corresponding row
        """
        if df_in.empty:
            return None, None

        # 复制DataFrame避免修改原始数据
        df = df_in.copy()

        # 转换目标字段为datetime格式
        for target_field in target_fields:
            df[target_field] = df[target_field].apply(
                utils.safe_convert_datetime_with_tz
            )

        # 初始化结果变量
        extreme_value = None
        extreme_row = None

        # 对每个目标字段进行处理
        for target_field in target_fields:
            # 跳过所有值为空的字段
            if df[target_field].isna().all():
                continue

            # 获取极值
            if extreme == 'max':
                current_extreme = df[target_field].max()
            else:  # extreme == 'min'
                current_extreme = df[target_field].min()

            # 如果找到了有效的极值
            if pd.notna(current_extreme):
                # 获取具有该极值的所有行
                extreme_rows = df[df[target_field] == current_extreme]

                # 如果只有一行，直接使用该行
                if len(extreme_rows) == 1:
                    extreme_value = current_extreme
                    extreme_row = extreme_rows.iloc[0]
                    break
                # 如果有多行，优先选择registration不为空的行
                elif len(extreme_rows) > 1:
                    # 假设存在'registration'列，如果没有这列需要相应调整
                    valid_rows = extreme_rows[extreme_rows['registration'].notna()]
                    if not valid_rows.empty:
                        extreme_value = current_extreme
                        extreme_row = valid_rows.iloc[0]
                        break
                    else:
                        # 如果没有registration不为空的行，使用第一行
                        extreme_value = current_extreme
                        extreme_row = extreme_rows.iloc[0]
                        break

        return extreme_value, extreme_row

    @staticmethod
    def _get_earliest_estimated_time_and_row(
        df_in: pd.DataFrame, direction: str = "D"
    ) -> Tuple[Optional[pd.Timestamp], Optional[pd.Series]]:
        """
        :param df_in: 分组后的航班信息DataFrame
        :param direction: 起飞或降落
        :return: 最早的预计起飞或者降落时间和对应的行
        """
        if direction not in ["A", "D"]:
            raise ValueError("direction should be 'A' or 'D'")
        if direction == 'D':
            index = df_in[
                (df_in['flight_direction'] == 'D')
                & (pd.isna(df_in['actual_take_off_date_time']))
            ].index
        else:
            index = df_in[
                (df_in['flight_direction'] == 'A')
                & (pd.isna(df_in['actual_landing_date_time']))
            ].index
        if index.empty:
            return None, None
        df = df_in.loc[index].copy()
        if direction == 'D':
            (
                earliest_estimated_datetime,
                earliest_estimated_row,
            ) = ApronStandStatusProcessor._get_target_fields_extreme_value_and_row(
                df,
                target_fields=[
                    'estimated_off_block_date_time',
                    'estimated_take_off_date_time',
                ],
                extreme='min',
            )
            return earliest_estimated_datetime, earliest_estimated_row
        else:
            (
                earliest_estimated_datetime,
                earliest_estimated_row,
            ) = ApronStandStatusProcessor._get_target_fields_extreme_value_and_row(
                df,
                target_fields=[
                    'estimated_on_block_date_time',
                    'estimated_landing_date_time',
                ],
                extreme='min',
            )
            return earliest_estimated_datetime, earliest_estimated_row

    def _probe_departure_time(
        self, df_in: pd.DataFrame, registration: str
    ) -> Optional[pd.Timestamp]:
        """
        探测飞机的预计起飞时间
        :param df_in: 航班信息
        :param registration: 飞机注册号
        :return: 预计起飞时间
        """
        df = df_in[
            (df_in['registration'] == registration) & (df_in['flight_direction'] == 'D')
        ].copy()
        if df.empty:
            return None
        df['estimated_take_off_date_time'] = df['estimated_take_off_date_time'].apply(
            utils.safe_convert_datetime_with_tz
        )
        valid_estimated_take_off_df = df[
            df['estimated_take_off_date_time'] > self.max_data_source_time
        ]
        if not valid_estimated_take_off_df.empty:
            return valid_estimated_take_off_df['estimated_take_off_date_time'].min()

        df['scheduled_take_off_date_time'] = df['scheduled_take_off_date_time'].apply(
            utils.safe_convert_datetime_with_tz
        )
        valid_schedule_take_off_df = df[
            df['scheduled_take_off_date_time'] > self.max_data_source_time
        ]
        if not valid_schedule_take_off_df.empty:
            return valid_schedule_take_off_df['scheduled_take_off_date_time'].min()
        return None

    def _get_earliest_departure_time_and_row(
        self, df_in: pd.DataFrame
    ) -> Tuple[Optional[pd.Timestamp], Optional[pd.Series]]:
        """
        :param df_in: 分组后的航班信息DataFrame
        :return: 最早的预计起飞时间和对应的行
        """
        df = df_in[
            (df_in['flight_direction'] == 'D')
            & (pd.isna(df_in['actual_take_off_date_time']))
        ].copy()

        if df.empty:
            return None, None

        df['estimated_take_off_date_time'] = df['estimated_take_off_date_time'].apply(
            utils.safe_convert_datetime_with_tz
        )
        valid_estimated_take_off_df = df[
            (self.max_stand_occupy_end_time > df['estimated_take_off_date_time'])
            & (df['estimated_take_off_date_time'] > self.max_data_source_time)
        ]
        if not valid_estimated_take_off_df.empty:
            return self._get_target_fields_extreme_value_and_row(
                valid_estimated_take_off_df,
                target_fields=[
                    'estimated_off_block_date_time',
                    'estimated_take_off_date_time',
                ],
                extreme='min',
            )

        df['scheduled_take_off_date_time'] = df['scheduled_take_off_date_time'].apply(
            utils.safe_convert_datetime_with_tz
        )
        valid_schedule_take_off_df = df[
            (self.max_stand_occupy_end_time > df['scheduled_take_off_date_time'])
            & (df['scheduled_take_off_date_time'] > self.max_data_source_time)
        ]
        if not valid_schedule_take_off_df.empty:
            return self._get_target_fields_extreme_value_and_row(
                valid_schedule_take_off_df,
                target_fields=[
                    'scheduled_off_block_date_time',
                    'scheduled_take_off_date_time',
                ],
                extreme='min',
            )
        return None, None

    def _get_stand_current_flight_info(self, stand_group: pd.DataFrame):
        """
        根据机位的航班信息，推断机位的状态
        :param stand_group: 该机位的历史航班信息
        :return: 当前该机位的航班信息(如果有），以及该机位最近的起飞和降落信息
        """
        # 针对 PA 和 PD 的特别说明：
        # 1. PA 按 actual_on_block_date_time 到 actual_landing_date_time 顺序，取最大值
        # 2. PD 按 actual_off_block_date_time 到 actual_take_off_date_time 顺序，取最大值
        PA_time, PA_row = self._get_target_fields_extreme_value_and_row(
            stand_group,
            target_fields=['actual_on_block_date_time', 'actual_landing_date_time'],
            extreme='max',
        )
        PD_time, PD_row = self._get_target_fields_extreme_value_and_row(
            stand_group,
            target_fields=['actual_off_block_date_time', 'actual_take_off_date_time'],
            extreme='max',
        )  # 利用实际撤轮档时间作为飞机离开机位时间
        FA_time, FA_row = self._get_earliest_estimated_time_and_row(stand_group, 'A')
        FD_time, FD_row = self._get_earliest_estimated_time_and_row(stand_group, 'D')

        more_info_dict = {
            'PA_time': PA_time,
            'PD_time': PD_time,
            'FA_time': FA_time,
            'FD_time': FD_time,
            'PA_row': PA_row,
            'PD_row': PD_row,
            'FA_row': FA_row,
            'FD_row': FD_row,
            'message_time': None,
            'stand_occupation_start_time': None,
            'stand_occupation_end_time': None,
            'occupation_flight': None,
            'reason_list': [],
        }

        def check_fd_occupation(
            fd_time, fd_row, fa_time, fa_row, reference_time: Optional[pd.Timestamp]
        ):
            if fd_time is None:
                return None
            if reference_time is not None and reference_time > fd_time:
                return None
            if self._is_time_in_gone_occupy_stand_range(fd_time):
                if (
                    pd.notna(fa_time)
                    and fa_time < fd_time
                    and fa_row['registration'] == fd_row['registration']
                ):
                    # 未来起飞的飞机恰好是未来到达的飞机，且未来到来比未来起飞早，说明在未来到来之前机位是空的
                    return handle_empty(
                        f"with FA:{self._get_flight_str(fa_row)} before FD:{self._get_flight_str(fd_row)}, so empty"
                    )
                start_time = self._get_fd_occupation_start_time(fd_row, PA_row)
                return handle_occupation(fd_row, start_time, fd_time, "FD")
            return None

        # 辅助函数：根据条件返回结果
        def handle_occupation(
            flight_row, occupation_start_time, occupation_end_time, flight_type
        ):
            flight_str = self._get_flight_str(flight_row)
            more_info_dict['reason_list'].append(
                f"occupied by {flight_type}:{flight_str}"
            )
            more_info_dict['stand_occupation_start_time'] = occupation_start_time
            more_info_dict['stand_occupation_end_time'] = occupation_end_time
            more_info_dict['occupation_flight'] = flight_type
            more_info_dict['message_time'] = flight_row['message_time']
            return flight_row, more_info_dict

        def handle_empty(reason):
            more_info_dict['reason_list'].append(reason)
            return None, more_info_dict

        if pd.notna(PA_time):  # 过去有飞机降落
            PA_str = self._get_flight_str(PA_row)
            more_info_dict['reason_list'].append(f"with PA:{PA_str}")

            if pd.notna(PD_time):  # 有最近的起飞事件
                PD_str = self._get_flight_str(PD_row)
                more_info_dict['reason_list'].append(f"with PD:{PD_str}")

                if PD_time > PA_time:  # 降落后有起飞
                    fd_result = check_fd_occupation(
                        FD_time, FD_row, FA_time, FA_row, PA_time
                    )
                    if fd_result is not None:
                        return fd_result

                    if (
                        self._is_time_in_gone_free_stand_range(FA_time)
                        and PD_time < FA_time
                    ):
                        return handle_empty(
                            f"with FA:{self._get_flight_str(FA_row)}, so empty"
                        )
                    return handle_empty("PD after PA, so empty")
                else:  # 先有起飞，再有降落
                    fd_result = check_fd_occupation(
                        FD_time, FD_row, FA_time, FA_row, PA_time
                    )
                    if fd_result is not None:
                        return fd_result

                    if (
                        self._is_time_in_gone_free_stand_range(FA_time)
                        and PA_time < FA_time
                    ):
                        return handle_empty(
                            f"with FA:{self._get_flight_str(FA_row)}, so empty"
                        )
                    if (
                        self.max_data_source_time
                        < PA_time + self.landing_to_occupy_stand_gap
                    ):
                        return handle_empty(
                            f"with PA:{self._get_flight_str(PA_row)} at {utils.time_to_local_str(PA_time)}, "
                            f"but too close to landing, so empty"
                        )
                    return handle_occupation(PA_row, PA_time, None, 'PA')
            else:  # 过去没有飞机起飞
                more_info_dict['reason_list'].append("no PD")
                fd_result = check_fd_occupation(
                    FD_time, FD_row, FA_time, FA_row, PA_time
                )
                if fd_result is not None:
                    return fd_result
                if (
                    self._is_time_in_gone_free_stand_range(FA_time)
                    and PA_time < FA_time
                ):
                    return handle_empty(
                        f"with FA:{self._get_flight_str(FA_row)}, so empty"
                    )
                if (
                    self.max_data_source_time
                    < PA_time + self.landing_to_occupy_stand_gap
                ):
                    return handle_empty(
                        f"with PA:{self._get_flight_str(PA_row)} at {utils.time_to_local_str(PA_time)}, "
                        f"but too close to landing, so empty"
                    )
                return handle_occupation(PA_row, PA_time, None, 'PA')
        else:  # 过去没有飞机降落
            more_info_dict['reason_list'].append("no PA")

            if pd.notna(PD_time):
                # 有起飞事件
                PD_str = self._get_flight_str(PD_row)
                more_info_dict['reason_list'].append(f"with PD:{PD_str}")

                fd_result = check_fd_occupation(
                    FD_time, FD_row, FA_time, FA_row, PD_time
                )
                if fd_result is not None:
                    return fd_result

                if (
                    self._is_time_in_gone_free_stand_range(FA_time)
                    and PD_time < FA_time
                ):
                    return handle_empty(
                        f"with FA:{self._get_flight_str(FA_row)}, so empty"
                    )
                return handle_empty("only PD, so empty")
            else:  # PD_time 为空，说明即没有起飞又没有降落
                more_info_dict['reason_list'].append("no PD")

                fd_result = check_fd_occupation(FD_time, FD_row, FA_time, FA_row, None)
                if fd_result is not None:
                    return fd_result
                if self._is_time_in_gone_free_stand_range(FA_time):
                    return handle_empty(
                        f"with FA:{self._get_flight_str(FA_row)}, so empty"
                    )
                return handle_empty("no PD, FD or FA, so empty")

    def _is_time_in_gone_occupy_stand_range(self, time: pd.Timestamp) -> bool:
        """判断时间是否在即将占用的时间范围内"""
        return pd.notna(time) and self.max_data_source_time < time < self.to_occupy_time

    def _is_time_in_gone_free_stand_range(self, time: pd.Timestamp) -> bool:
        """判断时间是否在即将空闲的时间范围内"""
        return pd.notna(time) and self.max_data_source_time < time < self.to_free_time

    @staticmethod
    def _merge_safeguard_and_flight_info_stand_status(
        stand_id: str, safeguard_df: pd.DataFrame, flight_info_df: pd.DataFrame
    ):
        """
        合并保障和航班信息的机位状态
        :param stand_id: 机位号
        :param safeguard_df: 保障节点数据
        :param flight_info_df: 航班信息数据
        :return: 合并后的机位状态
        """
        safeguard_row_index = safeguard_df[safeguard_df['stand_id'] == stand_id].index
        flight_info_row_index = flight_info_df[
            flight_info_df['stand_id'] == stand_id
        ].index
        if safeguard_row_index.empty:
            # 保障节点中无该机位，则直接取航班信息数据
            return flight_info_df[flight_info_row_index]
        safeguard_row = safeguard_df.loc[safeguard_row_index[0]].copy()
        if flight_info_row_index.empty:
            # 航班信息中无该机位，则直接取保障节点数据
            safeguard_row['reason'] = "no flight info, so return safeguard data"
            safeguard_row['occupation_flight'] = 'safeguard'
            return safeguard_row
        flight_info_row = (
            flight_info_df[flight_info_df['stand_id'] == stand_id].iloc[0].copy()
        )
        safeguard_str = ApronStandStatusProcessor._get_flight_str(safeguard_row)
        flight_info_str = ApronStandStatusProcessor._get_flight_str(flight_info_row)
        if flight_info_row['flight_uid'] is not None:
            # 有飞机
            if flight_info_row['registration'] == safeguard_row['registration']:
                flight_info_time_str = utils.time_to_local_str(
                    flight_info_row['message_time']
                )
                safeguard_time_str = utils.time_to_local_str(
                    safeguard_row['events_max_time']
                )
                # 保障节点显示的飞机和航班信息显示的飞机是同一架飞机，根据谁更新返回说明
                if flight_info_row['message_time'] > safeguard_row['events_max_time']:
                    flight_info_row['reason'] += (
                        f"\n flight_info {flight_info_str} time {flight_info_time_str} "
                        f"is later_than safeguard {safeguard_str} time {safeguard_time_str}, "
                        f"so return flight info {flight_info_str}"
                    )
                    return flight_info_row
                else:
                    safeguard_row['reason'] = (
                        flight_info_row['reason']
                        + f"\n safeguard {safeguard_str} time {safeguard_time_str} "
                        f"is later_than flight_info {flight_info_str} time {flight_info_time_str}, "
                        f"so return safeguard {safeguard_str}"
                    )
                    safeguard_row['occupation_flight'] = 'safeguard'
                    return safeguard_row

            # 如果两边显示是不同的飞机
            if flight_info_row['occupation_flight'] == "PA":
                if pd.notna(safeguard_row['start_time']) and pd.notna(
                    flight_info_row['stand_occupation_start_time']
                ):
                    # 认为更晚到的飞机是新来的，正确的飞机
                    flight_info_time = flight_info_row['stand_occupation_start_time']
                    safeguard_time = safeguard_row['start_time']
                elif pd.notna(safeguard_row['events_max_time']) and pd.notna(
                    flight_info_row['message_time']
                ):
                    flight_info_time = flight_info_row['message_time']
                    safeguard_time = safeguard_row['events_max_time']
                else:
                    # 无法判断，返回航班信息
                    safeguard_row['reason'] = flight_info_row['reason'] + (
                        f"\nconflict between safeguard {safeguard_str} and flight info {flight_info_str}, "
                        "and cannot determine by time, "
                        "so return safeguard data"
                    )
                    safeguard_row['occupation_flight'] = 'safeguard'
                    return safeguard_row
                # 两个值都不为空，进行比较后返回正确的值
                flight_info_time_str = utils.time_to_local_str(flight_info_time)
                safeguard_time_str = utils.time_to_local_str(safeguard_time)
                if flight_info_time > safeguard_time:
                    flight_info_row['reason'] += (
                        f"\n flight_info {flight_info_str} time {flight_info_time_str} "
                        f"is later_than safeguard {safeguard_str} time {safeguard_time_str}, "
                        f"so return flight info {flight_info_str}"
                    )

                    return flight_info_row
                safeguard_row['reason'] = flight_info_row['reason'] + (
                    f"\n safeguard {safeguard_str} time {safeguard_time_str} "
                    f"is later_than flight_info {flight_info_str} time {flight_info_time_str}, "
                    f"so return safeguard {safeguard_str}"
                )
                safeguard_row['occupation_flight'] = 'safeguard'
                return safeguard_row
            elif flight_info_row['occupation_flight'] == "FD":
                if pd.notna(safeguard_row['events_max_time']) and pd.notna(
                    flight_info_row['message_time']
                ):
                    # 两个值都不为空，进行表叫后返回正确的值
                    flight_info_time = flight_info_row['message_time']
                    safeguard_time = safeguard_row['events_max_time']
                    flight_info_time_str = utils.time_to_local_str(flight_info_time)
                    safeguard_time_str = utils.time_to_local_str(safeguard_time)
                    if flight_info_time > safeguard_time:
                        flight_info_row['reason'] += (
                            f"\n flight_info {flight_info_str} time {flight_info_time_str} "
                            f"is later_than safeguard {safeguard_str} time {safeguard_time_str}, "
                            f"so return flight info {flight_info_str}"
                        )
                        return flight_info_row
                    safeguard_row['reason'] = flight_info_row['reason'] + (
                        f"\n safeguard {safeguard_str} time {safeguard_time_str} "
                        f"is later_than flight_info {flight_info_str} time {flight_info_time_str}, "
                        f"so return safeguard {safeguard_str}"
                    )
                    safeguard_row['occupation_flight'] = 'safeguard'
                    return safeguard_row

                # 无法判断，采用safeguard数据
                safeguard_row['reason'] = flight_info_row['reason'] + (
                    f"\nconflict between safeguard {safeguard_str} and flight info {flight_info_str}, "
                    "and cannot determine by time, "
                    "so return safeguard data"
                )
                safeguard_row['occupation_flight'] = 'safeguard'
                return safeguard_row
            else:
                # 如果不是PA或者FD，无法判断，直接返回safeguard数据
                safeguard_row['reason'] = flight_info_row['reason'] + (
                    f"\nflight info {flight_info_str} is not PA or FD, so return safeguard {safeguard_str}"
                )
                safeguard_row['occupation_flight'] = 'safeguard'
                return safeguard_row
        else:
            # 从该机位的航班信息看，该机位没有飞机，但保障节点显示仍然有飞机在机位上
            # 此时根据飞机起飞的时间和保障节点的时间区间来判断
            # 判断是否实际该飞机起飞但是保障节点数据没有更新
            if (
                flight_info_row['PD_time'] is not None
                and flight_info_row['PD_time'] > safeguard_row['events_max_time']
            ):
                flight_info_row['reason'] += (
                    f"\nflight {flight_info_str} has taken off but safeguard {safeguard_str} is still in progress, "
                    f"take flight info {flight_info_str}"
                )
                return flight_info_row
            else:
                # 其他情况，取safeguard的数据
                safeguard_row['reason'] = flight_info_row['reason'] + (
                    f"\nflight info {flight_info_str} , so return safeguard {safeguard_str}"
                )
                safeguard_row['occupation_flight'] = 'safeguard'
                return safeguard_row

    @staticmethod
    def _get_events_max_time(events: list) -> Optional[pd.Timestamp]:
        if len(events) == 0:
            return None
        events_df = pd.DataFrame(events)
        events_df['time'] = events_df['time'].apply(utils.safe_convert_datetime_with_tz)
        return events_df['time'].max()

    @staticmethod
    def _get_flight_str(in_data: Union[pd.Series, dict, None]) -> str:
        if (
            in_data is None
            or 'flight_uid' not in in_data
            or 'registration' not in in_data
        ):
            return "None flight"
        return f"({in_data['flight_uid']}@{in_data['registration']})"

    @staticmethod
    def transform_row_to_dict(row: pd.Series):
        """Transform the given row to dict and remove None or empty value"""
        if row is not None:
            return {k: v for k, v in row.items() if v is not None and v != ''}
        else:
            return None


class SaaApronStandStatusTask(Task):
    """虹桥机场停机坪机位数据任务"""

    TASK_NAME = "saa_apron_stand_status"
    TASK_INTERVAL = int(os.getenv("APRON_STAND_STATUS_INTERVAL", 1))

    def __init__(self):
        super().__init__()
        self._processor = ApronStandStatusProcessor(
            flight_info_index_name="saafis*", safeguard_table="safeguard", station="SHA"
        )

    def process(self):
        """Task processing"""
        self._processor.process()


class PvgApronStandStatusTask(Task):
    """浦东机场停机坪机位数据任务"""

    TASK_NAME = "pvg_apron_stand_status"
    TASK_INTERVAL = int(os.getenv("APRON_STAND_STATUS_INTERVAL", 1))

    def __init__(self):
        super().__init__()
        self._processor = ApronStandStatusProcessor(
            flight_info_index_name="pvgfis*",
            safeguard_table="pvg_safeguard",
            station="PVG",
        )

    def process(self):
        """Task processing"""
        self._processor.process()
