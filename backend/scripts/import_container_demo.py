"""Import a read-only snapshot ONLY into the empty, dedicated Compose database."""
from datetime import date,datetime
from decimal import Decimal
import json
import hashlib
import sys
from sqlalchemy import MetaData,Table,Date,DateTime,Numeric,select,text
import config
from database.connection import engine
from scripts.ae4_preservation import snapshot,check_constraints

def main():
    if config.DB_SERVER!='sqlserver' or config.DB_NAME!='TurismoPosadas_AE4_Integration' or config.DB_USER!='sa':
        raise RuntimeError('Import refused outside dedicated Compose SQL')
    data=json.load(sys.stdin)
    expected=data['snapshot'];names=set(expected)
    allowed={'usuarios','hoteles','habitaciones','actividades','actividad_turnos','reservas','pagos','viajes','viaje_hoteles','eventos_procesados'}
    assert names==allowed and set(data['tables'])==allowed
    before=snapshot(engine)
    if before==expected:
        print(json.dumps({'status':'already_copied','snapshot':before}));return
    if any(value['count'] for value in before.values()):
        raise RuntimeError('Target contains data; refusing overwrite/delete')
    metadata=MetaData()
    for name in allowed:Table(name,metadata,schema='dbo',autoload_with=engine)
    with engine.begin() as db:
        for table in metadata.sorted_tables:
            if table.name not in allowed:continue
            values=[]
            for row in data['tables'][table.name]:
                assert set(row)==set(table.columns.keys())
                converted={}
                for column in table.columns:
                    value=row[column.name]
                    if value is not None:
                        if isinstance(column.type,DateTime):value=datetime.fromisoformat(value)
                        elif isinstance(column.type,Date):value=date.fromisoformat(value)
                        elif isinstance(column.type,Numeric):value=Decimal(value)
                    converted[column.name]=value
                values.append(converted)
            if values:db.execute(table.insert(),values)
        # Inspect using the same transaction; mismatch aborts all inserted rows.
        for name in allowed:
            table=metadata.tables['dbo.'+name]
            rows=[dict(row) for row in db.execute(select(table).order_by(*table.primary_key.columns)).mappings()]
            actual={'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()}
            if actual!=expected[name]:raise RuntimeError('Snapshot verification failed for '+name)
    check_constraints(engine)
    print(json.dumps({'status':'copied','snapshot':snapshot(engine),'dbcc_violations':0}))

if __name__=='__main__':main()
