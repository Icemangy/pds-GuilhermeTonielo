"""Testes da API: python -m unittest discover -s backend -v.

O banco fica em uma pasta temporaria. O arquivo instance/petshop.db do
projeto nunca e usado, alterado ou apagado pelos testes.
"""

import importlib.util
import io
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from flask import Flask


BACKEND = Path(__file__).resolve().parent


class ApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pasta = tempfile.TemporaryDirectory(prefix="petshop_test_")
        cls.addClassCleanup(pasta.cleanup)

        class FlaskDeTeste(Flask):
            def __init__(self, *args, **kwargs):
                # A configuracao precisa acontecer antes de SQLAlchemy(app).
                kwargs["instance_path"] = pasta.name
                kwargs["root_path"] = str(BACKEND)
                super().__init__(*args, **kwargs)

        spec = importlib.util.spec_from_file_location(
            "petshop_app_em_teste", BACKEND / "app.py"
        )
        cls.modulo = importlib.util.module_from_spec(spec)
        with patch("flask.Flask", FlaskDeTeste):
            spec.loader.exec_module(cls.modulo)

        cls.app = cls.modulo.app
        cls.db = cls.modulo.db
        cls.app.config["TESTING"] = True
        cls.addClassCleanup(cls.fechar_banco)

        with cls.app.app_context():
            banco = Path(cls.db.engine.url.database).resolve()
            if banco.parent != Path(pasta.name).resolve():
                raise AssertionError("O banco dos testes deve ficar na pasta temporaria")

    @classmethod
    def fechar_banco(cls):
        with cls.app.app_context():
            cls.db.session.remove()
            cls.db.engine.dispose()

    def executar_seed(self):
        # criar_banco.py importa o mesmo app ligado ao banco temporario.
        with patch.dict(sys.modules, {"app": self.modulo}):
            with redirect_stdout(io.StringIO()):
                runpy.run_path(str(BACKEND / "criar_banco.py"), run_name="__main__")

    def setUp(self):
        with self.app.app_context():
            self.db.drop_all()
            self.db.create_all()
        self.executar_seed()
        self.client = self.app.test_client()
        self.pet_valido = {
            "nome": "Bidu",
            "especie": "cachorro",
            "idade": 2,
            "dono_id": 1,
        }

    def assert_erro(self, resposta, status, mensagem):
        self.assertEqual(resposta.status_code, status)
        self.assertEqual(resposta.get_json(), {"erro": mensagem})

    def test_listar_pets_inclui_idade_e_nome_do_dono(self):
        resposta = self.client.get("/pets")
        self.assertEqual(resposta.status_code, 200)
        pets = resposta.get_json()
        self.assertEqual(len(pets), 5)
        campos = {"id", "nome", "especie", "idade", "dono_id", "dono_nome"}
        for pet in pets:
            self.assertEqual(set(pet), campos)
        self.assertIn(
            {
                "id": 1,
                "nome": "Rex",
                "especie": "cachorro",
                "idade": 4,
                "dono_id": 1,
                "dono_nome": "Ana Paula Ribeiro",
            },
            pets,
        )

    def test_filtrar_pets_por_dono(self):
        for filtro, ids in (("1", {1, 2}), ("3", {4, 5}), ("999", set())):
            with self.subTest(dono_id=filtro):
                resposta = self.client.get("/pets", query_string={"dono_id": filtro})
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual({pet["id"] for pet in resposta.get_json()}, ids)

    def test_filtro_vazio_equivale_a_listar_todos(self):
        resposta = self.client.get("/pets?dono_id=")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json(), self.client.get("/pets").get_json())

    def test_filtro_invalido_retorna_400(self):
        for filtro in ("abc", "1.5", "1 OR 1=1"):
            with self.subTest(dono_id=filtro):
                resposta = self.client.get("/pets", query_string={"dono_id": filtro})
                self.assert_erro(resposta, 400, "Informe um dono_id inteiro")

    def test_buscar_pet_e_retornar_404_quando_nao_existe(self):
        resposta = self.client.get("/pets/1")
        self.assertEqual(resposta.status_code, 200)
        esperado = next(pet for pet in self.client.get("/pets").get_json() if pet["id"] == 1)
        self.assertEqual(resposta.get_json(), esperado)
        self.assert_erro(self.client.get("/pets/999"), 404, "Pet nao encontrado")

    def test_cadastrar_pet_persiste_todos_os_campos(self):
        resposta = self.client.post("/pets", json=self.pet_valido)
        self.assertEqual(resposta.status_code, 201)
        pet = resposta.get_json()
        self.assertIsInstance(pet["id"], int)
        self.assertEqual(
            pet,
            dict(self.pet_valido, id=pet["id"], dono_nome="Ana Paula Ribeiro"),
        )
        self.assertEqual(self.client.get(f"/pets/{pet['id']}").get_json(), pet)
        self.assertEqual(len(self.client.get("/pets").get_json()), 6)

    def test_post_e_put_exigem_os_quatro_campos(self):
        corpos = [{}]
        for campo in self.pet_valido:
            corpos.append({chave: valor for chave, valor in self.pet_valido.items() if chave != campo})
        for metodo, url in (("POST", "/pets"), ("PUT", "/pets/1")):
            for corpo in corpos:
                with self.subTest(metodo=metodo, corpo=corpo):
                    resposta = self.client.open(url, method=metodo, json=corpo)
                    self.assert_erro(resposta, 400, "Informe nome, especie, idade e dono_id")

    def test_dono_inexistente_nao_cria_nem_altera_pet(self):
        antes = self.client.get("/pets").get_json()
        corpo = dict(self.pet_valido, dono_id=999)
        for metodo, url in (("POST", "/pets"), ("PUT", "/pets/1")):
            with self.subTest(metodo=metodo):
                resposta = self.client.open(url, method=metodo, json=corpo)
                self.assert_erro(resposta, 404, "Dono nao encontrado")
                self.assertEqual(self.client.get("/pets").get_json(), antes)

    def test_atualizar_pet_persiste_nova_idade_e_novo_dono(self):
        corpo = {"nome": "Rex Junior", "especie": "cachorro", "idade": 5, "dono_id": 2}
        resposta = self.client.put("/pets/1", json=corpo)
        self.assertEqual(resposta.status_code, 200)
        esperado = dict(corpo, id=1, dono_nome="Bruno Cardoso")
        self.assertEqual(resposta.get_json(), esperado)
        self.assertEqual(self.client.get("/pets/1").get_json(), esperado)
        self.assertEqual(
            {pet["id"] for pet in self.client.get("/pets?dono_id=2").get_json()},
            {1, 3},
        )

    def test_atualizar_pet_inexistente_retorna_404(self):
        resposta = self.client.put("/pets/999", json=self.pet_valido)
        self.assert_erro(resposta, 404, "Pet nao encontrado")

    def test_remover_pet_e_retornar_404_depois(self):
        resposta = self.client.delete("/pets/1")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json(), {"mensagem": "Pet removido com sucesso"})
        self.assertEqual(len(self.client.get("/pets").get_json()), 4)
        self.assert_erro(self.client.get("/pets/1"), 404, "Pet nao encontrado")
        self.assert_erro(self.client.delete("/pets/1"), 404, "Pet nao encontrado")

    def test_crud_de_donos(self):
        resposta = self.client.get("/donos")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.get_json()), 3)
        resposta = self.client.post("/donos", json={"nome": "Teste", "telefone": "45999990000"})
        self.assertEqual(resposta.status_code, 201)
        dono = resposta.get_json()
        self.assertEqual(set(dono), {"id", "nome", "telefone"})
        url = f"/donos/{dono['id']}"
        self.assertEqual(self.client.get(url).get_json(), dono)

        corpo = {"nome": "Nome atualizado", "telefone": "45999991111"}
        resposta = self.client.put(url, json=corpo)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json(), dict(corpo, id=dono["id"]))
        self.assertEqual(self.client.get(url).get_json(), resposta.get_json())

        resposta = self.client.delete(url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json(), {"mensagem": "Dono removido com sucesso"})
        self.assert_erro(self.client.get(url), 404, "Dono nao encontrado")
        self.assert_erro(self.client.put(url, json=corpo), 404, "Dono nao encontrado")
        self.assert_erro(self.client.delete(url), 404, "Dono nao encontrado")

    def test_dono_com_pets_so_pode_ser_removido_apos_desvincular_pets(self):
        donos_antes = self.client.get("/donos").get_json()
        pets_antes = self.client.get("/pets").get_json()
        resposta = self.client.delete("/donos/1")
        self.assert_erro(resposta, 409, "Dono possui pets cadastrados")
        self.assertEqual(self.client.get("/donos").get_json(), donos_antes)
        self.assertEqual(self.client.get("/pets").get_json(), pets_antes)

        # Transfere Rex e remove Mimi, deixando Ana sem pets associados.
        rex = self.client.get("/pets/1").get_json()
        corpo = {campo: rex[campo] for campo in ("nome", "especie", "idade")}
        corpo["dono_id"] = 2
        self.assertEqual(self.client.put("/pets/1", json=corpo).status_code, 200)
        self.assertEqual(self.client.delete("/pets/2").status_code, 200)

        resposta = self.client.delete("/donos/1")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json(), {"mensagem": "Dono removido com sucesso"})
        self.assert_erro(self.client.get("/donos/1"), 404, "Dono nao encontrado")
        self.assertEqual(len(self.client.get("/pets").get_json()), 4)
        self.assertEqual(self.client.get("/pets/1").get_json()["dono_nome"], "Bruno Cardoso")

    def test_validacao_dos_campos_de_donos(self):
        for metodo, url in (("POST", "/donos"), ("PUT", "/donos/1")):
            for corpo in ({}, {"nome": "Teste"}, {"telefone": "45999990000"}):
                with self.subTest(metodo=metodo, corpo=corpo):
                    resposta = self.client.open(url, method=metodo, json=corpo)
                    self.assert_erro(resposta, 400, "Informe nome e telefone")

    def test_seed_e_idempotente_e_preserva_dados_originais(self):
        donos = self.client.get("/donos").get_json()
        pets = self.client.get("/pets").get_json()
        self.assertEqual(
            [(dono["nome"], dono["telefone"]) for dono in donos],
            [
                ("Ana Paula Ribeiro", "45999110001"),
                ("Bruno Cardoso", "45999110002"),
                ("Carla Meneghel", "45999110003"),
            ],
        )
        self.assertEqual(
            [(pet["nome"], pet["especie"], pet["idade"], pet["dono_id"]) for pet in pets],
            [
                ("Rex", "cachorro", 4, 1),
                ("Mimi", "gato", 2, 1),
                ("Thor", "cachorro", 7, 2),
                ("Nina", "gato", 1, 3),
                ("Pingo", "passaro", 3, 3),
            ],
        )
        self.executar_seed()
        self.assertEqual(self.client.get("/donos").get_json(), donos)
        self.assertEqual(self.client.get("/pets").get_json(), pets)

    def test_seed_nao_apaga_edicoes_nem_novos_registros(self):
        self.client.put("/pets/1", json=dict(self.pet_valido, idade=8))
        self.client.post("/pets", json=self.pet_valido)
        self.client.post("/donos", json={"nome": "Novo dono", "telefone": "45999992222"})
        donos = self.client.get("/donos").get_json()
        pets = self.client.get("/pets").get_json()
        self.executar_seed()
        self.assertEqual(self.client.get("/donos").get_json(), donos)
        self.assertEqual(self.client.get("/pets").get_json(), pets)


if __name__ == "__main__":
    unittest.main()
