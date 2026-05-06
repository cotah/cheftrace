# Handoff — Auditoria Sprint 3 → Sprint 4

> Data: 2026-05-06
> Commit: 5a4ec53
> Autor da auditoria: Claude (claude.ai, sessão externa ao repo)
> Para: Claude Code (sessão de desenvolvimento contínuo)

---

## Contexto

Antes de arrancar o Sprint 4, foi feita uma auditoria técnica completa
dos Sprints 1–3. Foram encontrados e corrigidos 8 bugs. Este documento
descreve o que mudou, por que mudou, e o que ficou pendente para o Sprint 4.

**Não é necessário reler toda a codebase.** Lê este ficheiro e os
diffs dos 9 ficheiros alterados. O resto do projecto está intacto.

---

## Ficheiros alterados (commit 5a4ec53)

```
apps/backend/app/schemas/haccp.py
apps/backend/app/schemas/equipment.py
apps/backend/app/core/security.py
apps/backend/app/api/v1/endpoints/haccp.py
apps/backend/app/api/v1/endpoints/stock_lots.py
apps/backend/app/services/dashboard_service.py
apps/backend/tests/conftest.py
apps/web/lib/api/resources.ts
apps/web/app/app/[restaurantId]/haccp/[runId]/page.tsx
```

---

## O que mudou e porquê

### 1. `HACCPRunRead` agora inclui `equipment_snapshot_json`

**Ficheiro:** `apps/backend/app/schemas/haccp.py`

O schema de resposta não incluía o campo `equipment_snapshot_json`.
O frontend usa este campo para decidir se renderiza equipamentos (run
dinâmico) ou itens de checklist (run estático). Sem ele, o template
"Temperature Log" era inutilizável — mostrava lista de itens vazia.

Também foi corrigido o tipo `run_date`: era `str`, agora é `date` com
`@field_serializer` que produz `"YYYY-MM-DD"` em ISO 8601.

```python
# ANTES
class HACCPRunRead(BaseModel):
    run_date: str
    # equipment_snapshot_json: ausente

# AGORA
class HACCPRunRead(BaseModel):
    run_date: date
    equipment_snapshot_json: list[dict[str, Any]] | None = None

    @field_serializer("run_date")
    def serialize_run_date(self, value: date) -> str:
        return value.isoformat()
```

**Impacto no frontend:** O tipo `HACCPRun` em `lib/api/types.ts` já tinha
`equipment_snapshot_json: EquipmentSnapshot[] | null` — não precisou alterar.

---

### 2. `TemperatureLogRead` agora usa `datetime` correctamente

**Ficheiro:** `apps/backend/app/schemas/equipment.py`

Os campos `recorded_at` e `created_at` eram `str`. O ORM tem `datetime`.
Pydantic v2 não coage `datetime → str` de forma fiável. Corrigido para
`datetime` — FastAPI serializa automaticamente para ISO 8601.

```python
# ANTES
class TemperatureLogRead(BaseModel):
    recorded_at: str
    created_at: str

# AGORA
class TemperatureLogRead(BaseModel):
    recorded_at: datetime
    created_at: datetime
```

**Impacto no frontend:** Nenhum — o JSON continua a ter strings ISO 8601.
O tipo TypeScript `TemperatureLog` em `types.ts` usa `string` — correcto.

---

### 3. JWKS cache tem TTL de 1 hora

**Ficheiro:** `apps/backend/app/core/security.py`

A cache de chaves públicas Supabase era permanente. Se Supabase rodar as
chaves, todos os tokens novos seriam rejeitados até restart. Adicionado
TTL de 3600 segundos com `time.monotonic()`.

```python
# Variáveis adicionadas ao módulo:
_jwks_cache_at: float = 0.0
_JWKS_TTL_SECONDS: float = 3600.0
```

---

### 4. Novo endpoint: `GET /restaurants/{restaurant_id}/haccp/runs/{run_id}`

**Ficheiro:** `apps/backend/app/api/v1/endpoints/haccp.py`

Não existia endpoint para buscar um run por ID. O frontend contornava
com `listRuns(today) + find()`, o que quebrava para runs de outros dias.

O novo endpoint está antes do `POST /runs` no router:

```python
@router.get("/runs/{run_id}", response_model=HACCPRunRead)
async def get_run(run_id: UUID, membership: CurrentMembership, ...) -> HACCPChecklistRun:
```

