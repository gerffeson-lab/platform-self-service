import subprocess
import sys
import unittest

from helpers import CAT, ROOT

from selfservice import forms
from selfservice.operacoes import OPERACOES


class FormsTest(unittest.TestCase):
    def test_render_e_parse_usam_os_mesmos_rotulos(self):
        form = OPERACOES["novo-servico"].formulario(CAT)
        yaml = forms.render(form)
        self.assertIn('- "crt-credito"', yaml)
        corpo = "\n\n".join(f"### {c.label}\n\nvalor-{c.id}" for c in form.campos)
        campos = forms.parse(corpo, form)
        self.assertEqual(campos["aplicacao"], "valor-aplicacao")
        self.assertNotIn("confirmacao", campos)

    def test_sem_resposta_vira_vazio(self):
        form = OPERACOES["novo-servico"].formulario(CAT)
        self.assertEqual(forms.parse("### Descrição\n\n_No response_\n", form), {"descricao": ""})

    def test_formularios_do_repo_em_dia(self):
        proc = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "cli.py"), "formularios", "--check"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
