# Plano de Construção — Restaurant Stock + HACCP App

Documento técnico de referência. Não é roadmap motivacional. É o que vai ser construído, em que ordem, com que arquitetura, e como se valida que cada etapa está pronta para vender.

Codinome interno provisório: `kitchenstock`. Nome comercial a definir.

---

## 1. Diagnóstico estratégico

### 1.1 Tese de venda confirmada

O cliente-alvo é dono de restaurante pequeno/médio do convívio do Henrique em Dublin. A dor que ele paga para resolver é uma combinação de três problemas que hoje exigem três sistemas diferentes ou planilha + papel:

1. Controle de validade de produtos (perda de dinheiro real toda semana).
2. HACCP irlandês que hoje é feito em caderno e dá problema na inspeção.
3. POS desconectado do estoque, gerando trabalho dobrado e inventário errado.

### 1.2 Diferenciais defendíveis

| Diferencial | Quem mais oferece junto |
|---|---|
| HACCP irlandês + estoque + invoice por foto + POS no mesmo produto | Ninguém no segmento pequeno |
| Adaptação ao POS que o cliente já usa (não força migração) | Apicbase força integrações deles |
| Preço entry-level (€30–100/mês) com onboarding em vídeo | MarketMan e Lightspeed começam acima de €150 |
| Autenticação manual de validade lote a lote (sem erro de IA) | Quase todos prometem 100% automático e quebram |
| Treinamento em vídeo gravado e suporte em português | Nenhum competidor global |

### 1.3 O que NÃO está no escopo (decisão consciente)

- Pedido automático para fornecedor (V2 ou nunca).
- Previsão de consumo com IA (V2).
- Scanner de código de barras (V2).
- Multi-location complexo (V2).
- Contabilidade, payroll, pagamentos (nunca — não somos isso).
- Chat interno, BI avançado (nunca).

---

## 2. Stack tecnológica final

### 2.1 Backend

- **Linguagem:** Python 3.12
- **Framework:** FastAPI
- **ORM:** SQLModel (Pydantic + SQLAlchemy unificados)
- **Migrations:** Alembic
- **Banco:** PostgreSQL 16 (Railway)
- **Auth:** Supabase Auth (JWT, refresh, magic link, recovery prontos)
- **Storage:** Supabase Storage (invoices, exports PDF, anexos)
- **OCR/LLM:** Camada abstrata `OCRProvider` + implementação Gemini 2.5 Flash com structured output via Pydantic. Implementação fake para testes.
- **PDF:** WeasyPrint (HTML→PDF para HACCP)
- **Logs:** structlog + Better Stack/Logtail em produção
- **Lint/format:** ruff
- **Type check:** mypy (modo `strict` no backend novo)
- **Testes:** pytest, pytest-asyncio, httpx, factory-boy, freezegun
- **Tarefas assíncronas (V2):** Celery + Redis (apenas quando necessário; MVP usa BackgroundTasks do FastAPI)

### 2.2 Frontend

- **Framework:** Next.js 15 (App Router)
- **Linguagem:** TypeScript (strict)
- **Estilo:** Tailwind CSS + shadcn/ui
- **Estado servidor:** TanStack Query (React Query)
- **Forms:** React Hook Form + Zod
- **Cliente Supabase:** `@supabase/ssr`
- **Lint:** ESLint + Prettier
- **Testes:** Vitest + React Testing Library + Playwright (E2E)

### 2.3 Infraestrutura

- **Backend deploy:** Railway (FastAPI + Postgres no mesmo projeto)
- **Frontend deploy:** Vercel
- **Auth + Storage:** Supabase (projeto SEPARADO do SmartDocket)
- **DNS / domínio:** Cloudflare (a definir após nome comercial)
- **Erros:** Sentry (free tier resolve no início)
- **Analytics:** PostHog (self-host opcional, ou cloud free)
- **Monitoramento de uptime:** Better Stack

### 2.4 Repositório

Estratégia: **monorepo** com pnpm workspaces.

