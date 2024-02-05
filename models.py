from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from flask import Flask, jsonify
from flask_restful import Api, Resource
from pydantic import BaseModel
from sqlalchemy import Column, Float, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from gas_scrapper import GasDFPetrobraz


class CRUDError(Exception):
    """Exceção base para erros de CRUD."""


class GasolinaModel(declarative_base()):
    __tablename__ = "gasolina"

    id = Column(Integer, primary_key=True)
    preco_gas = Column(Float)


class TipoOperacao(Enum):
    """Enum para os tipos de operação CRUD."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


class GerenciadorDB:
    """Classe gerenciadora do banco de dados."""

    def __init__(self):
        self._engine = create_engine("sqlite:///./gas_scrapper/data/gas_db.sqlite3")
        self._sessionmaker = sessionmaker(bind=self._engine)

        # Cria as tabelas se ainda não existirem
        GasolinaModel.metadata.create_all(self._engine)

    def criar_sessao(self):
        """Cria uma nova sessão."""
        return self._sessionmaker()

    def executar_operacao(
        self, sessao, tipo_operacao: TipoOperacao, **kwargs: Any
    ) -> Any:
        """Executa a operação CRUD especificada."""
        operacao = self._get_operacao(tipo_operacao)
        try:
            return operacao(sessao, **kwargs)
        except Exception as e:
            raise CRUDError(e) from e

    def _get_operacao(self, tipo_operacao: TipoOperacao):
        """Retorna a função da operação CRUD específica."""
        operacoes = {
            TipoOperacao.CREATE: self._create,
            TipoOperacao.READ: self._read,
            TipoOperacao.UPDATE: self._update,
            TipoOperacao.DELETE: self._delete,
        }
        return operacoes[tipo_operacao]

    @staticmethod
    def _create(sessao, model: GasolinaModel) -> GasolinaModel:
        """Cria um novo registro no banco de dados."""
        sessao.add(model)
        sessao.commit()
        return model

    @staticmethod
    def _read(sessao, **kwargs: Any) -> Optional[GasolinaModel]:
        """Retorna um registro do banco de dados."""
        filtro = kwargs.get("filtro")
        return sessao.query(GasolinaModel).filter_by(**filtro).first()

    @staticmethod
    def _update(sessao, model: GasolinaModel) -> GasolinaModel:
        """Atualiza um registro no banco de dados."""
        sessao.merge(model)
        sessao.commit()
        return model

    @staticmethod
    def _delete(sessao, **kwargs: Any) -> None:
        """Exclui um registro do banco de dados."""
        filtro = kwargs.get("filtro")
        sessao.query(GasolinaModel).filter_by(**filtro).delete()
        sessao.commit()


class GasolinaManager:
    """Classe para gerenciar o preço da gasolina no banco de dados."""

    def __init__(self, db_manager: GerenciadorDB):
        self.db_manager = db_manager

    def atualizar_preco_gasolina(self, novo_preco: float) -> None:
        """Atualiza o preço da gasolina no banco de dados."""
        session = self.db_manager.criar_sessao()
        try:
            gasolina = self.db_manager.executar_operacao(
                session, TipoOperacao.READ, filtro={}
            )
            if gasolina:
                gasolina.preco_gas = novo_preco
                self.db_manager.executar_operacao(
                    session, TipoOperacao.UPDATE, model=gasolina
                )
            else:
                novo_model = GasolinaModel(preco_gas=novo_preco)
                self.db_manager.executar_operacao(
                    session, TipoOperacao.CREATE, model=novo_model
                )
        finally:
            session.close()

def run():
    db_manager = GerenciadorDB()
    gasolina_manager = GasolinaManager(db_manager)
    gas_att = GasDFPetrobraz().gas

    gasolina_manager.atualizar_preco_gasolina(gas_att)

if __name__ == "__main__":
    run()