Multi-tenancy preservado: filtra `restaurant_id` como todos os outros.

---

### 5. `receive_lot` valida `expiry_required` no backend

**Ficheiro:** `apps/backend/app/api/v1/endpoints/stock_lots.py`

A regra "produto com `expiry_required=True` obriga a data de validade"
existia apenas no frontend. Via API directa era possível criar lotes
sem data. Agora o backend retorna HTTP 422 se a regra for violada.

```python
# Lógica adicionada antes de chamar svc.receive():
if product.expiry_required and data.expiry_date is None:
    raise HTTPException(422, detail="expiry_date is required for this product")
```

---

### 6. `_low_stock_alerts` sem N+1

**Ficheiro:** `apps/backend/app/services/dashboard_service.py`

Era: 1 query por produto para buscar os seus lots → N+1 queries.
Agora: 2 queries totais (produtos + todos os lots activos desses produtos),
agrupamento em memória com dict.

---

### 7. `conftest.py` simplificado

**Ficheiro:** `apps/backend/tests/conftest.py`

Removidas fixtures `db_engine`, `session`, `client` que nunca eram
usadas por nenhum teste. Cada ficheiro de teste define as suas próprias
fixtures localmente. O conftest agora só define env vars.

---

### 8. `haccpApi.getRun` corrigido + página de run actualizada

**Ficheiros:**
- `apps/web/lib/api/resources.ts`
- `apps/web/app/app/[restaurantId]/haccp/[runId]/page.tsx`

`getRun` antes ignorava o `runId` e chamava o endpoint errado.
Corrigido para usar `/haccp/runs/${runId}`.

A página `[runId]/page.tsx` foi actualizada para usar `haccpApi.getRun`
directamente em vez do workaround `listRuns(today) + find()`. Agora tem
estado de erro explícito (em vez de loading eterno quando run não existe).

---

## O que NÃO mudou

- Todos os modelos ORM (models/)
- Stock service (FEFO, receber, descartar, etc.)
- HACCP service (seed templates, start_run, submit_answer, complete_run)
- Sistema de permissões (permissions.py)
- Todas as migrations (001–005 — não há nova migration)
- Todas as outras páginas frontend
- Contratos de todas as outras APIs
- CI workflows

---

## O que ficou pendente para o Sprint 4

### PENDENTE-01 — UI para discard de lote e editar validade

Os endpoints `POST /stock-lots/{lotId}/discard` e
`PUT /stock-lots/{lotId}/expiry` existem e funcionam. As funções
`stockLotsApi.discard()` e `stockLotsApi.updateExpiry()` existem em
`resources.ts`. Mas nenhum botão na UI as chama.

O chef vê alertas de validade no dashboard mas não consegue agir.
Isto deve ser adicionado no Sprint 4 como parte dos fluxos completos
de stock.

---

## Estado actual do CI

Após as correcções, todos os checks passam:

```
Backend:
  ruff check       → ALL CHECKS PASSED
  ruff format      → 71 files already formatted
  mypy app         → Success: no issues found in 57 source files
  pytest (sem DB)  → 11 passed

Frontend:
  tsc --noEmit     → 0 errors
  eslint           → 0 errors, 0 warnings
  vitest           → 1 passed
  next build       → 14 routes, 0 errors
```

Os testes DB (57 testes no CI com Postgres) continuam a passar em CI
— as alterações nos schemas são compatíveis com os testes existentes.

---

## Como validar manualmente antes do Sprint 4

```bash
# Backend
cd apps/backend
uv run ruff check . && uv run mypy app
uv run pytest tests/test_permissions.py tests/test_health.py -v

# Frontend
pnpm --filter web typecheck
pnpm --filter web lint
pnpm --filter web test run
```

Para validação com DB real, seguir o plano de teste de Henrique:
1. Login → Dashboard (vazio)
2. Equipment → criar fridge → log temp 7.5°C → should flag out of range
3. HACCP → Temperature Log → Start → deve mostrar lista de equipamentos
4. Products → criar produto expiry_required=true
5. Stock → Receive sem data → deve recusar (422)
6. Stock → Receive com data amanhã → deve aceitar
7. Dashboard → deve mostrar alerta critical_expiry

---

_Este ficheiro pode ser removido depois do Sprint 4 estar completo._
