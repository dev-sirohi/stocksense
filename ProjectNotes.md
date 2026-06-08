# Migrations

### Commands
- ```alembic init migrations```
- *Update alembic.ini - database url*
- *Update migrations/env.py - metadata from app/models/model_name and app/database/Base*
- ```alembic revision --autogenerate -m "create skus and inventory records tables"```
- ```alembic upgrade head```
