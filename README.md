# AutoTech Backend

Marketplace de repuestos y servicios automotrices para Venezuela. Plataforma con crédito en línea, pagos a cuotas, verificación de talleres, y gestión completa de órdenes de compra y servicio. Incluye sistema de niveles de crédito con puntos, líneas de financiamiento para repuestos y servicios, y validaciones específicas para el contexto venezolano (RIF, CI, bancos, pago móvil).

## Stack tecnológico

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.137-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Alembic](https://img.shields.io/badge/Alembic-000?logo=alembic&logoColor=white)](https://alembic.sqlalchemy.org)
[![Poetry](https://img.shields.io/badge/Poetry-60A5FA?logo=poetry&logoColor=white)](https://python-poetry.org)
[![Pydantic](https://img.shields.io/badge/Pydantic-E92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev)
[![JWT](https://img.shields.io/badge/JWT-000?logo=jsonwebtokens&logoColor=white)](https://jwt.io)
[![Resend](https://img.shields.io/badge/Resend-000?logo=resend&logoColor=white)](https://resend.com)
[![Ruff](https://img.shields.io/badge/Ruff-000?logo=ruff&logoColor=white)](https://docs.astral.sh/ruff)
[![pytest](https://img.shields.io/badge/pytest-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org)

## Arquitectura

Monolito modular con **Clean Architecture** por módulo. Cada módulo sigue la estructura `domain → application → infrastructure`:

```
src/modules/{module}/
├── domain/entity.py          # Dataclass con lógica de negocio
├── application/create.py     # DTOs Pydantic (request/response)
└── infrastructure/
    ├── mapper.py             # Entity ↔ SQLAlchemy model
    ├── repository.py         # Queries SQLAlchemy (extends GenericSQLRepository)
    ├── service.py            # Business logic (Transaction pattern)
    └── router.py             # FastAPI endpoints (extends BaseRouter)
```

- **Transaction pattern**: Context manager que crea sesión, instancia repos, auto-commit/rollback.
- **Response genérico**: Todos los servicios retornan `Response[T]` con `success`, `status_code`, `content`, `message`.
- **Core compartido**: `src/core/` provee `Entity`, `GenericRepository`, `GenericMapper`, `GenericSQLRepository`, `Transaction`, `BaseRouter`, `Response[T]`, `PaginatedDTO`.

### Módulos principales

| Módulo | Descripción |
|--------|-------------|
| `users` | Usuarios, autenticación JWT, roles, perfiles |
| `workshops` | Talleres, verificación, red de talleres |
| `parts` | Repuestos, categorías, condiciones, fotos |
| `orders` | Órdenes de compra, cuotas, pagos, envíos |
| `services` | Servicios de taller, órdenes de servicio, presupuestos |
| `vehicles` | Vehículos de clientes |
| `credit` | Líneas de crédito, niveles, puntos, moras |

## Guía de inicio rápido

### Prerrequisitos

- **Python 3.12+**
- **PostgreSQL 14+**
- **Poetry** ([instalación](https://python-poetry.org/docs/#installation))
- **Resend** API key (para emails) — opcional para desarrollo local

### Instalación

```bash
# Clonar el repositorio
git clone https://github.com/Luuisaker/AutoTech.git
cd AutoTech/AutoTech-Backend

# Instalar dependencias con Poetry
poetry install
```

### Configurar variables de entorno

Crear archivo `.env` en la raíz del proyecto:

```env
DATABASE_URL=postgresql://usuario:password@localhost:5432/autotech
SECRET_KEY=tu-clave-secreta-super-segura
UPLOAD_DIR=uploads
RESEND_API_KEY=re_xxxxxxxxxxxx
RESEND_FROM=AutoTech <onboarding@resend.dev>
FRONTEND_URL=http://localhost:3000
CRON_API_KEY=tu-cron-api-key
BCV_API_URL=https://ve.dolarapi.com/v1/dolares/bcv
```

### Correr migraciones y seed

```bash
# Aplicar migraciones
poetry run alembic upgrade head

# Cargar datos iniciales (usuarios, talleres, repuestos de prueba)
poetry run python -m src.seed
```

### Iniciar servidor de desarrollo

```bash
poetry run uvicorn src.main:app --reload
```

El servidor estará disponible en `http://localhost:8000`. La documentación interactiva (Swagger UI) en `http://localhost:8000/docs`.

### Scripts disponibles

| Comando | Descripción |
|---------|-------------|
| `poetry run uvicorn src.main:app --reload` | Servidor de desarrollo con hot reload |
| `poetry run alembic upgrade head` | Aplicar migraciones pendientes |
| `poetry run alembic revision --autogenerate -m "msg"` | Generar nueva migración |
| `poetry run python -m src.seed` | Cargar datos de prueba |
| `poetry run ruff check .` | Lint del código |
| `poetry run ruff format .` | Formatear código |
| `poetry run pytest` | Ejecutar tests |
| `poetry run pytest -m integration` | Tests de integración (requieren PostgreSQL) |

## Licencia

© 2026 Luis Ayala (@Luuisaker). Todos los derechos reservados.

Este software y su código fuente son propiedad exclusiva de Luis Ayala (@Luuisaker).

* No está permitido copiar, modificar, distribuir, sublicenciar ni usar este código, total o parcialmente, sin autorización expresa y por escrito del autor.
* No está permitido usar este código con fines comerciales ni privados sin una licencia válida.
* Cualquier uso no autorizado constituye una violación de los derechos de autor y será perseguido conforme a la ley.

Este es un software propietario. No es código abierto (open source) ni software libre. Ver [LICENSE](LICENSE) para más detalles.
