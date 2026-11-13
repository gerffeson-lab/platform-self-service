"""Registro das operações de self-service.

Para adicionar uma operação, crie um módulo aqui com:
    ID                                  id da operação (também é a label da issue)
    formulario(cat) -> Formulario       campos do Issue Form (gerado a partir do catálogo)
    validar(campos, cat) -> (pedido, erros)   regras sem rede; pedido só com valores seguros
    checar(pedido, gh) -> erros         regras que consultam o GitHub
    autorizar(pedido, gh, solicitante) -> erros   quem pode pedir
    resumo(pedido) -> str               linha para o comentário de pedido válido
    executar(pedido, gh, cfg) -> str    executa (idempotente) e devolve a mensagem final
e registre em OPERACOES. Depois: `python3 scripts/cli.py formularios` e testes em tests/."""

from . import novo_servico

OPERACOES = {m.ID: m for m in (novo_servico,)}