```
kitchenstock/
├── apps/
│   ├── backend/         # FastAPI
│   └── web/             # Next.js
├── packages/
│   ├── shared-types/    # tipos TS gerados a partir do OpenAPI
│   └── shared-utils/    # validações, formatadores
├── docs/                # planos, ADRs, runbooks
├── .github/
│   └── workflows/       # CI: lint, type-check, test, build
├── docker-compose.yml   # postgres local
├── pnpm-workspace.yaml
└── README.md
```

Se preferir polirepo (separa backend e frontend em dois repos), também serve. Recomendo monorepo para você como solo dev — menos contexto trocado, tipos compartilhados de graça.

---

## 3. Arquitetura backend — estrutura de pastas

```
apps/backend/
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── alembic.ini
├── pyproject.toml
├── Dockerfile
├── railway.toml
├── .env.example
├── tests/
│   ├── conftest.py
│   ├── factories/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── app/
    ├── main.py                    # FastAPI app, middlewares, routers
    ├── core/
    │   ├── config.py              # Pydantic Settings
    │   ├── database.py            # engine, async sessions
    │   ├── security.py            # JWT verify (Supabase), password
    │   ├── logging.py             # structlog config
    │   └── exceptions.py          # exception handlers
    ├── models/                    # SQLModel - tabelas
    │   ├── __init__.py
    │   ├── base.py                # TimestampedBase, mixins
    │   ├── user.py
    │   ├── restaurant.py
    │   ├── membership.py
    │   ├── product.py
    │   ├── stock_lot.py
    │   ├── stock_movement.py
    │   ├── supplier.py
    │   ├── invoice.py
    │   ├── menu_item.py
    │   ├── recipe.py
    │   ├── pos_integration.py
    │   ├── pos_event.py
    │   ├── purchase_list.py
    │   ├── waste_record.py
    │   ├── equipment.py
    │   ├── temperature_log.py
    │   └── haccp.py
    ├── schemas/                   # Pydantic - DTOs API
    │   ├── auth.py
    │   ├── restaurant.py
    │   ├── product.py
    │   └── ...
    ├── api/
    │   ├── deps.py                # current_user, current_membership
    │   └── v1/
    │       ├── router.py          # agrega todos os routers
    │       ├── auth.py
    │       ├── restaurants.py
    │       ├── products.py
    │       ├── suppliers.py
    │       ├── stock_lots.py
    │       ├── stock_movements.py
    │       ├── invoices.py
    │       ├── recipes.py
    │       ├── pos.py
    │       ├── purchase_lists.py
    │       ├── waste.py
    │       ├── haccp.py
    │       ├── reports.py
    │       └── webhooks.py
    ├── services/                  # regra de negócio
    │   ├── auth_service.py
    │   ├── restaurant_service.py
    │   ├── product_service.py
    │   ├── stock_service.py       # FEFO, alertas, cálculos
    │   ├── invoice_service.py
    │   ├── recipe_service.py
    │   ├── pos_service.py
    │   ├── purchase_list_service.py
    │   ├── waste_service.py
    │   ├── haccp_service.py
    │   ├── report_service.py
    │   └── alert_service.py
    ├── repositories/              # acesso a dados
    │   ├── base.py
    │   ├── product_repository.py
    │   └── ...
    ├── integrations/
    │   ├── ocr/
    │   │   ├── base.py            # OCRProvider abstrato
    │   │   ├── gemini_provider.py
    │   │   └── fake_provider.py
    │   ├── llm/
    │   │   ├── base.py
    │   │   └── gemini_provider.py
    │   ├── pos/
    │   │   ├── base.py            # POSAdapter abstrato
    │   │   ├── square_adapter.py
    │   │   ├── flipdish_adapter.py
    │   │   ├── sumup_adapter.py
    │   │   └── normalizer.py
    │   └── storage/
    │       └── supabase_storage.py
    ├── pdf/
    │   ├── templates/             # Jinja2 HTML
    │   ├── temperature_log.py
    │   ├── daily_checklist.py
    │   └── purchase_list.py
    └── utils/
        ├── units.py               # conversão unidades
        ├── dates.py
        └── pagination.py
```

