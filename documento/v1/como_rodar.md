# Como rodar o projeto

Guia prático, passo a passo. Para entender **o que** cada parte faz, veja `explicacao_implementacao.md`.

Todos os comandos partem da raiz do projeto:

```bash
cd ~/Documentos/Projeto_TCC
```

---

## Resumo rápido (quem já configurou uma vez)

```bash
docker compose up -d                                          # 1. banco + broker
.venv/bin/uvicorn app.main:app --app-dir api --port 8010      # 2. API (deixe o terminal aberto)
# 3. abra http://localhost:8010/
```

---

## 1. Pré-requisitos

| Ferramenta | Para quê | Verificar |
| --- | --- | --- |
| Python 3.12 | API, orquestrador, testes | `python3 --version` |
| Docker + Docker Compose | PostgreSQL e Mosquitto | `docker compose version` |
| Git | versionamento | `git --version` |
| (hardware) 3 × ESP32 + OLED SSD1306 I²C | nós de processamento | — |
| (hardware) `esptool` e `mpremote` | gravar o firmware | instalados no passo 7 |

O computador e os ESP32 precisam estar **na mesma rede Wi-Fi**.

---

## 2. Configuração inicial (uma vez só)

### 2.1 Ambiente Python

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

`requirements.txt` tem só o necessário para rodar; `requirements-dev.txt` acrescenta pytest e mpy-cross.

### 2.2 Arquivo `.env`

```bash
cp .env.example .env
```

Abra o `.env` e troque `PG_PASSWORD=troque-esta-senha` por uma senha sua. As demais variáveis já vêm
com valores que funcionam (a lista completa está na seção 3 de `explicacao_implementacao.md`).

> O `.env` não vai para o git. Se ele já existe na sua máquina, não precisa refazer.

**Atenção:** a senha é gravada no banco na **primeira** vez que o container do Postgres sobe. Se você
trocar a senha depois, ou recria o volume (seção 10.4) ou altera a senha dentro do Postgres.

---

## 3. Subir o banco e o broker

```bash
docker compose up -d
docker compose ps
```

Saída esperada: `tcc-postgres` (healthy) e `tcc-mosquitto` rodando.

| Serviço | Porta no computador |
| --- | --- |
| PostgreSQL | 5434 |
| Mosquitto (MQTT) | 1884 |

As portas são diferentes das padrão (5432/1883) para não conflitar com outros projetos. Para mudar,
edite `PG_PORTA` / `MQTT_PORTA` no `.env` e rode `docker compose up -d` de novo.

---

## 4. Rodar a API

```bash
.venv/bin/uvicorn app.main:app --app-dir api --port 8010
```

Deixe esse terminal aberto. Na inicialização a API:
1. aplica as migrações do banco (cria as tabelas na primeira vez);
2. conecta ao Mosquitto — o log mostra `Conectado ao broker localhost:1884`;
3. recupera execuções que estavam em andamento, se houver.

| Endereço | O que é |
| --- | --- |
| http://localhost:8010/ | painel web |
| http://localhost:8010/docs | documentação interativa (dá para testar todas as rotas) |

Para acessar o painel de outro dispositivo da rede, use `--host 0.0.0.0`.

> Use **um único processo** (não passe `--workers`): o orquestrador vive dentro da API.

Para parar: `Ctrl+C` no terminal da API.

---

## 5. Colocar uma planilha no Bronze

Escolha **uma** das opções.

**a) Pelo painel:** em *Fontes (Bronze)*, escolha o ano e clique em **Coletar ano** — ou envie um XLSX
em **Enviar**.

**b) Pela linha de comando — coletar da Prefeitura:**

```bash
# ver os anos disponíveis na página oficial
curl -s localhost:8010/fontes/itbi-sp/anos

# baixar um ano
curl -s -X POST localhost:8010/coletas/itbi-sp -H 'content-type: application/json' -d '{"ano": 2026}'

# acompanhar (troque 1 pelo coleta_id retornado)
curl -s localhost:8010/coletas/1
```

Para baixar **todos** os anos: `-d '{"todos": true}'` (são ~21 arquivos de 20–45 MB).

**c) Pela linha de comando — enviar um arquivo que você já tem:**

```bash
curl -s -F "arquivo=@$HOME/Downloads/GUIAS DE ITBI PAGAS (27082026) XLS.xlsx" -F ano_fonte=2026 \
     localhost:8010/arquivos
```

Depois, liste os arquivos para descobrir o `id`:

```bash
curl -s localhost:8010/arquivos
```

Os arquivos ficam em `data/bronze/itbi_sp/<ano>/`. Enviar o mesmo arquivo duas vezes não duplica
(o sistema compara o SHA-256).

---

## 6. Primeira execução sem hardware (nós simulados)

Serve para ver o sistema inteiro funcionando antes de ligar os ESP32.

### 6.1 Ligar nós simulados

Em **outro terminal** (um por nó):

```bash
.venv/bin/python scripts/simulador_no.py --id sim-01
.venv/bin/python scripts/simulador_no.py --id sim-02
.venv/bin/python scripts/simulador_no.py --id sim-03
```

