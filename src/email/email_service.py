import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import jinja2
from jinja2 import Environment, FileSystemLoader
from ..models import (
    Client,
    RiskAlert,
    EmailReport,
    SectorType,
    RiskLevel,
    Article,
    Source,
)
from ..database import AsyncSessionLocal
from ..config import settings
from sqlalchemy import select, and_, or_

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.smtp_server = settings.smtp_server
        self.smtp_port = settings.smtp_port
        self.email_user = settings.email_user
        self.email_password = settings.email_password
        self.from_email = settings.from_email

        # Initialize Jinja2 for email templates
        self.template_env = Environment(
            loader=FileSystemLoader("src/email/templates"),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
        )

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """Send individual email"""
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self.from_email
            msg["To"] = to_email
            msg["Subject"] = subject

            # Add text content
            if text_content:
                msg.attach(MIMEText(text_content, "plain", "utf-8"))

            # Add HTML content
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    def generate_daily_report(
        self, client: Client, alerts: List[RiskAlert]
    ) -> Dict[str, str]:
        """Generate daily risk report for client"""
        template = self.template_env.get_template("daily_report.html")

        # Organize alerts by sector and risk level
        alerts_by_sector = {}
        critical_alerts = []
        high_alerts = []

        for alert in alerts:
            if alert.sector not in alerts_by_sector:
                alerts_by_sector[alert.sector] = []
            alerts_by_sector[alert.sector].append(alert)

            if alert.risk_level == RiskLevel.CRITICAL:
                critical_alerts.append(alert)
            elif alert.risk_level == RiskLevel.HIGH:
                high_alerts.append(alert)

        # Calculate statistics
        stats = {
            "total_alerts": len(alerts),
            "critical_count": len(critical_alerts),
            "high_count": len(high_alerts),
            "sectors_affected": len(alerts_by_sector),
            "top_sector": (
                max(alerts_by_sector.keys(), key=lambda x: len(alerts_by_sector[x]))
                if alerts_by_sector
                else None
            ),
        }

        html_content = template.render(
            client=client,
            alerts=alerts,
            alerts_by_sector=alerts_by_sector,
            critical_alerts=critical_alerts,
            high_alerts=high_alerts,
            stats=stats,
            date=datetime.now().strftime("%d de %B de %Y"),
            echoframe_url=settings.frontend_url,
        )

        # Generate subject
        if critical_alerts:
            subject = f"🚨 ALERTA CRÍTICA - {len(critical_alerts)} riesgos críticos detectados"
        elif high_alerts:
            subject = f"⚠️ ALERTA ALTA - {len(high_alerts)} riesgos altos detectados"
        else:
            subject = f"📊 Reporte Diario EchoFrame - {len(alerts)} alertas"

        return {
            "subject": subject,
            "html_content": html_content,
            "text_content": self._generate_text_summary(alerts, stats),
        }

    def generate_critical_alert(
        self, client: Client, alert: RiskAlert
    ) -> Dict[str, str]:
        """Generate immediate critical alert email"""
        template = self.template_env.get_template("critical_alert.html")

        html_content = template.render(
            client=client,
            alert=alert,
            article=alert.article,
            timestamp=datetime.now().strftime("%d de %B de %Y - %H:%M"),
            echoframe_url=settings.frontend_url,
        )

        subject = f"🚨 RIESGO CRÍTICO DETECTADO - {alert.sector.value.upper()} en {alert.article.source.state}"

        return {
            "subject": subject,
            "html_content": html_content,
            "text_content": f"RIESGO CRÍTICO: {alert.summary}",
        }

    def _generate_text_summary(self, alerts: List[RiskAlert], stats: Dict) -> str:
        """Generate plain text summary"""
        text = f"""
REPORTE DIARIO ECHOFRAME
========================

Resumen del día:
- Total de alertas: {stats['total_alerts']}
- Alertas críticas: {stats['critical_count']}
- Alertas altas: {stats['high_count']}
- Sectores afectados: {stats['sectors_affected']}

ALERTAS CRÍTICAS:
"""

        critical_alerts = [a for a in alerts if a.risk_level == RiskLevel.CRITICAL]
        for alert in critical_alerts[:5]:  # Top 5
            text += f"- {alert.summary}\n"

        text += "\nPara ver el reporte completo, visita: " + settings.frontend_url
        return text

    async def get_client_alerts(
        self, client: Client, hours_back: int = 24
    ) -> List[RiskAlert]:
        """Get relevant alerts for a client"""
        cutoff_date = datetime.now() - timedelta(hours=hours_back)

        async with AsyncSessionLocal() as db:
            query = select(RiskAlert).where(
                and_(RiskAlert.created_at >= cutoff_date, RiskAlert.is_sent == False)
            )

            # Filter by client's sectors
            if client.sectors:
                query = query.where(RiskAlert.sector.in_(client.sectors))

            # Filter by client's states
            if client.states:
                query = (
                    query.join(RiskAlert.article)
                    .join(Article.source)
                    .where(
                        or_(
                            *[
                                Source.state.ilike(f"%{state}%")
                                for state in client.states
                            ]
                        )
                    )
                )

            result = await db.execute(query.order_by(RiskAlert.risk_score.desc()))
            return result.scalars().all()

    async def send_daily_reports(self) -> Dict[str, int]:
        """Send daily reports to all active clients"""
        results = {"sent": 0, "failed": 0, "no_alerts": 0}

        async with AsyncSessionLocal() as db:
            # Get active clients with daily frequency
            result = await db.execute(
                select(Client).where(
                    and_(
                        Client.is_active == True,
                        Client.notification_frequency == "daily",
                    )
                )
            )
            clients = result.scalars().all()

            for client in clients:
                try:
                    alerts = await self.get_client_alerts(client, hours_back=24)

                    if not alerts:
                        results["no_alerts"] += 1
                        continue

                    # Generate report
                    email_content = self.generate_daily_report(client, alerts)

                    # Send email
                    success = await self.send_email(
                        client.email,
                        email_content["subject"],
                        email_content["html_content"],
                        email_content["text_content"],
                    )

                    if success:
                        # Store email report
                        email_report = EmailReport(
                            client_id=client.id,
                            subject=email_content["subject"],
                            content=email_content["html_content"],
                            alert_ids=[alert.id for alert in alerts],
                            sent_at=datetime.now(),
                            status="sent",
                        )
                        db.add(email_report)

                        # Mark alerts as sent
                        for alert in alerts:
                            alert.is_sent = True

                        results["sent"] += 1
                    else:
                        results["failed"] += 1

                except Exception as e:
                    logger.error(
                        f"Error sending daily report to {client.email}: {str(e)}"
                    )
                    results["failed"] += 1

            await db.commit()

        logger.info(f"Daily reports completed: {results}")
        return results

    async def send_critical_alerts(self, hours_back: int = 1) -> Dict[str, int]:
        """Send immediate alerts for critical risks"""
        results = {"sent": 0, "failed": 0}

        cutoff_date = datetime.now() - timedelta(hours=hours_back)

        async with AsyncSessionLocal() as db:
            # Get unsent critical alerts
            result = await db.execute(
                select(RiskAlert)
                .where(
                    and_(
                        RiskAlert.risk_level == RiskLevel.CRITICAL,
                        RiskAlert.created_at >= cutoff_date,
                        RiskAlert.is_sent == False,
                    )
                )
                .order_by(RiskAlert.created_at.desc())
            )
            critical_alerts = result.scalars().all()

            for alert in critical_alerts:
                # Get relevant clients
                clients_result = await db.execute(
                    select(Client).where(
                        and_(
                            Client.is_active == True,
                            or_(
                                Client.sectors.contains([alert.sector]),
                                Client.states.contains([alert.article.source.state]),
                            ),
                        )
                    )
                )
                relevant_clients = clients_result.scalars().all()

                for client in relevant_clients:
                    try:
                        email_content = self.generate_critical_alert(client, alert)

                        success = await self.send_email(
                            client.email,
                            email_content["subject"],
                            email_content["html_content"],
                            email_content["text_content"],
                        )

                        if success:
                            results["sent"] += 1
                        else:
                            results["failed"] += 1

                    except Exception as e:
                        logger.error(
                            f"Error sending critical alert to {client.email}: {str(e)}"
                        )
                        results["failed"] += 1

                # Mark alert as sent after processing all clients
                alert.is_sent = True

            await db.commit()

        logger.info(f"Critical alerts completed: {results}")
        return results

    async def send_weekly_summary(self) -> Dict[str, int]:
        """Send weekly summary reports"""
        results = {"sent": 0, "failed": 0}

        async with AsyncSessionLocal() as db:
            # Get clients with weekly frequency
            result = await db.execute(
                select(Client).where(
                    and_(
                        Client.is_active == True,
                        Client.notification_frequency == "weekly",
                    )
                )
            )
            clients = result.scalars().all()

            for client in clients:
                try:
                    # Get last week's alerts
                    alerts = await self.get_client_alerts(
                        client, hours_back=168
                    )  # 7 days

                    if alerts:
                        email_content = self.generate_weekly_summary(client, alerts)

                        success = await self.send_email(
                            client.email,
                            email_content["subject"],
                            email_content["html_content"],
                            email_content["text_content"],
                        )

                        if success:
                            results["sent"] += 1
                        else:
                            results["failed"] += 1

                except Exception as e:
                    logger.error(
                        f"Error sending weekly summary to {client.email}: {str(e)}"
                    )
                    results["failed"] += 1

        return results

    def generate_weekly_summary(
        self, client: Client, alerts: List[RiskAlert]
    ) -> Dict[str, str]:
        """Generate weekly summary report"""
        template = self.template_env.get_template("weekly_summary.html")

        # Weekly statistics
        stats = self._calculate_weekly_stats(alerts)

        html_content = template.render(
            client=client,
            alerts=alerts,
            stats=stats,
            week_start=(datetime.now() - timedelta(days=7)).strftime("%d de %B"),
            week_end=datetime.now().strftime("%d de %B de %Y"),
            echoframe_url=settings.frontend_url,
        )

        subject = f"📈 Resumen Semanal EchoFrame - {len(alerts)} alertas detectadas"

        return {
            "subject": subject,
            "html_content": html_content,
            "text_content": f"Resumen semanal: {len(alerts)} alertas detectadas en los últimos 7 días.",
        }

    def _calculate_weekly_stats(self, alerts: List[RiskAlert]) -> Dict:
        """Calculate weekly statistics"""
        stats = {
            "total_alerts": len(alerts),
            "critical_count": len(
                [a for a in alerts if a.risk_level == RiskLevel.CRITICAL]
            ),
            "high_count": len([a for a in alerts if a.risk_level == RiskLevel.HIGH]),
            "sectors": {},
            "trend": "stable",
        }

        for alert in alerts:
            sector = alert.sector.value
            if sector not in stats["sectors"]:
                stats["sectors"][sector] = 0
            stats["sectors"][sector] += 1

        return stats
