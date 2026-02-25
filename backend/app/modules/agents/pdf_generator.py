import io
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Any

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas as pdfgen_canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.modules.agents.llm_provider import AnalysisResult
from app.shared.storage import StorageClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paleta de cores inspirada no design system AgentVision
# ---------------------------------------------------------------------------
_COLOR_BG_BASE = colors.HexColor('#0F1117')
_COLOR_BG_SURFACE = colors.HexColor('#1A1D2E')
_COLOR_BG_ELEVATED = colors.HexColor('#242838')
_COLOR_PRIMARY = colors.HexColor('#6366F1')
_COLOR_PRIMARY_HOVER = colors.HexColor('#4F46E5')
_COLOR_SECONDARY = colors.HexColor('#8B5CF6')
_COLOR_TEXT_PRIMARY = colors.HexColor('#F9FAFB')
_COLOR_TEXT_SECONDARY = colors.HexColor('#9CA3AF')
_COLOR_TEXT_MUTED = colors.HexColor('#6B7280')
_COLOR_BORDER = colors.HexColor('#2E3348')
_COLOR_SUCCESS = colors.HexColor('#10B981')
_COLOR_ERROR = colors.HexColor('#EF4444')
_COLOR_WARNING = colors.HexColor('#F59E0B')

# Cores claras para texto em PDF (melhor legibilidade em impressao)
_COLOR_DARK_TEXT = colors.HexColor('#1F2937')
_COLOR_DARK_HEADING = colors.HexColor('#111827')
_COLOR_LIGHT_BG = colors.HexColor('#F9FAFB')
_COLOR_TABLE_HEADER_BG = colors.HexColor('#4F46E5')
_COLOR_TABLE_ROW_ALT = colors.HexColor('#F3F4F6')
_COLOR_TABLE_BORDER = colors.HexColor('#D1D5DB')

# Dimensoes da pagina
_PAGE_WIDTH, _PAGE_HEIGHT = A4

# ---------------------------------------------------------------------------
# Limites de validacao de screenshots (11.1.2)
# ---------------------------------------------------------------------------
_MIN_SCREENSHOT_SIZE: int = 1024       # 1 KB
_MAX_SCREENSHOT_SIZE: int = 10485760   # 10 MB
_MAX_SCREENSHOT_WIDTH: int = 1920
_MAX_SCREENSHOT_HEIGHT: int = 1080

# Magic bytes para formatos de imagem suportados
_PNG_MAGIC: bytes = b'\x89PNG'
_JPEG_MAGIC: bytes = b'\xff\xd8\xff'

# ---------------------------------------------------------------------------
# Limites de PDF (11.1.5)
# ---------------------------------------------------------------------------
_LARGE_PDF_THRESHOLD: int = 10 * 1024 * 1024   # 10 MB — usa arquivo temporario
_MAX_PDF_SIZE: int = 50 * 1024 * 1024           # 50 MB — aborta geracao


