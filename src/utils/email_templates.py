"""Styled HTML email templates for AutoTech notifications."""

import base64
from pathlib import Path

from src.config.settings import settings

_FAVICON_B64: str | None = None


def _favicon_data_uri() -> str | None:
    """Return the favicon as a base64 data URI, cached after first load."""
    global _FAVICON_B64
    if _FAVICON_B64 is not None:
        return _FAVICON_B64
    # Try frontend public/favicon.svg
    candidates = [
        Path(__file__).resolve().parent.parent.parent.parent / "AutoTech-Frontend" / "public" / "favicon.svg",
        Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "favicon.svg",
    ]
    for p in candidates:
        if p.exists():
            _FAVICON_B64 = "data:image/svg+xml;base64," + base64.b64encode(p.read_bytes()).decode()
            return _FAVICON_B64
    _FAVICON_B64 = ""  # mark as not found so we don't keep trying
    return None


def _inline_favicon_svg() -> str:
    """Return inline SVG for the robot icon, suitable for email clients that don't render SVG img tags."""
    return '''<svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="28" height="28" style="vertical-align:middle;margin-right:10px;flex-shrink:0;" xmlns="http://www.w3.org/2000/svg">
  <rect x="4" y="4" width="16" height="12" rx="2" />
  <circle cx="9" cy="9" r="1.5" fill="#ffffff" stroke="none" />
  <circle cx="15" cy="9" r="1.5" fill="#ffffff" stroke="none" />
  <path d="M8 14h8" />
  <path d="M6 16v3" />
  <path d="M18 16v3" />
  <path d="M12 16v4" />
  <path d="M10 20h4" />
</svg>'''


def _base_template(title: str, content: str, accent_color: str = "#e85d3c", lang: str = "es") -> str:
    logo_html = _inline_favicon_svg()
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#0f0f12;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0f0f12;min-height:100vh;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table width="560" cellpadding="0" cellspacing="0" style="background-color:#1a1a20;border-radius:16px;overflow:hidden;max-width:560px;">
          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,{accent_color},{accent_color}dd);padding:24px 32px;">
              <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.3px;">
                {logo_html}AutoTech
              </h1>
              <p style="margin:4px 0 0;color:rgba(255,255,255,0.8);font-size:13px;">
                {title}
              </p>
            </td>
          </tr>
          <!-- Content -->
          <tr>
            <td style="padding:32px;color:#d4d4d8;font-size:14px;line-height:1.6;">
              {content}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:16px 32px 24px;border-top:1px solid #2a2a32;">
              <p style="margin:0;color:#71717a;font-size:11px;text-align:center;">
                {_s("Este es un mensaje automático de AutoTech. No respondas a este correo.", "This is an automated message from AutoTech. Do not reply to this email.", lang)}
              </p>
              <p style="margin:4px 0 0;color:#52525b;font-size:11px;text-align:center;">
                &copy; 2026 AutoTech. {_s("Todos los derechos reservados.", "All rights reserved.", lang)}
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _info_row(label: str, value: str) -> str:
    return f"""
      <tr>
        <td style="padding:8px 0;color:#a1a1aa;font-size:13px;">{label}</td>
        <td style="padding:8px 0;color:#ffffff;font-size:14px;font-weight:600;text-align:right;">{value}</td>
      </tr>"""


def _info_table(rows: list[tuple[str, str]]) -> str:
    body = "".join(_info_row(l, v) for l, v in rows)
    return f'<table width="100%" cellpadding="0" cellspacing="0">{body}</table>'


def _button(text: str, url: str) -> str:
    return f"""
      <a href="{url}" style="display:inline-block;background-color:#e85d3c;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;margin-top:8px;">
        {text}
      </a>"""


def _divider() -> str:
    return '<hr style="border:none;border-top:1px solid #2a2a32;margin:20px 0;">'


def _s(es: str, en: str, lang: str = "es") -> str:
    """Return text in the specified language."""
    return en if lang == "en" else es


# --- Notification templates ---

