# platform-self-service

Self-service da plataforma via **IssueOps**: os times pedem pelo GitHub, a plataforma valida e
executa na hora, e todo o acompanhamento fica na issue. Sem fila e sem portal.

## Dois níveis de controle

| Pedido | Quem pede | Como | Aprovação |
|---|---|---|---|
| **Sigla ou produto novo** | Tech lead ou PO | PR em [`catalogo/siglas.yaml`](catalogo/siglas.yaml) | **Sim**: revisão da plataforma (CODEOWNERS) |
| **Golden path novo** (ex.: Go) | Time dono do template | Template na org + PR em [`catalogo/golden-paths.yaml`](catalogo/golden-paths.yaml) | **Sim**: revisão da plataforma (CODEOWNERS) |
| **Serviço novo** numa sigla/produto do catálogo | Maintainer (tech lead) do time dono | Issue **Novo serviço** | **Não**: validou, criou |

A governança fica no que é estrutural e raro (sigla, produto, times, golden paths). O dia a dia não depende
de alguém aprovar no meio de centenas de notificações.

## Pedir um serviço

1. **Issues → New issue → Novo serviço**: sigla, produto, nome da aplicação, time, golden path
   e o `AB#` do Azure Boards. Sigla, produto, time e golden path são listas do catálogo; só o
   nome da aplicação é livre.
2. O repositório se chama **`<sigla>-<produto>-<aplicação>`** (ex.: `crt-credito-autorizador`).
3. A validação roda na hora:
   - sigla no catálogo, produto da sigla e time do produto (o Issue Form não filtra uma lista
     pela outra, então a validação confere a combinação e diz quais são as opções válidas);
   - golden path no catálogo, com o template existente na org;
   - nome da aplicação no padrão, sem repetir a sigla ou o produto, e repositório inexistente;
   - **quem pediu é maintainer do time** (senão o pedido é fechado como não autorizado);
   - `AB#` no formato do Azure Boards.
4. Com erro, o bot comenta o que corrigir e marca `pedido-invalido`; **editar a issue**
   revalida. Válido, o repositório é criado, o **time é mencionado** e a issue é fechada com
   `concluido`.

O mesmo pedido pode vir por **Actions → selfservice → Run workflow** (`operacao` + `dados` em
JSON). É a entrada para automações e para um portal IDP no futuro.

## O que o novo serviço recebe

