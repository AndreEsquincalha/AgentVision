import io
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, inch, mm
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

    return styles


class PDFGenerator:
    """
    Gerador de relatorios PDF profissionais para execucoes do AgentVision.

    Utiliza a biblioteca ReportLab para construir PDFs com layout estruturado
    contendo capa, screenshots, analise textual, dados extraidos e insights.
    """

    def __init__(self) -> None:
        """Inicializa o gerador com os estilos pre-configurados."""
        self._styles = _build_styles()

    # -----------------------------------------------------------------------
    # Metodo principal de geracao
    # -----------------------------------------------------------------------

    def generate(
        self,
        screenshots: list[bytes],
        analysis: AnalysisResult,
        metadata: dict[str, Any] | None = None,
    ) -> bytes:
        """
        Gera o relatorio PDF completo.

        Args:
            screenshots: Lista de screenshots em bytes (PNG/JPEG).
            analysis: Resultado da analise visual do LLM.
            metadata: Metadados da execucao (project_name, job_name,
                      execution_id, base_url, started_at, finished_at,
                      duration).

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
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                topMargin=2 * cm,
                bottomMargin=2.5 * cm,
                leftMargin=2 * cm,
                rightMargin=2 * cm,
                title='Relatorio de Execucao - AgentVision',
                author='AgentVision',
            )

            story: list[Any] = []

            # Capa
            story.extend(self._build_cover_page(metadata))

            # Secao de screenshots
            if screenshots:
                story.append(PageBreak())
                story.extend(self._build_screenshots_section(screenshots))

            # Secao de analise textual
            if analysis.text:
                story.append(PageBreak())
                story.extend(self._build_analysis_section(analysis.text))

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

            # Constroi o documento com funcoes de header/footer
            doc.build(
                story,
                onFirstPage=self._draw_first_page,
                onLaterPages=self._draw_later_pages,
            )

            pdf_bytes = buffer.getvalue()
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
    # Metodo de salvamento no storage
    # -----------------------------------------------------------------------

    @staticmethod
    def save_to_storage(
        pdf_bytes: bytes,
        execution_id: str,
        storage_client: StorageClient,
    ) -> str:
        """
        Salva o PDF gerado no MinIO/S3.

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

        logger.info(
            'Salvando PDF no storage: %s (tamanho: %d bytes)',
            key,
            len(pdf_bytes),
        )

        storage_client.upload_file(
            key=key,
            file_data=pdf_bytes,
            content_type='application/pdf',
        )

        logger.info('PDF salvo com sucesso: %s', key)
        return key

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
        project_name = metadata.get('project_name', 'N/A')
        job_name = metadata.get('job_name', 'N/A')
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
                    f'<b>URL Base:</b> {self._escape_html(base_url)}',
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
    # Secao de screenshots
    # -----------------------------------------------------------------------

    def _build_screenshots_section(
        self, screenshots: list[bytes]
    ) -> list[Any]:
        """
        Constroi a secao de screenshots do relatorio.

        Cada screenshot e inserido como imagem com legenda numerada.

        Args:
            screenshots: Lista de screenshots em bytes.

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

                # Agrupa imagem com legenda para nao separar entre paginas
                caption = Paragraph(
                    f'Screenshot {index} de {total}',
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
                        f'<i>[Erro ao carregar screenshot {index}: {self._escape_html(str(e))}]</i>',
                        self._styles['body_small'],
                    )
                )
                elements.append(Spacer(1, 4 * mm))

        return elements

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
            if k not in ('insights',)
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
                value_text = self._truncate_text(value_text, max_length=500)
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
                value_text = self._truncate_text(value_text, max_length=500)
                formatted_value = Paragraph(
                    self._escape_html(value_text),
                    self._styles['table_cell'],
                )
            else:
                value_text = str(value) if value is not None else 'N/A'
                value_text = self._truncate_text(value_text, max_length=500)
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
                elements.append(
                    Paragraph(
                        f'<b>{index}.</b> {self._escape_html(insight.strip())}',
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
            summary_rows.append(['Projeto', metadata['project_name']])
        if metadata.get('job_name'):
            summary_rows.append(['Job', metadata['job_name']])
        if metadata.get('execution_id'):
            summary_rows.append(['ID da Execu\u00e7\u00e3o', str(metadata['execution_id'])])
        if metadata.get('base_url'):
            summary_rows.append(['URL Base', metadata['base_url']])

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
    # Funcoes de header/footer para o canvas
    # -----------------------------------------------------------------------

    @staticmethod
    def _draw_first_page(canvas: Any, doc: Any) -> None:
        """
        Desenha elementos fixos na primeira pagina (capa).

        Adiciona borda decorativa e rodape minimalista.

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

        Adiciona header com titulo e linha, rodape com numero da pagina.

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

        # Rodape: numero da pagina
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(_COLOR_TEXT_MUTED)
        canvas.drawCentredString(
            _PAGE_WIDTH / 2.0,
            1.5 * cm,
            f'P\u00e1gina {doc.page}',
        )

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