def _build_styles() -> dict[str, ParagraphStyle]:
    """
    Constroi o conjunto de estilos customizados para o relatorio PDF.

    Returns:
        Dicionario com os estilos nomeados.
    """
    base = getSampleStyleSheet()

    styles: dict[str, ParagraphStyle] = {}

    # --- Estilos da capa ---
    styles['cover_title'] = ParagraphStyle(
        'cover_title',
        parent=base['Title'],
        fontSize=28,
        leading=34,
        textColor=_COLOR_PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=6 * mm,
        fontName='Helvetica-Bold',
    )
    styles['cover_subtitle'] = ParagraphStyle(
        'cover_subtitle',
        parent=base['Normal'],
        fontSize=14,
        leading=18,
        textColor=_COLOR_TEXT_MUTED,
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
        fontName='Helvetica',
    )
    styles['cover_info'] = ParagraphStyle(
        'cover_info',
        parent=base['Normal'],
        fontSize=11,
        leading=16,
        textColor=_COLOR_DARK_TEXT,
        alignment=TA_CENTER,
        spaceAfter=3 * mm,
        fontName='Helvetica',
    )

    # --- Estilos de conteudo ---
    styles['section_title'] = ParagraphStyle(
        'section_title',
        parent=base['Heading1'],
        fontSize=18,
        leading=22,
        textColor=_COLOR_PRIMARY,
        spaceBefore=12 * mm,
        spaceAfter=6 * mm,
        fontName='Helvetica-Bold',
        borderWidth=0,
        borderPadding=0,
    )
    styles['subsection_title'] = ParagraphStyle(
        'subsection_title',
        parent=base['Heading2'],
        fontSize=14,
        leading=18,
        textColor=_COLOR_PRIMARY_HOVER,
        spaceBefore=8 * mm,
        spaceAfter=4 * mm,
        fontName='Helvetica-Bold',
    )
    styles['body'] = ParagraphStyle(
        'body',
        parent=base['Normal'],
        fontSize=10,
        leading=14,
        textColor=_COLOR_DARK_TEXT,
        alignment=TA_JUSTIFY,
        spaceAfter=3 * mm,
        fontName='Helvetica',
    )
    styles['body_small'] = ParagraphStyle(
        'body_small',
        parent=base['Normal'],
        fontSize=9,
        leading=12,
        textColor=_COLOR_TEXT_MUTED,
        alignment=TA_LEFT,
        spaceAfter=2 * mm,
        fontName='Helvetica',
    )
    styles['caption'] = ParagraphStyle(
        'caption',
        parent=base['Normal'],
        fontSize=9,
        leading=12,
        textColor=_COLOR_TEXT_MUTED,
        alignment=TA_CENTER,
        spaceBefore=2 * mm,
        spaceAfter=6 * mm,
        fontName='Helvetica-Oblique',
    )
    styles['insight_item'] = ParagraphStyle(
        'insight_item',
        parent=base['Normal'],
        fontSize=10,
        leading=14,
        textColor=_COLOR_DARK_TEXT,
        alignment=TA_LEFT,
        spaceAfter=2 * mm,
        leftIndent=8 * mm,
        fontName='Helvetica',
    )
    styles['table_header'] = ParagraphStyle(
        'table_header',
        parent=base['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.white,
        fontName='Helvetica-Bold',
    )
    styles['table_cell'] = ParagraphStyle(
        'table_cell',
        parent=base['Normal'],
        fontSize=9,
        leading=12,
        textColor=_COLOR_DARK_TEXT,
        fontName='Helvetica',
    )
    styles['footer'] = ParagraphStyle(
        'footer',
        parent=base['Normal'],
        fontSize=8,
        leading=10,
        textColor=_COLOR_TEXT_MUTED,
        alignment=TA_CENTER,
        fontName='Helvetica',
    )

    # --- Estilos para secoes novas (11.2) ---
    styles['status_badge'] = ParagraphStyle(
        'status_badge',
        parent=base['Normal'],
        fontSize=14,
        leading=18,
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
        fontName='Helvetica-Bold',
    )
    styles['metric_label'] = ParagraphStyle(
        'metric_label',
        parent=base['Normal'],
        fontSize=9,
        leading=12,
        textColor=_COLOR_TEXT_MUTED,
        alignment=TA_CENTER,
        fontName='Helvetica',
    )
    styles['metric_value'] = ParagraphStyle(
        'metric_value',
        parent=base['Normal'],
        fontSize=14,
        leading=18,
        textColor=_COLOR_DARK_HEADING,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )
    styles['summary_bullet'] = ParagraphStyle(
        'summary_bullet',
        parent=base['Normal'],
        fontSize=11,
        leading=16,
        textColor=_COLOR_DARK_TEXT,
        alignment=TA_LEFT,
        spaceAfter=4 * mm,
        leftIndent=6 * mm,
        fontName='Helvetica',
    )
    styles['timeline_item'] = ParagraphStyle(
        'timeline_item',
        parent=base['Normal'],
        fontSize=9,
        leading=13,
        textColor=_COLOR_DARK_TEXT,
        alignment=TA_LEFT,
        spaceAfter=2 * mm,
        leftIndent=10 * mm,
        fontName='Helvetica',
    )

    return styles


# ---------------------------------------------------------------------------
# NumberedCanvas — para suportar "Pagina X de Y" (11.2.4)
# ---------------------------------------------------------------------------

class _NumberedCanvas(pdfgen_canvas.Canvas):
    """
    Canvas customizado que registra cada pagina e, ao final, insere
    o total de paginas em todas elas (padrao "Pagina X de Y").
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        """Salva o estado antes de iniciar nova pagina."""
        self._saved_page_states.append(dict(self.__dict__))
        super().showPage()

    def save(self) -> None:
        """Adiciona o total de paginas a cada pagina antes de salvar."""
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_number(total_pages)
            super().showPage()
        super().save()

    def _draw_page_number(self, total_pages: int) -> None:
        """Desenha 'Pagina X de Y' no rodape de cada pagina (exceto capa)."""
        if self._pageNumber <= 1:
            return
        self.saveState()
        self.setFont('Helvetica', 8)
        self.setFillColor(_COLOR_TEXT_MUTED)
        self.drawCentredString(
            _PAGE_WIDTH / 2.0,
            1.5 * cm,
            f'P\u00e1gina {self._pageNumber} de {total_pages}',
        )
        self.restoreState()


class PDFGenerator:
    """
    Gerador de relatorios PDF profissionais para execucoes do AgentVision.

    Utiliza a biblioteca ReportLab para construir PDFs com layout estruturado
    contendo capa, sumario executivo, status visual, screenshots com legendas
    contextuais, analise textual, dados extraidos, insights e marca d'agua.
    """

    def __init__(self) -> None:
        """Inicializa o gerador com os estilos pre-configurados."""
        self._styles = _build_styles()

    # -----------------------------------------------------------------------
    # Metodo principal de geracao (mantido compativel)
    # -----------------------------------------------------------------------

    def generate(
        self,
        screenshots: list[bytes],
        analysis: AnalysisResult,
        metadata: dict[str, Any] | None = None,
        *,
        screenshot_contexts: list[dict[str, Any]] | None = None,
    ) -> bytes:
        """
        Gera o relatorio PDF completo.

        Args:
            screenshots: Lista de screenshots em bytes (PNG/JPEG).
            analysis: Resultado da analise visual do LLM.
            metadata: Metadados da execucao (project_name, job_name,
                      execution_id, base_url, started_at, finished_at,
                      duration, status, tokens_used, logs).
            screenshot_contexts: Lista opcional de contextos por screenshot
                      com chaves url, action, timestamp (11.2.3).

        Returns:
            Conteudo do PDF em bytes.
        """
        metadata = metadata or {}
        buffer = io.BytesIO()

        logger.info(
            'Iniciando geracao de PDF. Screenshots: %d, Metadata: %s',
            len(screenshots),
            list(metadata.keys()),
        )

        try:
            # Valida e filtra screenshots (11.1.2)
            valid_screenshots = self._validate_screenshots(screenshots)

            # Metadados do PDF (11.2.4)
            pdf_title = self._safe_text(
                f'Relat\u00f3rio de Execu\u00e7\u00e3o - '
                f'{metadata.get("project_name", "AgentVision")}',
                max_length=200,
            )
            pdf_subject = self._safe_text(
                f'Execu\u00e7\u00e3o {metadata.get("execution_id", "")} '
                f'- Job {metadata.get("job_name", "")}',
                max_length=200,
            )

            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                topMargin=2 * cm,
                bottomMargin=2.5 * cm,
                leftMargin=2 * cm,
                rightMargin=2 * cm,
                title=pdf_title,
                author='AgentVision',
                subject=pdf_subject,
                creator='AgentVision PDF Generator',
            )

            story: list[Any] = []

            # Capa
            story.extend(self._build_cover_page(metadata))

            # Secao de status visual (11.2.2) — logo apos a capa
            story.append(PageBreak())
            story.extend(self._build_status_section(metadata, analysis))

            # Sumario executivo (11.2.1)
            story.extend(
                self._build_executive_summary(analysis, metadata)
            )

            # Secao de screenshots com legendas contextuais (11.2.3)
            if valid_screenshots:
                story.append(PageBreak())
                story.extend(
                    self._build_screenshots_section(
                        valid_screenshots,
                        screenshot_contexts=screenshot_contexts,
                    )
                )

            # Secao de analise textual
            if analysis.text:
                story.append(PageBreak())
                story.extend(
                    self._build_analysis_section(
                        self._safe_text(analysis.text, max_length=15000)
                    )
                )

            # Secao de dados extraidos
            if analysis.extracted_data:
                story.extend(
                    self._build_extracted_data_section(analysis.extracted_data)
                )

                # Secao de insights (se presente nos dados extraidos)
                insights = analysis.extracted_data.get('insights')
                if insights and isinstance(insights, list):
                    story.extend(self._build_insights_section(insights))

            # Secao de metadados de execucao (resumo final)
            story.extend(self._build_execution_summary(metadata, analysis))

            # Constroi o documento com canvas numerado (11.2.4)
            doc.build(
                story,
                onFirstPage=self._draw_first_page,
                onLaterPages=self._draw_later_pages,
                canvasmaker=_NumberedCanvas,
            )

            pdf_bytes = buffer.getvalue()

            # Verifica limite maximo de tamanho (11.1.5)
            if len(pdf_bytes) > _MAX_PDF_SIZE:
                logger.error(
                    'PDF excede o limite maximo de %d bytes (%d bytes gerados). '
                    'Abortando.',
                    _MAX_PDF_SIZE, len(pdf_bytes),
                )
                raise ValueError(
                    f'PDF excede o limite maximo de '
                    f'{_MAX_PDF_SIZE // (1024 * 1024)} MB'
                )

            logger.info(
                'PDF gerado com sucesso. Tamanho: %d bytes',
                len(pdf_bytes),
            )
            return pdf_bytes

        except Exception as e:
            logger.error('Erro ao gerar PDF: %s', str(e))
            raise

        finally:
            buffer.close()

    # -----------------------------------------------------------------------
    # Fallback progressivo (11.1.1)
    # -----------------------------------------------------------------------

    def generate_with_fallback(
        self,
        screenshots: list[bytes] | None = None,
        analysis: AnalysisResult | None = None,
        metadata: dict[str, Any] | None = None,
        *,
        screenshot_contexts: list[dict[str, Any]] | None = None,
        execution_logs: list[str] | None = None,
    ) -> bytes:
        """
        Gera o PDF com fallback progressivo — NUNCA falha completamente.

        Niveis de fallback:
        1. Ideal: screenshots + analise + dados extraidos -> PDF completo
        2. Fallback 1: screenshots sem analise -> PDF com screenshots e metadata
        3. Fallback 2: analise sem screenshots -> PDF com texto da analise
        4. Fallback 3: erro total -> PDF minimo com logs e status de erro

        Args:
            screenshots: Lista de screenshots em bytes (pode ser None/vazia).
            analysis: Resultado da analise visual (pode ser None).
            metadata: Metadados da execucao.
            screenshot_contexts: Contextos opcionais por screenshot.
            execution_logs: Logs da execucao para uso no fallback 3.

        Returns:
            Conteudo do PDF em bytes (sempre retorna algo).
        """
        metadata = metadata or {}
        screenshots = screenshots or []
        execution_logs = execution_logs or []

        has_screenshots = len(screenshots) > 0
        has_analysis = analysis is not None and bool(analysis.text)

        # --- Nivel 1: Ideal (screenshots + analise) ---
        if has_screenshots and has_analysis:
            try:
                logger.info('PDF Fallback: nivel 1 (ideal — screenshots + analise)')
                return self.generate(
                    screenshots=screenshots,
                    analysis=analysis,
                    metadata=metadata,
                    screenshot_contexts=screenshot_contexts,
                )
            except Exception as e:
                logger.warning(
                    'PDF Fallback nivel 1 falhou: %s. Tentando nivel 2...', str(e)
                )

        # --- Nivel 2: Fallback 1 (screenshots sem analise) ---
        if has_screenshots:
            try:
                logger.info(
                    'PDF Fallback: nivel 2 (screenshots sem analise completa)'
                )
                fallback_analysis = AnalysisResult(
                    text='An\u00e1lise visual n\u00e3o dispon\u00edvel para esta execu\u00e7\u00e3o.',
                    extracted_data=None,
                    tokens_used=0,
                )
                return self.generate(
                    screenshots=screenshots,
                    analysis=fallback_analysis,
                    metadata=metadata,
                    screenshot_contexts=screenshot_contexts,
                )
            except Exception as e:
                logger.warning(
                    'PDF Fallback nivel 2 falhou: %s. Tentando nivel 3...', str(e)
                )

        # --- Nivel 3: Fallback 2 (analise sem screenshots) ---
        if has_analysis:
            try:
                logger.info(
                    'PDF Fallback: nivel 3 (analise sem screenshots)'
                )
                return self.generate(
                    screenshots=[],
                    analysis=analysis,
                    metadata=metadata,
                )
            except Exception as e:
                logger.warning(
                    'PDF Fallback nivel 3 falhou: %s. Tentando nivel minimo...', str(e)
                )

        # --- Nivel 4: Fallback 3 (PDF minimo com logs e erro) ---
        logger.info('PDF Fallback: nivel 4 (PDF minimo com logs e status de erro)')
        return self._generate_minimal_pdf(metadata, execution_logs)

    def _generate_minimal_pdf(
        self,
        metadata: dict[str, Any],
        execution_logs: list[str],
    ) -> bytes:
        """
        Gera um PDF minimo contendo apenas metadados e logs de execucao.

        Usado como ultimo recurso quando todas as tentativas anteriores falham.

        Args:
            metadata: Metadados da execucao.
            execution_logs: Lista de logs da execucao.

        Returns:
            Conteudo do PDF em bytes.
        """
        buffer = io.BytesIO()

        try:
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                topMargin=2 * cm,
                bottomMargin=2.5 * cm,
                leftMargin=2 * cm,
                rightMargin=2 * cm,
                title='Relat\u00f3rio Parcial - AgentVision',
                author='AgentVision',
            )

            story: list[Any] = []

            # Capa simplificada
            story.append(Spacer(1, 4 * cm))
            story.append(
                Paragraph(
                    'Relat\u00f3rio Parcial de Execu\u00e7\u00e3o',
                    self._styles['cover_title'],
                )
            )
            story.append(
                Paragraph('AgentVision', self._styles['cover_subtitle'])
            )
            story.append(Spacer(1, 1 * cm))

            # Status de erro
            story.append(
                Paragraph(
                    '<font color="#EF4444"><b>STATUS: FALHA NA GERA\u00c7\u00c3O COMPLETA</b></font>',
                    self._styles['cover_info'],
                )
            )
            story.append(Spacer(1, 6 * mm))

            # Metadados basicos
            for key in ('project_name', 'job_name', 'execution_id', 'base_url'):
                value = metadata.get(key)
                if value:
                    label = self._format_key_label(key)
                    story.append(
                        Paragraph(
                            f'<b>{self._escape_html(label)}:</b> '
                            f'{self._escape_html(self._safe_text(str(value), 200))}',
                            self._styles['cover_info'],
                        )
                    )

            started_at = metadata.get('started_at')
            if started_at:
                if isinstance(started_at, datetime):
                    date_str = started_at.strftime('%d/%m/%Y %H:%M:%S UTC')
                else:
                    date_str = str(started_at)
                story.append(
                    Paragraph(
                        f'<b>Data:</b> {self._escape_html(date_str)}',
                        self._styles['cover_info'],
                    )
                )

            # Logs de execucao
            if execution_logs:
                story.append(PageBreak())
                story.append(
                    Paragraph(
                        'Logs da Execu\u00e7\u00e3o', self._styles['section_title']
                    )
                )
                story.append(
                    HRFlowable(
                        width='100%',
                        thickness=1,
                        color=_COLOR_ERROR,
                        spaceAfter=6 * mm,
                    )
                )

                # Limita a quantidade de linhas de log no PDF minimo
                max_log_lines = 100
                logs_to_show = execution_logs[:max_log_lines]
                for log_line in logs_to_show:
                    safe_line = self._safe_text(log_line, max_length=500)
                    story.append(
                        Paragraph(
                            f'<font face="Courier" size="8">'
                            f'{self._escape_html(safe_line)}'
                            f'</font>',
                            self._styles['body_small'],
                        )
                    )

                if len(execution_logs) > max_log_lines:
                    story.append(
                        Paragraph(
                            f'<i>... [{len(execution_logs) - max_log_lines} '
                            f'linhas adicionais omitidas]</i>',
                            self._styles['body_small'],
                        )
                    )

            doc.build(
                story,
                onFirstPage=self._draw_first_page,
                onLaterPages=self._draw_later_pages,
            )

            pdf_bytes = buffer.getvalue()
            logger.info(
                'PDF minimo gerado com sucesso. Tamanho: %d bytes',
                len(pdf_bytes),
            )
            return pdf_bytes

        except Exception as e:
            # Ultimo recurso absoluto: PDF com texto bruto
            logger.error(
                'Falha ao gerar PDF minimo: %s. Gerando PDF ultra-minimo.', str(e)
            )
            return self._generate_ultra_minimal_pdf(metadata)

        finally:
            buffer.close()

    def _generate_ultra_minimal_pdf(
        self, metadata: dict[str, Any]
    ) -> bytes:
        """
        Gera um PDF ultra-minimo usando canvas direto (sem Platypus).

        Usado quando ate o SimpleDocTemplate falha.

        Args:
            metadata: Metadados da execucao.

        Returns:
            Conteudo do PDF em bytes.
        """
        buffer = io.BytesIO()
        try:
            c = pdfgen_canvas.Canvas(buffer, pagesize=A4)
            c.setTitle('Relatorio Parcial - AgentVision')
            c.setAuthor('AgentVision')

            c.setFont('Helvetica-Bold', 16)
            c.drawCentredString(
                _PAGE_WIDTH / 2.0,
                _PAGE_HEIGHT - 4 * cm,
                'AgentVision - Relatorio Parcial',
            )

            c.setFont('Helvetica', 10)
            y_pos = _PAGE_HEIGHT - 6 * cm
            for key in ('project_name', 'job_name', 'execution_id'):
                value = metadata.get(key, 'N/A')
                label = self._format_key_label(key)
                c.drawString(3 * cm, y_pos, f'{label}: {str(value)[:80]}')
                y_pos -= 20

            c.setFont('Helvetica', 9)
            c.setFillColor(_COLOR_ERROR)
            c.drawCentredString(
                _PAGE_WIDTH / 2.0,
                y_pos - 40,
                'Erro na geracao do relatorio completo. Consulte os logs.',
            )

            c.setFillColor(_COLOR_TEXT_MUTED)
            c.setFont('Helvetica', 8)
            c.drawCentredString(
                _PAGE_WIDTH / 2.0,
                2 * cm,
                'Gerado automaticamente pelo AgentVision',
            )

            c.save()
            return buffer.getvalue()
        finally:
            buffer.close()

    # -----------------------------------------------------------------------
    # Retry com degradacao (11.1.4)
    # -----------------------------------------------------------------------

    def generate_with_retry(
        self,
        screenshots: list[bytes] | None = None,
        analysis: AnalysisResult | None = None,
        metadata: dict[str, Any] | None = None,
        *,
        screenshot_contexts: list[dict[str, Any]] | None = None,
        execution_logs: list[str] | None = None,
        max_retries: int = 3,
    ) -> bytes:
        """
        Gera o PDF com logica de retry e degradacao progressiva.

        Tentativas:
        1. PDF completo (mesmos parametros)
        2. PDF somente texto (sem imagens)
        3. PDF minimo (apenas metadados e logs)

        Args:
            screenshots: Lista de screenshots em bytes.
            analysis: Resultado da analise visual.
            metadata: Metadados da execucao.
            screenshot_contexts: Contextos por screenshot.
            execution_logs: Logs da execucao.
            max_retries: Numero maximo de tentativas (padrao: 3).

        Returns:
            Conteudo do PDF em bytes (sempre retorna algo).
        """
        metadata = metadata or {}
        screenshots = screenshots or []
        execution_logs = execution_logs or []
        analysis = analysis or AnalysisResult(text='', extracted_data=None, tokens_used=0)

        errors: list[str] = []

        # --- Tentativa 1: PDF completo ---
        if max_retries >= 1:
            try:
                logger.info('PDF Retry: tentativa 1/3 (PDF completo)')
                return self.generate(
                    screenshots=screenshots,
                    analysis=analysis,
                    metadata=metadata,
                    screenshot_contexts=screenshot_contexts,
                )
            except Exception as e:
                error_msg = f'Tentativa 1 falhou: {str(e)}'
                errors.append(error_msg)
                logger.warning('PDF Retry: %s', error_msg)

        # --- Tentativa 2: PDF sem imagens (somente texto) ---
        if max_retries >= 2:
            try:
                logger.info('PDF Retry: tentativa 2/3 (sem imagens)')
                return self.generate(
                    screenshots=[],
                    analysis=analysis,
                    metadata=metadata,
                )
            except Exception as e:
                error_msg = f'Tentativa 2 falhou: {str(e)}'
                errors.append(error_msg)
                logger.warning('PDF Retry: %s', error_msg)

        # --- Tentativa 3: PDF minimo ---
        if max_retries >= 3:
            try:
                logger.info('PDF Retry: tentativa 3/3 (PDF minimo)')
                combined_logs = execution_logs + [
                    '',
                    '--- Erros de geracao de PDF ---',
                ] + errors
                return self._generate_minimal_pdf(metadata, combined_logs)
            except Exception as e:
                error_msg = f'Tentativa 3 falhou: {str(e)}'
                errors.append(error_msg)
                logger.error('PDF Retry: %s', error_msg)

        # Ultimo recurso absoluto
        logger.error(
            'Todas as %d tentativas de geracao de PDF falharam. '
            'Gerando PDF ultra-minimo.',
            max_retries,
        )
        return self._generate_ultra_minimal_pdf(metadata)

    # -----------------------------------------------------------------------
    # Salvamento no storage com suporte a arquivos grandes (11.1.5)
    # -----------------------------------------------------------------------

    @staticmethod
    def save_to_storage(
        pdf_bytes: bytes,
        execution_id: str,
        storage_client: StorageClient,
    ) -> str:
        """
        Salva o PDF gerado no MinIO/S3.

        Para PDFs maiores que 10 MB, usa arquivo temporario em vez de manter
        tudo em memoria.

        Args:
            pdf_bytes: Conteudo do PDF em bytes.
            execution_id: ID da execucao associada.
            storage_client: Cliente de storage (MinIO/S3).

        Returns:
            Caminho do arquivo no storage (ex: pdfs/{execution_id}/report.pdf).
        """
        # Garante que o bucket existe
        storage_client.ensure_bucket_exists()

        key = f'pdfs/{execution_id}/report.pdf'
        pdf_size = len(pdf_bytes)

        logger.info(
            'Salvando PDF no storage: %s (tamanho: %d bytes)',
            key,
            pdf_size,
        )

        if pdf_size > _LARGE_PDF_THRESHOLD:
            # Para PDFs grandes, usa arquivo temporario para evitar picos de memoria
            logger.info(
                'PDF grande detectado (%d bytes > %d). Usando arquivo temporario.',
                pdf_size, _LARGE_PDF_THRESHOLD,
            )
            tmp_path: str | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    suffix='.pdf', delete=False
                ) as tmp_file:
                    tmp_path = tmp_file.name
                    tmp_file.write(pdf_bytes)

                storage_client.upload_file_from_path(
                    file_path=tmp_path,
                    key=key,
                    content_type='application/pdf',
                )
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
        else:
            storage_client.upload_file(
                key=key,
                file_data=pdf_bytes,
                content_type='application/pdf',
            )

        logger.info('PDF salvo com sucesso: %s', key)
        return key

    # -----------------------------------------------------------------------
    # Validacao de screenshots (11.1.2)
    # -----------------------------------------------------------------------

    def _validate_screenshots(
        self, screenshots: list[bytes]
    ) -> list[bytes]:
        """
        Valida e filtra screenshots, retornando apenas os validos.

        Args:
            screenshots: Lista de screenshots em bytes.

        Returns:
            Lista de screenshots validos (possivelmente redimensionados).
        """
        valid: list[bytes] = []
        for index, img_bytes in enumerate(screenshots, start=1):
            is_valid, processed = self._validate_screenshot(img_bytes)
            if is_valid and processed is not None:
                valid.append(processed)
            else:
                logger.warning(
                    'Screenshot %d descartado na validacao (tamanho=%d bytes)',
                    index, len(img_bytes),
                )
        logger.info(
            'Validacao de screenshots: %d/%d validos',
            len(valid), len(screenshots),
        )
        return valid

    @staticmethod
    def _validate_screenshot(img_bytes: bytes) -> tuple[bool, bytes | None]:
        """
        Valida um screenshot individual verificando magic bytes, tamanho
        e redimensionando se necessario.

        Verificacoes:
        - Magic bytes (PNG: 0x89PNG, JPEG: 0xFFD8FF)
        - Tamanho minimo (> 1 KB)
        - Tamanho maximo (< 10 MB)
        - Redimensiona imagens maiores que 1920x1080

        Args:
            img_bytes: Bytes da imagem.

        Returns:
            Tupla (valido, bytes_processados). Se invalido, retorna (False, None).
        """
        # Verifica tamanho minimo
        if len(img_bytes) < _MIN_SCREENSHOT_SIZE:
            logger.warning(
                'Screenshot muito pequeno: %d bytes (minimo: %d)',
                len(img_bytes), _MIN_SCREENSHOT_SIZE,
            )
            return False, None

        # Verifica tamanho maximo
        if len(img_bytes) > _MAX_SCREENSHOT_SIZE:
            logger.warning(
                'Screenshot muito grande: %d bytes (maximo: %d)',
                len(img_bytes), _MAX_SCREENSHOT_SIZE,
            )
            return False, None

        # Verifica magic bytes
        is_png = img_bytes[:4] == _PNG_MAGIC
        is_jpeg = img_bytes[:3] == _JPEG_MAGIC

        if not is_png and not is_jpeg:
            logger.warning(
                'Screenshot com formato invalido (magic bytes: %s)',
                img_bytes[:4].hex(),
            )
            return False, None

        # Tenta abrir e redimensionar se necessario
        try:
            img = PILImage.open(io.BytesIO(img_bytes))
            width, height = img.size

            if width > _MAX_SCREENSHOT_WIDTH or height > _MAX_SCREENSHOT_HEIGHT:
                # Redimensiona mantendo proporcao
                ratio = min(
                    _MAX_SCREENSHOT_WIDTH / width,
                    _MAX_SCREENSHOT_HEIGHT / height,
                )
                new_width = int(width * ratio)
                new_height = int(height * ratio)

                img = img.resize((new_width, new_height), PILImage.LANCZOS)
                logger.info(
                    'Screenshot redimensionado: %dx%d -> %dx%d',
                    width, height, new_width, new_height,
                )

                # Salva de volta no formato original
                output = io.BytesIO()
                if is_png:
                    img.save(output, format='PNG')
                else:
                    # Converte RGBA para RGB se for JPEG
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')
                    img.save(output, format='JPEG', quality=90)
                return True, output.getvalue()

            return True, img_bytes

        except Exception as e:
            logger.warning(
                'Screenshot corrompido ou invalido: %s', str(e)
            )
            return False, None

    # -----------------------------------------------------------------------
    # Tratamento seguro de texto (11.1.3)
    # -----------------------------------------------------------------------

    @staticmethod
    def _safe_text(text: str, max_length: int = 2000) -> str:
        """
        Trata texto para inclusao segura no PDF.

        - Garante codificacao UTF-8 correta
        - Remove caracteres de controle (exceto newline e tab)
        - Trunca textos longos com indicador
        - Escapa entidades XML que podem quebrar o ReportLab

        Args:
            text: Texto a ser tratado.
            max_length: Comprimento maximo permitido.

        Returns:
            Texto tratado e seguro para o PDF.
        """
        if not text:
            return ''

        # Garante string valida (trata bytes acidentais)
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='replace')

        # Remove caracteres de controle (exceto \n e \t)
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        # Remove caracteres nulos que podem quebrar XML
        cleaned = cleaned.replace('\x00', '')

        # Trunca se necessario
        if len(cleaned) > max_length:
            truncated = cleaned[:max_length - 50]
            cleaned = truncated + '\n... [texto truncado, ver log completo]'

        return cleaned

    # -----------------------------------------------------------------------
    # Sumario executivo (11.2.1)
    # -----------------------------------------------------------------------

    def _build_executive_summary(
        self,
        analysis: AnalysisResult,
        metadata: dict[str, Any],
    ) -> list[Any]:
        """
        Constroi a secao de sumario executivo do relatorio.

        Gera 2-3 bullet points com achados-chave a partir dos dados
        extraidos, insights do LLM ou conteudo capturado pelo browser.

        Args:
            analysis: Resultado da analise visual.
            metadata: Metadados da execucao.

        Returns:
            Lista de flowables para o sumario executivo.
        """
        elements: list[Any] = []

        elements.append(
            Paragraph(
                'Sum\u00e1rio Executivo', self._styles['section_title']
            )
        )
        elements.append(
            HRFlowable(
                width='100%',
                thickness=1,
                color=_COLOR_PRIMARY,
                spaceAfter=6 * mm,
            )
        )

        # Coleta pontos para o sumario
        summary_points: list[str] = []

        # Fonte 1: insights do extracted_data
        if analysis.extracted_data:
            summary_text = analysis.extracted_data.get('summary')
            if summary_text and isinstance(summary_text, str):
                summary_points.append(summary_text)

            insights = analysis.extracted_data.get('insights')
            if insights and isinstance(insights, list):
                for insight in insights[:3]:
                    if isinstance(insight, str) and insight.strip():
                        summary_points.append(insight.strip())

        # Fonte 2: texto da analise (primeiros paragrafos)
        if len(summary_points) < 2 and analysis.text:
            clean_text = self._strip_json_blocks(analysis.text)
            paragraphs = [
                p.strip() for p in clean_text.split('\n')
                if p.strip() and not p.strip().startswith('#')
                and not p.strip().startswith('```')
                and len(p.strip()) > 20
            ]
            for para in paragraphs[:3]:
                if para not in summary_points:
                    summary_points.append(para)
                    if len(summary_points) >= 3:
                        break

        # Fonte 3: conteudo extraido pelo browser (metadata.extracted_content)
        if len(summary_points) < 2:
            extracted_content = metadata.get('extracted_content')
            if extracted_content and isinstance(extracted_content, list):
                for content in extracted_content[:2]:
                    if isinstance(content, str) and content.strip():
                        summary_points.append(content.strip()[:200])

        # Fallback: mensagem generica
        if not summary_points:
            project_name = metadata.get('project_name', 'N/A')
            job_name = metadata.get('job_name', 'N/A')
            summary_points.append(
                f'Execu\u00e7\u00e3o do job "{job_name}" no projeto '
                f'"{project_name}" conclu\u00edda.'
            )

        # Renderiza os pontos do sumario (maximo 3)
        for point in summary_points[:3]:
            safe_point = self._safe_text(point, max_length=500)
            elements.append(
                Paragraph(
                    f'\u2022 {self._escape_html(safe_point)}',
                    self._styles['summary_bullet'],
                )
            )

        elements.append(Spacer(1, 6 * mm))
        return elements

    # -----------------------------------------------------------------------
    # Secao de status visual (11.2.2)
    # -----------------------------------------------------------------------

    def _build_status_section(
        self,
        metadata: dict[str, Any],
        analysis: AnalysisResult,
    ) -> list[Any]:
        """
        Constroi a secao de status visual com badge, metricas e timeline.

        Args:
            metadata: Metadados da execucao.
            analysis: Resultado da analise visual.

        Returns:
            Lista de flowables para a secao de status.
        """
        elements: list[Any] = []

        elements.append(
            Paragraph(
                'Status da Execu\u00e7\u00e3o', self._styles['section_title']
            )
        )
        elements.append(
            HRFlowable(
                width='100%',
                thickness=1,
                color=_COLOR_PRIMARY,
                spaceAfter=6 * mm,
            )
        )

        # --- Badge de status ---
        status = metadata.get('status', 'success')
        status_map = {
            'success': ('\u2713 SUCESSO', '#10B981'),
            'partial': ('\u26a0 PARCIAL', '#F59E0B'),
            'failed': ('\u2717 FALHA', '#EF4444'),
        }
        status_label, status_color = status_map.get(
            status, status_map['success']
        )

        elements.append(
            Paragraph(
                f'<font color="{status_color}" size="16">'
                f'<b>{status_label}</b></font>',
                self._styles['status_badge'],
            )
        )
        elements.append(Spacer(1, 6 * mm))

        # --- Metricas visuais (tabela inline) ---
        duration = metadata.get('duration')
        screenshots_count = metadata.get('screenshots_count', 0)
        tokens_used = metadata.get('tokens_used', 0)
        if analysis.tokens_used > 0:
            tokens_used = analysis.tokens_used

        metrics_data = []
        if duration is not None:
            metrics_data.append(('Dura\u00e7\u00e3o', f'{duration}s'))
        if screenshots_count > 0:
            metrics_data.append(('Screenshots', str(screenshots_count)))
        if tokens_used > 0:
            metrics_data.append(('Tokens', f'{tokens_used:,}'))

        if metrics_data:
            # Constroi tabela de metricas lado a lado
            header_row: list[Any] = []
            value_row: list[Any] = []

            for label, value in metrics_data:
                header_row.append(
                    Paragraph(
                        self._escape_html(label),
                        self._styles['metric_label'],
                    )
                )
                value_row.append(
                    Paragraph(
                        f'<b>{self._escape_html(value)}</b>',
                        self._styles['metric_value'],
                    )
                )

            available_width = _PAGE_WIDTH - 4 * cm
            col_width = available_width / max(len(metrics_data), 1)
            col_widths = [col_width] * len(metrics_data)

            metrics_table = Table(
                [value_row, header_row],
                colWidths=col_widths,
            )
            metrics_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LINEBELOW', (0, 0), (-1, 0), 0.5, _COLOR_BORDER),
            ]))

            elements.append(metrics_table)
            elements.append(Spacer(1, 8 * mm))

        # --- Timeline de execucao ---
        timeline_events = metadata.get('timeline')
        if timeline_events and isinstance(timeline_events, list):
            elements.append(
                Paragraph(
                    'Timeline da Execu\u00e7\u00e3o',
                    self._styles['subsection_title'],
                )
            )

            for event in timeline_events:
                if isinstance(event, dict):
                    time_str = event.get('time', '')
                    label = event.get('label', '')
                    icon = event.get('icon', '\u2192')
                    elements.append(
                        Paragraph(
                            f'{self._escape_html(icon)} '
                            f'<b>{self._escape_html(self._safe_text(time_str, 50))}</b>'
                            f' \u2014 '
                            f'{self._escape_html(self._safe_text(label, 200))}',
                            self._styles['timeline_item'],
                        )
                    )
                elif isinstance(event, str):
                    elements.append(
                        Paragraph(
                            f'\u2192 {self._escape_html(self._safe_text(event, 200))}',
                            self._styles['timeline_item'],
                        )
                    )

            elements.append(Spacer(1, 4 * mm))

        return elements

    # -----------------------------------------------------------------------
    # Construcao da capa
    # -----------------------------------------------------------------------

    def _build_cover_page(self, metadata: dict[str, Any]) -> list[Any]:
        """
        Constroi os elementos da pagina de capa.

        Args:
            metadata: Metadados da execucao.

        Returns:
            Lista de flowables para a capa.
        """
        elements: list[Any] = []

        # Espaco superior para centralizar visualmente
        elements.append(Spacer(1, 6 * cm))

        # Linha decorativa superior
        elements.append(
            HRFlowable(
                width='60%',
                thickness=2,
                color=_COLOR_PRIMARY,
                spaceBefore=0,
                spaceAfter=8 * mm,
                hAlign='CENTER',
            )
        )

        # Titulo principal
        elements.append(
            Paragraph(
                'Relat\u00f3rio de Execu\u00e7\u00e3o',
                self._styles['cover_title'],
            )
        )

        # Subtitulo com nome da plataforma
        elements.append(
            Paragraph(
                'AgentVision',
                self._styles['cover_subtitle'],
            )
        )

        # Linha decorativa inferior
        elements.append(
            HRFlowable(
                width='60%',
                thickness=2,
                color=_COLOR_PRIMARY,
                spaceBefore=8 * mm,
                spaceAfter=12 * mm,
                hAlign='CENTER',
            )
        )

        # Informacoes do projeto e job
        project_name = self._safe_text(
            metadata.get('project_name', 'N/A'), 200
        )
        job_name = self._safe_text(metadata.get('job_name', 'N/A'), 200)
        execution_id = metadata.get('execution_id', 'N/A')
        base_url = metadata.get('base_url', '')

        elements.append(
            Paragraph(
                f'<b>Projeto:</b> {self._escape_html(project_name)}',
                self._styles['cover_info'],
            )
        )
        elements.append(
            Paragraph(
                f'<b>Job:</b> {self._escape_html(job_name)}',
                self._styles['cover_info'],
            )
        )

        if base_url:
            elements.append(
                Paragraph(
                    f'<b>URL Base:</b> {self._escape_html(self._safe_text(base_url, 200))}',
                    self._styles['cover_info'],
                )
            )

        elements.append(
            Paragraph(
                f'<b>ID da Execu\u00e7\u00e3o:</b> {self._escape_html(str(execution_id))}',
                self._styles['cover_info'],
            )
        )

        # Data e hora da execucao
        started_at = metadata.get('started_at')
        if started_at:
            if isinstance(started_at, datetime):
                date_str = started_at.strftime('%d/%m/%Y %H:%M:%S UTC')
            else:
                date_str = str(started_at)
        else:
            date_str = datetime.now(timezone.utc).strftime(
                '%d/%m/%Y %H:%M:%S UTC'
            )

        elements.append(Spacer(1, 4 * mm))
        elements.append(
            Paragraph(
                f'<b>Data:</b> {date_str}',
                self._styles['cover_info'],
            )
        )

        # Duracao se disponivel
        duration = metadata.get('duration')
        if duration is not None:
            elements.append(
                Paragraph(
                    f'<b>Dura\u00e7\u00e3o:</b> {duration}s',
                    self._styles['cover_info'],
                )
            )

        return elements

    # -----------------------------------------------------------------------
    # Secao de screenshots com legendas contextuais (11.2.3)
    # -----------------------------------------------------------------------

    def _build_screenshots_section(
        self,
        screenshots: list[bytes],
        *,
        screenshot_contexts: list[dict[str, Any]] | None = None,
    ) -> list[Any]:
        """
        Constroi a secao de screenshots do relatorio com legendas contextuais.

        Quando screenshot_contexts e fornecido, usa URL, acao e timestamp
        em vez de legendas genericas "Screenshot 1 de N".

        Args:
            screenshots: Lista de screenshots em bytes (ja validados).
            screenshot_contexts: Lista opcional com contexto por screenshot.
                Cada dict pode ter: url, action, timestamp.

        Returns:
            Lista de flowables para a secao de screenshots.
        """
        elements: list[Any] = []

        elements.append(
            Paragraph('Screenshots Capturados', self._styles['section_title'])
        )
        elements.append(
            HRFlowable(
                width='100%',
                thickness=1,
                color=_COLOR_PRIMARY,
                spaceAfter=6 * mm,
            )
        )

        total = len(screenshots)
        # Largura maxima disponivel para a imagem no frame
        max_width = _PAGE_WIDTH - 4 * cm  # descontando margens
        max_height = _PAGE_HEIGHT - 8 * cm  # espaco para caption e margens

        contexts = screenshot_contexts or []

        for index, screenshot_bytes in enumerate(screenshots, start=1):
            try:
                img_buffer = io.BytesIO(screenshot_bytes)
                img = Image(img_buffer)

                # Calcula dimensoes proporcionais que cabem na pagina
                original_width = img.drawWidth
                original_height = img.drawHeight

                if original_width > 0 and original_height > 0:
                    ratio = min(
                        max_width / original_width,
                        max_height / original_height,
                    )
                    img.drawWidth = original_width * ratio
                    img.drawHeight = original_height * ratio
                else:
                    # Fallback: dimensoes fixas caso nao consiga detectar
                    img.drawWidth = max_width
                    img.drawHeight = max_width * 0.75

                img.hAlign = 'CENTER'

                # Constroi legenda contextual (11.2.3)
                caption_text = self._build_screenshot_caption(
                    index=index,
                    total=total,
                    context=contexts[index - 1] if index - 1 < len(contexts) else None,
                )

                caption = Paragraph(
                    self._escape_html(caption_text),
                    self._styles['caption'],
                )
                elements.append(KeepTogether([img, caption]))
                elements.append(Spacer(1, 4 * mm))

            except Exception as e:
                logger.warning(
                    'Erro ao processar screenshot %d: %s', index, str(e)
                )
                elements.append(
                    Paragraph(
                        f'<i>[Erro ao carregar screenshot {index}: '
                        f'{self._escape_html(self._safe_text(str(e), 200))}]</i>',
                        self._styles['body_small'],
                    )
                )
                elements.append(Spacer(1, 4 * mm))

        return elements

    def _build_screenshot_caption(
        self,
        index: int,
        total: int,
        context: dict[str, Any] | None,
    ) -> str:
        """
        Constroi legenda contextual para um screenshot.

        Se o contexto esta disponivel, usa URL/acao/timestamp.
        Caso contrario, retorna legenda generica.

        Args:
            index: Numero do screenshot (1-based).
            total: Total de screenshots.
            context: Dicionario opcional com url, action, timestamp.

        Returns:
            Texto da legenda.
        """
        if not context:
            return f'Screenshot {index} de {total}'

        parts: list[str] = []

        # Acao ou descricao
        action = context.get('action', '')
        url = context.get('url', '')

        if action and url:
            # Combina acao com URL truncada
            url_display = url if len(url) <= 60 else url[:57] + '...'
            parts.append(f'{action} - {url_display}')
        elif action:
            parts.append(action)
        elif url:
            url_display = url if len(url) <= 80 else url[:77] + '...'
            parts.append(url_display)
        else:
            parts.append(f'Screenshot {index} de {total}')

        # Timestamp
        timestamp = context.get('timestamp')
        if timestamp:
            if isinstance(timestamp, datetime):
                ts_str = timestamp.strftime('%H:%M:%S')
            else:
                ts_str = str(timestamp)
            parts.append(f'[{ts_str}]')

        return ' '.join(parts)

    # -----------------------------------------------------------------------
    # Secao de analise textual
    # -----------------------------------------------------------------------

    def _build_analysis_section(self, analysis_text: str) -> list[Any]:
        """
        Constroi a secao de analise textual do LLM.

        Processa o texto de analise em paragrafos e formata marcadores de secao.

        Args:
            analysis_text: Texto completo da analise retornada pelo LLM.

        Returns:
            Lista de flowables para a secao de analise.
        """
        elements: list[Any] = []

        elements.append(
            Paragraph('An\u00e1lise Visual', self._styles['section_title'])
        )
        elements.append(
            HRFlowable(
                width='100%',
                thickness=1,
                color=_COLOR_PRIMARY,
                spaceAfter=6 * mm,
            )
        )

        # Remove blocos JSON do texto de analise para exibicao limpa
        clean_text = self._strip_json_blocks(analysis_text)

        # Divide em paragrafos e formata
        paragraphs = clean_text.split('\n')
        for line in paragraphs:
            stripped = line.strip()
            if not stripped:
                elements.append(Spacer(1, 2 * mm))
                continue

            # Aplica safe_text para cada linha
            stripped = self._safe_text(stripped, max_length=2000)

            # Detecta titulos de secao (### ou ##)
            if stripped.startswith('###'):
                title_text = stripped.lstrip('#').strip()
                elements.append(
                    Paragraph(
                        self._escape_html(title_text),
                        self._styles['subsection_title'],
                    )
                )
            elif stripped.startswith('##'):
                title_text = stripped.lstrip('#').strip()
                elements.append(
                    Paragraph(
                        self._escape_html(title_text),
                        self._styles['subsection_title'],
                    )
                )
            elif stripped.startswith('- ') or stripped.startswith('* '):
                # Itens de lista
                item_text = stripped[2:].strip()
                elements.append(
                    Paragraph(
                        f'\u2022 {self._escape_html(item_text)}',
                        self._styles['insight_item'],
                    )
                )
            elif stripped.startswith('**') and stripped.endswith('**'):
                # Texto em negrito (titulo inline)
                bold_text = stripped.strip('*').strip()
                elements.append(
                    Paragraph(
                        f'<b>{self._escape_html(bold_text)}</b>',
                        self._styles['body'],
                    )
                )
            else:
                elements.append(
                    Paragraph(
                        self._escape_html(stripped),
                        self._styles['body'],
                    )
                )

        return elements

    # -----------------------------------------------------------------------
    # Secao de dados extraidos
    # -----------------------------------------------------------------------

    def _build_extracted_data_section(
        self, extracted_data: dict[str, Any]
    ) -> list[Any]:
        """
        Constroi a secao de dados extraidos em formato de tabela.

        Processa o dicionario de dados extraidos e apresenta
        em pares chave-valor usando uma tabela estilizada.
        Tabelas com muitas colunas sao auto-ajustadas.

        Args:
            extracted_data: Dicionario com dados extraidos pelo LLM.

        Returns:
            Lista de flowables para a secao de dados extraidos.
        """
        elements: list[Any] = []

        elements.append(
            Paragraph(
                'Dados Extra\u00eddos', self._styles['section_title']
            )
        )
        elements.append(
            HRFlowable(
                width='100%',
                thickness=1,
                color=_COLOR_PRIMARY,
                spaceAfter=6 * mm,
            )
        )

        # Filtra chaves especiais que tem secoes proprias
        filtered_data = {
            k: v
            for k, v in extracted_data.items()
            if k not in ('insights', 'summary')
        }

        if not filtered_data:
            elements.append(
                Paragraph(
                    '<i>Nenhum dado estruturado extra\u00eddo.</i>',
                    self._styles['body_small'],
                )
            )
            return elements

        # Constroi tabela de dados
        table_data: list[list[Any]] = []

        # Header
        table_data.append([
            Paragraph('Campo', self._styles['table_header']),
            Paragraph('Valor', self._styles['table_header']),
        ])

        # Linhas de dados
        for key, value in filtered_data.items():
            key_label = self._format_key_label(key)

            if isinstance(value, dict):
                # Sub-dicionarios: formata como JSON indentado
                value_text = json.dumps(value, ensure_ascii=False, indent=2)
                value_text = self._safe_text(value_text, max_length=500)
                formatted_value = Paragraph(
                    f'<font face="Courier" size="8">'
                    f'{self._escape_html(value_text)}'
                    f'</font>',
                    self._styles['table_cell'],
                )
            elif isinstance(value, list):
                # Listas: formata como itens separados por virgula
                list_items = [str(item) for item in value]
                value_text = ', '.join(list_items)
                value_text = self._safe_text(value_text, max_length=500)
                formatted_value = Paragraph(
                    self._escape_html(value_text),
                    self._styles['table_cell'],
                )
            else:
                value_text = str(value) if value is not None else 'N/A'
                value_text = self._safe_text(value_text, max_length=500)
                formatted_value = Paragraph(
                    self._escape_html(value_text),
                    self._styles['table_cell'],
                )

            table_data.append([
                Paragraph(
                    f'<b>{self._escape_html(key_label)}</b>',
                    self._styles['table_cell'],
                ),
                formatted_value,
            ])

        # Larguras das colunas: 30% chave, 70% valor
        available_width = _PAGE_WIDTH - 4 * cm
        col_widths = [available_width * 0.30, available_width * 0.70]

        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        # Estilo da tabela
        style_commands: list[tuple] = [
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), _COLOR_TABLE_HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            # Corpo
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            # Alinhamento
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            # Bordas
            ('GRID', (0, 0), (-1, -1), 0.5, _COLOR_TABLE_BORDER),
            ('BOX', (0, 0), (-1, -1), 1, _COLOR_TABLE_BORDER),
        ]

        # Linhas alternadas
        for row_idx in range(1, len(table_data)):
            if row_idx % 2 == 0:
                style_commands.append(
                    ('BACKGROUND', (0, row_idx), (-1, row_idx), _COLOR_TABLE_ROW_ALT)
                )

        table.setStyle(TableStyle(style_commands))
        elements.append(table)
        elements.append(Spacer(1, 6 * mm))

        return elements

    # -----------------------------------------------------------------------
    # Secao de insights
    # -----------------------------------------------------------------------

    def _build_insights_section(
        self, insights: list[str]
    ) -> list[Any]:
        """
        Constroi a secao de insights do relatorio.

        Args:
            insights: Lista de strings com insights/observacoes.

        Returns:
            Lista de flowables para a secao de insights.
        """
        elements: list[Any] = []

        elements.append(
            Paragraph('Insights e Observa\u00e7\u00f5es', self._styles['section_title'])
        )
        elements.append(
            HRFlowable(
                width='100%',
                thickness=1,
                color=_COLOR_PRIMARY,
                spaceAfter=6 * mm,
            )
        )

        for index, insight in enumerate(insights, start=1):
            if isinstance(insight, str) and insight.strip():
                safe_insight = self._safe_text(insight.strip(), max_length=1000)
                elements.append(
                    Paragraph(
                        f'<b>{index}.</b> {self._escape_html(safe_insight)}',
                        self._styles['insight_item'],
                    )
                )

        elements.append(Spacer(1, 6 * mm))
        return elements

    # -----------------------------------------------------------------------
    # Resumo final da execucao
    # -----------------------------------------------------------------------

    def _build_execution_summary(
        self,
        metadata: dict[str, Any],
        analysis: AnalysisResult,
    ) -> list[Any]:
        """
        Constroi o resumo final com metadados da execucao.

        Args:
            metadata: Metadados da execucao.
            analysis: Resultado da analise.

        Returns:
            Lista de flowables para o resumo.
        """
        elements: list[Any] = []

        elements.append(
            Paragraph(
                'Resumo da Execu\u00e7\u00e3o', self._styles['section_title']
            )
        )
        elements.append(
            HRFlowable(
                width='100%',
                thickness=1,
                color=_COLOR_PRIMARY,
                spaceAfter=6 * mm,
            )
        )

        # Monta tabela de resumo
        summary_rows: list[list[str]] = []

        if metadata.get('project_name'):
            summary_rows.append([
                'Projeto', self._safe_text(metadata['project_name'], 200)
            ])
        if metadata.get('job_name'):
            summary_rows.append([
                'Job', self._safe_text(metadata['job_name'], 200)
            ])
        if metadata.get('execution_id'):
            summary_rows.append(['ID da Execu\u00e7\u00e3o', str(metadata['execution_id'])])
        if metadata.get('base_url'):
            summary_rows.append([
                'URL Base', self._safe_text(metadata['base_url'], 200)
            ])

        # Timestamps
        started_at = metadata.get('started_at')
        if started_at:
            if isinstance(started_at, datetime):
                summary_rows.append([
                    'In\u00edcio',
                    started_at.strftime('%d/%m/%Y %H:%M:%S UTC'),
                ])
            else:
                summary_rows.append(['In\u00edcio', str(started_at)])

        finished_at = metadata.get('finished_at')
        if finished_at:
            if isinstance(finished_at, datetime):
                summary_rows.append([
                    'T\u00e9rmino',
                    finished_at.strftime('%d/%m/%Y %H:%M:%S UTC'),
                ])
            else:
                summary_rows.append(['T\u00e9rmino', str(finished_at)])

        duration = metadata.get('duration')
        if duration is not None:
            summary_rows.append(['Dura\u00e7\u00e3o', f'{duration} segundos'])

        # Informacoes da analise
        if analysis.tokens_used > 0:
            summary_rows.append(['Tokens Utilizados', str(analysis.tokens_used)])

        if analysis.extracted_data:
            status = analysis.extracted_data.get('status', 'N/A')
            summary_rows.append(['Status da An\u00e1lise', str(status)])

            confidence = analysis.extracted_data.get('confidence')
            if confidence is not None:
                confidence_pct = f'{float(confidence) * 100:.1f}%'
                summary_rows.append(['Confian\u00e7a', confidence_pct])

        if not summary_rows:
            return elements

        # Constroi tabela formatada
        table_data: list[list[Any]] = []
        table_data.append([
            Paragraph('Par\u00e2metro', self._styles['table_header']),
            Paragraph('Valor', self._styles['table_header']),
        ])

        for key_label, value_text in summary_rows:
            table_data.append([
                Paragraph(
                    f'<b>{self._escape_html(key_label)}</b>',
                    self._styles['table_cell'],
                ),
                Paragraph(
                    self._escape_html(str(value_text)),
                    self._styles['table_cell'],
                ),
            ])

        available_width = _PAGE_WIDTH - 4 * cm
        col_widths = [available_width * 0.35, available_width * 0.65]

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        style_commands: list[tuple] = [
            ('BACKGROUND', (0, 0), (-1, 0), _COLOR_TABLE_HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, _COLOR_TABLE_BORDER),
            ('BOX', (0, 0), (-1, -1), 1, _COLOR_TABLE_BORDER),
        ]

        for row_idx in range(1, len(table_data)):
            if row_idx % 2 == 0:
                style_commands.append(
                    ('BACKGROUND', (0, row_idx), (-1, row_idx), _COLOR_TABLE_ROW_ALT)
                )

        table.setStyle(TableStyle(style_commands))
        elements.append(table)

        return elements

    # -----------------------------------------------------------------------
    # Funcoes de header/footer/watermark para o canvas (11.2.4)
    # -----------------------------------------------------------------------

    @staticmethod
    def _draw_first_page(canvas: Any, doc: Any) -> None:
        """
        Desenha elementos fixos na primeira pagina (capa).

        Adiciona borda decorativa, rodape e marca d'agua sutil.

        Args:
            canvas: Canvas do ReportLab.
            doc: Documento sendo construido.
        """
        canvas.saveState()

        # Borda decorativa na capa (linha fina ao redor)
        canvas.setStrokeColor(_COLOR_PRIMARY)
        canvas.setLineWidth(1.5)
        margin = 1.5 * cm
        canvas.rect(
            margin,
            margin,
            _PAGE_WIDTH - 2 * margin,
            _PAGE_HEIGHT - 2 * margin,
        )

        # Rodape da capa
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(_COLOR_TEXT_MUTED)
        canvas.drawCentredString(
            _PAGE_WIDTH / 2.0,
            1.8 * cm,
            'Gerado automaticamente pelo AgentVision',
        )

        canvas.restoreState()

    @staticmethod
    def _draw_later_pages(canvas: Any, doc: Any) -> None:
        """
        Desenha elementos fixos nas paginas subsequentes.

        Inclui header com titulo, linha separadora, marca d'agua sutil
        e rodape com linha. O numero de pagina "X de Y" e gerenciado
        pelo _NumberedCanvas.

        Args:
            canvas: Canvas do ReportLab.
            doc: Documento sendo construido.
        """
        canvas.saveState()

        # Header: titulo e linha
        canvas.setFont('Helvetica-Bold', 9)
        canvas.setFillColor(_COLOR_PRIMARY)
        canvas.drawString(2 * cm, _PAGE_HEIGHT - 1.2 * cm, 'AgentVision')

        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(_COLOR_TEXT_MUTED)
        canvas.drawRightString(
            _PAGE_WIDTH - 2 * cm,
            _PAGE_HEIGHT - 1.2 * cm,
            'Relat\u00f3rio de Execu\u00e7\u00e3o',
        )

        # Linha do header
        canvas.setStrokeColor(_COLOR_PRIMARY)
        canvas.setLineWidth(0.5)
        canvas.line(
            2 * cm,
            _PAGE_HEIGHT - 1.5 * cm,
            _PAGE_WIDTH - 2 * cm,
            _PAGE_HEIGHT - 1.5 * cm,
        )

        # Marca d'agua sutil (11.2.4) — texto diagonal semi-transparente
        canvas.saveState()
        canvas.translate(_PAGE_WIDTH / 2.0, _PAGE_HEIGHT / 2.0)
        canvas.rotate(45)
        canvas.setFont('Helvetica', 40)
        canvas.setFillColor(colors.HexColor('#E5E7EB'))
        canvas.setFillAlpha(0.08)
        canvas.drawCentredString(0, 0, 'Gerado por AgentVision')
        canvas.restoreState()

        # Linha do rodape
        canvas.setStrokeColor(_COLOR_BORDER)
        canvas.setLineWidth(0.3)
        canvas.line(
            2 * cm,
            1.8 * cm,
            _PAGE_WIDTH - 2 * cm,
            1.8 * cm,
        )

        canvas.restoreState()

    # -----------------------------------------------------------------------
    # Utilitarios
    # -----------------------------------------------------------------------

    @staticmethod
    def _escape_html(text: str) -> str:
        """
        Escapa caracteres especiais HTML para uso seguro em Paragraph.

        Args:
            text: Texto a ser escapado.

        Returns:
            Texto com caracteres HTML escapados.
        """
        return (
            text.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
        )

    @staticmethod
    def _strip_json_blocks(text: str) -> str:
        """
        Remove blocos de codigo JSON do texto de analise.

        Blocos no formato ```json ... ``` sao removidos para exibicao limpa
        na secao de analise textual (dados sao exibidos na secao de dados).

        Args:
            text: Texto completo da analise.

        Returns:
            Texto sem blocos JSON.
        """
        # Remove blocos ```json ... ```
        cleaned = re.sub(r'```(?:json)?\s*\n?[\s\S]*?\n?```', '', text)
        # Remove linhas vazias consecutivas resultantes
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

    @staticmethod
    def _format_key_label(key: str) -> str:
        """
        Formata uma chave de dicionario para exibicao como rotulo legivel.

        Converte snake_case e camelCase para formato com espacos e capitalizado.

        Args:
            key: Chave original do dicionario.

        Returns:
            Rotulo formatado para exibicao.
        """
        # Converte camelCase para espaco
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', key)
        # Converte snake_case para espaco
        label = label.replace('_', ' ')
        # Capitaliza primeira letra de cada palavra
        return label.title()

    @staticmethod
    def _truncate_text(text: str, max_length: int = 500) -> str:
        """
        Trunca texto longo, adicionando reticencias se necessario.

        Args:
            text: Texto a ser truncado.
            max_length: Comprimento maximo permitido.

        Returns:
            Texto truncado (ou original se menor que o limite).
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + '...'