def purchase_confirmation(
    buyer_name: str,
    order_id: str,
    workshop_name: str,
    total: float,
    down_payment: float,
    financed: float,
    installment_count: int,
    installment_schedule: list[dict] | None = None,
    lang: str = "es",
) -> str:
    rows = [
        (_s("Orden", "Order", lang), f"#{order_id[:8]}"),
        (_s("Taller", "Workshop", lang), workshop_name),
        (_s("Total", "Total", lang), f"${total:.2f}"),
    ]
    if installment_count > 1:
        rows.append((_s("Pago inicial", "Down payment", lang), f"${down_payment:.2f}"))
        rows.append((_s("Financiado", "Financed", lang), f"${financed:.2f}"))
        rows.append((_s("Cuotas", "Installments", lang), str(installment_count)))
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{buyer_name}</strong>,</p>
      <p style="margin:0 0 20px;">{_s("Tu compra se ha registrado correctamente. Aquí tienes los detalles:", "Your purchase has been registered successfully. Here are the details:", lang)}</p>
      {_info_table(rows)}"""
    if installment_schedule and len(installment_schedule) > 1:
        _status_map = {
            "PAID": (_s("Pagado", "Paid", lang), "#22c55e"),
            "PENDING_VERIFICATION": (_s("Pendiente por verificación", "Pending verification", lang), "#f59e0b"),
            "PENDING": (_s("Programado", "Scheduled", lang), "#a1a1aa"),
            "OVERDUE": (_s("Vencido", "Overdue", lang), "#ef4444"),
        }
        schedule_rows = ""
        for i, inst in enumerate(installment_schedule):
            amt = inst.get("amount", 0)
            label = _s("Pago inicial", "Down payment", lang) if i == 0 else f"{_s("Cuota", "Installment", lang)} #{i}"
            status = inst.get("status", "PENDING")
            status_label, status_color = _status_map.get(status, (_s("Programado", "Scheduled", lang), "#a1a1aa"))
            paid_at = inst.get("paid_at")
            date_display = paid_at if paid_at else inst.get("due_date", "")
            schedule_rows += f"""
            <tr>
              <td style="padding:8px 12px;border-bottom:1px solid #2a2a2e;color:#a1a1aa;font-size:13px;">{label}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #2a2a2e;color:#ffffff;font-size:13px;font-weight:600;">${amt:.2f}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #2a2a2e;color:#a1a1aa;font-size:13px;">{date_display}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #2a2a2e;color:{status_color};font-size:12px;font-weight:600;">{status_label}</td>
            </tr>"""
        content += f"""
      <p style="margin:20px 0 10px;font-size:14px;font-weight:600;color:#ffffff;">{_s("Plan de pagos", "Payment plan", lang)}</p>
      <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;background:#18181b;border-radius:8px;overflow:hidden;min-width:320px;">
          <thead>
            <tr style="background:#27272a;">
              <th style="padding:8px 12px;text-align:left;font-size:12px;color:#a1a1aa;text-transform:uppercase;letter-spacing:0.5px;">{_s("Cuota", "Installment", lang)}</th>
              <th style="padding:8px 12px;text-align:left;font-size:12px;color:#a1a1aa;text-transform:uppercase;letter-spacing:0.5px;">{_s("Monto", "Amount", lang)}</th>
              <th style="padding:8px 12px;text-align:left;font-size:12px;color:#a1a1aa;text-transform:uppercase;letter-spacing:0.5px;">{_s("Fecha", "Date", lang)}</th>
              <th style="padding:8px 12px;text-align:left;font-size:12px;color:#a1a1aa;text-transform:uppercase;letter-spacing:0.5px;">{_s("Estado", "Status", lang)}</th>
            </tr>
          </thead>
          <tbody>{schedule_rows}
          </tbody>
        </table>
      </div>"""
    content += f"""
      {_divider()}
      <p style="margin:0;color:#a1a1aa;font-size:13px;">
        {_s("Puedes ver el estado de tu compra en tu panel de AutoTech.", "You can check your purchase status in your AutoTech dashboard.", lang)}
      </p>
      <p style="margin:12px 0 0;">
        <a href="{settings.FRONTEND_URL}/dashboard/purchases" style="display:inline-block;background-color:#e85d3c;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {_s("Ver mis compras", "View my purchases", lang)}
        </a>
      </p>"""
    return _base_template(_s("Compra realizada", "Purchase completed", lang), content, lang=lang)


def installment_verified(
    buyer_name: str,
    order_id: str,
    installment_number: int,
    amount: float,
    next_due_date: str | None = None,
    schedule: list[dict] | None = None,
    lang: str = "es",
) -> str:
    rows = [
        (_s("Orden", "Order", lang), f"#{order_id[:8]}"),
        (_s("Cuota", "Installment", lang), f"#{installment_number}"),
        (_s("Monto", "Amount", lang), f"${amount:.2f}"),
    ]
    if next_due_date:
        rows.append((_s("Próximo vencimiento", "Next due date", lang), next_due_date))
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{buyer_name}</strong>,</p>
      <div style="display:flex;align-items:center;gap:12px;margin:0 0 20px;padding:16px;border-radius:12px;background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.3);">
        <div style="flex-shrink:0;width:40px;height:40px;border-radius:50%;background:#22c55e;display:flex;align-items:center;justify-content:center;">
          <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" width="20" height="20" xmlns="http://www.w3.org/2000/svg">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>
        <div>
          <p style="margin:0;color:#22c55e;font-size:15px;font-weight:600;">{_s("Pago verificado", "Payment verified", lang)}</p>
          <p style="margin:2px 0 0;color:#a1a1aa;font-size:13px;">{_s("Tu pago ha sido confirmado correctamente", "Your payment has been confirmed successfully", lang)}</p>
        </div>
      </div>
      {_info_table(rows)}"""

    if schedule and len(schedule) > 1:
        _status_map = {
            "PAID": (_s("Pagado", "Paid", lang), "#22c55e"),
            "PENDING_VERIFICATION": (_s("Pendiente por verificación", "Pending verification", lang), "#f59e0b"),
            "PENDING": (_s("Programado", "Scheduled", lang), "#a1a1aa"),
            "OVERDUE": (_s("Vencido", "Overdue", lang), "#ef4444"),
        }
        schedule_rows = ""
        for i, inst in enumerate(schedule):
            label = _s("Pago inicial", "Down payment", lang) if i == 0 else f"{_s("Cuota", "Installment", lang)} #{i}"
            amt = inst.get("amount", 0)
            status = inst.get("status", "PENDING")
            status_label, status_color = _status_map.get(status, (_s("Programado", "Scheduled", lang), "#a1a1aa"))
            paid_at = inst.get("paid_at")
            date_display = paid_at if paid_at else inst.get("due_date", "")
            schedule_rows += f"""
            <tr>
              <td style="padding:8px 12px;border-bottom:1px solid #2a2a2e;color:#a1a1aa;font-size:13px;">{label}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #2a2a2e;color:#ffffff;font-size:13px;font-weight:600;">${amt:.2f}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #2a2a2e;color:#a1a1aa;font-size:13px;">{date_display}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #2a2a2e;color:{status_color};font-size:12px;font-weight:600;">{status_label}</td>
            </tr>"""
        content += f"""
      <p style="margin:20px 0 10px;font-size:14px;font-weight:600;color:#ffffff;">{_s("Plan de pagos", "Payment plan", lang)}</p>
      <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;background:#18181b;border-radius:8px;overflow:hidden;min-width:320px;">
          <thead>
            <tr style="background:#27272a;">
              <th style="padding:8px 12px;text-align:left;font-size:12px;color:#a1a1aa;text-transform:uppercase;letter-spacing:0.5px;">{_s("Cuota", "Installment", lang)}</th>
              <th style="padding:8px 12px;text-align:left;font-size:12px;color:#a1a1aa;text-transform:uppercase;letter-spacing:0.5px;">{_s("Monto", "Amount", lang)}</th>
              <th style="padding:8px 12px;text-align:left;font-size:12px;color:#a1a1aa;text-transform:uppercase;letter-spacing:0.5px;">{_s("Fecha", "Date", lang)}</th>
              <th style="padding:8px 12px;text-align:left;font-size:12px;color:#a1a1aa;text-transform:uppercase;letter-spacing:0.5px;">{_s("Estado", "Status", lang)}</th>
            </tr>
          </thead>
          <tbody>{schedule_rows}
          </tbody>
        </table>
      </div>"""

    content += f"""
      {_divider()}
      <p style="margin:0;color:#a1a1aa;font-size:13px;">
        {_s("El monto ha sido abonado a tu cuenta. ¡Sigue así!", "The amount has been credited to your account. Keep it up!", lang)}
      </p>
      <p style="margin:16px 0 0;">
        <a href="{settings.FRONTEND_URL}/dashboard/purchases/{order_id}" style="display:inline-block;background-color:#e85d3c;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {_s("Ver mi orden", "View my order", lang)}
        </a>
      </p>"""
    return _base_template(_s("Pago verificado", "Payment verified", lang), content, accent_color="#22c55e", lang=lang)


