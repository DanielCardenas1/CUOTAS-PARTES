# Liquidaciones - Generador de cuentas de cobro

## Pasos rápidos

1) Levantar MySQL:

```
docker compose up -d
```

2) Instalar dependencias:

```
make venv
```

3) Crear esquema:

```
make db-init
```

4) Configurar `.env` (copiar desde `.env.example`).

5) Importar Excel a BD:

```
make run-cli
```

Luego: app/cli.py -> comando importar-excel

6) Generar liquidación (últimos 36 meses):

```
python -m app.cli generar-liq --entidad 900123456 --desde 2022-10 --hasta 2025-09
```

7) Exportar PDF:

```
python -m app.cli pdf --liquidacion-id 1 --out out/CCP-2025-09-0001.pdf
```

---

Tips para Copilot

- Escribe comentarios “Objetivo (Copilot): …” como los de los archivos en `app/` y acepta/completa sugerencias.
- Pídele:
  - “Crea la función X con pruebas unitarias simples”
  - “Lee columnas por nombre desde el Excel (no hardcodees letras)”
  - “Calcula intereses DTF por mes desde ‘Ultima fecha de pago’”