Eles aparecem no painel em *Nós* com a etiqueta `sim`. Para parar: `Ctrl+C`.

### 6.2 Iniciar a execução

**Pelo painel:** em *Nova execução*, escolha o arquivo, ano `2026`, mês `JAN`, limite `10`, marque
`sim-01` e clique em **Iniciar execução**.

**Pela linha de comando:**

```bash
curl -s -X POST localhost:8010/execucoes -H 'content-type: application/json' \
     -d '{"arquivo_id": 1, "ano": 2026, "mes": "JAN", "limite_registros": 10, "nos": ["sim-01"]}'
```

### 6.3 Acompanhar e consultar

```bash
curl -s localhost:8010/execucoes/exec-000001                 # status, progresso, lotes, eventos
curl -s localhost:8010/execucoes/exec-000001/registros       # bruto × tratado (Silver)
curl -s localhost:8010/execucoes/exec-000001/indicadores     # Gold
curl -s localhost:8010/execucoes/exec-000001/metricas        # tempos por nó
curl -s localhost:8010/nos                                    # nós conectados
```

A execução termina com `"status": "concluida"`.

### 6.4 Provocar falhas (opcional)

```bash
.venv/bin/python scripts/simulador_no.py --id sim-04 --cair-apos 3       # cai no meio do lote
.venv/bin/python scripts/simulador_no.py --id sim-05 --silenciar-apos 2  # para de responder
.venv/bin/python scripts/simulador_no.py --id sim-06 --duplicar          # respostas repetidas
```

Rode uma execução com um desses nós e um nó normal (ex.: `"nos": ["sim-04", "sim-01"]`) e veja no
painel os eventos `tentativa_expirada`, `reenvio` ou `resposta_duplicada`.

> Resultados de nós simulados ficam marcados como `simulado=true`. Não use-os como medição do TCC.

---

## 7. Preparar os ESP32 (uma vez por placa)

### 7.1 Montagem do OLED

| OLED SSD1306 | ESP32 |
| --- | --- |
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO 21 |
| SCL | GPIO 22 |

Endereço I²C padrão: `0x3C` (alguns módulos usam `0x3D`; ajuste em `config.py`).

### 7.2 Ferramentas

```bash
.venv/bin/pip install esptool mpremote
```

### 7.3 Gravar o MicroPython

Baixe o firmware **ESP32_GENERIC** (`.bin`) em https://micropython.org/download/ESP32_GENERIC/ e,
com a placa no USB:

```bash
.venv/bin/esptool.py --chip esp32 erase_flash
.venv/bin/esptool.py --chip esp32 write_flash -z 0x1000 ESP32_GENERIC-<versão>.bin
```

Se der erro de permissão na porta serial (`/dev/ttyUSB0`): `sudo usermod -aG dialout $USER` e faça
logout/login.

### 7.4 Bibliotecas no ESP32

A placa precisa de internet para isso, ou instale pelo computador (o `mpremote` baixa e copia):

```bash
.venv/bin/mpremote mip install umqtt.simple ssd1306
```

### 7.5 Configuração do nó

```bash
cp firmware/config_exemplo.py firmware/config.py
```

Edite `firmware/config.py`:

```python
WIFI_SSID = "nome-da-rede"
WIFI_SENHA = "senha-da-rede"
MQTT_HOST = "192.168.0.10"   # IP do computador (veja abaixo)
MQTT_PORTA = 1884
NO_ID = "esp32-01"           # esp32-01, esp32-02 ou esp32-03
```

Descobrir o IP do computador:

```bash
hostname -I | awk '{print $1}'
```

### 7.6 Copiar o firmware e reiniciar

```bash
.venv/bin/mpremote cp firmware/boot.py firmware/main.py firmware/regras.py firmware/tela.py firmware/config.py :
.venv/bin/mpremote reset
```

Para ver os logs do nó: `.venv/bin/mpremote repl` (sair com `Ctrl+]`).

O OLED deve mostrar `wifi...` → `conectando` → `disponivel` com `MQTT OK`.

### 7.7 Repetir para as outras placas

Mude apenas `NO_ID` em `firmware/config.py` (`esp32-02`, `esp32-03`) e repita o passo 7.6 com cada
placa conectada.

### 7.8 Liberar a porta no firewall (se houver)

```bash
sudo ufw allow 1884/tcp
```

---

## 8. Execução com os ESP32 físicos

1. Com a API rodando, confira se os nós aparecem:

   ```bash
   curl -s localhost:8010/nos
   ```

   Cada `esp32-0X` deve estar com `"estado": "disponivel"` e `"disponivel": true`.

2. **Primeira demonstração** — 10 registros em um nó:

   ```bash
   curl -s -X POST localhost:8010/execucoes -H 'content-type: application/json' \
        -d '{"arquivo_id": 1, "ano": 2026, "mes": "JAN", "limite_registros": 10, "nos": ["esp32-01"]}'
   ```

   O OLED deve avançar `REG 01/10` … `REG 10/10`, e a execução terminar em `concluida`.

