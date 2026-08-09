"""Parseo del tablón de movimientos de la liga.

Funciones PURAS (sin red ni BD) para transformar el feed crudo del tablón en
registros normalizados. La ingesta a BD (idempotente vía dedup_key) se apoya en
esto. Diseñado para "detectar y avisar": cualquier tipo de movimiento no
reconocido (p. ej. cesiones o retos) se recopila para revisión, no se ignora.

Estructura del tablón (verificada en proyectos reales):
    item = {"date": <epoch s>, "type": <str>, "content": <list|dict>}
  - transfer / adminTransfer / market: content es lista de
        {"amount", "player", "from"?:{"id","name"}, "to"?:{"id","name"}}
  - roundFinished: content es dict con
        {"round":{"id","name"}, "results":[{"user":{"id","name"},"position","points","bonus"?}]}
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Tipos de movimiento de compraventa que sabemos interpretar.
TRANSFER_TYPES = {"transfer", "adminTransfer", "market"}
# Tipos que reconocemos pero se tratan aparte.
KNOWN_OTHER_TYPES = {"roundFinished"}


@dataclass
class ParsedMovement:
    """Un movimiento de compraventa normalizado."""

    dedup_key: str
    date: datetime
    type: str
    player_id: int | None
    amount: int | None
    from_user_id: int | None
    to_user_id: int | None
    note: str | None = None


@dataclass
class ParsedRoundResult:
    """Resultado de un manager en una jornada (de roundFinished)."""

    round: int | None
    round_name: str | None
    user_id: int
    user_name: str | None
    position: int | None
    points: int | None
    bonus: int | None


@dataclass
class BoardParseResult:
    movements: list[ParsedMovement] = field(default_factory=list)
    round_results: list[ParsedRoundResult] = field(default_factory=list)
    # tipo -> nº de apariciones, para tipos no reconocidos (cesiones/retos/...).
    unknown_types: dict[str, int] = field(default_factory=dict)


def _to_datetime(raw_date: Any) -> datetime:
    """Convierte la fecha del tablón (epoch en segundos) a datetime."""
    try:
        return datetime.fromtimestamp(int(raw_date))
    except (TypeError, ValueError, OSError):
        return datetime.min


def _user_id(node: Any) -> int | None:
    if isinstance(node, dict):
        val = node.get("id")
        return int(val) if isinstance(val, (int, str)) and str(val).isdigit() else None
    return None


def make_dedup_key(date_epoch: Any, mtype: str, player_id: Any, frm: Any, to: Any, amount: Any) -> str:
    raw = f"{date_epoch}|{mtype}|{player_id}|{frm}|{to}|{amount}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


def _round_number(round_node: Any) -> int | None:
    """Extrae el número de jornada de un nodo round {id, name}."""
    if not isinstance(round_node, dict):
        return None
    rid = round_node.get("id")
    if isinstance(rid, int):
        return rid
    # fallback: primer entero del nombre ("Jornada 3" -> 3)
    name = round_node.get("name")
    if isinstance(name, str):
        for tok in name.replace("ª", " ").split():
            if tok.isdigit():
                return int(tok)
    return None


def parse_board(board: list[dict[str, Any]]) -> BoardParseResult:
    """Parsea el feed completo del tablón a estructuras normalizadas."""
    result = BoardParseResult()

    for item in board or []:
        if not isinstance(item, dict):
            continue
        mtype = item.get("type") or "transfer"
        raw_date = item.get("date")
        content = item.get("content")

        if mtype in TRANSFER_TYPES:
            _parse_transfer(result, mtype, raw_date, content)
        elif mtype == "roundFinished":
            _parse_round_finished(result, content)
        else:
            # Cesiones, retos u otros: los contamos para avisar.
            result.unknown_types[mtype] = result.unknown_types.get(mtype, 0) + 1
            _parse_unknown(result, mtype, raw_date, content)

    return result


def _parse_transfer(result: BoardParseResult, mtype: str, raw_date: Any, content: Any) -> None:
    items = content if isinstance(content, list) else [content]
    for c in items:
        if not isinstance(c, dict):
            continue
        player_id = c.get("player")
        player_id = int(player_id) if isinstance(player_id, (int, str)) and str(player_id).isdigit() else None
        frm = _user_id(c.get("from"))
        to = _user_id(c.get("to"))
        amount = c.get("amount")
        amount = int(amount) if isinstance(amount, (int, float)) else None
        result.movements.append(
            ParsedMovement(
                dedup_key=make_dedup_key(raw_date, mtype, player_id, frm, to, amount),
                date=_to_datetime(raw_date),
                type=mtype,
                player_id=player_id,
                amount=amount,
                from_user_id=frm,
                to_user_id=to,
            )
        )


def _parse_round_finished(result: BoardParseResult, content: Any) -> None:
    if not isinstance(content, dict):
        return
    round_node = content.get("round")
    rnum = _round_number(round_node)
    rname = round_node.get("name") if isinstance(round_node, dict) else None
    for res in content.get("results", []) or []:
        if not isinstance(res, dict):
            continue
        uid = _user_id(res.get("user"))
        if uid is None:
            continue
        result.round_results.append(
            ParsedRoundResult(
                round=rnum,
                round_name=rname,
                user_id=uid,
                user_name=(res.get("user") or {}).get("name") if isinstance(res.get("user"), dict) else None,
                position=res.get("position") if isinstance(res.get("position"), int) else None,
                points=res.get("points") if isinstance(res.get("points"), int) else None,
                bonus=res.get("bonus") if isinstance(res.get("bonus"), int) else None,
            )
        )


def _parse_unknown(result: BoardParseResult, mtype: str, raw_date: Any, content: Any) -> None:
    """Intenta extraer from/to/amount/player de un tipo no reconocido (cesión/reto).

    No asumimos su semántica; guardamos lo que parezca dinero entre usuarios y
    lo marcamos con una nota para revisarlo manualmente.
    """
    items = content if isinstance(content, list) else [content]
    for c in items:
        if not isinstance(c, dict):
            continue
        frm = _user_id(c.get("from"))
        to = _user_id(c.get("to"))
        amount = c.get("amount")
        amount = int(amount) if isinstance(amount, (int, float)) else None
        player_id = c.get("player")
        player_id = int(player_id) if isinstance(player_id, (int, str)) and str(player_id).isdigit() else None
        result.movements.append(
            ParsedMovement(
                dedup_key=make_dedup_key(raw_date, mtype, player_id, frm, to, amount),
                date=_to_datetime(raw_date),
                type=mtype,
                player_id=player_id,
                amount=amount,
                from_user_id=frm,
                to_user_id=to,
                note=f"tipo no reconocido '{mtype}' — revisar (posible cesión/reto)",
            )
        )
