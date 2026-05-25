from pydantic import BaseModel
from typing import Optional, List

class ParseRequest(BaseModel):
    text: str

class Rack(BaseModel):
    raw: str
    seriesNum: int
    seriesKey: str
    hall: str
    column: int
    row: int
    config: dict

class ParsedPair(BaseModel):
    lineNum: int
    rawLine: str
    originRaw: Optional[str] = None
    destRaw: Optional[str] = None
    origin: Optional[Rack] = None
    dest: Optional[Rack] = None
    interHall: bool = False
    seriesKey: Optional[str] = None
    directConnection: bool = False
    error: Optional[str] = None

class ParseResponse(BaseModel):
    pairs: List[ParsedPair]

class CalculateItemRequest(BaseModel):
    pair: ParsedPair
    tier: int = 3
    path: Optional[str] = None
    interHallMeters: Optional[float] = None
    roundingMode: str = "2"

class CalculateRequest(BaseModel):
    items: List[CalculateItemRequest]

class CalculationResult(BaseModel):
    type: str
    verticalInicial: float
    horizontal: float
    interHallDist: float
    horizontalOrigen: Optional[float] = None
    horizontalDestino: Optional[float] = None
    verticalFinal: float
    bandeja: int
    margen: float
    totalRaw: Optional[float] = None
    total: float
    error: Optional[str] = None

class CalculateItemResponse(BaseModel):
    pair: ParsedPair
    roundingMode: str
    pathLabel: str
    calc: Optional[CalculationResult] = None
    error: Optional[str] = None

class CalculateResponse(BaseModel):
    results: List[CalculateItemResponse]
    hasErrors: bool

class ExportRequest(BaseModel):
    results: List[CalculateItemResponse]