3. **Três nós:**

   ```bash
   curl -s -X POST localhost:8010/execucoes -H 'content-type: application/json' \
        -d '{"arquivo_id": 1, "ano": 2026, "mes": "JAN", "limite_registros": 300,
             "nos": ["esp32-01", "esp32-02", "esp32-03"]}'
   ```

4. Guarde as métricas de cada execução:

   ```bash
   curl -s localhost:8010/execucoes/exec-00000X/metricas > metricas_exec-00000X.json
   ```

O roteiro completo do experimento (1, 2 e 3 nós, repetições, desligar um nó) está na seção 18 de
`explicacao_implementacao.md`.

---

## 9. Testes automatizados

```bash
.venv/bin/pytest -q
```

Resultado esperado: **55 passed**.

| Grupo | Precisa de |
| --- | --- |
| `test_regras.py`, `test_leitor.py` | nada |
| `test_integracao.py` | `docker compose up -d` (usa um banco separado `tcc_itbi_teste`; se os serviços estiverem parados, é pulado) |
| `test_micropython.py` | imagem Docker `micropython/unix` (`docker pull micropython/unix`); sem ela, é pulado |

Rodar só um grupo: `.venv/bin/pytest -q tests/test_regras.py`.

Regenerar as fixtures a partir das planilhas reais (se mudar as regras, revise a saída antes!):

```bash
.venv/bin/python scripts/extrair_fixtures.py --dir ~/Downloads
```

Conferir se o firmware compila para o ESP32:

```bash
for f in firmware/*.py; do .venv/bin/python -m mpy_cross -march=xtensawin "$f" -o /tmp/x.mpy && echo "ok $f"; done
```

---

## 10. Comandos úteis

### 10.1 Parar tudo

```bash
# API: Ctrl+C no terminal dela
docker compose stop          # para banco e broker (os dados continuam)
```

### 10.2 Consultar o banco direto

```bash
docker exec -it tcc-postgres psql -U tcc -d tcc_itbi
```

Consultas úteis:

```sql
SELECT id, status, total_esperado, criado_em FROM execucoes ORDER BY criado_em DESC;
SELECT no_id, count(*) FROM registros_silver WHERE execucao_id = 'exec-000001' GROUP BY no_id;
SELECT tipo, count(*) FROM eventos_execucao WHERE execucao_id = 'exec-000001' GROUP BY tipo;
SELECT * FROM silver_tipado WHERE execucao_id = 'exec-000001' LIMIT 10;
```

### 10.3 Ver as mensagens MQTT passando

```bash
docker exec -it tcc-mosquitto mosquitto_sub -p 1883 -t 'tcc/#' -v
```

(Dentro do container a porta é 1883; fora, 1884.)

### 10.4 Apagar o banco e começar do zero

```bash
docker compose down -v       # APAGA todas as tabelas e execuções
docker compose up -d
```

Os arquivos em `data/bronze/` **não** são apagados por esse comando. Depois de recriar o banco, envie
os arquivos de novo pela API para catalogá-los.

### 10.5 Retomar uma execução que falhou

```bash
curl -s -X POST localhost:8010/execucoes/exec-00000X/retomar
```

---

## 11. Problemas comuns

| Sintoma | Causa provável | O que fazer |
| --- | --- | --- |
| API não sobe: `connection refused` na porta 5434 | Postgres parado | `docker compose up -d` |
| API não sobe: `password authentication failed` | senha do `.env` diferente da usada ao criar o volume | voltar a senha antiga ou `docker compose down -v` (apaga dados) |
| `docker compose up` falha com porta em uso | outro serviço usa 5434/1884 | trocar `PG_PORTA`/`MQTT_PORTA` no `.env` |
| Painel mostra `broker: desconectado` | Mosquitto parado ou porta errada | `docker compose ps`; conferir `MQTT_PORTA` |
| Execução fica em `em_andamento` sem avançar | nenhum nó da execução está disponível | `curl localhost:8010/nos`; ligar os nós listados em `"nos"` |
| Execução fica em `preparando` | lendo a planilha (meses completos levam ~10 s) | aguardar; erros aparecem em `mensagem` |
| `422` ao criar execução | ano/mês não existe no arquivo | a mensagem lista as abas disponíveis |
| OLED fica em `wifi...` | SSID/senha errados ou rede 5 GHz | ESP32 só usa **2,4 GHz** |
| OLED fica em `conectando`/`reconectando` | IP/porta do broker errados ou firewall | conferir `MQTT_HOST`, `MQTT_PORTA=1884`, `sudo ufw allow 1884/tcp` |
| OLED apagado, mas o nó processa | fiação/endereço I²C | conferir SDA/SCL e `OLED_ENDERECO` (`0x3C`/`0x3D`) |
| `ImportError: no module named 'umqtt'` no ESP32 | bibliotecas não instaladas | `mpremote mip install umqtt.simple ssd1306` |
| Simulador recusa `--id esp32-01` | proteção para não se passar por nó físico | usar `sim-01`, `sim-02`… |