**Princípios obrigatórios:**

1. `routes` chamam `services`. Nunca SQL.
2. `services` chamam `repositories`. Repositories isolam queries.
3. Toda integração externa (OCR, LLM, POS, Storage) tem interface abstrata em `integrations/<tipo>/base.py`. Implementação concreta nunca é importada direto fora de `integrations/`.
4. `models` (SQLModel) e `schemas` (Pydantic API) são separados. Não retornar SQLModel cru pra API.
5. Toda função que toca banco recebe `session` por parâmetro. Não criar sessões internas.

---

## 4. Modelo de dados — Fase 1 (Núcleo)

### 4.1 Princípios de schema

- **Toda tabela tem:** `id` (UUID), `created_at`, `updated_at`.
- **Toda tabela de domínio tem:** `restaurant_id` (FK NOT NULL com index). Sem exceção, nem mesmo categorias, suppliers, equipment.
- **Soft delete** via `is_active BOOLEAN` em produtos, suppliers, equipment, recipes, menu_items. Stock movements e logs nunca são deletados.
- **Enums** vivem como tipos PostgreSQL (não strings livres).
- **Money** sempre como `NUMERIC(12, 2)` em EUR. Nunca float.
- **Quantidades** sempre como `NUMERIC(12, 3)` (gramas com 3 casas).
- **Timestamps** sempre `TIMESTAMPTZ` (com timezone).

### 4.2 Tabelas Fase 1

