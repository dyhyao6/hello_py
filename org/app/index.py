"""
API 路由模块
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel

from flight_safeguard.apron_stand_status import (
    ApronStandStatusService,
    StandStatus,
    StandStatusResult,
    AircraftInfo,
    get_service,
)

router = APIRouter()


class AircraftResponse(BaseModel):
    """飞机信息响应"""
    registration: Optional[str] = None
    flight_uid: Optional[str] = None
    flight_identity: Optional[str] = None
    stand_id: Optional[str] = None
    status: Optional[str] = None
    source: str = "fis"


class StandStatusResponse(BaseModel):
    """机位状态响应"""
    stand_id: str
    status: str
    aircraft: Optional[AircraftResponse]
    reasoning: str


class AllStandsStatusResponse(BaseModel):
    """所有机位状态响应"""
    total: int
    stands: List[StandStatusResponse]


@router.get("/stand/{stand_id}/status", response_model=StandStatusResponse)
def get_stand_status(stand_id: str):
    """
    根据 stand_id 获取机位的占用情况及当前停靠的飞机实体

    - **stand_id**: 机位号，如 "221"
    """
    try:
        service = get_service()
        result = service.infer_stand_status(stand_id)

        aircraft_response = None
        if result.aircraft:
            aircraft_response = AircraftResponse(
                registration=result.aircraft.registration,
                flight_uid=result.aircraft.flight_uid,
                flight_identity=result.aircraft.flight_identity,
                stand_id=result.aircraft.stand_id,
                status=result.aircraft.status,
                source=result.aircraft.source,
            )

        return StandStatusResponse(
            stand_id=result.stand_id,
            status=result.status.value,
            aircraft=aircraft_response,
            reasoning=result.reasoning,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stands/status", response_model=AllStandsStatusResponse)
def get_all_stands_status():
    """
    获取所有机位的占用情况及当前停靠的飞机实体
    """
    try:
        service = get_service()
        results = service.infer_all_stands_status()

        stands = []
        for result in results:
            aircraft_response = None
            if result.aircraft:
                aircraft_response = AircraftResponse(
                    registration=result.aircraft.registration,
                    flight_uid=result.aircraft.flight_uid,
                    flight_identity=result.aircraft.flight_identity,
                    stand_id=result.aircraft.stand_id,
                    status=result.aircraft.status,
                    source=result.aircraft.source,
                )
            stands.append(StandStatusResponse(
                stand_id=result.stand_id,
                status=result.status.value,
                aircraft=aircraft_response,
                reasoning=result.reasoning,
            ))

        return AllStandsStatusResponse(total=len(stands), stands=stands)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))