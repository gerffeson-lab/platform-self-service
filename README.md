# platform-self-service

Porta de entrada self-service da plataforma, sem portal: pedidos de novos serviços via Issue Form.

## Como pedir um serviço

1. **Issues → New issue → Novo serviço**: nome, produto, time responsável e `AB#` do Azure Boards.
2. A plataforma revisa e aplica a label **`aprovado`**.
3. O workflow `scaffold-service` cria o repositório e responde na issue com o link.

Também dá para disparar direto em **Actions → scaffold-service → Run workflow**. É a mesma
entrada que um portal IDP ou uma automação do Azure Boards usariam no futuro.

## O que o scaffold faz

1. Valida o pedido (`scripts/parse_request.py`) e confere se o time existe na org.
2. Cria `<nome>` a partir do `platform-java-boilerplate`.
3. Personaliza artifactId, pacote Java, classe principal, time e produto (`scripts/rename_service.py`).
4. Commita com o `AB#` (vínculo com o Azure Boards), cria `main` e `develop`, e define `develop` como padrão.
5. Dá acesso de escrita ao time (que também é o CODEOWNER).
6. Aplica o ruleset `rulesets/gitflow.json`: `main` e `develop` só via PR, sem force push e sem deleção.

## Configuração da organization

**Times:** `plataforma` (dono do boilerplate e dos templates) e um time de produto para teste,
por exemplo `pagamentos`.

**Labels** neste repo: `novo-servico` e `aprovado`.

**GitHub App da plataforma** (Settings → Developer settings → GitHub Apps), instalada na org
com acesso a todos os repositórios:

| Tipo | Permissão | Acesso |
|---|---|---|
| Repositório | Administration | Read and write |
| Repositório | Contents | Read and write |
| Repositório | Workflows | Read and write |
| Repositório | Metadata | Read-only |
| Organização | Members | Read-only |

**Credenciais da App:**

- Variável `PLATFORM_APP_ID` (org): o App ID. É um identificador público, não um segredo.
- Secret `PLATFORM_APP_PRIVATE_KEY` no **environment `scaffold` deste repo**: o conteúdo do `.pem`.
  Assim, só o job de scaffold consegue gerar tokens. Restrinja o environment à branch `main`.
  Não use um secret de org visível para todos os repos, porque qualquer workflow da org
  conseguiria emitir um token de administrador.
- Opcional: variável `NEW_REPO_VISIBILITY` (`public`, `internal` ou `private`). O padrão é `public`.

```bash
gh variable set PLATFORM_APP_ID --org gerffeson-lab --visibility all --body "<APP_ID>"
gh secret set PLATFORM_APP_PRIVATE_KEY --repo gerffeson-lab/platform-self-service \
  --env scaffold < caminho/da-chave.pem
```

Depois de cadastrar, apague o `.pem` local. Para rotacionar, gere uma chave nova na App,
atualize o secret e revogue a antiga.
