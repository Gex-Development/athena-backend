import re
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

PASTA = Path(__file__).resolve().parent.parent / "openapi"


def carregar(nome: str) -> dict:
    return yaml.safe_load((PASTA / nome).read_text(encoding="utf-8"))


def referencias(no) -> list[str]:
    if isinstance(no, dict):
        achadas = [no["$ref"]] if isinstance(no.get("$ref"), str) else []
        return achadas + [r for valor in no.values() for r in referencias(valor)]
    if isinstance(no, list):
        return [r for item in no for r in referencias(item)]
    return []


def test_schemas_dos_componentes_sao_json_schema_valido():
    componentes = carregar("componentes.yaml")

    for schema in componentes["schemas"].values():
        Draft202012Validator.check_schema(schema)


def test_referencias_internas_dos_componentes_existem():
    componentes = carregar("componentes.yaml")

    for ref in referencias(componentes):
        partes = re.fullmatch(r"#/(\w+)/(\w+)", ref)
        assert partes, ref
        secao, nome = partes.groups()
        assert nome in componentes[secao], ref


def test_motivo_incerto_sai_nulo_com_palpite_separado():
    classificacao = carregar("componentes.yaml")["schemas"]["Classificacao"]

    assert {"motivo", "provavel"} <= set(classificacao["required"])
    assert "null" in classificacao["properties"]["motivo"]["type"]
    assert "null" in classificacao["properties"]["provavel"]["type"]


def test_pedido_separa_base_da_oferta_do_valor_cobrado():
    pedido = carregar("componentes.yaml")["schemas"]["Pedido"]["properties"]

    assert {"valorSemTaxasUsd", "valorCobradoUsd"} <= set(pedido)
    assert "valorUsd" not in pedido
