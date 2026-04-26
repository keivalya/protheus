from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any

from app.services.protocol_models import ProtocolVersionResponse

DAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

DEFAULT_WORKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
PASSIVE_TERMS = ["incubat", "wait", "overnight", "culture", "dry", "rest", "stain", "hybridiz"]


def _parse_time(value: str | None, fallback: time) -> time:
    if not value:
        return fallback
    try:
        hour, minute = value.split(":", 1)
        return time(int(hour), int(minute))
    except Exception:
        return fallback


def _parse_start_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return date.today()
    return date.today()


def _holiday_dates(year: int) -> set[date]:
    return {
        date(year, 1, 1),
        date(year, 7, 4),
        date(year, 11, 11),
        date(year, 12, 25),
    }


def _is_workday(day: date, workday_indexes: set[int], include_us_holidays: bool) -> bool:
    if day.weekday() not in workday_indexes:
        return False
    if include_us_holidays and day in _holiday_dates(day.year):
        return False
    return True


def _next_work_start(
    current: datetime,
    work_start: time,
    work_end: time,
    workday_indexes: set[int],
    include_us_holidays: bool,
) -> datetime:
    cursor = current
    while not _is_workday(cursor.date(), workday_indexes, include_us_holidays):
        cursor = datetime.combine(cursor.date() + timedelta(days=1), work_start)

    day_start = datetime.combine(cursor.date(), work_start)
    day_end = datetime.combine(cursor.date(), work_end)
    if cursor < day_start:
        return day_start
    if cursor >= day_end:
        return _next_work_start(
            datetime.combine(cursor.date() + timedelta(days=1), work_start),
            work_start,
            work_end,
            workday_indexes,
            include_us_holidays,
        )
    return cursor


def _schedule_hands_on(
    current: datetime,
    hours: float,
    work_start: time,
    work_end: time,
    workday_indexes: set[int],
    include_us_holidays: bool,
) -> tuple[datetime, datetime]:
    start = _next_work_start(current, work_start, work_end, workday_indexes, include_us_holidays)
    cursor = start
    remaining = max(0.0, hours)
    if remaining == 0:
        return start, start

    while remaining > 0:
        cursor = _next_work_start(cursor, work_start, work_end, workday_indexes, include_us_holidays)
        day_end = datetime.combine(cursor.date(), work_end)
        available = max(0.0, (day_end - cursor).total_seconds() / 3600)
        if available <= 0:
            cursor = datetime.combine(cursor.date() + timedelta(days=1), work_start)
            continue
        worked = min(remaining, available)
        cursor = cursor + timedelta(hours=worked)
        remaining -= worked
        if remaining > 0:
            cursor = datetime.combine(cursor.date() + timedelta(days=1), work_start)

    return start, cursor


def _passive_wait_hours(text: str) -> float:
    lowered = text.lower()
    if not any(term in lowered for term in PASSIVE_TERMS):
        return 0.0
    if "overnight" in lowered:
        return 16.0
    day_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:day|days|d)\b", lowered)
    if day_match:
        return min(336.0, float(day_match.group(1)) * 24.0)
    hour_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:hour|hours|hr|hrs|h)\b", lowered)
    if hour_match:
        return min(336.0, float(hour_match.group(1)))
    minute_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:minute|minutes|min|mins)\b", lowered)
    if minute_match:
        return min(24.0, float(minute_match.group(1)) / 60.0)
    return 0.0


def _step_time_text(step: Any) -> str:
    params = getattr(step, "parameters", None)
    time_value = getattr(params, "time", None) if params else None
    return " ".join(part for part in [getattr(step, "action", ""), time_value or ""] if part)


def _phase_estimate(phase: Any) -> tuple[float, float]:
    steps = getattr(phase, "steps", []) or []
    hands_on = min(6.0, max(1.5, len(steps) * 0.75))
    passive = min(168.0, sum(_passive_wait_hours(_step_time_text(step)) for step in steps))
    return round(hands_on, 2), round(passive, 2)


