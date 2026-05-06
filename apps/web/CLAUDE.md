@AGENTS.md
# Regras específicas do projeto ChefTrace
Antes de escrever qualquer código neste repositório, leia:
- docs/PHASE-0-BRIEF.md (especificação executável da fase atual)
- docs/PLANO_CONSTRUCAO.md (estratégia geral do produto)
- docs/adr/*.md (Architecture Decision Records — TODAS as decisões fundadoras)
## Princípios não-negociáveis
1. Multi-tenant rigoroso: TODA query filtra restaurant_id. Sem exceção.
2. Movimentos de estoque, logs HACCP e POS events são IMUTÁVEIS. Não
   existe endpoint de UPDATE ou DELETE neles.
3. IA nunca atualiza estoque sozinha. Confirmação humana sempre.
4. FEFO obrigatório: lotes consumidos por ordem de vencimento (NULLS LAST).
5. Validade obrigatória em produtos perecíveis (expiry_required=true).
6. Quantity nunca negativa (constraint de banco).
## Padrões de código
- Routes chamam services. Services chamam repositories. Nunca SQL em route.
- SQLModel pra modelos. Schemas Pydantic separados pra API.
- Toda integração externa (OCR, LLM, POS, Storage) atrás de interface
  abstrata em integrations/<tipo>/base.py.
- Logs estruturados com structlog: request_id, user_id, restaurant_id,
  endpoint, duration_ms.
- Money sempre NUMERIC(12,2). Quantidades sempre NUMERIC(12,3).
- Timestamps sempre TIMESTAMPTZ.
## Sem emojis
NUNCA use emojis em folder names, file names, paths ou identificadores
técnicos. Apenas em texto conversacional se o usuário usar primeiro.
## Antes de propor mudança de stack
Se for sugerir trocar uma tecnologia decidida no ADR-001 (FastAPI, SQLModel,
Next.js, Supabase Auth, Railway, Tailwind 3, etc.), pare e proponha um ADR
novo justificando. Não faça mudança silenciosa.
## Antes de adicionar uma dependência nova
Confirme com o usuário (Henrique) antes de adicionar pacote novo ao
pyproject.toml ou package.json. Cada dependência é dívida técnica futura.
