# Guia de execução e testes

Ponto de partida para testar o projeto. Resume **como funciona**, **como rodar** e **o que testar**, em
ordem crescente de dependência (sem nada → Docker → API → hardware). Detalhes completos em
`README.md`, `documento/v1/como_rodar.md` e `documento/v1/explicacao_implementacao.md`.

---

## 1. Como funciona (visão de 1 minuto)

```
 Prefeitura SP (XLSX ITBI)
          │  coleta.py (download) ou POST /arquivos (upload)
          ▼
 ┌──────────────────────── API FastAPI (1 processo) ───────────────────────┐
 │ BRONZE  bronze.py   guarda o arquivo original + SHA-256 (data/bronze/)   │
 │ LEITURA leitor.py   lê a aba em streaming, mapeia as 28 colunas,         │
 │                     NÃO limpa valores; anota o tipo da célula (n/s/d)    │
 │ LOTES   execucoes.py  monta lotes de 10 registros                        │
 │ ORQ.    orquestrador.py  distribui por MQTT, timeout, reenvio, failover  │
 └───────────────┬──────────────────────────────────────▲──────────────────┘
                 │ tcc/nos/{no_id}/tarefa (1 registro)  │ tcc/resultados
                 ▼                                      │
        Mosquitto (MQTT, porta 1884) ◄── estado/LWT ── ESP32 × 3 (MicroPython)
                                                        firmware/regras.py = LIMPEZA
                 │                                      OLED mostra lote/registro/erros
                 ▼
 PostgreSQL (porta 5434)
   SILVER  registros_silver (dados tratados + erros por campo, 1 por registro)
   GOLD    gold.py → indicadores e métricas (tempo por nó, memória, erros)
```

Ideia central do TCC: o **computador só lê e distribui**; quem **aplica as regras de limpeza** são os
ESP32. Sem hardware, `scripts/simulador_no.py` faz o papel de um nó executando o **mesmo** `regras.py`
(resultados ficam marcados `simulado=true`).

Ciclo de um lote: `pendente → atribuido → processando → concluido | falhou`. O próximo registro só sai
depois que a resposta anterior foi gravada; respostas repetidas não sobrescrevem o Silver.

---

## 2. Preparar o ambiente

```bash
cd ~/Documentos/Projeto_TCC_Arquitetura_Baixo_Custo

python3 -m venv .venv                         # Python 3.12
.venv/bin/pip install -r requirements-dev.txt

cp .env.example .env                          # troque PG_PASSWORD
docker compose up -d --wait                   # Postgres :5434 + Mosquitto :1884
docker pull micropython/unix                  # opcional: teste das regras no MicroPython real
```

> ⚠️ **Nesta máquina o banco é o PostgreSQL local, não o do Docker.** O `.env` aponta para
> `localhost:5432`, banco **`tcc_itbi`**, usuário `postgres`. Os dados foram copiados do container
> `tcc-postgres` em 2026-10-26, e o container ficou parado como cópia antiga. Do Docker, só o
> **Mosquitto** é usado.
>
> - **Não rode `docker compose up -d`** sem nomear o serviço: com `PG_PORTA=5432`, o Postgres do compose
>   brigaria pela porta com o Postgres local. E o `container_name` fixo também conflita com os containers
>   criados pela pasta antiga `~/Documentos/Projeto_TCC`.
> - Os XLSX do Bronze estão em `~/Documentos/Projeto_TCC/data/bronze/` (caminho absoluto no catálogo):
>   **não apague a pasta antiga**, ou reenvie os arquivos por `POST /arquivos`.
> - O banco `project_tcc` (mesma instância) é de outro código, com `itbi_sp` e o próprio Alembic. Este
>   projeto não mexe nele.
>
> **DBeaver:** host `localhost`, porta **5432**, banco **`tcc_itbi`**, usuário `postgres`.

### Rodar no dia a dia

