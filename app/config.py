import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Paths e arquivos
    WORKSPACE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "workspace")
    TEST_FILE = "test_app.py"
    IMPLEMENTATION_MODULE = "app_code"
    
    # Configuração OpenAI
    OPENAI_API_KEY = os.getenv("OAI_API_KEY")
    if not OPENAI_API_KEY:
        raise ValueError("Chave de API (OAI_API_KEY) não encontrada. Configure no arquivo .env")
    
    # Configurações do fluxo TDD
    MAX_ITERATIONS = 5  # Máximo de tentativas de refatoração
    MAX_TEST_REGENERATIONS = 3  # Máximo de tentativas de regenerar testes
    
    # Logging
    LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
    LOG_LEVEL = logging.INFO
    
    @classmethod
    def setup_logging(cls) -> None:
        """Configurar logging formatado"""
        logging.basicConfig(
            level=cls.LOG_LEVEL,
            format=cls.LOG_FORMAT
        )
    
    @classmethod
    def get_llm_config(cls) -> Dict[str, Any]:
        """Retorna configuração do LLM para autogen"""
        return {
            "config_list": [{
                "model": "gpt-4o-mini",
                "api_key": cls.OPENAI_API_KEY,
            }],
            "cache_seed": 42,
            "temperature": 0.0,
        }

# Configurar logging
Config.setup_logging()

# Expor llm_config para compatibilidade com código existente
llm_config = Config.get_llm_config()
