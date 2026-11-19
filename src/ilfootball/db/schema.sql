-- Canonical ("gold") schema. Ids are TEXT minted by ilfootball.resolve.id_map.
CREATE TABLE IF NOT EXISTS competition (
    competition_id TEXT PRIMARY KEY,
    name_en TEXT,
    name_he TEXT,
    tier INTEGER,
    type TEXT NOT NULL CHECK (type IN ('league', 'cup', 'europe', 'friendly'))
);

CREATE TABLE IF NOT EXISTS season (
    season_id TEXT PRIMARY KEY,
    competition_id TEXT NOT NULL,
    label TEXT NOT NULL,
    start_date DATE,
    end_date DATE
);

CREATE TABLE IF NOT EXISTS club (
    club_id TEXT PRIMARY KEY,
    name_en TEXT,
    name_he TEXT,
    city TEXT,
    founded INTEGER,
    wikidata_qid TEXT
);

CREATE TABLE IF NOT EXISTS player (
    player_id TEXT PRIMARY KEY,
    name_en TEXT,
    name_he TEXT,
    birth_date DATE,
    nationality TEXT,
    position TEXT,
    wikidata_qid TEXT
);

CREATE TABLE IF NOT EXISTS match (
    match_id TEXT PRIMARY KEY,
    season_id TEXT NOT NULL,
    round TEXT,
    stage TEXT,
    kickoff_utc TIMESTAMP,
    home_club_id TEXT NOT NULL,
    away_club_id TEXT NOT NULL,
    home_goals INTEGER,
    away_goals INTEGER,
    stadium TEXT,
    referee TEXT,
    attendance INTEGER,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'played', 'postponed', 'cancelled', 'awarded'))
);

CREATE TABLE IF NOT EXISTS lineup (
    match_id TEXT NOT NULL,
    club_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    shirt_no INTEGER,
    is_starter BOOLEAN NOT NULL,
    minutes INTEGER,
    is_captain BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (match_id, player_id)
);

-- club_id is always the club of player_id; an own_goal is credited to the opponent.
CREATE TABLE IF NOT EXISTS event (
    event_id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL,
    minute INTEGER NOT NULL,
    added_time INTEGER,
    club_id TEXT NOT NULL,
    player_id TEXT,
    type TEXT NOT NULL CHECK (type IN (
        'goal', 'pen_goal', 'own_goal', 'pen_miss',
        'yellow', 'second_yellow', 'red', 'sub_in', 'sub_out')),
    related_player_id TEXT
);

CREATE TABLE IF NOT EXISTS standing (
    season_id TEXT NOT NULL,
    round INTEGER NOT NULL,
    club_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    played INTEGER, won INTEGER, drawn INTEGER, lost INTEGER,
    goals_for INTEGER, goals_against INTEGER, points INTEGER,
    PRIMARY KEY (season_id, round, club_id)
);

CREATE TABLE IF NOT EXISTS id_map (
    entity_type TEXT NOT NULL,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    canonical_id TEXT NOT NULL,
    source_name TEXT,
    confidence DOUBLE NOT NULL,
    method TEXT NOT NULL,
    PRIMARY KEY (entity_type, source, source_id)
);
