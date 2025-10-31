import re
import logging
from typing import Dict, List, Optional
from autogen import AssistantAgent  # type: ignore
from app.config import Config
from app.state import StateManager

REVIEWER_SYSTEM_MESSAGE = """
Você é o Revisor de Código e Analista de Testes (Reviewer).
Suas responsabilidades:

1. Análise de Falhas:
   - Analisar saída de testes que falharam
   - Identificar a causa raiz das falhas
   - Fornecer feedback claro para o Developer

2. Review de Código:
   - Verificar qualidade do código
   - Sugerir melhorias de clareza e eficiência
   - Garantir conformidade com PEP8
   - Identificar oportunidades de refatoração

Para análise de falhas, forneça:
- Lista de testes que falharam
- Causa raiz de cada falha
- Sugestões específicas de correção

Para review de código bem-sucedido:
- Se o código estiver bom: responda "TERMINATE"
- Se houver melhorias: liste sugestões específicas

Seja preciso e direto em seu feedback.
"""

def extract_test_results(output: str) -> Dict[str, List[str]]:
    """
    Extrair resultados detalhados dos testes da saída do pytest.
    
    Returns:
        Dict com listas de testes que passaram e falharam
    """
    results: Dict[str, List[str]] = {
        "passed": [],
        "failed": [],
        "errors": []
    }
    
    # Procurar por resultados de teste no formato pytest
    test_pattern = r"(PASSED|FAILED|ERROR)\s+(test_[\w\d_]+)"
    matches = re.finditer(test_pattern, output, re.IGNORECASE)
    
    for match in matches:
        status, test_name = match.groups()
        status = status.lower()
        if status == "passed":
            results["passed"].append(test_name)
        elif status == "failed":
            results["failed"].append(test_name)
        else:
            results["errors"].append(test_name)
    
    return results

def analyze_failures(output: str, state: Optional[StateManager] = None) -> str:
    """
    Analisar saída de teste com falha e gerar feedback.
    
    Args:
        output: Saída do pytest
        state: Estado atual do TDD (opcional)
    
    Returns:
        str: Feedback formatado para o Developer
    """
    logging.info("=" * 60)
    logging.info("🔍 FASE 4 (TDD): Analisando resultados dos testes")
    logging.info("=" * 60)
    
    if not output:
        logging.error("❌ Nenhuma saída de teste fornecida")
        return "Erro: Nenhuma saída de teste fornecida"
        
    logging.info("📊 Iniciando análise detalhada dos resultados...")
    
    # Extrair resultados
    logging.info("🔍 Extraindo resultados dos testes...")
    results = extract_test_results(output)
    
    # Gerar relatório
    logging.info("📝 Gerando relatório detalhado...")
    feedback = []
    feedback.append("=" * 40)
    feedback.append("📊 RELATÓRIO DE TESTES")
    feedback.append("=" * 40)
    
    # Sumário
    n_passed = len(results["passed"])
    n_failed = len(results["failed"])
    n_errors = len(results["errors"])
    total = n_passed + n_failed + n_errors
    
    feedback.append(f"Total de testes: {total}")
    feedback.append(f"✅ Passaram: {n_passed}")
    if n_failed > 0:
        feedback.append(f"❌ Falharam: {n_failed}")
    if n_errors > 0:
        feedback.append(f"⚠️ Erros: {n_errors}")
    
    # Detalhes das falhas
    if n_failed > 0 or n_errors > 0:
        feedback.append("\nDetalhes das Falhas:")
        for test in results["failed"]:
            feedback.append(f"❌ {test}")
        for test in results["errors"]:
            feedback.append(f"⚠️ {test}")
        
        # Extrair mensagens de erro específicas
        error_pattern = r"(test_[\w\d_]+).*?\n(.*?)(?=\n\n|$)"
        error_matches = re.finditer(error_pattern, output, re.DOTALL)
        
        feedback.append("\nCausas das Falhas:")
        for match in error_matches:
            test_name, error_msg = match.groups()
            if test_name in (results["failed"] + results["errors"]):
                feedback.append(f"- {test_name}:")
                feedback.append(f"  {error_msg.strip()}")
    
    # Atualizar estado se fornecido
    if state:
        status = "failed" if (n_failed > 0 or n_errors > 0) else "passed"
        logging.info(f"📌 Atualizando estado: status = {status}")
        state.update(status=status)
    
    logging.info("✓ Análise de testes concluída")
    if n_failed > 0 or n_errors > 0:
        logging.warning("⚠️ Falhas detectadas - feedback gerado para correção")
    else:
        logging.info("✅ Todos os testes passaram")
    
    return "\n".join(feedback)

def get_agent() -> AssistantAgent:
    """Retorna uma instância do Agente Revisor"""
    return AssistantAgent(
        name="Reviewer",
        system_message=REVIEWER_SYSTEM_MESSAGE,
        llm_config=Config.get_llm_config(),
    )
