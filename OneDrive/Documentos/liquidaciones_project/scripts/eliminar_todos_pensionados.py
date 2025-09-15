from app.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text('DELETE FROM pensionado'))
    print(f"Pensionados eliminados: {result.rowcount}")
