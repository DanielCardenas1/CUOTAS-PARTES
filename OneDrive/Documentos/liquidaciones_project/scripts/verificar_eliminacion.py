from app.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM pensionado WHERE pensionado_id >= 354'))
    print('Pensionados con id >= 354:', result.fetchone()[0])
    result2 = conn.execute(text('SELECT pensionado_id, nombre FROM pensionado WHERE pensionado_id >= 354 LIMIT 5'))
    for row in result2:
        print(row)
