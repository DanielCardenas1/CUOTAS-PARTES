from app.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM pensionado'))
    print('Pensionados restantes:', result.fetchone()[0])
