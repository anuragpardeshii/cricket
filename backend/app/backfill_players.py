"""Insert missing catalog records; keep existing records and saved games intact."""
import json
from pathlib import Path
from sqlalchemy import select, func, text
from sqlalchemy.dialects.postgresql import insert
from .db import engine, SquadRecord, PlayerRecord, Audit, uid, now


def backfill(connection):
    data = json.loads(Path(__file__).with_name('catalog.json').read_text())
    # Serialize maintenance runs, including runs started in different containers.
    connection.execute(text('SELECT pg_advisory_xact_lock(734829106)'))
    added_squads = added_players = 0
    for order, squad in enumerate(data['squads']):
        squad_id = squad['players'][0]['id'].split('-')[0]
        added_squads += len(connection.execute(insert(SquadRecord).values(
            id=squad_id, country=squad['country'], tournament=squad['tournament'], sort_order=order
        ).on_conflict_do_nothing(index_elements=['id']).returning(SquadRecord.id)).all())
        values = [dict(id=p['id'], squad_id=squad_id, name=p['name'], role=p['role'], rating=p['rating'], sort_order=i)
                  for i, p in enumerate(squad['players'])]
        added_players += len(connection.execute(insert(PlayerRecord).values(values)
                            .on_conflict_do_nothing(index_elements=['id']).returning(PlayerRecord.id)).all())
    if added_squads or added_players:
        connection.execute(insert(Audit).values(id=uid(), action='catalog.backfilled', created_at=now()))
    return dict(inserted_squads=added_squads, inserted_players=added_players,
                total_squads=connection.scalar(select(func.count()).select_from(SquadRecord)),
                total_players=connection.scalar(select(func.count()).select_from(PlayerRecord)))


def main():
    with engine.begin() as connection:
        result = backfill(connection)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
