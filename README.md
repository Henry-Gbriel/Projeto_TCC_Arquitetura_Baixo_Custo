# TCC — Framework distribuído de baixo custo (ITBI-SP)

Implementação da especificação `documento/v1/document.md`. Uma API em FastAPI coleta e preserva as
planilhas de ITBI (Bronze), distribui os registros por MQTT para três ESP32 com MicroPython,
que **aplicam as regras de limpeza**, e grava as respostas no PostgreSQL (Silver), de onde saem os
indicadores (Gold).

```
api/app/
  config.py        variáveis de ambiente (.env)
  canonico.py      nomes canônicos das 28 colunas (estrutura, não limpeza)
  leitor.py        leitura XLSX em streaming, cabeçalhos, serialização para JSON sem limpar valores
  bronze.py        preservação do arquivo original + catálogo (SHA-256, versões)
  coleta.py        descoberta dos anos na página oficial e download com redirecionamentos explícitos
  execucoes.py     seleção de abas, leitura e montagem de lotes de 10
  orquestrador.py  MQTT, distribuição, timeouts, reenvio, reatribuição, idempotência, recuperação
  gold.py          indicadores, métricas, consulta pública do preço do m² e status do cluster
  auth.py          login do painel (usuários no Postgres, scrypt, cookie assinado)
  main.py          rotas da API; serve o build do front-end em /
api/migracoes/    migrações Alembic do PostgreSQL (SQL puro; alembic.ini na raiz)
frontend/          site "quadra" (React + Vite + TypeScript + Recharts), telas de documento/v1/project-fron-end
firmware/          MicroPython do ESP32: main.py, regras.py, tela.py (OLED), config_exemplo.py
scripts/           extrair_fixtures.py, simulador_no.py (testes sem hardware)
tests/             regras, leitor, integração (Postgres+Mosquitto), MicroPython real via Docker
```

## Como rodar

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env            # ajuste PG_PASSWORD
docker compose up -d            # PostgreSQL :5434 e Mosquitto :1884 (portas do .env)
.venv/bin/uvicorn app.main:app --app-dir api --host 0.0.0.0 --port 8010
```

Front-end (uma vez, e de novo a cada mudança em `frontend/`):

```bash
cd frontend && npm install && npm run build      # gera frontend/dist, servido pela API em /
.venv/bin/python scripts/criar_usuario.py admin   # usuário do painel (ou ADMIN_USUARIO/ADMIN_SENHA no .env)
```

Use **um único worker**: o orquestrador vive no processo da API. Site: <http://localhost:8010/>,
documentação interativa: <http://localhost:8010/docs>. As migrações (Alembic) rodam na inicialização;
pela linha de comando: `.venv/bin/alembic upgrade head` / `.venv/bin/alembic current`.

Fluxo típico:

1. `POST /coletas/itbi-sp {"ano": 2026}` (ou `{"todos": true}`) baixa para `data/bronze/`, sem processar.
   Ou `POST /arquivos` com um XLSX. `GET /fontes/itbi-sp/anos` mostra anos e versões já preservadas.
2. `POST /execucoes {"arquivo_id": 1, "ano": 2026, "mes": "JAN", "limite_registros": 10, "nos": ["esp32-01"]}`
   responde na hora com o ID; acompanhe em `GET /execucoes/{id}`.
3. `GET /execucoes/{id}/registros` (Silver, lado a lado com o bruto), `/indicadores` (Gold), `/metricas`.
4. `GET /nos` mostra conectividade e lote atual de cada nó.

## Front-end e painel de controle

| Rota | Tela | Acesso |
| --- | --- | --- |
| `#/` | Página inicial, com um exemplo calculado ao vivo | público |
| `#/consulta` → `#/resultado` | Busca com filtros e resultado (preço do m², variação, série trimestral, tipos, ruas, CSV) | público |
| `#/cluster` | Sala das máquinas: nós, fila, vazão e log (`GET /cluster`, a cada 2 s) | público |
| `#/sobre` | Componentes, tecnologias, equipe (textos em `frontend/src/conteudo.ts`) | público |
| `#/login` → `#/painel` | Coleta, upload, execuções, lotes, indicadores, métricas, registros | **login** |

As rotas que alteram dados ou mostram a operação (`/arquivos`, `/fontes`, `/coletas`, `/execucoes/*`,
`/gold/atualizar`) exigem a sessão do painel (cookie HttpOnly assinado; defina `SESSAO_SEGREDO` no `.env`
para a sessão sobreviver a reinícios). `/consulta/*`, `/cluster` e `/nos` são abertas e só leem.

A consulta usa a view materializada `gold_transacoes` (migração 0003): compras e vendas deduplicadas
entre execuções, área ≥ 10 m² e preço entre R$ 500 e R$ 60.000/m². Ela é recalculada sozinha quando uma
execução conclui (ou pelo botão "Recalcular Gold" no painel). O período conta a partir da transação mais
recente do recorte, e a variação em 12 meses só aparece com pelo menos 10 transações em cada ano.

Desenvolvimento do front com recarga automática: `cd frontend && npm run dev` (porta 5173, chamadas
encaminhadas para a API em :8010).

