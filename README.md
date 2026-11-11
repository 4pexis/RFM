# RFM — Roblox Farm Manager

Central desktop (Windows 10/11) para **organizar e acompanhar** registros de contas Roblox,
jogos, tarefas, progresso, sessões locais e produtividade.

Python · PySide6 · SQLAlchemy · Alembic · SQLite (com caminho pronto para PostgreSQL)

> **O que o RFM é — e o que não é.** É uma ferramenta de gestão e monitoramento: você registra,
> o painel consolida. Ele **não** contém exploits, injeção de código, bypass de anticheat,
> automação de jogabilidade nem abertura de múltiplas instâncias por contorno do cliente, e
> **não pede nem armazena senhas, cookies ou tokens** do Roblox.

## Começando

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1   # cria .venv e instala dependências
.\run.bat                                                    # abre o aplicativo
```

Ou manualmente: `.venv\Scripts\python.exe -m app.main`.

No primeiro início o banco `data\rfm.db` é criado, as migrações são aplicadas e os 12 jogos
iniciais entram no catálogo. Requer Python 3.12 ou superior.

Para ver o aplicativo cheio antes de cadastrar seus dados, gere dados **fictícios** em uma pasta separada:

```powershell
$env:RFM_DATA_DIR = "$PWD\data_demo"
.venv\Scripts\python.exe scripts\seed_demo.py 500
.venv\Scripts\python.exe -m app.main
```

## Telas

| Tela | O que faz |
|---|---|
| **Dashboard** | 8 indicadores e 5 gráficos (contas por jogo, status, atividade diária, produtividade semanal, progresso por jogo), com atualização automática |
| **Contas** | Cadastro, pesquisa, filtros por jogo/status/categoria, agrupamento, histórico, importação e exportação CSV |
| **Jogos** | Catálogo, objetivos por jogo, status da integração, abrir a experiência pelo link oficial |
| **Sessões** | Detecta clientes Roblox abertos, mede duração/CPU/memória, sinaliza ociosidade, associação manual a conta e jogo, sessões manuais |
| **Tarefas** | Tarefas por conta/jogo com prioridade, status, fila ordenada e histórico |
| **Progresso** | Registros datados de nível, itens, conquistas, objetivos e estatísticas |
| **Relatórios** | Tempo de operação e produtividade por conta ou jogo, auditoria, exportação CSV |
| **Monitoramento** | CPU, RAM, disco, processos acompanhados e alertas configuráveis |
| **Configurações** | Intervalos, limites de alerta, backups, perfil de acesso e PIN |

### Importação de contas (CSV)

Separador `,` ou `;`. Só `username` é obrigatório; usuários já existentes são atualizados.

```csv
username,roblox_user_id,category,level,status,tags,notes,games
conta_01,123456,Lote A,120,Ativa,"main,vip",,Blox Fruits|Fisch
```

Também são aceitos os cabeçalhos `usuario`, `categoria`, `nivel`, `observacoes` e `jogos`.

### Sessões: como funciona

O RFM lista os processos do sistema pelo nome do executável (`RobloxPlayerBeta.exe`, configurável)
e lê apenas contadores públicos de CPU e memória. Funciona igualmente com clientes abertos à mão.

- Um processo não revela qual conta está logada, então a associação **conta ↔ sessão é manual**.
- "Ociosa" significa CPU abaixo do limite pelo tempo configurado — um indício de desconexão ou
  travamento, não uma certeza.
- "Abrir no Roblox" usa o link oficial `roblox://experiences/start?placeId=…` com a conta que
  estiver logada no aplicativo.
- "Encerrar acompanhamento" fecha só o registro; o RFM nunca encerra o jogo.
- Quantas sessões cabem ao mesmo tempo depende do computador e das regras do Roblox, não do RFM.

## Arquitetura