```bash
docker start tcc-mosquitto                                                     # 1. broker MQTT (o Postgres local já está no ar)
.venv/bin/uvicorn app.main:app --app-dir api --host 0.0.0.0 --port 8010        # 2. API (terminal 1)
.venv/bin/python scripts/simulador_no.py --id sim-01                           # 3. nó simulado (terminal 2)
# 4. abra http://localhost:8010/
```

---

## 3. Testes automatizados

```bash
.venv/bin/pytest -q -rs          # -rs mostra o motivo dos testes pulados
```

| Arquivo | O que verifica | Precisa de |
| --- | --- | --- |
| `tests/test_regras.py` | regras de limpeza do ESP32 (decimal, CEP, número, data, inteiro, registro inteiro) | nada |
| `tests/test_leitor.py` | leitura XLSX, abas, limite, ACC duplicado 2019, grafia "pardão", 29ª coluna, fixtures reais | nada |
| `tests/test_micropython.py` | roda as fixtures das regras no MicroPython (port Unix) e exige `falhas: 0` | imagem `micropython/unix` |
| `tests/test_integracao.py` | 3 nós distribuindo lotes, resposta duplicada, queda de nó, timeout/reenvio, reinício do orquestrador, indicadores | Postgres + Mosquitto no ar |

A integração usa banco próprio (`tcc_itbi_teste`, criado no mesmo Postgres do `.env`) e prefixo MQTT aleatório: não interfere numa API
rodando. Se os serviços não respondem, os testes são **pulados** (não falham). Fique atento a isso.

Rodar um grupo ou um teste:

```bash
.venv/bin/pytest -q tests/test_regras.py
.venv/bin/pytest -q tests/test_integracao.py -k queda
```

Conferir se o firmware compila para o ESP32:

```bash
for f in firmware/*.py; do .venv/bin/python -m mpy_cross -march=xtensawin "$f" -o /tmp/x.mpy && echo "ok $f"; done
```

### Situação verificada em 2026-10-26

- `55 passed` (regras, leitor, MicroPython e integração).
- Ponta a ponta manual: `exec-000004` (arquivo 1, JAN-2026, 10 registros, `sim-01`) → `concluida 10/10`.

---

## 4. Teste manual ponta a ponta (sem hardware)

**Terminal 1: API** (um único processo, sem `--workers`):

```bash
.venv/bin/uvicorn app.main:app --app-dir api --host 0.0.0.0 --port 8010
```

Painel: <http://localhost:8010/> · Swagger: <http://localhost:8010/docs>

**Terminal 2: nó simulado**

```bash
.venv/bin/python scripts/simulador_no.py --id sim-01
```

**Terminal 3: roteiro**

```bash
# 1. Bronze: baixar um ano (ou enviar um XLSX já baixado)
curl -s -X POST localhost:8010/coletas/itbi-sp -H 'content-type: application/json' -d '{"ano": 2026}'
curl -s localhost:8010/coletas/1
#   alternativa: curl -s -F "arquivo=@planilha.xlsx" -F ano_fonte=2026 localhost:8010/arquivos
curl -s localhost:8010/arquivos                      # anote o id

# 2. Executar 10 registros em 1 nó
curl -s -X POST localhost:8010/execucoes -H 'content-type: application/json' \
     -d '{"arquivo_id": 1, "ano": 2026, "mes": "JAN", "limite_registros": 10, "nos": ["sim-01"]}'

# 3. Acompanhar e conferir
# (o POST responde {"execucao_id": "exec-00000N", ...}; use esse ID abaixo)
curl -s localhost:8010/execucoes/exec-000001               # status deve chegar a "concluida"
curl -s localhost:8010/execucoes/exec-000001/registros     # bruto × tratado
curl -s localhost:8010/execucoes/exec-000001/indicadores   # Gold
curl -s localhost:8010/execucoes/exec-000001/metricas
curl -s localhost:8010/nos
```

Ver o MQTT passando: `docker exec -it tcc-mosquitto mosquitto_sub -p 1883 -t 'tcc/#' -v`

### Cenários de falha a provocar

