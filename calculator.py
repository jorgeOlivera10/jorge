import re
import math
from typing import Dict, Any, List
from .config import (
    SERIES_CONFIG,
    TIER_VALUES,
    MARGIN,
    ROW_MIN,
    ROW_MAX,
    VERTICAL_PER_ROW,
    EXTREME_TRANSITION
)

RACK_REGEX = re.compile(r"^ZAZ(\d{2})\.(\d{2}-\d{2})-(\d{3})-(\d{1,3})$", re.IGNORECASE)

def parse_rack(raw: str) -> Dict[str, Any]:
    trimmed = raw.strip().upper()
    match = RACK_REGEX.match(trimmed)
    if not match:
        return {"error": f'Formato inválido: "{trimmed}"'}

    series_num = int(match.group(1), 10)
    hall = match.group(2)
    column = int(match.group(3), 10)
    row = int(match.group(4), 10)

    if 60 <= series_num <= 69:
        series_key = '6X'
    elif 70 <= series_num <= 79:
        series_key = '7X'
    else:
        return {"error": f"Serie {series_num} no válida (debe ser 60-69 o 70-79)"}

    config = SERIES_CONFIG[series_key]

    if row < ROW_MIN or row > ROW_MAX:
        return {"error": f"Fila {row} fuera de rango ({ROW_MIN}-{ROW_MAX})"}
    
    if column < config['columns']['min'] or column > config['columns']['max']:
        return {"error": f"Columna {column} fuera de rango ({config['columns']['min']}-{config['columns']['max']}) para {config['label']}"}

    return {
        "raw": trimmed,
        "seriesNum": series_num,
        "seriesKey": series_key,
        "hall": hall,
        "column": column,
        "row": row,
        "config": config
    }

def parse_input(text: str) -> List[Dict[str, Any]]:
    lines = [l for l in text.split('\n') if l.strip()]
    pairs = []

    for i, line in enumerate(lines):
        line = line.strip()
        parts = [s.strip() for s in re.split(r'[\t,]+|\s{2,}', line) if s.strip()]

        if len(parts) < 2:
            pairs.append({
                "lineNum": i + 1,
                "rawLine": line,
                "error": "Se requieren rack de origen y rack de destino separados por tabulador o varios espacios"
            })
            continue

        origin = parse_rack(parts[0])
        dest = parse_rack(parts[1])

        if "error" in origin or "error" in dest:
            pairs.append({
                "lineNum": i + 1,
                "rawLine": line,
                "originRaw": parts[0],
                "destRaw": parts[1],
                "error": origin.get("error") or dest.get("error")
            })
            continue

        if origin["seriesKey"] != dest["seriesKey"]:
            pairs.append({
                "lineNum": i + 1,
                "rawLine": line,
                "originRaw": parts[0],
                "destRaw": parts[1],
                "origin": origin,
                "dest": dest,
                "error": f'Las series no coinciden ({SERIES_CONFIG[origin["seriesKey"]]["label"]} vs {SERIES_CONFIG[dest["seriesKey"]]["label"]}).'
            })
            continue

        if origin["seriesNum"] != dest["seriesNum"]:
            pairs.append({
                "lineNum": i + 1,
                "rawLine": line,
                "originRaw": parts[0],
                "destRaw": parts[1],
                "origin": origin,
                "dest": dest,
                "error": f'Las series no coinciden exactamente (ZAZ{origin["seriesNum"]} vs ZAZ{dest["seriesNum"]}).'
            })
            continue

        inter_hall = origin["hall"] != dest["hall"]

        pairs.append({
            "lineNum": i + 1,
            "rawLine": line,
            "origin": origin,
            "dest": dest,
            "interHall": inter_hall,
            "seriesKey": origin["seriesKey"],
            "directConnection": origin["column"] == dest["column"],
            "error": None
        })

    return pairs

def calc_vertical(rack_row: int, avenue: Dict[str, Any]) -> float:
    avenue_row = avenue["row"]
    is_extreme = avenue["extreme"]

    if is_extreme:
        if avenue_row == 10:
            return (rack_row - ROW_MIN) * VERTICAL_PER_ROW + EXTREME_TRANSITION
        else:
            return (ROW_MAX - rack_row) * VERTICAL_PER_ROW + EXTREME_TRANSITION
    else:
        return abs(rack_row - avenue_row) * VERTICAL_PER_ROW