def installment_rejected(
    buyer_name: str,
    order_id: str,
    installment_number: int,
    amount: float,
    reason: str | None = None,
    lang: str = "es",
) -> str:
    rows = [
        (_s("Orden", "Order", lang), f"#{order_id[:8]}"),
        (_s("Cuota", "Installment", lang), f"#{installment_number}"),
        (_s("Monto", "Amount", lang), f"${amount:.2f}"),
    ]
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{buyer_name}</strong>,</p>
      <div style="display:flex;align-items:center;gap:12px;margin:0 0 20px;padding:16px;border-radius:12px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);">
        <div style="flex-shrink:0;width:40px;height:40px;border-radius:50%;background:#ef4444;display:flex;align-items:center;justify-content:center;">
          <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" width="20" height="20" xmlns="http://www.w3.org/2000/svg">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </div>
        <div>
          <p style="margin:0;color:#ef4444;font-size:15px;font-weight:600;">{_s("Pago rechazado", "Payment rejected", lang)}</p>
          <p style="margin:2px 0 0;color:#a1a1aa;font-size:13px;">{_s("Tu pago no pudo ser verificado", "Your payment could not be verified", lang)}</p>
        </div>
      </div>
      {_info_table(rows)}
      {f'<p style="margin:12px 0 0;color:#ef4444;font-size:13px;">{_s("Motivo", "Reason", lang)}: {reason}</p>' if reason else ''}
      {_divider()}
      <p style="margin:0;color:#a1a1aa;font-size:13px;">
        {_s("Por favor, contacta al taller o registra tu pago nuevamente.", "Please contact the workshop or register your payment again.", lang)}
      </p>
      <p style="margin:12px 0 0;">
        <a href="{settings.FRONTEND_URL}/dashboard/purchases/{order_id}" style="display:inline-block;background-color:#e85d3c;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {_s("Ver mi orden", "View my order", lang)}
        </a>
      </p>"""
    return _base_template(_s("Pago rechazado", "Payment rejected", lang), content, accent_color="#ef4444", lang=lang)


def installment_due_soon(
    buyer_name: str,
    order_id: str,
    installment_number: int,
    amount: float,
    due_date: str,
    lang: str = "es",
) -> str:
    rows = [
        (_s("Orden", "Order", lang), f"#{order_id[:8]}"),
        (_s("Cuota", "Installment", lang), f"#{installment_number}"),
        (_s("Monto", "Amount", lang), f"${amount:.2f}"),
        (_s("Vence", "Due", lang), due_date),
    ]
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{buyer_name}</strong>,</p>
      <p style="margin:0 0 20px;">{_s("Tu cuota vence en", "Your installment is due in", lang)} <strong style="color:#f59e0b;">3 {_s("días", "days", lang)}</strong>. {_s("Recuerda realizar tu pago a tiempo para evitar moras.", "Remember to pay on time to avoid late fees.", lang)}</p>
      {_info_table(rows)}
      {_divider()}
      <p style="margin:0;color:#a1a1aa;font-size:13px;">
        {_s("Los pagos a tiempo suman puntos para subir tu nivel de crédito.", "On-time payments earn points to increase your credit level.", lang)}
      </p>
      <p style="margin:12px 0 0;">
        <a href="{settings.FRONTEND_URL}/dashboard/purchases" style="display:inline-block;background-color:#f59e0b;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {_s("Pagar ahora", "Pay now", lang)}
        </a>
      </p>"""
    return _base_template(_s("Vencimiento próximo", "Due date approaching", lang), content, accent_color="#f59e0b", lang=lang)


