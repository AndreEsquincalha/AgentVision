"""
Utilitarios de logging estruturado para execucoes.

Fornece classes para registrar logs estruturados durante a execucao de jobs,
com suporte a niveis (INFO, WARNING, ERROR, FATAL), fases e metadados.
Compativel com o formato legado (texto simples) para retrocompatibilidade.
"""

import json
from dataclasses import asdict, dataclass, field

from app.shared.utils import utc_now


@dataclass
class ExecutionLogEntry:
    """
    Entrada individual de log de execucao.

    Representa um evento que ocorreu durante a execucao de um job,
    com timestamp, nivel de severidade, fase e mensagem.
    """

    timestamp: str
    level: str  # INFO, WARNING, ERROR, FATAL
    phase: str  # setup, browser, screenshots, analysis, pdf, delivery, finalize
    message: str
    metadata: dict | None = None


@dataclass
class ExecutionLogger:
    """
    Logger estruturado para execucoes de jobs.

    Coleta entradas de log durante a execucao e permite serializar
    para JSON (formato estruturado) ou texto (formato legado).
    """

    entries: list[ExecutionLogEntry] = field(default_factory=list)

    def _add(
        self,
        level: str,
        phase: str,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        """Adiciona uma entrada de log com timestamp atual."""
        entry = ExecutionLogEntry(
            timestamp=utc_now().isoformat(),
            level=level,
            phase=phase,
            message=message,
            metadata=metadata,
        )
        self.entries.append(entry)

    def info(
        self,
        phase: str,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        """Registra mensagem informativa."""
        self._add('INFO', phase, message, metadata)

    def warning(
        self,
        phase: str,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        """Registra aviso (erro nao-fatal, execucao continua)."""
        self._add('WARNING', phase, message, metadata)

    def error(
        self,
        phase: str,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        """Registra erro critico (pode pular fase, mas execucao continua)."""
        self._add('ERROR', phase, message, metadata)

    def fatal(
        self,
        phase: str,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        """Registra erro fatal (execucao deve ser interrompida)."""
        self._add('FATAL', phase, message, metadata)

    def to_json(self) -> str:
        """
        Serializa todas as entradas para JSON.

        Returns:
            String JSON com a lista de entradas de log.
        """
        return json.dumps(
            [asdict(e) for e in self.entries],
            ensure_ascii=False,
        )

    def to_text(self) -> str:
        """
        Serializa para formato de texto legado (retrocompativel).

        Cada entrada e formatada como uma linha de texto:
        [TIMESTAMP] [LEVEL] [PHASE] message

        Returns:
            String com todas as entradas em formato texto.
        """
        lines: list[str] = []
        for entry in self.entries:
            prefix = f'[{entry.timestamp}] [{entry.level}] [{entry.phase}]'
            lines.append(f'{prefix} {entry.message}')
        return '\n'.join(lines)

    def has_fatal(self) -> bool:
        """Verifica se existe alguma entrada com nivel FATAL."""
        return any(e.level == 'FATAL' for e in self.entries)

    def has_errors(self) -> bool:
        """Verifica se existe alguma entrada com nivel ERROR ou FATAL."""
        return any(e.level in ('ERROR', 'FATAL') for e in self.entries)

    def has_warnings(self) -> bool:
        """Verifica se existe alguma entrada com nivel WARNING ou superior."""
        return any(e.level in ('WARNING', 'ERROR', 'FATAL') for e in self.entries)

    def get_last_fatal_message(self) -> str | None:
        """Retorna a mensagem do ultimo erro FATAL, ou None."""
        for entry in reversed(self.entries):
            if entry.level == 'FATAL':
                return entry.message
        return None

    @staticmethod
    def parse_json(json_str: str) -> list[ExecutionLogEntry]:
        """
        Reconstroi entradas de log a partir de JSON.

        Args:
            json_str: String JSON com a lista de entradas.

        Returns:
            Lista de ExecutionLogEntry reconstruidas.
        """
        try:
            data = json.loads(json_str)
            if isinstance(data, list):
                return [
                    ExecutionLogEntry(
                        timestamp=item.get('timestamp', ''),
                        level=item.get('level', 'INFO'),
                        phase=item.get('phase', 'unknown'),
                        message=item.get('message', ''),
                        metadata=item.get('metadata'),
                    )
                    for item in data
                ]
        except (json.JSONDecodeError, TypeError):
            pass
        return []