def calc_horizontal(col_a: int, col_b: int, series_key: str) -> float:
    if col_a == col_b:
        return 0.0

    config = SERIES_CONFIG[series_key]
    exc = config["horizontalException"]
    start = min(col_a, col_b)
    end = max(col_a, col_b)
    distance = 0.0

    for c in range(start, end):
        next_col = c + 1
        is_exception = (c == exc["from"] and next_col == exc["to"]) or \
                       (c == exc["to"] - 1 and next_col == exc["to"])

        if is_exception:
            distance += exc["distance"]
        else:
            distance += 2.0 if next_col % 2 == 0 else 3.0

    return distance

def calc_direct_vertical(row_a: int, row_b: int) -> float:
    return (abs(row_a - row_b) + 1) * VERTICAL_PER_ROW

def round_to_2(n: float) -> float:
    return round(n, 2)

def apply_rounding(value: float, mode: str) -> float:
    try:
        step = float(mode)
    except ValueError:
        step = 0.0
    if not step or step == 0.0:
        return round_to_2(value)
    return math.ceil(value / step) * step

def calculate_cable(origin: Dict[str, Any], dest: Dict[str, Any], path: str, tier: int) -> Dict[str, Any]:
    bandeja = TIER_VALUES.get(tier, 0)
    series_key = origin["seriesKey"]
    config = SERIES_CONFIG[series_key]

    if origin["column"] == dest["column"]:
        vertical_direct = calc_direct_vertical(origin["row"], dest["row"])
        return {
            "type": "direct",
            "verticalInicial": round_to_2(vertical_direct),
            "horizontal": 0.0,
            "interHallDist": 0.0,
            "verticalFinal": 0.0,
            "bandeja": float(bandeja),
            "margen": MARGIN,
            "total": round_to_2(vertical_direct + bandeja + MARGIN)
        }

    avenue = config["avenues"].get(path)
    if not avenue:
        return {"error": f'Path "{path}" no válido para {config["label"]}'}

    vertical_inicial = calc_vertical(origin["row"], avenue) + 0.3
    horizontal = calc_horizontal(origin["column"], dest["column"], series_key)
    vertical_final = calc_vertical(dest["row"], avenue) + 0.3

    total = vertical_inicial + horizontal + vertical_final + bandeja + MARGIN

    return {
        "type": "normal",
        "verticalInicial": round_to_2(vertical_inicial),
        "horizontal": round_to_2(horizontal),
        "interHallDist": 0.0,
        "verticalFinal": round_to_2(vertical_final),
        "bandeja": float(bandeja),
        "margen": MARGIN,
        "total": round_to_2(total)
    }

def calculate_inter_hall_cable(origin: Dict[str, Any], dest: Dict[str, Any], path: str, tier: int, inter_hall_distance: float) -> Dict[str, Any]:
    bandeja = TIER_VALUES.get(tier, 0)
    series_key = origin["seriesKey"]
    config = SERIES_CONFIG[series_key]
    avenue = config["avenues"].get(path)

    if not avenue:
        return {"error": f'Path "{path}" no válido para {config["label"]}'}

    vertical_inicial = calc_vertical(origin["row"], avenue) + 0.3
    horizontal_origen = calc_horizontal(origin["column"], 1, series_key)

    horizontal_destino = calc_horizontal(1, dest["column"], series_key)
    vertical_final = calc_vertical(dest["row"], avenue) + 0.3

    total = vertical_inicial + horizontal_origen + inter_hall_distance + horizontal_destino + vertical_final + bandeja + MARGIN

    return {
        "type": "inter-hall",
        "verticalInicial": round_to_2(vertical_inicial),
        "horizontalOrigen": round_to_2(horizontal_origen),
        "horizontal": round_to_2(horizontal_origen + horizontal_destino),
        "interHallDist": round_to_2(inter_hall_distance),
        "horizontalDestino": round_to_2(horizontal_destino),
        "verticalFinal": round_to_2(vertical_final),
        "bandeja": float(bandeja),
        "margen": MARGIN,
        "total": round_to_2(total)
    }

def validate_pair_for_calc(pair: Dict[str, Any], path: str, tier: int) -> List[str]:
    errors = []
    if pair.get("error"):
        errors.append(pair["error"])
        return errors
    
    if not pair.get("directConnection") and not pair.get("interHall"):
        config = SERIES_CONFIG[pair["seriesKey"]]
        if path not in config["paths"]:
            errors.append(f'Path "{path}" no válido para {config["label"]}. Opciones: {", ".join(config["paths"])}')
    
    if tier not in [3, 4, 5]:
        errors.append(f"Tier {tier} no válido. Opciones: 3, 4, 5")

    return errors