def _workflow_packages(accepted_version: ProtocolVersionResponse, team_size: int, procurement_lead_days: int | None) -> list[dict[str, Any]]:
    protocol = accepted_version.protocol
    lead_hours = float(procurement_lead_days if procurement_lead_days is not None else 3) * 24.0
    packages: list[dict[str, Any]] = [
        {
            "task_name": "Confirm materials and supplier availability",
            "phase": "Procurement",
            "hands_on_hours": 2.0,
            "passive_wait_hours": 0.0,
            "dependencies": ["Accepted custom protocol"],
            "assigned_people": 1,
            "parallelizable": False,
        },
        {
            "task_name": "Supplier processing and delivery lead time",
            "phase": "Procurement",
            "hands_on_hours": 0.0,
            "passive_wait_hours": lead_hours,
            "dependencies": ["Confirm materials and supplier availability"],
            "assigned_people": 0,
            "parallelizable": False,
        },
        {
            "task_name": "Materials received checkpoint",
            "phase": "Procurement",
            "hands_on_hours": 1.0,
            "passive_wait_hours": 0.0,
            "dependencies": ["Supplier processing and delivery lead time"],
            "assigned_people": 1,
            "parallelizable": False,
        },
        {
            "task_name": "Prepare lab workspace and equipment",
            "phase": "Lab preparation",
            "hands_on_hours": 3.0,
            "passive_wait_hours": 0.0,
            "dependencies": ["Materials received checkpoint"],
            "assigned_people": 1,
            "parallelizable": False,
        },
        {
            "task_name": "Prepare samples or biological materials",
            "phase": "Sample/cell preparation",
            "hands_on_hours": 4.0,
            "passive_wait_hours": 0.0,
            "dependencies": ["Prepare lab workspace and equipment"],
            "assigned_people": 1,
            "parallelizable": False,
        },
    ]

    phases = protocol.adapted_workflow.phases
    if phases:
        midpoint = max(1, (len(phases) + 1) // 2)
        previous = "Prepare samples or biological materials"
        for index, phase in enumerate(phases, start=1):
            hands_on, passive = _phase_estimate(phase)
            package_phase = "Protocol execution phase 1" if index <= midpoint else "Protocol execution phase 2"
            task_name = getattr(phase, "phase_name", None) or f"Workflow phase {index}"
            packages.append(
                {
                    "task_name": task_name,
                    "phase": package_phase,
                    "hands_on_hours": hands_on,
                    "passive_wait_hours": passive,
                    "dependencies": [previous],
                    "assigned_people": 1,
                    "parallelizable": False,
                }
            )
            previous = task_name
    else:
        previous = "Prepare samples or biological materials"
        for task_name, phase in [
            ("Run initial protocol operations", "Protocol execution phase 1"),
            ("Run follow-up protocol operations", "Protocol execution phase 2"),
        ]:
            packages.append(
                {
                    "task_name": task_name,
                    "phase": phase,
                    "hands_on_hours": 4.0,
                    "passive_wait_hours": 0.0,
                    "dependencies": [previous],
                    "assigned_people": 1,
                    "parallelizable": False,
                }
            )
            previous = task_name

    validation_hands_on = 3.0
    validation_passive = 0.0
    if protocol.validation_readout.phases:
        estimates = [_phase_estimate(phase) for phase in protocol.validation_readout.phases]
        validation_hands_on = max(2.0, sum(item[0] for item in estimates))
        validation_passive = sum(item[1] for item in estimates)

    packages.extend(
        [
            {
                "task_name": "Validation and readout",
                "phase": "Validation/readout",
                "hands_on_hours": round(validation_hands_on, 2),
                "passive_wait_hours": round(validation_passive, 2),
                "dependencies": [previous],
                "assigned_people": 1,
                "parallelizable": False,
            },
            {
                "task_name": "Data analysis",
                "phase": "Data analysis",
                "hands_on_hours": 4.0,
                "passive_wait_hours": 0.0,
                "dependencies": ["Validation and readout"],
                "assigned_people": min(max(team_size, 1), 2),
                "parallelizable": True,
            },
            {
                "task_name": "Review and report",
                "phase": "Review/report",
                "hands_on_hours": 2.0,
                "passive_wait_hours": 0.0,
                "dependencies": ["Data analysis"],
                "assigned_people": min(max(team_size, 1), 2),
                "parallelizable": True,
            },
        ]
    )
    return packages


def build_timeline(accepted_version: ProtocolVersionResponse, schedule: dict[str, Any]) -> dict[str, Any]:
    team_size = max(1, int(schedule.get("team_size") or 2))
    workday_names = schedule.get("workdays") or DEFAULT_WORKDAYS
    workday_indexes = {
        DAY_INDEX[name.lower()]
        for name in workday_names
        if isinstance(name, str) and name.lower() in DAY_INDEX
    }
    if schedule.get("skip_weekends", True):
        workday_indexes -= {5, 6}
    if not workday_indexes:
        workday_indexes = {0, 1, 2, 3, 4}

    work_start = _parse_time(schedule.get("workday_start"), time(9, 0))
    work_end = _parse_time(schedule.get("workday_end"), time(17, 0))
    if work_end <= work_start:
        work_start = time(9, 0)
        work_end = time(17, 0)

    include_us_holidays = bool(schedule.get("include_us_holidays", False))
    cursor = datetime.combine(_parse_start_date(schedule.get("start_date")), work_start)
    packages = _workflow_packages(accepted_version, team_size, schedule.get("procurement_lead_days"))
    scheduled_tasks: list[dict[str, Any]] = []

    for package in packages:
        assigned_people = max(1, int(package.get("assigned_people") or 1))
        effective_hands_on = float(package["hands_on_hours"])
        if package.get("parallelizable"):
            effective_hands_on = effective_hands_on / min(team_size, assigned_people)

        if effective_hands_on > 0:
            scheduled_start, hands_on_end = _schedule_hands_on(
                cursor,
                effective_hands_on,
                work_start,
                work_end,
                workday_indexes,
                include_us_holidays,
            )
        else:
            scheduled_start = cursor
            hands_on_end = cursor

        passive_wait_hours = float(package.get("passive_wait_hours") or 0.0)
        scheduled_end = hands_on_end + timedelta(hours=passive_wait_hours)
        cursor = scheduled_end

        scheduled_tasks.append(
            {
                **package,
                "effective_hands_on_hours": round(effective_hands_on, 2),
                "scheduled_start": scheduled_start.strftime("%Y-%m-%d %H:%M"),
                "scheduled_end": scheduled_end.strftime("%Y-%m-%d %H:%M"),
                "hands_on_start": scheduled_start.strftime("%Y-%m-%d %H:%M"),
                "hands_on_end": hands_on_end.strftime("%Y-%m-%d %H:%M"),
                "passive_wait_end": scheduled_end.strftime("%Y-%m-%d %H:%M")
                if passive_wait_hours
                else None,
            }
        )

    return {
        "timeline": scheduled_tasks,
        "assumptions": [
            f"Team size: {team_size}.",
            f"Hands-on work is scheduled from {work_start.strftime('%H:%M')} to {work_end.strftime('%H:%M')} on selected workdays.",
            "Passive waits can span nights and weekends; the next hands-on checkpoint resumes in the next working window.",
            "Procurement lead time defaults to 3 days when supplier-specific lead time is unavailable.",
        ],
    }