def order_shipped(
    buyer_name: str,
    order_id: str,
    workshop_name: str,
    tracking_number: str | None,
    shipping_notes: str | None,
    lang: str = "es",
) -> str:
    rows = [
        (_s("Orden", "Order", lang), f"#{order_id[:8]}"),
        (_s("Taller", "Workshop", lang), workshop_name),
    ]
    if tracking_number:
        rows.append((_s("Guía", "Tracking", lang), tracking_number))
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{buyer_name}</strong>,</p>
      <p style="margin:0 0 20px;">{_s("Tu orden ha sido", "Your order has been", lang)} <strong style="color:#3b82f6;">{_s("enviada", "shipped", lang)}</strong>.</p>
      {_info_table(rows)}
      {f'<p style="margin:12px 0 0;color:#a1a1aa;font-size:13px;">{_s("Agencia", "Agency", lang)}: {shipping_notes}</p>' if shipping_notes else ''}
      {_divider()}
      <p style="margin:0;color:#a1a1aa;font-size:13px;">
        {_s("Recibirás tu producto pronto. Marca como recibido cuando lo tengas.", "You will receive your product soon. Mark as received when you get it.", lang)}
      </p>"""
    return _base_template(_s("Orden enviada", "Order shipped", lang), content, accent_color="#3b82f6", lang=lang)


def order_fully_paid(
    buyer_name: str,
    order_id: str,
    workshop_name: str,
    total: float,
    lang: str = "es",
) -> str:
    rows = [
        (_s("Orden", "Order", lang), f"#{order_id[:8]}"),
        (_s("Taller", "Workshop", lang), workshop_name),
        (_s("Total pagado", "Total paid", lang), f"${total:.2f}"),
    ]
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{buyer_name}</strong>,</p>
      <p style="margin:0 0 20px;">{_s("¡Tu orden ha sido", "Your order has been", lang)} <strong style="color:#22c55e;">{_s("completamente pagada", "fully paid", lang)}</strong>! {_s("Todos tus pagos han sido verificados.", "All your payments have been verified.", lang)}</p>
      {_info_table(rows)}
      {_divider()}
      <p style="margin:0;color:#a1a1aa;font-size:13px;">
        {_s("Puedes recoger tu producto en el taller o esperar el envío según tu método de entrega.", "You can pick up your product at the workshop or wait for shipping according to your delivery method.", lang)}
      </p>
      <p style="margin:12px 0 0;">
        <a href="{settings.FRONTEND_URL}/dashboard/purchases/{order_id}" style="display:inline-block;background-color:#e85d3c;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {_s("Ver mi orden", "View my order", lang)}
        </a>
      </p>"""
    return _base_template(_s("Orden completamente pagada", "Order fully paid", lang), content, accent_color="#22c55e", lang=lang)


