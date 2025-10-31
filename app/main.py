import os
import time
import logging
import autogen  # type: ignore
from typing import Dict, Any, List, Optional

from app.config import Config
from app.state import StateManager, TDDState
from app.agents.planner import get_agent as get_planner
from app.agents.tester import get_agent as get_tester, generate_tests
from app.agents.developer import get_agent as get_developer, generate_code
from app.agents.reviewer import get_agent as get_reviewer, analyze_failures
from app.agents.runner import run_tests, create_empty_implementation

class TDDOrchestrator:
    """Orquestrador do fluxo TDD usando autogen"""
    
    def _log_group_message(self, sender_name: str, receiver_name: str, message: str) -> None:
        """Log detalhado de cada mensagem do chat em grupo"""
        if not message or not message.strip():
            logging.debug(f"⚪ Mensagem vazia: {sender_name} → {receiver_name}")
            return
        
        # Determinar tipo e ícone da mensagem
        msg_type = "📝"  # Texto normal
        if "```python" in message:
            msg_type = "💻"  # Código Python
        elif message.startswith(">>>>>>>> EXECUTING"):
            msg_type = "⚡"  # Execução
        elif "exitcode:" in message:
            msg_type = "🔄"  # Resultado de execução
        elif message.startswith("Plano de TDD:"):
            msg_type = "📋"  # Plano
        
        # Formatar e truncar mensagem para log
        msg_preview = message.replace("\n", "\\n")[:100]
        if len(message) > 100:
            msg_preview += "..."
        
        # Log da interação com tipo de mensagem
        logging.info("-" * 80)  # Linha separadora
        logging.info(f"{msg_type} {sender_name} → {receiver_name}: {msg_preview}")
        
        # Log de métricas em modo debug
        chars = len(message)
        lines = len(message.split("\n"))
        logging.debug(f"📊 Métricas: {chars} caracteres, {lines} linhas")
    
    def __init__(self):
        """Inicializar orquestrador TDD"""
        self.workspace_dir = Config.WORKSPACE_PATH
        os.makedirs(self.workspace_dir, exist_ok=True)
        
        # Inicializar agentes
        self.planner = get_planner()
        self.tester = get_tester()
        self.developer = get_developer()
        self.reviewer = get_reviewer()
        
        # Configurar executor
        self.executor = self._setup_executor()
        
        # Lista de agentes e configuração do chat
        self.agents = [
            self.executor,
            self.planner,
            self.tester,
            self.developer,
            self.reviewer
        ]
        
        # Configurar função de log para cada agente
        for agent in self.agents:
            # Salvar referências originais
            agent._original_receive = agent.receive
            agent._original_send = agent.send
            orchestrator = self  # Referência para usar nas closures
            
            def make_receive_with_log(agent):
                def receive_with_log(self, message: Dict[str, Any], sender: Any, *args, **kwargs) -> None:
                    try:
                        sender_name = getattr(sender, "name", "unknown")
                        content = message.get("content", "")
                        orchestrator._log_group_message(sender_name, agent.name, content)
                    except Exception as e:
                        logging.debug(f"Erro ao fazer log de mensagem recebida: {e}")
                    return agent._original_receive(message, sender, *args, **kwargs)
                return receive_with_log
            
            def make_send_with_log(agent):
                def send_with_log(self, message: Dict[str, Any], recipient: Any, *args, **kwargs) -> None:
                    try:
                        recipient_name = getattr(recipient, "name", "unknown")
                        content = message.get("content", "")
                        orchestrator._log_group_message(agent.name, recipient_name, content)
                    except Exception as e:
                        logging.debug(f"Erro ao fazer log de mensagem enviada: {e}")
                    return agent._original_send(message, recipient, *args, **kwargs)
                return send_with_log
            
            # Substituir métodos com versões que fazem logging
            try:
                agent.receive = make_receive_with_log(agent).__get__(agent)
                agent.send = make_send_with_log(agent).__get__(agent)
                logging.debug(f"✓ Logging configurado para agente: {agent.name}")
            except Exception as e:
                logging.error(f"❌ Erro ao configurar logging para agente {agent.name}: {e}")
        
        # Configurar chat em grupo
        self.groupchat = autogen.GroupChat(
            agents=self.agents,
            messages=[],
            max_round=50
        )
        
        # Manager do chat em grupo
        self.manager = autogen.GroupChatManager(
            groupchat=self.groupchat,
            llm_config=Config.get_llm_config(),
            system_message=self._get_manager_prompt()
        )
    
    def _setup_executor(self) -> autogen.UserProxyAgent:
        """Configurar agente executor"""
        return autogen.UserProxyAgent(
            name="Executor",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=10,
            is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
            code_execution_config={
                "work_dir": self.workspace_dir,
                "use_docker": False,
            },
            system_message="""
            Você é o Executor. Você executa o código Python e os testes, reportando resultados.
            
            Seu papel:
            1. Após o Tester criar testes, chame o Developer
            2. Após o Developer criar/modificar código, execute os testes
            3. Para executar testes, use:
            ```sh
            pytest workspace/test_app.py -v
            ```
            
            Reporte o resultado completo dos testes para o grupo.
            """
        )
    
    def _get_manager_prompt(self) -> str:
        """Retorna prompt do manager com fluxo TDD"""
        return """
        Você é o Orquestrador. Gerencie o fluxo TDD entre os agentes.
        
        Siga estritamente este fluxo:
        1. Comece com o Planner para definir o plano
        2. Chame o Tester para criar o primeiro teste
        3. Após o Executor criar arquivo de teste, chame o Developer
        4. Após o Executor criar arquivo de código, chame o Executor novamente
        5. Analise resultado dos testes:
           - Se FALHAREM: Developer corrige (volte ao passo 4)
           - Se PASSAREM: Reviewer analisa
        6. Analise resposta do Reviewer:
           - Se sugerir mudanças: Developer refatora (volte ao passo 4)
           - Se "TERMINATE": Trabalho concluído
        
        Não desvie deste fluxo.
        """
    
    def run(self, specification: str) -> TDDState:
        """
        Executar fluxo TDD completo.
        
        Args:
            specification: Especificação do que deve ser implementado
        
        Returns:
            TDDState: Estado final do ciclo TDD
        """
        logging.info("=" * 60)
        logging.info("INICIANDO WORKFLOW TDD")
        logging.info("=" * 60)
        logging.info(f"\n📋 Especificação:\n{specification}\n")
        
        # Inicializar estado
        state = StateManager(specification)
        
        # Limpar workspace
        if os.path.exists(self.workspace_dir):
            for f in os.listdir(self.workspace_dir):
                if f.endswith('.py'):
                    os.remove(os.path.join(self.workspace_dir, f))
        
        # Executar fluxo TDD
        for iteration in range(1, Config.MAX_ITERATIONS + 1):
            state.update(iteration=iteration)
            
            try:
                # Iniciar chat com o grupo
                logging.info("=" * 60)
                logging.info(f"💬 INICIANDO ITERAÇÃO {iteration}")
                logging.info("=" * 60)
                
                chat_response = self.manager.initiate_chat(
                    self.manager,
                    message=f"Implemente uma solução TDD para: {specification}"
                )
                
                if not chat_response:
                    logging.error("❌ Chat não produziu resposta")
                    break
                
                if state.get("status") == "passed":
                    logging.info("🎉 Ciclo TDD concluído com sucesso!")
                    break
                
                # Aguardar antes da próxima iteração
                if iteration < Config.MAX_ITERATIONS:
                    logging.info(f"⏳ Aguardando 2s antes da iteração {iteration + 1}...")
                    time.sleep(2)
            
            except Exception as e:
                logging.error(f"❌ Erro na iteração {iteration}: {str(e)}")
                state.update(status="error")
                break
        
        # Relatório final
        self._print_final_report(state)
        return state.state
    
    def _print_final_report(self, state: StateManager) -> None:
        """Imprimir relatório final do TDD"""
        logging.info("=" * 60)
        logging.info("📊 RELATÓRIO FINAL DO TDD")
        logging.info("=" * 60)
        logging.info(f"✅ Status: {state.get('status', 'unknown')}")
        logging.info(f"🔢 Iterações: {state.get('iteration', 0)}")
        logging.info(f"📄 Implementação: {Config.WORKSPACE_PATH}/{Config.IMPLEMENTATION_MODULE}.py")
        logging.info(f"📄 Testes: {Config.WORKSPACE_PATH}/{Config.TEST_FILE}")
        
        if state.get("status") == "passed":
            logging.info("\n🎉 Ciclo TDD concluído com sucesso!")
            logging.info("   ✓ RED: Testes falharam inicialmente")
            logging.info("   ✓ GREEN: Implementação passou todos os testes")
            logging.info("   ✓ REFACTOR: Código refinado (se necessário)")
        
        logging.info("=" * 60)

def main():
    """Função principal"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    logging.info("Iniciando o sistema de Agentes TDD AutoGen...")

    user_request = """
    Eu preciso de um código Python.
    A tarefa é criar uma função chamada 'add(a, b)' que receba dois inteiros
    e retorne a soma deles.
    
    Por favor, siga o processo TDD completo, incluindo testes para números positivos,
    números negativos e zero.
    """

    orchestrator = TDDOrchestrator()
    state = orchestrator.run(user_request)

    logging.info("🏁 Sistema TDD AutoGen finalizado.")
    return state

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("\n⚠️ Execução interrompida pelo usuário")
    except Exception as e:
        logging.error(f"\n❌ Erro fatal: {str(e)}")