1. Repositório criado a partir do **template do golden path escolhido** (não é fork: histórico
   limpo e a visibilidade da org) e personalizado pelo script do próprio template (veja
   [Golden path novo](#golden-path-novo)).
2. Commit inicial com o `AB#` (vínculo com o Azure Boards), branches `main` e `develop`, e
   `develop` como padrão.
3. **Custom properties** `sigla`, `produto`, `time` e `golden-path`, que servem de alvo para
   rulesets e políticas da organização.
4. Acesso de escrita para o time, que também é o CODEOWNER.
5. Ruleset [`rulesets/gitflow.json`](rulesets/gitflow.json): `main` e `develop` só via PR, sem
   force push e sem deleção.
6. Topics `golden-path`, `sigla-<sigla>` e `produto-<produto>`.

A execução é **idempotente**: se algo falhar no meio, o "Re-run failed jobs" retoma de onde
parou, sem duplicar nada.

## Como funciona

```
issue (label = operação)  ─┐
                           ├─▶ selfservice.yaml: validar ─▶ aprovar ─▶ executar
workflow_dispatch          ─┘        │                       │            │
                                     └─ scripts/cli.py ──────┴────────────┘
                                          └─ selfservice/operacoes/<operação>.py
```

O workflow é **genérico** e não sabe nada de "novo serviço". Cada operação é um módulo Python
com formulário, validação, autorização e execução, coberto por testes
([`tests/`](tests/)). O mesmo código gera o Issue Form e lê as respostas, então rótulo e parser
nunca divergem.

### Adicionar uma operação

1. Crie `scripts/selfservice/operacoes/<operação>.py` (o contrato está em
   [`operacoes/__init__.py`](scripts/selfservice/operacoes/__init__.py)) e registre em
   `OPERACOES`.
2. `python3 scripts/cli.py formularios` gera o Issue Form.
3. Escreva os testes. O workflow `catalogo` roda os testes e confere se os formulários estão
   em dia.

Nenhum YAML muda. A aprovação é por operação: o environment `aprovacao-<operação>` com ou sem
required reviewers.

## Sigla ou produto novo

1. PR em `catalogo/siglas.yaml` (sigla → produtos → times).
2. No mesmo PR, `python3 scripts/cli.py formularios` atualiza as opções dos formulários.
3. O workflow `catalogo` valida a estrutura, os testes e os formulários.
4. A plataforma revisa e faz o merge. Na fase 2, o mesmo catálogo alimenta o onboarding no
   GitOps (namespaces e AppProject do Argo CD por sigla/produto).

## Golden path novo

O self-service não sabe nada de linguagem. Cada golden path é um **repositório template** da
org, mantido por quem é dono dele, e uma entrada em
[`catalogo/golden-paths.yaml`](catalogo/golden-paths.yaml):

```yaml
golden_paths:
  go:
    nome: Go
    descricao: API REST em Go com contrato OpenAPI primeiro
    template: platform-go-boilerplate
    primeiro_passo: Comece pelo contrato em `api/openapi.yaml`.
```

Contrato com o template:

- O repositório é marcado como **template** na org.
- Se o template tiver o script executável **`.golden-path/personalizar`**, o self-service roda
  esse script na raiz do repositório gerado, **sem nenhum token no ambiente**, com o pedido em
  `GP_ORG`, `GP_NOME`, `GP_SIGLA`, `GP_PRODUTO`, `GP_APLICACAO`, `GP_TIME` e `GP_DESCRICAO`.
  Depois apaga `.golden-path/` e publica. Sem o script, o repositório é publicado como veio.
- O template prova no próprio CI que continua personalizável (veja o `golden-path.yaml` do
  `platform-java-boilerplate`).

No PR do catálogo, `python3 scripts/cli.py formularios` adiciona a opção ao formulário.

## Configuração da organização

**Times:** `plataforma` (dona dos repos da plataforma) e os times de produto. Quem pede precisa
ser **maintainer** do time.

**Custom properties** (org → Settings → Custom properties): `sigla`, `produto`, `time` e
`golden-path`, do tipo texto. Em linha de comando, com um owner da org:

```bash
gh api -X PATCH orgs/<org>/properties/schema --input - <<'EOF'
{"properties": [
  {"property_name": "sigla",   "value_type": "string", "description": "Sigla do sistema"},
  {"property_name": "produto", "value_type": "string", "description": "Produto da sigla"},
  {"property_name": "time",    "value_type": "string", "description": "Time dono"},
  {"property_name": "golden-path", "value_type": "string", "description": "Golden path de origem"}
]}
EOF
```

**Labels** neste repo: `novo-servico` (uma por operação), `pedido-invalido` e `concluido`.

**Environments** neste repo:

- `scaffold`: guarda a chave da App; restrito à branch `main`.
- `aprovacao-<operação>`: gate de aprovação, sem secrets. É criado no primeiro uso, sem
  reviewers (segue direto). Para exigir aprovação, adicione required reviewers.

**GitHub App da plataforma**, instalada na org com acesso a todos os repositórios:

| Tipo | Permissão | Acesso |
|---|---|---|
| Repositório | Administration | Read and write |
| Repositório | Contents | Read and write |
| Repositório | Custom properties | Read and write |
| Repositório | Workflows | Read and write |
| Repositório | Metadata | Read-only |
| Organização | Members | Read-only |

**Credenciais da App:**

- Variável `PLATFORM_APP_ID` (org): o App ID. É público, não é segredo.
- Secret `PLATFORM_APP_PRIVATE_KEY` no **environment `scaffold`**: o conteúdo do `.pem`. Não
  use um secret de org visível para todos os repos, porque qualquer workflow da org
  conseguiria emitir um token de administrador.
- Opcional: variável `NEW_REPO_VISIBILITY` (`public`, `internal` ou `private`). O padrão é
  `public`.

```bash
gh variable set PLATFORM_APP_ID --org <org> --visibility all --body "<APP_ID>"
gh secret set PLATFORM_APP_PRIVATE_KEY --repo <org>/platform-self-service --env scaffold < chave.pem
```

Depois de cadastrar, apague o `.pem` local. Para rotacionar, gere uma chave nova na App,
atualize o secret e revogue a antiga.

## Em produção (GitHub Enterprise)

| POC (org Free) | Enterprise |
|---|---|
| Repos públicos | Serviços `private` ou `internal` (a confirmar); repos da plataforma `internal`, para todos abrirem pedidos e lerem a esteira |
| Times criados à mão | Times sincronizados com grupos do IdP; tech leads como maintainers |
| Ruleset por repositório | Rulesets da org mirando as custom properties (ex.: `sigla`), sem lista de repos |
| Criar repo pela UI é possível | "Members can create repositories" desligado: a App é o único caminho |
| Uma App para validar e criar | Duas Apps: leitura (validação) e escrita (criação); chave sob custódia no Delinea |
| Notificação pelo GitHub | Também no canal do Teams do time |
