import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.modules.delivery.base_channel import DeliveryChannel, DeliveryResult

logger = logging.getLogger(__name__)


# Template HTML basico para emails de entrega
EMAIL_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #0F1117;
            color: #F9FAFB;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #1A1D2E;
            border-radius: 8px;
            padding: 30px;
            border: 1px solid #2E3348;
        }}
        .header {{
            text-align: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid #2E3348;
        }}
        .header h1 {{
            color: #6366F1;
            font-size: 24px;
            margin: 0;
        }}
        .content {{
            margin-bottom: 24px;
            line-height: 1.6;
        }}
        .content p {{
            color: #9CA3AF;
            margin: 8px 0;
        }}
        .content .label {{
            color: #F9FAFB;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            padding-top: 16px;
            border-top: 1px solid #2E3348;
            color: #6B7280;
            font-size: 12px;
        }}
        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        .status-success {{
            background-color: rgba(16, 185, 129, 0.2);
            color: #10B981;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AgentVision - Relatorio</h1>
        </div>
        <div class="content">
            <p><span class="label">Job:</span> {job_name}</p>
            <p><span class="label">Status:</span>
                <span class="status-badge status-success">Concluido</span>
            </p>
            <p><span class="label">Data:</span> {execution_date}</p>
            {extra_content}
        </div>
        <div class="footer">
            <p>Este email foi gerado automaticamente pelo AgentVision.</p>
            <p>Nao responda a este email.</p>
        </div>
    </div>
</body>
</html>
"""


class EmailChannel(DeliveryChannel):
    """
    Canal de entrega por email.

    Envia emails com relatorio PDF anexado via SMTP.
    As configuracoes de SMTP sao fornecidas via parametros
    (carregadas da tabela Settings ou variaveis de ambiente).
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        smtp_from: str,
        smtp_use_tls: bool = True,
    ) -> None:
        """
        Inicializa o canal de email com configuracoes SMTP.

        Args:
            smtp_host: Host do servidor SMTP.
            smtp_port: Porta do servidor SMTP.
            smtp_user: Usuario para autenticacao SMTP.
            smtp_password: Senha para autenticacao SMTP.
            smtp_from: Endereco de email do remetente.
            smtp_use_tls: Se deve usar TLS (padrao: True).
        """
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_password = smtp_password
        self._smtp_from = smtp_from
        self._smtp_use_tls = smtp_use_tls

    def send(
        self,
        recipients: list[str],
        pdf_path: str | None,
        config: dict | None,
        execution_data: dict | None = None,
    ) -> DeliveryResult:
        """
        Envia email com PDF anexado para os destinatarios.

        Args:
            recipients: Lista de enderecos de email dos destinatarios.
            pdf_path: Caminho local do arquivo PDF para anexar.
            config: Configuracoes do canal (ex: subject, body_text).
            execution_data: Dados da execucao para incluir no corpo do email.

        Returns:
            DeliveryResult indicando sucesso ou falha.
        """
        try:
            # Configuracoes do email
            subject = 'AgentVision - Relatorio de Execucao'
            if config and config.get('subject'):
                subject = config['subject']

            job_name = 'N/A'
            execution_date = 'N/A'
            project_name = 'N/A'
            summary = ''
            status = 'success'
            extra_content = ''

            if execution_data:
                job_name = execution_data.get('job_name', 'N/A')
                execution_date = execution_data.get('execution_date', 'N/A')
                project_name = execution_data.get('project_name', 'N/A')
                summary = execution_data.get('summary', '') or execution_data.get('analysis_text', '')
                status = execution_data.get('status', 'success')

                # Conteudo extra opcional
                if summary:
                    extra_content = (
                        f'<p><span class="label">Resumo:</span> '
                        f'{summary[:500]}</p>'
                    )

            # Tenta usar template customizado (passado via config)
            custom_template = (config or {}).get('_email_template_content')
            if custom_template:
                html_body = self._render_custom_template(
                    template=custom_template,
                    project_name=project_name,
                    job_name=job_name,
                    execution_date=execution_date,
                    summary=summary,
                    status=status,
                )
            else:
                # Template padrao
                html_body = EMAIL_HTML_TEMPLATE.format(
                    job_name=job_name,
                    execution_date=execution_date,
                    extra_content=extra_content,
                )

            # Monta o email
            msg = MIMEMultipart()
            msg['From'] = self._smtp_from
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject

            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

            # Anexa o PDF, se disponivel
            if pdf_path:
                try:
                    pdf_file = Path(pdf_path)
                    if pdf_file.exists():
                        with open(pdf_file, 'rb') as f:
                            pdf_attachment = MIMEApplication(
                                f.read(),
                                _subtype='pdf',
                            )
                            pdf_attachment.add_header(
                                'Content-Disposition',
                                'attachment',
                                filename=pdf_file.name,
                            )
                            msg.attach(pdf_attachment)
                    else:
                        logger.warning(
                            'Arquivo PDF nao encontrado para anexar: %s',
                            pdf_path,
                        )
                except Exception as e:
                    logger.warning(
                        'Erro ao anexar PDF ao email: %s',
                        str(e),
                    )

            # Envia o email via SMTP
            self._send_smtp(msg, recipients)

            logger.info(
                'Email enviado com sucesso para %d destinatarios',
                len(recipients),
            )
            return DeliveryResult(success=True)

        except smtplib.SMTPAuthenticationError as e:
            error_msg = f'Erro de autenticacao SMTP: {str(e)}'
            logger.error(error_msg)
            return DeliveryResult(success=False, error_message=error_msg)

        except smtplib.SMTPException as e:
            error_msg = f'Erro SMTP ao enviar email: {str(e)}'
            logger.error(error_msg)
            return DeliveryResult(success=False, error_message=error_msg)

        except Exception as e:
            error_msg = f'Erro inesperado ao enviar email: {str(e)}'
            logger.error(error_msg)
            return DeliveryResult(success=False, error_message=error_msg)

    @staticmethod
    def _render_custom_template(
        template: str,
        project_name: str,
        job_name: str,
        execution_date: str,
        summary: str,
        status: str,
    ) -> str:
        """
        Renderiza um template customizado substituindo variaveis.

        Variaveis suportadas:
            {{project_name}} - Nome do projeto
            {{job_name}} - Nome do job
            {{execution_date}} - Data da execucao
            {{summary}} - Resumo executivo (truncado a 500 caracteres)
            {{status}} - Status da execucao
        """
        rendered = template
        variables = {
            '{{project_name}}': project_name,
            '{{job_name}}': job_name,
            '{{execution_date}}': execution_date,
            '{{summary}}': summary[:500] if summary else '',
            '{{status}}': status,
        }
        for var, value in variables.items():
            rendered = rendered.replace(var, value)
        return rendered

    def _send_smtp(
        self,
        msg: MIMEMultipart,
        recipients: list[str],
    ) -> None:
        """
        Envia a mensagem via SMTP.

        Args:
            msg: Mensagem MIME montada.
            recipients: Lista de destinatarios.
        """
        if self._smtp_use_tls:
            with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self._smtp_user, self._smtp_password)
                server.sendmail(self._smtp_from, recipients, msg.as_string())
        else:
            with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
                server.ehlo()
                if self._smtp_user and self._smtp_password:
                    server.login(self._smtp_user, self._smtp_password)
                server.sendmail(self._smtp_from, recipients, msg.as_string())