def service_quote_sent(
    buyer_name: str,
    service_name: str,
    workshop_name: str,
    price: float,
    order_id: str,
    lang: str = "es",
) -> str:
    rows = [
        (_s("Servicio", "Service", lang), service_name),
        (_s("Taller", "Workshop", lang), workshop_name),
        (_s("Presupuesto", "Quote", lang), f"${price:.2f}"),
    ]
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{buyer_name}</strong>,</p>
      <p style="margin:0 0 20px;">{_s("El taller te ha enviado un", "The workshop has sent you a", lang)} <strong style="color:#8b5cf6;">{_s("presupuesto", "quote", lang)}</strong> {_s("para tu servicio.", "for your service.", lang)}</p>
      {_info_table(rows)}
      {_divider()}
      <p style="margin:0;color:#a1a1aa;font-size:13px;">
        {_s("Revisa el presupuesto y decide si aceptarlo o rechazarlo.", "Review the quote and decide whether to accept or reject it.", lang)}
      </p>
      <p style="margin:12px 0 0;">
        <a href="{settings.FRONTEND_URL}/dashboard/service-orders" style="display:inline-block;background-color:#8b5cf6;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {_s("Ver presupuesto", "View quote", lang)}
        </a>
      </p>"""
    return _base_template(_s("Presupuesto recibido", "Quote received", lang), content, accent_color="#8b5cf6", lang=lang)


def password_recovery(email: str, reset_link: str, lang: str = "es") -> str:
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)},</p>
      <p style="margin:0 0 20px;">{_s("Has solicitado restablecer tu contraseña en AutoTech. Haz clic en el botón para continuar:", "You have requested to reset your password on AutoTech. Click the button to continue:", lang)}</p>
      <p style="margin:0;">
        <a href="{reset_link}" style="display:inline-block;background-color:#e85d3c;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {_s("Restablecer contraseña", "Reset password", lang)}
        </a>
      </p>
      {_divider()}
      <p style="margin:0;color:#a1a1aa;font-size:13px;">
        {_s("Si no solicitaste este cambio, ignora este correo. Tu contraseña seguirá sin cambios.", "If you did not request this change, ignore this email. Your password will remain unchanged.", lang)}
      </p>
      <p style="margin:8px 0 0;color:#52525b;font-size:12px;">
        {_s("O copia este enlace", "Or copy this link", lang)}: {reset_link}
      </p>
      <p style="margin:8px 0 0;color:#52525b;font-size:12px;">
        {_s("Este enlace expira en 1 hora.", "This link expires in 1 hour.", lang)}
      </p>"""
    return _base_template(_s("Recuperación de contraseña", "Password recovery", lang), content, lang=lang)


def service_revision_sent(
    buyer_name: str,
    service_name: str,
    workshop_name: str,
    revision_cost: float,
    order_id: str,
    lang: str = "es",
) -> str:
    rows = [
        (_s("Servicio", "Service", lang), service_name),
        (_s("Taller", "Workshop", lang), workshop_name),
        (_s("Costo de revisión", "Revision cost", lang), f"${revision_cost:.2f}"),
    ]
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{buyer_name}</strong>,</p>
      <p style="margin:0 0 20px;">{_s("El taller te ha enviado el", "The workshop has sent you the", lang)} <strong style="color:#a855f7;">{_s("costo de revisión", "revision cost", lang)}</strong> {_s("de tu vehículo.", "for your vehicle.", lang)}</p>
      {_info_table(rows)}
      {_divider()}
      <p style="margin:0;color:#a1a1aa;font-size:13px;">
        {_s("Revisa el costo de revisión y decide si aceptarlo o rechazarlo en tu panel.", "Review the revision cost and decide whether to accept or reject it in your dashboard.", lang)}
      </p>
      <p style="margin:12px 0 0;">
        <a href="{settings.FRONTEND_URL}/dashboard/service-orders" style="display:inline-block;background-color:#a855f7;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {_s("Ver revisión", "View revision", lang)}
        </a>
      </p>"""
    return _base_template(_s("Revisión enviada", "Revision sent", lang), content, accent_color="#a855f7", lang=lang)


def service_extra_charge(
    buyer_name: str,
    service_name: str,
    workshop_name: str,
    extra_charge: float,
    note: str | None,
    order_id: str,
    lang: str = "es",
) -> str:
    rows = [
        (_s("Servicio", "Service", lang), service_name),
        (_s("Taller", "Workshop", lang), workshop_name),
        (_s("Cargo extra", "Extra charge", lang), f"${extra_charge:.2f}"),
    ]
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{buyer_name}</strong>,</p>
      <p style="margin:0 0 20px;">{_s("El taller ha agregado un", "The workshop has added an", lang)} <strong style="color:#f59e0b;">{_s("cargo extra", "extra charge", lang)}</strong> {_s("a tu orden de servicio, pendiente de tu aprobación.", "to your service order, pending your approval.", lang)}</p>
      {_info_table(rows)}
      {f'<p style="margin:12px 0 0;color:#a1a1aa;font-size:13px;">{_s("Nota", "Note", lang)}: {note}</p>' if note else ''}
      {_divider()}
      <p style="margin:0;color:#a1a1aa;font-size:13px;">
        {_s("Entra a tu panel para aprobar o rechazar el cargo extra.", "Go to your dashboard to approve or reject the extra charge.", lang)}
      </p>
      <p style="margin:12px 0 0;">
        <a href="{settings.FRONTEND_URL}/dashboard/service-orders" style="display:inline-block;background-color:#f59e0b;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {_s("Ver cargo extra", "View extra charge", lang)}
        </a>
      </p>"""
    return _base_template(_s("Cargo extra pendiente", "Extra charge pending", lang), content, accent_color="#f59e0b", lang=lang)


