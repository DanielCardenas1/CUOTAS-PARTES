from app.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM pensionado'))
    print('Cantidad de pensionados:', result.fetchone()[0])
