"""Typed rows for the canonical tables. Field names == column names in schema.sql."""
from __future__ import annotations

from datetime import date, datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict


class Row(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    table: ClassVar[str]


class Competition(Row):
    table: ClassVar[str] = "competition"
    competition_id: str
    name_en: str | None = None
    name_he: str | None = None
    tier: int | None = None
    type: Literal["league", "cup", "europe", "friendly"]


class Season(Row):
    table: ClassVar[str] = "season"
    season_id: str
    competition_id: str
    label: str
    start_date: date | None = None
    end_date: date | None = None


class Club(Row):
    table: ClassVar[str] = "club"
    club_id: str
    name_en: str | None = None
    name_he: str | None = None
    city: str | None = None
    founded: int | None = None
    wikidata_qid: str | None = None


class Player(Row):
    table: ClassVar[str] = "player"
    player_id: str
    name_en: str | None = None
    name_he: str | None = None
    birth_date: date | None = None
    nationality: str | None = None
    position: str | None = None
    wikidata_qid: str | None = None


class Match(Row):
    table: ClassVar[str] = "match"
    match_id: str
    season_id: str
    round: str | None = None
    stage: str | None = None
    kickoff_utc: datetime | None = None
    home_club_id: str
    away_club_id: str
    home_goals: int | None = None
    away_goals: int | None = None
    stadium: str | None = None
    referee: str | None = None
    attendance: int | None = None
    status: Literal["scheduled", "played", "postponed", "cancelled", "awarded"] = "scheduled"


class LineupEntry(Row):
    table: ClassVar[str] = "lineup"
    match_id: str
    club_id: str
    player_id: str
    shirt_no: int | None = None
    is_starter: bool
    minutes: int | None = None
    is_captain: bool = False


class MatchEvent(Row):
    table: ClassVar[str] = "event"
    event_id: str
    match_id: str
    minute: int
    added_time: int | None = None
    club_id: str
    player_id: str | None = None
    type: Literal[
        "goal", "pen_goal", "own_goal", "pen_miss",
        "yellow", "second_yellow", "red", "sub_in", "sub_out",
    ]
    related_player_id: str | None = None


class Standing(Row):
    table: ClassVar[str] = "standing"
    season_id: str
    round: int
    club_id: str
    position: int
    played: int | None = None
    won: int | None = None
    drawn: int | None = None
    lost: int | None = None
    goals_for: int | None = None
    goals_against: int | None = None
    points: int | None = None
