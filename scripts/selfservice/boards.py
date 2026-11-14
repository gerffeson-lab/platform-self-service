"""Azure Boards (Azure DevOps): só o necessário para conferir o work item do pedido.

O ID de work item é único na organização do Azure DevOps inteira, então a consulta não
precisa do projeto. Só stdlib, para rodar em qualquer runner (inclusive sem acesso ao PyPI)."""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = "7.1"
CAMPOS = "System.Title,System.State,System.TeamProject,System.WorkItemType"


class BoardsError(RuntimeError):
    pass


class Boards:
    def __init__(self, org: str, pat: str, urlopen=urllib.request.urlopen):
        self.org, self._urlopen = org, urlopen
        self._auth = "Basic " + base64.b64encode(f":{pat}".encode()).decode()

    def work_item(self, numero: int) -> dict | None:
        """Campos do work item, ou None se não existe (ou o token não tem acesso a ele)."""
        url = (f"https://dev.azure.com/{urllib.parse.quote(self.org)}/_apis/wit/workitems/{numero}"
               f"?fields={CAMPOS}&api-version={API_VERSION}")
        req = urllib.request.Request(url, headers={"Authorization": self._auth, "Accept": "application/json"})
        try:
            with self._urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())["fields"]
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            # 401/403: token inválido ou sem permissão; 203 com HTML também indica token inválido
            raise BoardsError(f"Azure DevOps respondeu HTTP {exc.code} ao consultar o work item {numero}.") from None
        except (json.JSONDecodeError, KeyError):
            raise BoardsError("Resposta inesperada do Azure DevOps (token inválido?).") from None
