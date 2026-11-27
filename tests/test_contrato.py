import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, ValidationError
from openapi_spec_validator import validate
from openapi_spec_validator.readers import read_from_filename
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from athena.api.app import app

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


def validador(schema: str) -> Draft202012Validator:
    recurso = Resource.from_contents(
        carregar("componentes.yaml"), default_specification=DRAFT202012
    )
    registro = Registry().with_resource("urn:componentes", recurso)
    alvo = {"$ref": f"urn:componentes#/components/schemas/{schema}"}
    return Draft202012Validator(alvo, registry=registro)


def operacoes_do_contrato() -> dict[tuple[str, str], dict]:
    operacoes = {}
    for caminho, item in carregar("openapi.yaml")["paths"].items():
        if "$ref" in item:
            arquivo, chave = item["$ref"].split("#/")
            item = carregar(arquivo)[chave]
        for metodo, operacao in item.items():
            if metodo in {"get", "post", "put", "delete", "patch"}:
                operacoes[(metodo.upper(), caminho)] = operacao
    return operacoes


def test_contrato_e_openapi_3_1_valido():
    spec, base_uri = read_from_filename(str(PASTA / "openapi.yaml"))

    validate(spec, base_uri=base_uri)


def test_x_implementada_bate_com_as_rotas_do_backend():
    no_backend = {
        (metodo.upper(), caminho.removeprefix("/v1"))
        for caminho, item in app.openapi()["paths"].items()
        if caminho.startswith("/v1/") or caminho == "/health"
        for metodo in item
    }
    assert len(no_backend) >= 8
    marcadas = {
        chave
        for chave, operacao in operacoes_do_contrato().items()
        if operacao.get("x-implementada") is True
    }

    assert marcadas == no_backend


def test_schemas_dos_componentes_sao_json_schema_valido():
    for schema in carregar("componentes.yaml")["components"]["schemas"].values():
        Draft202012Validator.check_schema(schema)


def test_referencias_internas_usam_components_e_existem():
    componentes = carregar("componentes.yaml")

    for ref in referencias(componentes):
        partes = re.fullmatch(r"#/components/(\w+)/(\w+)", ref)
        assert partes, ref
        secao, nome = partes.groups()
        assert nome in componentes["components"][secao], ref


def test_motivo_so_vem_preenchido_com_confianca_alta():
    classificacao = validador("Classificacao")
    base = {"provavel": None, "versaoCatalogo": "v3.4"}

    classificacao.validate({**base, "motivo": "rastreio", "confianca": "alta"})
    classificacao.validate(
        {**base, "motivo": None, "provavel": "rastreio", "confianca": "a_confirmar"}
    )
    for confianca in ("a_confirmar", "indefinido"):
        with pytest.raises(ValidationError):
            classificacao.validate({**base, "motivo": "rastreio", "confianca": confianca})
    with pytest.raises(ValidationError):
        classificacao.validate({**base, "motivo": None, "confianca": "alta"})


def test_pedido_separa_base_da_oferta_do_valor_cobrado():
    pedido = carregar("componentes.yaml")["components"]["schemas"]["Pedido"]["properties"]

    assert {"valorSemTaxasUsd", "valorCobradoUsd"} <= set(pedido)
    assert "valorUsd" not in pedido


def test_so_painel_e_indicadores_ficam_provisorios():
    operacoes = operacoes_do_contrato()
    provisorias = {
        chave
        for chave, operacao in operacoes.items()
        if operacao.get("x-estabilidade") == "provisorio"
    }

    assert provisorias == {("GET", "/chatwoot/conversas/{id}"), ("GET", "/agente/indicadores")}
    assert all("x-estabilidade" in operacao for operacao in operacoes.values())


def test_regras_do_controle_ficam_travadas():
    operacoes = operacoes_do_contrato()
    motivo = operacoes[("PUT", "/agente/motivos/{codigo}")]
    corpo = motivo["requestBody"]["content"]["application/json"]["schema"]
    cortes = operacoes[("PUT", "/agente/cortes")]
    evento = carregar("componentes.yaml")["components"]["schemas"]["Evento"]

    assert "justificativa" in corpo["required"]
    assert corpo["properties"]["justificativa"]["minLength"] == 10
    assert "bloqueado_por_regra" in motivo["responses"]["409"]["description"]
    assert "corte_invalido" in cortes["responses"]["409"]["description"]
    assert cortes["requestBody"]["content"]["application/json"]["schema"]["minItems"] == 1
    for chave in (("PUT", "/agente/motivos/{codigo}"), ("POST", "/agente/parada")):
        assert "controle_alterado" in operacoes[chave]["description"]
    assert "controle_alterado" in cortes["description"]
    assert "null" in evento["properties"]["conversaId"]["type"]