#### users
```
id              UUID PK (vem do Supabase Auth)
email           CITEXT UNIQUE NOT NULL
full_name       TEXT
preferred_lang  TEXT DEFAULT 'pt-BR'
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

#### restaurants
```
id              UUID PK
name            TEXT NOT NULL
legal_name      TEXT
address         TEXT
city            TEXT
country         TEXT DEFAULT 'IE'
postal_code     TEXT
timezone        TEXT DEFAULT 'Europe/Dublin'
currency        TEXT DEFAULT 'EUR'
vat_number      TEXT
expiry_warning_days       INT DEFAULT 3
critical_expiry_days      INT DEFAULT 1
low_stock_alert_enabled   BOOLEAN DEFAULT TRUE
haccp_alert_enabled       BOOLEAN DEFAULT TRUE
is_active       BOOLEAN DEFAULT TRUE
created_at, updated_at
```

#### restaurant_memberships
```
id              UUID PK
restaurant_id   UUID FK -> restaurants
user_id         UUID FK -> users
role            ENUM('owner','manager','staff') NOT NULL
is_active       BOOLEAN DEFAULT TRUE
created_at, updated_at
UNIQUE(restaurant_id, user_id)
INDEX(user_id, is_active)
```

#### product_categories
```
id              UUID PK
restaurant_id   UUID FK NULL  -- NULL = global, default seed
name            TEXT NOT NULL
slug            TEXT NOT NULL
created_at
UNIQUE(restaurant_id, slug)
```

Seed inicial de categorias globais: Meat, Fish, Dairy, Vegetables, Fruit, Bakery, Dry goods, Drinks, Cleaning, Packaging, Other.

#### suppliers
```
id              UUID PK
restaurant_id   UUID FK NOT NULL
name            TEXT NOT NULL
contact_name    TEXT
email           TEXT
phone           TEXT
address         TEXT
notes           TEXT
is_active       BOOLEAN DEFAULT TRUE
created_at, updated_at
INDEX(restaurant_id, is_active)
```

#### products
```
id                       UUID PK
restaurant_id            UUID FK NOT NULL
name                     TEXT NOT NULL
normalized_name          TEXT NOT NULL  -- lowercase, sem acento
category_id              UUID FK
default_unit             ENUM unit_kind NOT NULL
storage_type             ENUM('fridge','freezer','dry','ambient','other') NOT NULL
minimum_stock_quantity   NUMERIC(12,3) DEFAULT 0
par_level_quantity       NUMERIC(12,3)
default_supplier_id      UUID FK
cost_average             NUMERIC(12,4)
expiry_required          BOOLEAN DEFAULT TRUE
is_active                BOOLEAN DEFAULT TRUE
created_at, updated_at
INDEX(restaurant_id, normalized_name)
INDEX(restaurant_id, is_active)
```

`unit_kind` ENUM: `g, kg, ml, l, tsp, tbsp, cup, unit, pack, box, case, bottle, can, bag`.

#### stock_lots
```
id                  UUID PK
restaurant_id       UUID FK NOT NULL
product_id          UUID FK NOT NULL
supplier_id         UUID FK
invoice_id          UUID FK NULL  -- preenchido na fase 2
batch_code          TEXT
quantity_initial    NUMERIC(12,3) NOT NULL CHECK (>= 0)
quantity_current    NUMERIC(12,3) NOT NULL CHECK (>= 0)
unit                ENUM unit_kind NOT NULL
expiry_date         DATE NULL  -- NULL = sem validade definida (gera alerta)
received_date       DATE NOT NULL
storage_type        ENUM(...)
unit_cost           NUMERIC(12,4)
total_cost          NUMERIC(12,2)
status              ENUM('active','depleted','expired','discarded') DEFAULT 'active'
notes               TEXT
created_at, updated_at
INDEX(restaurant_id, product_id, status)
INDEX(restaurant_id, expiry_date) WHERE status='active'
```

#### stock_movements (IMUTÁVEL — sem update, sem delete)
```
id                       UUID PK
restaurant_id            UUID FK NOT NULL
product_id               UUID FK NOT NULL
stock_lot_id             UUID FK NULL
movement_type            ENUM('invoice_in','manual_in','manual_out','pos_sale_out','waste','stock_count_adjustment','correction','transfer')
quantity                 NUMERIC(12,3) NOT NULL  -- positivo = entrada, negativo = saída
unit                     ENUM unit_kind NOT NULL
unit_cost_snapshot       NUMERIC(12,4)
total_value_snapshot     NUMERIC(12,2)
reason                   TEXT
source_type              ENUM('manual','invoice','pos','haccp','system')
source_id                UUID NULL
created_by_user_id       UUID FK
created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
INDEX(restaurant_id, created_at DESC)
INDEX(restaurant_id, product_id, created_at DESC)
INDEX(stock_lot_id)
```

#### equipment
```
id                  UUID PK
restaurant_id       UUID FK NOT NULL
name                TEXT NOT NULL
type                ENUM('fridge','freezer','hot_hold','other')
location            TEXT
min_temp_celsius    NUMERIC(5,2)
max_temp_celsius    NUMERIC(5,2)
is_active           BOOLEAN DEFAULT TRUE
created_at, updated_at
```

Defaults sugeridos por tipo (configuráveis):
- Fridge: 0°C a 5°C
- Freezer: ≤ -18°C
- Hot hold: ≥ 63°C

#### temperature_logs
```
id                            UUID PK
restaurant_id                 UUID FK NOT NULL
equipment_id                  UUID FK NOT NULL
temperature_celsius           NUMERIC(5,2) NOT NULL
checked_at                    TIMESTAMPTZ NOT NULL
checked_by_user_id            UUID FK NOT NULL
status                        ENUM('ok','warning','critical') NOT NULL
corrective_action_required    BOOLEAN DEFAULT FALSE
corrective_action_notes       TEXT
created_at
INDEX(restaurant_id, equipment_id, checked_at DESC)
INDEX(restaurant_id, checked_at DESC)
```

#### haccp_checklist_templates
```
id              UUID PK
restaurant_id   UUID FK NOT NULL
name            TEXT NOT NULL
type            ENUM('opening','closing','cleaning','delivery','custom')
frequency       ENUM('daily','weekly','monthly','custom')
is_active       BOOLEAN DEFAULT TRUE
created_at, updated_at
```

#### haccp_checklist_item_templates
```
id              UUID PK
template_id     UUID FK NOT NULL
text            TEXT NOT NULL
input_type      ENUM('checkbox','temperature','text','number','select')
required        BOOLEAN DEFAULT TRUE
order_index     INT NOT NULL
options_json    JSONB  -- para input_type=select
INDEX(template_id, order_index)
```

#### haccp_checklist_runs
```
id                      UUID PK
restaurant_id           UUID FK NOT NULL
template_id             UUID FK NOT NULL
run_date                DATE NOT NULL
status                  ENUM('pending','completed','missed') DEFAULT 'pending'
completed_by_user_id    UUID FK
completed_at            TIMESTAMPTZ
created_at, updated_at
INDEX(restaurant_id, run_date DESC)
UNIQUE(restaurant_id, template_id, run_date)
```

#### haccp_checklist_answers
```
id                  UUID PK
run_id              UUID FK NOT NULL
item_template_id    UUID FK NOT NULL
value_text          TEXT
value_number        NUMERIC(12,3)
value_boolean       BOOLEAN
notes               TEXT
created_at, updated_at
UNIQUE(run_id, item_template_id)
```

### 4.3 Tabelas adicionadas na Fase 2

`invoices`, `invoice_line_items` — schemas conforme documento original.

### 4.4 Tabelas adicionadas na Fase 3

`menu_items`, `recipes`, `recipe_ingredients`, `waste_records`, `purchase_lists`, `purchase_list_items`.

### 4.5 Tabelas adicionadas na Fase 4

`pos_integrations`, `pos_events`.

---

## 5. Regras de negócio críticas

### 5.1 Multi-tenant — não-negociável

Toda query DEVE filtrar por `restaurant_id`. Implementação:

- Dependency `get_current_membership(restaurant_id, user)` em todos os routers de domínio.
- Repositórios recebem `restaurant_id` como primeiro argumento OBRIGATÓRIO.
- Teste de regressão dedicado: tentar acessar dado de restaurante B logado em restaurante A → 404 (não 403, não revelar existência).

### 5.2 FEFO (First Expired, First Out)

Ao baixar estoque de um produto, ordenar lotes ativos por:
1. `expiry_date ASC NULLS LAST`
2. `received_date ASC` (desempate)

Lotes sem validade definida vão por último — gera alerta de pendência mas não bloqueia consumo.

Função canônica: `StockService.consume(restaurant_id, product_id, quantity, unit, source) -> List[Movement]`. Usa transação. Se quantidade > soma dos lotes ativos, lança `InsufficientStockError` e cria alerta sem movimento.

### 5.3 Movimentos imutáveis

- Não existe endpoint de UPDATE ou DELETE em `stock_movements`.
- Correção = novo movimento `correction` com sinal oposto + motivo.
- Mesma regra para `temperature_logs` e `haccp_checklist_answers`.

### 5.4 Idempotência POS (Fase 4)

`pos_events.external_event_id + provider` é único. Webhook que chega 2x com mesmo evento não baixa estoque 2x. Salvar payload bruto antes de processar; processar em transação separada.

### 5.5 IA nunca atualiza estoque sozinha

Invoice processada por IA gera `invoice` em status `needs_review`. Só vira lote depois do `POST /confirm` explícito do usuário. Sem exceção.

### 5.6 Validade é obrigatória em produtos perecíveis

Produto com `expiry_required=true` não permite criar lote sem `expiry_date`. UI obriga preenchimento. Backend valida.

### 5.7 Quantity nunca negativa

Constraint no banco. Tentativa de saída maior que disponível → erro 422 + alerta, sem persistir.

---

## 6. Roadmap de execução

Cada fase termina com **release tagged + deploy + cliente testando**. Não passar pra próxima fase enquanto a anterior tem bug Major aberto.

### Fase 0 — Setup (3-5 dias)

**Objetivo:** Esqueleto compilando, deployado, com pipeline de CI passando.

Entregáveis:
- Repo monorepo no GitHub.
- Backend FastAPI com `/health` retornando 200.
- Frontend Next.js com landing placeholder.
- Postgres no Railway, Supabase project criado, Vercel conectado.
- CI: lint + type-check + test rodando em PR.
- `.env.example` documentado.
- `README.md` com setup local em < 5 minutos.
- ADR 001 documentando stack.

Critério de aceite: clonar do zero em máquina nova e rodar `pnpm dev` + backend local em < 10 min.

### Fase 1 — Núcleo Vendável (4 semanas)

**Objetivo:** Cliente paga pra controlar validade + ter HACCP digital.

Sprint 1 (semana 1) — Auth + Restaurants
- Models: users, restaurants, memberships
- Endpoints auth (proxied to Supabase Auth)
- Endpoints restaurants CRUD + members
- Frontend: signup, login, criar restaurante, selecionar restaurante ativo
- Testes: regressão multi-tenant (acesso cruzado retorna 404)

Sprint 2 (semana 2) — Produtos + Lotes + Movimentos
- Models: categories, suppliers, products, stock_lots, stock_movements
- Endpoints CRUD
- StockService.consume com FEFO
- Endpoints manual_in / manual_out / adjustment
- Frontend: tela produtos, tela lotes, tela movimentos
- Testes unitários FEFO (10+ casos)

Sprint 3 (semana 3) — Alertas + Dashboard + HACCP base
- Queries de alerta dinâmico
- Endpoint dashboard consolidado
- Models: equipment, temperature_logs, haccp templates/runs/answers
- Frontend: dashboard, registro de temperatura, checklist diário
- Seed de templates HACCP padrão (opening/closing irlandês)

Sprint 4 (semana 4) — PDF HACCP + polish + onboarding
- WeasyPrint setup
- 3 PDFs: temperature log, daily checklist, monthly HACCP
- Onboarding wizard (criar primeiro produto, primeiro equipment, primeiro checklist)
- Vídeo de treinamento gravado
- Deploy produção
- 1 cliente testador real instalado

**Critério de pronto pra vender:** cliente real consegue, sem ajuda do Henrique, criar 10 produtos, registrar 5 lotes, fazer checklist HACCP de 1 dia e exportar PDF.

### Fase 2 — Invoice por Foto (3 semanas)

**Objetivo:** Reduzir entrada de estoque de 30 min para 3 min.

Sprint 5 (semana 1) — Upload + OCR base
- Storage Supabase
- Models: invoices, invoice_line_items
- Endpoint upload com pre-signed URL
- OCRProvider abstrato + FakeOCRProvider para testes

Sprint 6 (semana 2) — Gemini integration + normalização
- GeminiOCRProvider com structured output Pydantic
- LLMNormalizerService (matching com produtos existentes via embeddings ou similarity)
- Endpoint `POST /invoices/{id}/process`

Sprint 7 (semana 3) — Tela de revisão + confirmação
- Frontend: tela linha por linha com edição inline
- Validação manual de validade obrigatória em perecíveis
- Endpoint `POST /invoices/{id}/confirm` cria lotes + movimentos
- Telemetria: tempo médio de revisão, taxa de correção da IA

**Critério de pronto:** invoice de 20 itens processada e confirmada em < 5 min.

### Fase 3 — Receitas + Desperdício + Pré-lista (3 semanas)

Sprint 8 — Menu items + Recipes
Sprint 9 — Waste records + relatórios
Sprint 10 — Purchase list por fornecedor + PDF

### Fase 4 — Integrações POS (4-6 semanas)

Sprint 11-12 — Adapter base + Square
Sprint 13 — Flipdish (prioridade Irlanda)
Sprint 14 — SumUp
EposNow / Revolut sob demanda do cliente.

---

## 7. Estratégia de testes

### 7.1 Pirâmide

- **Unit (60%):** services, FEFO, cálculos, validações puras. Sem banco.
- **Integration (30%):** endpoints com banco real (test DB), com mocks de OCR/POS.
- **E2E (10%):** Playwright cobrindo 5 fluxos críticos.

### 7.2 Fluxos E2E obrigatórios

1. Signup → criar restaurante → criar produto → criar lote → ver dashboard.
2. Registrar temperatura fora do limite → ver alerta → adicionar ação corretiva.
3. (Fase 2) Upload de invoice → revisar → confirmar → ver estoque atualizado.
4. (Fase 3) Cadastrar receita → registrar venda manual → ver baixa correta com FEFO.
5. (Fase 4) Webhook POS → estoque baixa idempotente.

### 7.3 Testes de regressão obrigatórios em todo PR

- Multi-tenant: usuário do restaurante A não vê dado do B.
- FEFO: lote vencendo primeiro é consumido primeiro.
- Idempotência: mesmo `external_event_id` não cria 2 movimentos.
- Imutabilidade: tentativa de UPDATE em stock_movements falha.

### 7.4 Cobertura mínima exigida

- Backend: 75% global, 90% em `services/stock_service.py` e `services/invoice_service.py`.
- Frontend: 60% global, 100% em validações de form.

---

## 8. Segurança

### 8.1 Checklist mínimo antes do primeiro cliente real

- [ ] Supabase Row Level Security (RLS) ativada em TODAS as tabelas.
- [ ] Política RLS por `restaurant_id` validada.
- [ ] CORS configurado com whitelist explícita (sem `*`).
- [ ] Rate limit em `/auth/*` (5 tentativas/min/IP).
- [ ] Rate limit em `/invoices/upload` (10/hora/restaurante na Fase 2).
- [ ] Webhooks POS com verificação de assinatura HMAC.
- [ ] Logs nunca contêm: senhas, tokens, payloads de invoice com PII, números de cartão.
- [ ] Tokens POS criptografados em coluna (pgcrypto) com chave em env.
- [ ] Sentry configurado com filtro de PII.
- [ ] Backups Postgres automáticos (Railway oferece) + 1 restore testado.
- [ ] Política de retenção: invoices 7 anos (HACCP), logs 1 ano.
- [ ] HTTPS obrigatório (Railway + Vercel oferecem).
- [ ] Secret rotation documentada em runbook.

### 8.2 GDPR (Irlanda — obrigatório)

- Endpoint de export de dados do usuário (Article 20).
- Endpoint de deleção de conta (Article 17) — soft delete com purge em 30 dias.
- Cookie banner no frontend (essencial + analytics opt-in).
- Política de privacidade publicada antes de aceitar primeiro cliente.
- Data Processing Agreement com Supabase, Railway, Gemini documentado.

---

## 9. Observabilidade

### 9.1 Logs estruturados (structlog)

Todo log inclui: `request_id`, `user_id`, `restaurant_id`, `endpoint`, `duration_ms`. Em integrações: `provider`, `external_id`, `status`.

### 9.2 Métricas chave

- Latência p50/p95/p99 por endpoint.
- Taxa de erro por endpoint.
- Tempo de processamento de invoice (Fase 2).
- Taxa de correção da IA (% de linhas que o usuário editou) — métrica crítica de produto.
- Taxa de checklist HACCP completado por restaurante.
- Eventos POS com falha de processamento (Fase 4).

### 9.3 Alertas em produção

- Erro 5xx > 1% em janela de 5 min → Telegram.
- Latência p95 > 2s em janela de 10 min → Telegram.
- Banco de dados > 80% conexões → Telegram.
- Webhook POS falhando 3x consecutivas → Telegram + alerta no dashboard.

---

## 10. Modelo de pricing (proposta inicial)

Premissas: cliente pequeno (1 restaurante, até 3 usuários, até 200 produtos).

| Plano | Adesão | Mensalidade | Contrato mínimo |
|---|---|---|---|
| Starter (com setup) | €199 | €39/mês | 6 meses |
| Starter (sem setup) | €0 | €59/mês | 12 meses |
| Pro (com POS, V1.0+) | €299 | €79/mês | 6 meses |
| Pro (sem setup) | €0 | €99/mês | 12 meses |

Custos variáveis estimados/cliente/mês:
- Railway (compartilhado): ~€2
- Supabase (compartilhado): ~€1
- Gemini OCR (50 invoices/mês): ~€1
- Total infra: ~€4/cliente.

Margem bruta projetada: 90%+ (sem custos de aquisição). Realista com CAC: 70%.

Henrique, isso é proposta inicial — você decide. Recomendação: começar com Starter com setup em €199 + €39/mês em contrato 6 meses pra cliente do convívio. Se vender 5, valida pricing.

---

## 11. Decisões pendentes (precisam do Henrique)

| # | Decisão | Bloqueia | Prazo |
|---|---|---|---|
| 1 | Nome comercial do produto | Domínio, branding, signup pages | 1 semana |
| 2 | Reusar Supabase do SmartDocket OU criar novo | Setup Fase 0 | Antes de Fase 0 |
| 3 | Prazo realista pra primeiro cliente pagante | Cortes de escopo | Antes de Fase 0 |
| 4 | Repo no GitHub: monorepo ou polirepo | Setup Fase 0 | Antes de Fase 0 |
| 5 | Logo + identidade visual (V0 pode ser texto) | Onboarding cliente | Fase 1 sprint 4 |
| 6 | Política de privacidade + ToS | Antes do primeiro cliente real | Fase 1 sprint 4 |
| 7 | Aprovação do pricing acima ou alternativa | Onboarding cliente | Fase 1 sprint 4 |

---

## 12. Riscos identificados e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Henrique sobrecarregado (SmartDocket + Mad Monkey + isso) | Alta | Crítico | Cortar escopo no MVP, recusar features fora do plano, usar templates de IA pra acelerar |
| Cliente do convívio promete e não compra | Alta | Alto | Cobrar adesão de €199 ANTES de qualquer customização |
| Gemini muda preço ou API | Média | Médio | Camada abstrata já no MVP |
| POS providers (Square, Flipdish) demoram aprovar OAuth | Média | Médio | Submeter cedo, ter roadmap independente da aprovação |
| Concorrente lança feature similar | Baixa | Médio | Moat = comunidade brasileira + UX em PT + HACCP irlandês |
| Bug em FEFO causa estoque errado | Média | Crítico | Cobertura 90%+ em StockService + alerta de discrepância |
| Vazamento de dados multi-tenant | Baixa | Catastrófico | RLS + testes de regressão em todo PR + auditoria antes do primeiro cliente |
| Inspeção HACCP rejeita PDF gerado | Média | Alto | Validar template com inspetor irlandês ANTES de Fase 1 sprint 4 |

---

## 13. Critérios de "pronto pra release" por fase

Ao final de cada fase, antes do deploy de produção:

- [ ] Todos os testes passando em CI (unit + integration + E2E).
- [ ] Cobertura ≥ targets da seção 7.4.
- [ ] Zero erros 5xx no smoke test pós-deploy.
- [ ] Zero issues Blocker ou Critical abertas.
- [ ] Migration aplicada e rollback testado.
- [ ] Runbook atualizado.
- [ ] Changelog publicado.
- [ ] Backup do banco antes do deploy.
- [ ] Plano de rollback escrito.

---

## 14. Próximas 5 ações concretas (esta semana)

1. **Henrique:** decidir nome comercial. Opções: KitchenStock, FreshOps, Prepwise, ou alternativa própria.
2. **Henrique:** decidir reusar Supabase do SmartDocket ou criar novo (recomendação: novo).
3. **Henrique:** confirmar prazo realista pra primeiro cliente pagante (define se Fase 1 vira 4 semanas ou 3).
4. **Claude:** depois das respostas acima, criar repositório, estrutura de pastas, `.env.example`, primeiro endpoint `/health`, CI pipeline, README com setup local. Tudo em 1 sessão de trabalho.
5. **Henrique:** abrir conversa com 3 clientes do convívio: "estou construindo X, vou cobrar €199 + €39/mês com 6 meses de contrato, você topa testar nas primeiras 4 semanas com 50% de desconto?". Validar pricing antes de codar.

---

Documento vivo. Versionado. Atualizado a cada fim de fase.

Versão 1.0 — 2026-05-05.