def service_shipped(
    buyer_name: str,
    service_name: str,
    workshop_name: str,
    tracking_number: str | None,
    shipping_notes: str | None,
    order_id: str,
    lang: str = "es",
) -> str:
    rows = [
        (_s("Servicio", "Service", lang), service_name),
        (_s("Taller", "Workshop", lang), workshop_name),
    ]
    if tracking_number:
        rows.append((_s("Guía", "Tracking", lang), tracking_number))
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{buyer_name}</strong>,</p>
      <p style="margin:0 0 20px;">{_s("Tu vehículo ha sido", "Your vehicle has been", lang)} <strong style="color:#3b82f6;">{_s("enviado", "shipped", lang)}</strong> {_s("desde el taller.", "from the workshop.", lang)}</p>
      {_info_table(rows)}
      {f'<p style="margin:12px 0 0;color:#a1a1aa;font-size:13px;">{_s("Agencia", "Agency", lang)}: {shipping_notes}</p>' if shipping_notes else ''}
      {_divider()}
      <p style="margin:0;color:#a1a1aa;font-size:13px;">
        {_s("Marca como recibido cuando tengas tu vehículo.", "Mark as received when you have your vehicle.", lang)}
      </p>
      <p style="margin:12px 0 0;">
        <a href="{settings.FRONTEND_URL}/dashboard/service-orders" style="display:inline-block;background-color:#3b82f6;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {_s("Ver estado", "View status", lang)}
        </a>
      </p>"""
    return _base_template(_s("Vehículo enviado", "Vehicle shipped", lang), content, accent_color="#3b82f6", lang=lang)


def payment_registered_admin(
    payment_type: str,
    payer_name: str,
    amount: float,
    method: str,
    reference: str | None,
    lang: str = "es",
) -> str:
    """Notify superadmin that a payment (commission/mora) has been registered and needs verification."""
    rows = [
        (_s("Tipo", "Type", lang), payment_type),
        (_s("Pagador", "Payer", lang), payer_name),
        (_s("Monto", "Amount", lang), f"${amount:.2f}"),
        (_s("Método", "Method", lang), method),
    ]
    if reference:
        rows.append((_s("Referencia", "Reference", lang), reference))
    content = f"""
      <p style="margin:0 0 16px;">{_s("Se ha registrado un nuevo pago que requiere verificación.", "A new payment has been registered and requires verification.", lang)}</p>
      <div style="display:flex;align-items:center;gap:12px;margin:0 0 20px;padding:16px;border-radius:12px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);">
        <div style="flex-shrink:0;width:40px;height:40px;border-radius:50%;background:#f59e0b;display:flex;align-items:center;justify-content:center;">
          <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="20" height="20" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
        </div>
        <div>
          <p style="margin:0;color:#f59e0b;font-size:15px;font-weight:600;">{_s("Pago pendiente de verificación", "Payment pending verification", lang)}</p>
          <p style="margin:2px 0 0;color:#a1a1aa;font-size:13px;">{_s("Revisa y verifica el pago lo antes posible", "Review and verify the payment as soon as possible", lang)}</p>
        </div>
      </div>
      {_info_table(rows)}
      {_divider()}
      <p style="margin:0;color:#a1a1aa;font-size:13px;">
        {_s("Entra al panel de administración para verificar o rechazar este pago.", "Go to the admin panel to verify or reject this payment.", lang)}
      </p>
      <p style="margin:12px 0 0;">
        <a href="{settings.FRONTEND_URL}/dashboard/admin" style="display:inline-block;background-color:#f59e0b;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {_s("Ir al panel", "Go to panel", lang)}
        </a>
      </p>"""
    return _base_template(_s("Pago pendiente de verificación", "Payment pending verification", lang), content, accent_color="#f59e0b", lang=lang)


def payment_verified_user(
    user_name: str,
    payment_type: str,
    amount: float,
    lang: str = "es",
) -> str:
    """Notify user/workshop owner that their payment has been verified."""
    is_late_fee = "mora" in payment_type.lower()
    rows = [
        (_s("Tipo", "Type", lang), payment_type),
        (_s("Monto", "Amount", lang), f"${amount:.2f}"),
    ]

    if is_late_fee:
        main_msg = _s(
            "Tu cuota de mora fue verificada. El pago fue confirmado. Ya puedes volver a comprar en el marketplace.",
            "Your late fee has been verified. The payment has been confirmed. You can now buy again in the marketplace.",
            lang,
        )
        btn_label = _s("Ir al marketplace", "Go to marketplace", lang)
        btn_url = f"{settings.FRONTEND_URL}/dashboard/marketplace"
    else:
        main_msg = _s(
            "Tu pago de comisiones fue verificado. Tu aporte nos ayuda a mantener una plataforma sostenible y crecer de la mano.",
            "Your commission payment has been verified. Your contribution helps us maintain a sustainable platform and grow together.",
            lang,
        )
        btn_label = _s("Ir al panel", "Go to panel", lang)
        btn_url = f"{settings.FRONTEND_URL}/dashboard"

    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{user_name}</strong>,</p>
      <div style="display:flex;align-items:center;gap:12px;margin:0 0 20px;padding:16px;border-radius:12px;background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.3);">
        <div style="flex-shrink:0;width:40px;height:40px;border-radius:50%;background:#22c55e;display:flex;align-items:center;justify-content:center;">
          <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" width="20" height="20" xmlns="http://www.w3.org/2000/svg">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>
        <div>
          <p style="margin:0;color:#22c55e;font-size:15px;font-weight:600;">{_s("Pago verificado", "Payment verified", lang)}</p>
          <p style="margin:2px 0 0;color:#a1a1aa;font-size:13px;">{_s("Tu pago ha sido confirmado correctamente", "Your payment has been confirmed successfully", lang)}</p>
        </div>
      </div>
      {_info_table(rows)}
      {_divider()}
      <p style="margin:0 0 16px;color:#a1a1aa;font-size:13px;">
        {main_msg}
      </p>
      <p style="margin:12px 0 0;">
        <a href="{btn_url}" style="display:inline-block;background-color:#22c55e;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {btn_label}
        </a>
      </p>"""
    return _base_template(_s("Pago verificado", "Payment verified", lang), content, accent_color="#22c55e", lang=lang)


