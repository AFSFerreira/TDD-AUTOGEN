import logging
import subprocess
import sys
from typing import Optional
import os
from app.config import Config
from app.state import StateManager

def run_tests(state: Optional[StateManager] = None) -> str:
    """
    Executar testes pytest e retornar saída.
    
    Args:
        state: Estado atual do TDD (opcional)
    
    Returns:
        str: Saída completa do pytest
    """
    test_path = os.path.join(Config.WORKSPACE_PATH, Config.TEST_FILE)
    
    if not os.path.exists(test_path):
        msg = f"❌ Arquivo de teste não encontrado: {test_path}"
        logging.error(msg)
        return msg
    
    try:
        # Log do comando
        cmd = [sys.executable, "-m", "pytest", test_path, "-v"]
        logging.info("⚡ Executando testes...")
        logging.debug(f"🔧 Comando: {' '.join(cmd)}")
        
        # Executar pytest com verbose
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False  # Não levantar erro se testes falharem
        )
        
        logging.debug(f"📊 Processo finalizado: código {process.returncode}")
        
        # Combinar stdout e stderr
        output = process.stdout or ""
        if process.stderr:
            output += "\n" + process.stderr
        
        # Detectar status
        if state:
            has_passed = "passed" in output.lower()
            has_failures = "failed" in output.lower() or "error" in output.lower()
            
            if has_passed and not has_failures:
                state.update(status="passed")
                logging.info("=" * 60)
                logging.info("✅ Todos os testes passaram!")
                logging.info("=" * 60)
            else:
                state.update(status="failed")
                logging.warning("=" * 60)
                logging.warning("❌ Alguns testes falharam")
                logging.warning("=" * 60)
        
        return output
    
    except subprocess.SubprocessError as e:
        msg = f"Erro ao executar pytest: {str(e)}"
        logging.error(msg)
        return msg
    
    except Exception as e:
        msg = f"Erro inesperado: {str(e)}"
        logging.error(msg)
        return msg

def create_empty_implementation() -> None:
    """Criar arquivo de implementação vazio para fase RED"""
    path = os.path.join(Config.WORKSPACE_PATH, f"{Config.IMPLEMENTATION_MODULE}.py")
    logging.info("🔧 Criando arquivo de implementação vazio...")
    
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Arquivo vazio - implementação virá na fase GREEN\n")
    
    logging.info(f"✅ Arquivo vazio criado em: {path}")
    logging.debug("📝 Conteúdo: arquivo Python vazio para fase RED")
