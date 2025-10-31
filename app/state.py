from typing import Dict, Any, Optional
import logging
import os
from app.config import Config

class TDDState:
    """Estado do fluxo TDD"""
    def __init__(self, specification: str = "") -> None:
        self.specification: str = specification
        self.tests: str = ""
        self.code: str = ""
        self.feedback: str = ""
        self.status: str = ""
        self.iteration: int = 0
        self.test_phase: str = "red"
        self.previous_tests: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Converter estado para dicionário"""
        return {
            "specification": self.specification,
            "tests": self.tests,
            "code": self.code,
            "feedback": self.feedback,
            "status": self.status,
            "iteration": self.iteration,
            "test_phase": self.test_phase,
            "previous_tests": self.previous_tests
        }
    
    def update(self, updates: Dict[str, Any]) -> None:
        """Atualizar estado a partir de dicionário"""
        for key, value in updates.items():
            if hasattr(self, key):
                setattr(self, key, value)

class StateManager:
    """Gerencia o estado do fluxo TDD"""
    
    def __init__(self, specification: str):
        """Inicializar gerenciador de estado"""
        self.state = TDDState(specification)
        
        # Garantir workspace
        os.makedirs(Config.WORKSPACE_PATH, exist_ok=True)
    
    def update(self, **kwargs) -> None:
        """Atualizar estado com novos valores"""
        # Validar que as chaves são válidas para TDDState
        valid_keys = {'specification', 'tests', 'code', 'feedback', 
                     'status', 'iteration', 'test_phase', 'previous_tests'}
        
        # Filtrar apenas chaves válidas
        validated_updates = {k: v for k, v in kwargs.items() if k in valid_keys}
        
        if not validated_updates:
            logging.warning("⚠️ Nenhuma atualização válida fornecida")
            return
        
        # Atualizar estado com valores validados
        self.state.update(validated_updates)
        self._log_state_change(validated_updates)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obter valor do estado"""
        return getattr(self.state, key, default)
    
    def _log_state_change(self, changes: Dict[str, Any]) -> None:
        """Log de mudanças relevantes no estado"""
        relevant = {k: v for k, v in changes.items() 
                   if k in ['status', 'test_phase', 'iteration']}
        if relevant:
            logging.debug(f"Estado atualizado: {relevant}")
    
    def save_test_file(self, content: str) -> None:
        """Salvar arquivo de teste"""
        path = os.path.join(Config.WORKSPACE_PATH, Config.TEST_FILE)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logging.info(f"✅ Testes salvos em: {Config.TEST_FILE}")
    
    def save_implementation_file(self, content: str) -> None:
        """Salvar arquivo de implementação"""
        path = os.path.join(Config.WORKSPACE_PATH, f"{Config.IMPLEMENTATION_MODULE}.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logging.info(f"✅ Código salvo em: {Config.IMPLEMENTATION_MODULE}.py")