def payment_rejected_user(
    user_name: str,
    payment_type: str,
    amount: float,
    lang: str = "es",
) -> str:
    """Notify user/workshop owner that their payment was rejected."""
    is_late_fee = "mora" in payment_type.lower()
    rows = [
        (_s("Tipo", "Type", lang), payment_type),
        (_s("Monto", "Amount", lang), f"${amount:.2f}"),
    ]

    if is_late_fee:
        btn_label = _s("Ir a línea de crédito", "Go to credit line", lang)
        btn_url = f"{settings.FRONTEND_URL}/dashboard/credit-line"
    else:
        btn_label = _s("Ir a comisiones", "Go to commissions", lang)
        btn_url = f"{settings.FRONTEND_URL}/dashboard/my-workshops"

    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{user_name}</strong>,</p>
      <div style="display:flex;align-items:center;gap:12px;margin:0 0 20px;padding:16px;border-radius:12px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);">
        <div style="flex-shrink:0;width:40px;height:40px;border-radius:50%;background:#ef4444;display:flex;align-items:center;justify-content:center;">
          <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" width="20" height="20" xmlns="http://www.w3.org/2000/svg">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </div>
        <div>
          <p style="margin:0;color:#ef4444;font-size:15px;font-weight:600;">{_s("Pago rechazado", "Payment rejected", lang)}</p>
          <p style="margin:2px 0 0;color:#a1a1aa;font-size:13px;">{_s("Tu pago no pudo ser verificado", "Your payment could not be verified", lang)}</p>
        </div>
      </div>
      {_info_table(rows)}
      {_divider()}
      <p style="margin:0 0 16px;color:#a1a1aa;font-size:13px;">
        {_s("Tu pago no pudo ser verificado. Vuelve a registrarlo.", "Your payment could not be verified. Please register it again.", lang)}
      </p>
      <p style="margin:12px 0 0;">
        <a href="{btn_url}" style="display:inline-block;background-color:#ef4444;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {btn_label}
        </a>
      </p>"""
    return _base_template(_s("Pago rechazado", "Payment rejected", lang), content, accent_color="#ef4444", lang=lang)


def commission_due_soon(
    workshop_name: str,
    owner_name: str,
    total_pending: float,
    deadline: str,
    lang: str = "es",
) -> str:
    """Warn workshop owner that commissions are due soon."""
    rows = [
        (_s("Taller", "Workshop", lang), workshop_name),
        (_s("Total pendiente", "Total pending", lang), f"${total_pending:.2f}"),
        (_s("Fecha límite", "Deadline", lang), deadline),
    ]
    btn_url = f"{settings.FRONTEND_URL}/dashboard/my-workshops"
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{owner_name}</strong>,</p>
      <div style="display:flex;align-items:center;gap:12px;margin:0 0 20px;padding:16px;border-radius:12px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);">
        <div style="flex-shrink:0;width:40px;height:40px;border-radius:50%;background:#f59e0b;display:flex;align-items:center;justify-content:center;">
          <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="20" height="20" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="12 6 12 12 16 14"></polyline>
          </svg>
        </div>
        <div>
          <p style="margin:0;color:#f59e0b;font-size:15px;font-weight:600;">{_s("Comisiones por vencer", "Commissions due soon", lang)}</p>
          <p style="margin:2px 0 0;color:#a1a1aa;font-size:13px;">{_s("Paga antes del " + deadline, "Pay before " + deadline, lang)}</p>
        </div>
      </div>
      {_info_table(rows)}
      {_divider()}
      <p style="margin:0 0 16px;color:#a1a1aa;font-size:13px;">
        {_s("Si no pagas tus comisiones antes del " + deadline + ", tu taller será suspendido temporalmente y no podrá recibir nuevas órdenes financiadas. Paga ahora para evitarlo.", "If you don't pay your commissions before " + deadline + ", your workshop will be temporarily suspended and won't receive new financed orders. Pay now to avoid this.", lang)}
      </p>
      <p style="margin:12px 0 0;">
        <a href="{btn_url}" style="display:inline-block;background-color:#e85d3c;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {_s("Pagar comisiones", "Pay commissions", lang)}
        </a>
      </p>"""
    return _base_template(_s("Comisiones por vencer", "Commissions due soon", lang), content, accent_color="#f59e0b", lang=lang)


