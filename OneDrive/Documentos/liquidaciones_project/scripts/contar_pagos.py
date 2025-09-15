from app.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM pago'))
    print('Cantidad de pagos:', result.fetchone()[0])