| Cenário | Como provocar | Esperado |
| --- | --- | --- |
| Nó cai no meio do lote | `simulador_no.py --id sim-04 --cair-apos 3` + execução com `["sim-04","sim-01"]` | lote volta a `pendente`, `sim-01` continua do 1º registro faltante |
| Nó para de responder | `--id sim-05 --silenciar-apos 2` | eventos `reenvio` e depois `tentativa_expirada`, lote reatribuído |
| Respostas duplicadas | `--id sim-06 --duplicar` | evento `resposta_duplicada`, Silver sem duplicatas |
| API reinicia no meio | `Ctrl+C` na API durante a execução e subir de novo | lotes ativos voltam a `pendente`/`concluido`, a execução termina |
| Lote esgota tentativas | nós que sempre falham | `falhou`; `POST /execucoes/{id}/retomar` reabre |
| Mesmo arquivo 2× | enviar o mesmo XLSX duas vezes | não duplica (SHA-256) |

Conferências no banco:

```bash
psql -h localhost -p 5432 -U postgres -d tcc_itbi
```

```sql
SELECT id, status, total_esperado FROM execucoes ORDER BY criado_em DESC;
SELECT no_id, count(*) FROM registros_silver WHERE execucao_id = 'exec-000001' GROUP BY no_id;
SELECT tipo, count(*) FROM eventos_execucao WHERE execucao_id = 'exec-000001' GROUP BY tipo;
```

---

## 5. Teste com os ESP32 (pendente: nunca foi feito)

Passo a passo de gravação em `documento/v1/como_rodar.md` §7. Checklist do que validar:

- [ ] OLED liga (SDA=21, SCL=22, 0x3C) e mostra `wifi... → conectando → disponivel / MQTT OK`
- [ ] `GET /nos` lista `esp32-01..03` com `"disponivel": true`
- [ ] 10 registros em 1 nó: OLED vai de `REG 01/10` a `REG 10/10`, execução `concluida`
- [ ] Silver do ESP32 é **idêntico** ao do simulador para o mesmo arquivo/aba (mesmo `regras.py`)
- [ ] 300 registros em 3 nós: lotes divididos entre os três
- [ ] Desligar um ESP32 no meio: LWT `offline`, lote reatribuído
- [ ] Tirar o Wi-Fi e devolver: nó reconecta (`reconectando` no OLED)
- [ ] Coletar `mem_livre` e `duracao_us` por nó (`/metricas`) para o experimento (1, 2 e 3 nós)

Firewall, se houver: `sudo ufw allow 1884/tcp`.

---

## 6. Migrações do banco (Alembic)

O esquema é versionado com **Alembic**, usando SQL puro e sem ORM. A configuração está no
`alembic.ini` da raiz e as revisões em `api/migracoes/versions/`. A conexão vem do `.env`. A API roda
`alembic upgrade head` sozinha ao subir.

```bash
.venv/bin/alembic current                         # versão aplicada (hoje: 0002 (head))
.venv/bin/alembic history                         # lista de revisões
.venv/bin/alembic upgrade head                    # aplica as pendentes
.venv/bin/alembic downgrade -1                    # desfaz a última
.venv/bin/alembic revision -m "descricao" --rev-id 0003   # nova revisão (mantém a numeração)
```

Na revisão nova, escreva o SQL em `upgrade()` e `downgrade()` com `op.execute("...")`. Para rodar contra
o banco de teste: `PG_DB=tcc_itbi_teste .venv/bin/alembic ...`.

| Revisão | O que faz |
| --- | --- |
| `0001` | esquema inicial (`0001_inicial.sql`, idempotente: num banco antigo só registra a versão) |
| `0002` | remove a tabela `migracoes` (controle caseiro anterior ao Alembic) |

No DBeaver, a tabela `alembic_version` do banco `tcc_itbi` guarda a versão aplicada.

---

## 7. Limitações conhecidas

- Só XLSX é lido (`.xls` OLE2 é preservado no Bronze, mas não processado).
- Gold é um conjunto inicial de indicadores.
- `documento/v1/como_rodar.md` ainda manda fazer `cd ~/Documentos/Projeto_TCC` (caminho antigo).