```
app/
  main.py                 ponto de entrada (GUI ou --headless)
  core/                   config, eventos, logs, segurança, bootstrap
  database/               conexão, modelos, repositórios, migrações Alembic, cópia entre bancos
  managers/               regras de negócio: contas, jogos, sessões, tarefas, progresso,
                          relatórios, configurações, plugins
  game_modules/           um pacote por jogo (interface comum em base.py)
  services/               monitoramento de hardware, backup, agendador
  workers/                fila administrativa com prioridade, tarefas periódicas
  ui/                     janela principal, tema e uma pasta por tela
tests/  scripts/  assets/
```

A interface só conversa com os *managers*; os *managers* usam repositórios; nenhuma tela
executa SQL. Serviços em segundo plano publicam eventos e a interface se atualiza a partir deles.

**Tabelas:** `accounts`, `games`, `account_games`, `tasks`, `sessions`, `progress_records`,
`activity_logs`, `system_settings`, `game_integrations`, `hardware_metrics`.

### Adicionar um jogo

Pela tela **Jogos → Novo jogo** (acompanhamento manual), ou criando um módulo — o núcleo não muda:

```python
# app/game_modules/meu_jogo/__init__.py
from app.game_modules.base import K_LEVEL, K_STAT, GameModule, Objective

class MeuJogoModule(GameModule):
    slug = "meu_jogo"
    name = "Meu Jogo"
    experience_id = "123456789"      # Place ID
    category = "RPG"
    icon = "sword"                   # nomes disponíveis em app/ui/icons.py
    OBJECTIVES = (
        Objective("level", "Nível", K_LEVEL, max_value=500),
        Objective("gold", "Ouro", K_STAT),
    )

MODULE = MeuJogoModule()
```

O módulo é descoberto no próximo início. Os métodos de `GameModule` (validar progresso e tarefas,
estatísticas, `fetch_available_data` para integrações oficiais) podem ser sobrescritos.

> Os Place IDs dos 12 jogos iniciais foram preenchidos de memória — confira-os na tela Jogos
> (é o número em `roblox.com/games/<número>`) antes de usar "Abrir no Roblox".

## Segurança

- Validação de todos os campos; texto com aparência de cookie `.ROBLOSECURITY` é recusado.
- Consultas parametrizadas via SQLAlchemy (sem SQL montado por concatenação).
- Auditoria em `activity_logs` e logs JSON em `data\logs\rfm.jsonl`.
- Perfis: Administrador, Operador (cria/edita) e Somente leitura; PIN opcional com hash PBKDF2,
  guardado cifrado pela DPAPI do Windows.
- Backup automático do SQLite, com retenção e restauração (uma cópia do estado atual é salva antes).

## Banco de dados e PostgreSQL

SQLite é o padrão e basta para um computador. Para migrar:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-postgres.txt
.venv\Scripts\python.exe scripts\migrate_sqlite_to_postgres.py "postgresql+psycopg://usuario:senha@host:5432/rfm"
```

Depois defina `RFM_DATABASE_URL` no `.env`. Novas migrações:

```powershell
.venv\Scripts\alembic.exe revision --autogenerate -m "descricao"
.venv\Scripts\alembic.exe upgrade head
```

No PostgreSQL o backup integrado fica desativado — use `pg_dump`.

## Testes e executável

```powershell
.venv\Scripts\python.exe -m pytest                              # 36 testes
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1  # gera dist\RFM\RFM.exe
```

O executável guarda os dados em `%LOCALAPPDATA%\RFM`.

## Estado das fases

| Fase | Situação |
|---|---|
| 1 — Estrutura, SQLite, interface, contas | Pronta |
| 2 — Jogos, tarefas, progresso | Pronta |
| 3 — Sessões e hardware | Pronta |
| 4 — Módulos de jogo | 12 módulos de acompanhamento (objetivos e validações); sem integrações externas |
| 5 — PostgreSQL, VPS, backups | Backups e cópia SQLite→PostgreSQL prontos; a cópia foi testada entre bancos SQLite, **não contra um PostgreSQL real**. Sincronização com VPS e painel remoto **não implementados** — o `Dockerfile` roda apenas os serviços em modo `--headless` |
| 6 — Instalador e documentação | Script do PyInstaller incluído, **ainda não executado**; sem instalador (MSI/Inno Setup) |