def commission_overdue_suspended(
    workshop_name: str,
    owner_name: str,
    total_pending: float,
    lang: str = "es",
) -> str:
    """Notify workshop owner that their workshop has been suspended due to unpaid commissions."""
    rows = [
        (_s("Taller", "Workshop", lang), workshop_name),
        (_s("Total pendiente", "Total pending", lang), f"${total_pending:.2f}"),
    ]
    btn_url = f"{settings.FRONTEND_URL}/dashboard/my-workshops"
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{owner_name}</strong>,</p>
      <div style="display:flex;align-items:center;gap:12px;margin:0 0 20px;padding:16px;border-radius:12px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);">
        <div style="flex-shrink:0;width:40px;height:40px;border-radius:50%;background:#ef4444;display:flex;align-items:center;justify-content:center;">
          <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="20" height="20" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
        </div>
        <div>
          <p style="margin:0;color:#ef4444;font-size:15px;font-weight:600;">{_s("Taller suspendido", "Workshop suspended", lang)}</p>
          <p style="margin:2px 0 0;color:#a1a1aa;font-size:13px;">{_s("Comisiones impagas", "Unpaid commissions", lang)}</p>
        </div>
      </div>
      {_info_table(rows)}
      {_divider()}
      <p style="margin:0 0 16px;color:#a1a1aa;font-size:13px;">
        {_s("Tu taller ha sido suspendido por comisiones impagas. Tus clientes no podrán realizar nuevas compras financiadas en tu taller hasta que regularices tu situación. Paga tus comisiones pendientes para reactivar tu taller automáticamente.", "Your workshop has been suspended due to unpaid commissions. Your clients won't be able to make new financed purchases at your workshop until you regularize your situation. Pay your pending commissions to automatically reactivate your workshop.", lang)}
      </p>
      <p style="margin:12px 0 0;">
        <a href="{btn_url}" style="display:inline-block;background-color:#ef4444;color:#ffffff;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;">
          {_s("Pagar comisiones", "Pay commissions", lang)}
        </a>
      </p>"""
    return _base_template(_s("Taller suspendido por comisiones", "Workshop suspended due to commissions", lang), content, accent_color="#ef4444", lang=lang)


def support_resolved(
    user_name: str,
    subject: str,
    admin_note: str | None = None,
    lang: str = "es",
) -> str:
    rows = [
        (_s("Asunto", "Subject", lang), subject),
    ]
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{user_name}</strong>,</p>
      <div style="display:flex;align-items:center;gap:12px;margin:0 0 20px;padding:16px;border-radius:12px;background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.3);">
        <div style="flex-shrink:0;width:40px;height:40px;border-radius:50%;background:#22c55e;display:flex;align-items:center;justify-content:center;">
          <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" width="20" height="20" xmlns="http://www.w3.org/2000/svg">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>
        <div>
          <p style="margin:0;color:#22c55e;font-size:15px;font-weight:600;">{_s("Solicitud resuelta", "Request resolved", lang)}</p>
          <p style="margin:2px 0 0;color:#a1a1aa;font-size:13px;">{_s("Tu mensaje de soporte ha sido atendido", "Your support message has been addressed", lang)}</p>
        </div>
      </div>
      {_info_table(rows)}
      {f'<p style="margin:12px 0 0;color:#a1a1aa;font-size:13px;">{_s("Respuesta", "Response", lang)}: {admin_note}</p>' if admin_note else ''}
      {_divider()}
      <p style="margin:0;color:#a1a1aa;font-size:13px;">
        {_s("Gracias por contactarnos. Si tienes otra duda, no dudes en escribirnos.", "Thank you for reaching out. If you have another question, feel free to contact us.", lang)}
      </p>"""
    return _base_template(_s("Soporte resuelto", "Support resolved", lang), content, accent_color="#22c55e", lang=lang)


def support_rejected(
    user_name: str,
    subject: str,
    admin_note: str | None = None,
    lang: str = "es",
) -> str:
    rows = [
        (_s("Asunto", "Subject", lang), subject),
    ]
    content = f"""
      <p style="margin:0 0 16px;">{_s("Hola", "Hello", lang)} <strong style="color:#ffffff;">{user_name}</strong>,</p>
      <div style="display:flex;align-items:center;gap:12px;margin:0 0 20px;padding:16px;border-radius:12px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);">
        <div style="flex-shrink:0;width:40px;height:40px;border-radius:50%;background:#ef4444;display:flex;align-items:center;justify-content:center;">
          <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" width="20" height="20" xmlns="http://www.w3.org/2000/svg">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </div>
        <div>
          <p style="margin:0;color:#ef4444;font-size:15px;font-weight:600;">{_s("Solicitud rechazada", "Request rejected", lang)}</p>
          <p style="margin:2px 0 0;color:#a1a1aa;font-size:13px;">{_s("Tu mensaje de soporte no pudo ser atendido", "Your support message could not be addressed", lang)}</p>
        </div>
      </div>
      {_info_table(rows)}
      {f'<p style="margin:12px 0 0;color:#a1a1aa;font-size:13px;">{_s("Motivo", "Reason", lang)}: {admin_note}</p>' if admin_note else ''}
      {_divider()}
      <p style="margin:0;color:#a1a1aa;font-size:13px;">
        {_s("Si crees que esto es un error, puedes enviar un nuevo mensaje de soporte.", "If you believe this is an error, you can send a new support message.", lang)}
      </p>"""
    return _base_template(_s("Soporte rechazado", "Support rejected", lang), content, accent_color="#ef4444", lang=lang)
