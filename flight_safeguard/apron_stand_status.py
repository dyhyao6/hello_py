"""
停机坪机位状态 (Apron Stand Status) 推断模块

根据航班信息 (FIS) 和保障节点 (Safeguard) 数据，实时推断机位的占用情况及当前停靠的飞机实体。
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
from enum import Enum

import psycopg2
from psycopg2.extras import RealDictCursor


class StandStatus(Enum):
    OCCUPIED = "occupied"      # 占用
    FREE = "free"              # 空闲
    RESERVED = "reserved"      # 预留（即将有飞机）


@dataclass
class AircraftInfo:
    """飞机实体信息"""
    registration: Optional[str] = None      # 飞机注册号
    flight_uid: Optional[str] = None        # 航班唯一标识
    flight_identity: Optional[str] = None    # 航班号
    stand_id: Optional[str] = None          # 机位号
    status: Optional[str] = None            # 保障状态
    source: str = "fis"                     # 数据来源: fis / safeguard


@dataclass
class StandStatusResult:
    """机位状态推断结果"""
    stand_id: str
    status: StandStatus
    aircraft: Optional[AircraftInfo]
    reasoning: str


# 环境阈值配置
FLIGHT_TO_OCCUPY_STAND_DURATION = timedelta(minutes=45)   # 提前占用窗口
FLIGHT_TO_FREE_STAND_DURATION = timedelta(minutes=15)      # 预警空闲窗口
LANDING_TO_OCCUPY_STAND_GAP = timedelta(minutes=1)        # 滑行缓冲时间


class ApronStandStatusService:
    """机位状态推断服务"""

    def __init__(self):
        self._db_config = {
            "host": os.getenv("SOURCE_DB_HOST", "10.143.36.7"),
            "port": int(os.getenv("SOURCE_DB_PORT", "31647")),
            "database": os.getenv("SOURCE_DB_NAME", "edi_data"),
            "user": os.getenv("SOURCE_DB_USER", "readonly"),
            "password": os.getenv("SOURCE_DB_PASSWORD", "88UM6Joj7BhBPKjN0E1B"),
        }

    def _get_connection(self):
        return psycopg2.connect(
            **self._db_config,
            cursor_factory=RealDictCursor
        )

    def _get_now(self) -> datetime:
        """获取当前时间，可被子类覆盖用于测试"""
        return datetime.now()

    def get_flight_info_by_stand(self, stand_id: str) -> Optional[dict]:
        """获取指定机位最新的航班信息"""
        sql = """
            SELECT flight_uid, flight_identity, base_airport_iata_code,
                   actual_on_block_date_time, actual_landing_date_time,
                   actual_off_block_date_time, actual_take_off_date_time,
                   estimated_on_block_date_time, estimated_landing_date_time,
                   estimated_off_block_date_time, estimated_take_off_date_time,
                   scheduled_off_block_date_time, scheduled_take_off_date_time,
                   registration, stand_id, message_time
            FROM history_flight_info_refined
            WHERE stand_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (stand_id,))
                result = cur.fetchone()
                return dict(result) if result else None

    def get_all_stands_flight_info(self) -> list[dict]:
        """获取所有机位的最新航班信息"""
        sql = """
            SELECT DISTINCT ON (stand_id)
                   stand_id, flight_uid, flight_identity, base_airport_iata_code,
                   actual_on_block_date_time, actual_landing_date_time,
                   actual_off_block_date_time, actual_take_off_date_time,
                   estimated_on_block_date_time, estimated_landing_date_time,
                   estimated_off_block_date_time, estimated_take_off_date_time,
                   scheduled_off_block_date_time, scheduled_take_off_date_time,
                   registration, message_time
            FROM history_flight_info_refined
            WHERE stand_id IS NOT NULL
            ORDER BY stand_id, created_at DESC
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                return [dict(row) for row in cur.fetchall()]

    def get_safeguard_by_stand(self, stand_id: str) -> Optional[dict]:
        """获取指定机位最新的保障节点数据"""
        sql = """
            SELECT session_id, status, start_time, events, end_time,
                   stand_id, flight_uid, call_sign, registration, now_time
            FROM safeguard
            WHERE stand_id = %s AND status = 'in progress'
            ORDER BY created_at DESC
            LIMIT 1
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (stand_id,))
                result = cur.fetchone()
                return dict(result) if result else None

    def get_all_stands_safeguard(self) -> list[dict]:
        """获取所有机位的最新保障节点数据"""
        sql = """
            SELECT DISTINCT ON (stand_id)
                   session_id, status, start_time, events, end_time,
                   stand_id, flight_uid, call_sign, registration, now_time
            FROM safeguard
            WHERE stand_id IS NOT NULL AND status = 'in progress'
            ORDER BY stand_id, created_at DESC
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                return [dict(row) for row in cur.fetchall()]

    def _extract_events_max_time(self, events_data) -> Optional[datetime]:
        """从保障事件中提取最大时间"""
        if not events_data:
            return None
        try:
            # events 可能是 str (JSON) 或 list
            events = events_data if isinstance(events_data, list) else json.loads(events_data)
            if not events:
                return None
            max_time = None
            for event in events:
                event_time_str = event.get("time")
                if event_time_str:
                    # 解析 ISO 格式时间
                    event_time = datetime.fromisoformat(event_time_str.replace("+08:00", "+08:00"))
                    if max_time is None or event_time > max_time:
                        max_time = event_time
            return max_time
        except (json.JSONDecodeError, ValueError):
            return None

    def infer_stand_status(self, stand_id: str) -> StandStatusResult:
        """
        根据决策树推断指定机位的占用状态

        决策树优先级:
        1. FD窗口 (now < FD_time < now + 45min) -> 占用
        2. PA_time > PD_time 且 now > PA_time + 1min -> 占用
        3. now < FA_time < now + 15min -> 空闲(预留)
        4. PD_time > PA_time -> 空闲
        5. 其他 -> 空闲
        """
        now = self._get_now()
        fis = self.get_flight_info_by_stand(stand_id)
        safeguard = self.get_safeguard_by_stand(stand_id)

        # Safeguard 校准：如果存在且状态为 in_progress
        if safeguard:
            safeguard_aircraft = AircraftInfo(
                registration=safeguard.get("registration"),
                flight_uid=safeguard.get("flight_uid"),
                stand_id=stand_id,
                status=safeguard.get("status"),
                source="safeguard"
            )
            safeguard_max_time = self._extract_events_max_time(safeguard.get("events"))
            fis_message_time = fis.get("message_time") if fis else None

            # 如果 Safeguard 的事件时间更新，使用 Safeguard 数据
            if safeguard_max_time and fis_message_time:
                if safeguard_max_time > fis_message_time:
                    return StandStatusResult(
                        stand_id=stand_id,
                        status=StandStatus.OCCUPIED,
                        aircraft=safeguard_aircraft,
                        reasoning=f"Safeguard events_max_time ({safeguard_max_time}) > FIS message_time ({fis_message_time})"
                    )
            elif safeguard_max_time and not fis_message_time:
                return StandStatusResult(
                    stand_id=stand_id,
                    status=StandStatus.OCCUPIED,
                    aircraft=safeguard_aircraft,
                    reasoning="No FIS data, using Safeguard data"
                )

        if not fis:
            return StandStatusResult(
                stand_id=stand_id,
                status=StandStatus.FREE,
                aircraft=None,
                reasoning="No FIS or Safeguard data available"
            )

        # 提取时间字段
        actual_on_block = fis.get("actual_on_block_date_time")
        actual_landing = fis.get("actual_landing_date_time")
        actual_off_block = fis.get("actual_off_block_date_time")
        actual_take_off = fis.get("actual_take_off_date_time")
        estimated_on_block = fis.get("estimated_on_block_date_time")
        estimated_landing = fis.get("estimated_landing_date_time")
        estimated_off_block = fis.get("estimated_off_block_date_time")
        estimated_take_off = fis.get("estimated_take_off_date_time")
        scheduled_off_block = fis.get("scheduled_off_block_date_time")
        scheduled_take_off = fis.get("scheduled_take_off_date_time")

        # PA: 取最大值
        pa_time = None
        if actual_on_block:
            pa_time = actual_on_block
        if actual_landing and (pa_time is None or actual_landing > pa_time):
            pa_time = actual_landing

        # PD: 取最大值
        pd_time = None
        if actual_off_block:
            pd_time = actual_off_block
        if actual_take_off and (pd_time is None or actual_take_off > pd_time):
            pd_time = actual_take_off

        # FD: 取最小值
        fd_time = None
        if estimated_off_block:
            fd_time = estimated_off_block
        if estimated_take_off and (fd_time is None or estimated_take_off < fd_time):
            fd_time = estimated_take_off
        if scheduled_off_block and (fd_time is None or scheduled_off_block < fd_time):
            fd_time = scheduled_off_block
        if scheduled_take_off and (fd_time is None or scheduled_take_off < fd_time):
            fd_time = scheduled_take_off

        # FA: 取最小值
        fa_time = None
        if estimated_on_block:
            fa_time = estimated_on_block
        if estimated_landing and (fa_time is None or estimated_landing < fa_time):
            fa_time = estimated_landing

        aircraft = AircraftInfo(
            registration=fis.get("registration"),
            flight_uid=fis.get("flight_uid"),
            flight_identity=fis.get("flight_identity"),
            stand_id=stand_id,
            source="fis"
        )

        # 决策树
        # 优先级1: FD窗口
        if fd_time and now < fd_time < now + FLIGHT_TO_OCCUPY_STAND_DURATION:
            return StandStatusResult(
                stand_id=stand_id,
                status=StandStatus.OCCUPIED,
                aircraft=aircraft,
                reasoning=f"FD window: now={now}, FD_time={fd_time}"
            )

        # 优先级2: PA_time > PD_time 且 now > PA_time + 1min
        if pa_time and pd_time and pa_time > pd_time:
            if now > pa_time + LANDING_TO_OCCUPY_STAND_GAP:
                return StandStatusResult(
                    stand_id=stand_id,
                    status=StandStatus.OCCUPIED,
                    aircraft=aircraft,
                    reasoning=f"PA={pa_time} > PD={pd_time}, now={now} > PA+1min"
                )

        # 优先级3: now < FA_time < now + 15min
        if fa_time and now < fa_time < now + FLIGHT_TO_FREE_STAND_DURATION:
            return StandStatusResult(
                stand_id=stand_id,
                status=StandStatus.RESERVED,
                aircraft=None,
                reasoning=f"Reserved for FA: now={now}, FA_time={fa_time}"
            )

        # 优先级4: PD_time > PA_time
        if pd_time and pa_time and pd_time > pa_time:
            return StandStatusResult(
                stand_id=stand_id,
                status=StandStatus.FREE,
                aircraft=None,
                reasoning=f"PD={pd_time} > PA={pa_time}, stand is free"
            )

        # 优先级5: 其他
        return StandStatusResult(
            stand_id=stand_id,
            status=StandStatus.FREE,
            aircraft=None,
            reasoning="Default: stand is free"
        )

    def infer_all_stands_status(self) -> list[StandStatusResult]:
        """推断所有机位的占用状态"""
        fis_data = self.get_all_stands_flight_info()
        stand_ids = set()
        for fis in fis_data:
            if fis.get("stand_id"):
                stand_ids.add(fis["stand_id"])

        results = []
        for stand_id in stand_ids:
            result = self.infer_stand_status(stand_id)
            results.append(result)

        return results


def main():
    """主函数：演示机位状态查询"""
    service = ApronStandStatusService()

    # 示例1: 查询单个机位
    print("=" * 60)
    print("查询单个机位 (stand_id=221)")
    print("=" * 60)

    result = service.infer_stand_status("221")
    print(f"机位: {result.stand_id}")
    print(f"状态: {result.status.value}")
    print(f"推理: {result.reasoning}")
    if result.aircraft:
        print(f"飞机注册号: {result.aircraft.registration}")
        print(f"航班UID: {result.aircraft.flight_uid}")
        print(f"数据来源: {result.aircraft.source}")
    print()

    # 示例2: 查询所有机位
    print("=" * 60)
    print("查询所有机位状态")
    print("=" * 60)

    results = service.infer_all_stands_status()
    for r in results:
        status_icon = "🟢" if r.status == StandStatus.FREE else ("🔴" if r.status == StandStatus.OCCUPIED else "🟡")
        print(f"{status_icon} {r.stand_id}: {r.status.value}")
        if r.aircraft:
            print(f"   飞机: {r.aircraft.registration} | 航班: {r.aircraft.flight_uid}")
        print(f"   推理: {r.reasoning}")
    print()
    print(f"总计: {len(results)} 个机位")


if __name__ == "__main__":
    main()