# platform-self-service

Porta de entrada self-service da plataforma, sem portal: pedidos de novos serviços e
onboarding de produtos.

## Dois fluxos, dois níveis de controle

| Pedido | Quem pede | Como | Aprovação |
|---|---|---|---|
| **Produto novo** | Tech lead ou PO | PR em [`catalogo/produtos.yaml`](catalogo/produtos.yaml) | **Sim**: revisão do time plataforma (CODEOWNERS) |
| **Serviço novo** num produto do catálogo | Maintainer (tech lead) do time dono | Issue **Novo serviço** | **Não**: validou, criou (configurável, veja abaixo) |

A governança fica no que é estrutural (produto, times, dono). O dia a dia flui sem fila.

## Pedir um serviço

1. **Issues → New issue → Novo serviço**: nome, produto e time (listas vindas do catálogo) e o
   `AB#` do Azure Boards.
2. O workflow `scaffold-service` valida na hora:
   - nome no padrão `<produto>-<nome>`, sem prefixo reservado e sem repositório existente;
   - produto no catálogo e time pertencente ao produto;
   - **quem pediu é maintainer do time** (senão o pedido é fechado como não autorizado);
   - `AB#` no formato do Azure Boards.
3. Se houver erro, o bot comenta o que corrigir e marca `pedido-invalido`. Ao **editar a
   issue**, a validação roda de novo.
4. Se estiver válido, o repositório é criado e o **time é mencionado** na issue (todos os
   membros são notificados).

Também dá para disparar em **Actions → scaffold-service → Run workflow**: é a mesma entrada que
um portal IDP ou uma automação do Azure Boards usariam no futuro.

## Onboarding de produto

1. PR adicionando o produto em `catalogo/produtos.yaml` (times e `system`).
2. No mesmo PR, `python3 scripts/render_form.py` para atualizar as opções do formulário.
3. O workflow `catalogo` valida a estrutura, os testes e se o formulário está em dia.
4. A plataforma revisa e faz o merge. Na fase 2, o mesmo catálogo alimenta o onboarding no
   GitOps (`gitops-<produto>`, AppProject do Argo CD, namespaces).

## O que o scaffold faz

`validar` → `aprovar` → `criar`

1. Cria `<nome>` a partir do `platform-java-boilerplate`.
2. Personaliza artifactId, pacote Java, classe principal, time e `system` (`scripts/rename_service.py`).
3. Commita com o `AB#` (vínculo com o Azure Boards), cria `main` e `develop` e define `develop` como padrão.
4. Dá acesso de escrita ao time, que também é o CODEOWNER.
5. Aplica o ruleset `rulesets/gitflow.json`: `main` e `develop` só via PR, sem force push e sem deleção.

### Aprovação (modelo A ou B)

O job `aprovar` usa o environment **`aprovacao`**:

- **Sem required reviewers (padrão):** pedido válido segue direto.
- **Com required reviewers** (Settings → Environments → aprovacao → Required reviewers →
  time `plataforma`): todo pedido válido aguarda aprovação. Os reviewers são notificados pelo
  GitHub e o registro de quem aprovou fica no run.

Liga e desliga sem mudar código.

## Configuração da organization

**Times:** `plataforma` (dona dos repos da plataforma) e os times de produto. Quem pede
serviços precisa ser **maintainer** do time.

**Labels** neste repo: `novo-servico`, `pedido-invalido` e `servico-criado`.

**Environments** neste repo, ambos restritos à branch `main`:

- `scaffold`: guarda a chave da App.
- `aprovacao`: gate de aprovação, sem secrets.

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
- Secret `PLATFORM_APP_PRIVATE_KEY` no **environment `scaffold`**: o conteúdo do `.pem`.
  Só os jobs desse environment, na `main`, geram tokens. Não use um secret de org visível para
  todos os repos, porque qualquer workflow da org conseguiria emitir um token de administrador.
- Opcional: variável `NEW_REPO_VISIBILITY` (`public`, `internal` ou `private`). O padrão é `public`.

```bash
gh variable set PLATFORM_APP_ID --org gerffeson-lab --visibility all --body "<APP_ID>"
gh secret set PLATFORM_APP_PRIVATE_KEY --repo gerffeson-lab/platform-self-service \
  --env scaffold < caminho/da-chave.pem
```

Depois de cadastrar, apague o `.pem` local. Para rotacionar, gere uma chave nova na App,
atualize o secret e revogue a antiga.

## No GitHub Enterprise do banco

| POC | Banco |
|---|---|
| Repos públicos | `internal` (todos da enterprise abrem pedidos) |
| Times criados à mão; maintainer = quem criou | Times sincronizados com o IdP; tech leads como maintainers |
| Notificação pelo GitHub | Também no canal do Teams do time (app GitHub for Teams ou passo no workflow) |
| `AB#` validado só no formato | Consulta ao Azure Boards para confirmar que o work item existe |
| Uma App para validar e criar | Duas Apps: uma só de leitura (validação) e outra de escrita (criação) |