## Firmware (ESP32 + SSD1306)

1. Grave o MicroPython no ESP32 (`esptool.py --chip esp32 erase_flash` e `write_flash -z 0x1000 <firmware>.bin`).
2. Instale as dependências no nó: `mpremote mip install umqtt.simple ssd1306`.
3. Copie `firmware/config_exemplo.py` para `firmware/config.py` (não versionado), preencha Wi-Fi, IP do
   computador, `MQTT_PORTA=1884` e `NO_ID` (`esp32-01`, `esp32-02`, `esp32-03`).
4. `mpremote cp firmware/boot.py firmware/main.py firmware/regras.py firmware/tela.py firmware/config.py :`
   e `mpremote reset`.

OLED: `NO 02 MQTT OK / LOTE 014 / REG 04/10 / ERROS 01` + estado (conectando, disponível, recebendo,
processando, publicando, reconectando). Ligação padrão: SDA=21, SCL=22, endereço 0x3C. O Mosquitto do
compose aceita conexões anônimas (rede de laboratório); veja `infra/mosquitto/mosquitto.conf` para senha.

## Contrato MQTT v1

| Tópico | Sentido | QoS |
| --- | --- | --- |
| `tcc/nos/{no_id}/tarefa` | orquestrador → nó, 1 registro por mensagem, sem retain | 1 |
| `tcc/resultados` | nó → orquestrador | 1 |
| `tcc/nos/{no_id}/estado` | nó → orquestrador, retido; LWT `offline` | 1 |

A tarefa leva `dados` (28 colunas como texto, sem limpeza) e `tipos` (tipo da célula de origem:
`n` número, `s` texto, `d` data). É assim que o nó sabe que um CEP `5662000` veio de uma célula numérica
e pode recuperar o zero inicial; um CEP textual incompleto é sinalizado. A resposta traz
`dados_tratados`, `erros` (`campo`, `motivo`, `valor_original`), `duracao_us`, `mem_livre` e `versao_regras`.

## Decisões de processamento (lado ESP32)

Regras em `firmware/regras.py`, derivadas de `clean_sp()`. Diferenças documentadas no próprio arquivo:
`numero` remove `.0` só no final; CEP só recebe zero inicial se veio numérico; valores monetários saem
como decimal canônico em texto (`R$ 605.994,39` → `605994.39`) e viram `numeric` no Postgres; datas
aceitam ISO e `DD/MM/AAAA`; `acc_iptu` inteiro; toda falha de conversão vira `null` + erro.
`data_transacao` **não** é corrigida pelo ano da aba.

Leitura (lado computador): em 2019 as duas colunas `ACC (IPTU)` são resolvidas por posição (a primeira
é `descricao_padrao`; o código de referência invertia); `Descrição do pardão (IPTU)` de FEV-2026 é
reconhecida; a 29ª coluna sem cabeçalho é ignorada se vazia, e qualquer valor nela vira erro de leitura
(guardado em `registros_origem.extras`, nunca descartado em silêncio).

## Recuperação e idempotência

- Lote: `pendente → atribuido → processando → concluido | falhou`; um lote ativo por nó.
- O próximo registro só é enviado depois que a resposta anterior foi persistida.
- `registros_silver` é único por (execução, registro de origem): repetições de QoS 1 e respostas atrasadas
  viram evento `resposta_duplicada` e nunca sobrescrevem o resultado aceito.
- Sem resposta em `TIMEOUT_REGISTRO_S`: reenvia até `MAX_REENVIOS`; depois a tentativa expira e o lote
  volta a `pendente` para outro nó continuar do primeiro registro faltante (`MAX_TENTATIVAS_LOTE`).
- Nó offline (LWT ou silêncio > `NO_OFFLINE_S`): seus lotes voltam a `pendente`.
- Reinício da API: lotes ativos voltam a `pendente` (ou `concluido`, se já completos) a partir do banco.
- Execução `concluida` só quando a contagem de respostas únicas persistidas = total esperado.
  `POST /execucoes/{id}/retomar` reabre lotes que falharam.

## Testes

```bash
.venv/bin/pytest -q                       # regras, leitor, integração e MicroPython (se Docker)
.venv/bin/python scripts/extrair_fixtures.py --dir ~/Downloads   # regenera fixtures reais
```

`tests/test_integracao.py` usa um banco separado (`tcc_itbi_teste`) e um prefixo MQTT aleatório com nós
**simulados** (`scripts/simulador_no.py`, que roda o mesmo `regras.py`). Os resultados simulados ficam
marcados como `simulado=true` no Silver. O simulador é ferramenta de teste, não substitui os ESP32.

## Pendências reais

- **Teste físico nos ESP32 ainda não foi feito**: o firmware compila (`mpy-cross -march=xtensawin`) e as
  regras rodam no MicroPython (port Unix) com saída idêntica ao CPython, mas Wi-Fi, `umqtt`, OLED, memória
  e tempos só serão medidos no hardware.
- Arquivos `.xls` legados (formato OLE2) seriam preservados, mas o leitor aceita apenas XLSX; os links
  2019–2021 da página atual entregam XLSX.
- Gold é um conjunto inicial; a definição fina vem após o primeiro ciclo completo.
