from datetime import datetime, timezone
from io import BytesIO
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.invoice import Invoice
from app.models.session import ChargingSession
from app.models.reservation import Reservation
from app.models.station import ChargingPort, Station
from app.models.vehicle import Vehicle
from app.models.user import User
from app.schemas.invoice_schema import InvoiceResponse
from app.services.session_service import compute_snapshot

from app.core.response import UniformResponseRoute

router = APIRouter(route_class=UniformResponseRoute, prefix="/invoices", tags=["Invoices"])


@router.get("", response_model=List[InvoiceResponse])
def list_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Invoice)
        .filter(Invoice.user_id == current_user.user_id)
        .order_by(Invoice.created_at.desc())
        .all()
    )


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """FR-17: stream the invoice as a PDF file."""
    invoice = db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Load related records for the PDF content
    session = db.query(ChargingSession).filter(
        ChargingSession.session_id == invoice.charging_session_id
    ).first()
    reservation = db.query(Reservation).filter(
        Reservation.reservation_id == session.reservation_id
    ).first() if session else None
    port = db.query(ChargingPort).filter(
        ChargingPort.port_id == reservation.port_id
    ).first() if reservation else None
    station = db.query(Station).filter(
        Station.station_id == port.station_id
    ).first() if port else None
    vehicle = db.query(Vehicle).filter(
        Vehicle.vehicle_id == reservation.vehicle_id
    ).first() if reservation else None

    # Compute session snapshot for cost breakdown
    snapshot = None
    if session and vehicle and port and station and session.end_time:
        snapshot = compute_snapshot(session, vehicle, port, station, session.end_time)

    # Build PDF with reportlab
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Heading1"], fontSize=20, spaceAfter=4)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"], fontSize=10, textColor=colors.grey)
    h2_style = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=12, spaceAfter=4)
    normal = styles["Normal"]

    inv_num = str(invoice.invoice_id)[:8].upper()
    created_str = invoice.created_at.strftime("%Y-%m-%d %H:%M UTC") if invoice.created_at else "—"
    paid_str = invoice.paid_at.strftime("%Y-%m-%d %H:%M UTC") if invoice.paid_at else "Unpaid"

    story = []
    story.append(Paragraph("Electra Charging Invoice", title_style))
    story.append(Paragraph(f"Invoice #{inv_num}  ·  {created_str}", sub_style))
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 0.3*cm))

    # Session summary table
    story.append(Paragraph("Session Summary", h2_style))
    summary_data = [
        ["Field", "Value"],
        ["Station", station.name if station else "—"],
        ["Port QR Code", port.qr_code if port else "—"],
        ["Connector / Charger", f"{port.connector_type} / {port.charger_type}" if port else "—"],
        ["Vehicle", f"{vehicle.make} {vehicle.model} ({vehicle.registration_number})" if vehicle else "—"],
        ["Session Start", session.start_time.strftime("%Y-%m-%d %H:%M UTC") if session and session.start_time else "—"],
        ["Session End", session.end_time.strftime("%Y-%m-%d %H:%M UTC") if session and session.end_time else "—"],
        ["Battery: Initial -> Target", f"{session.initial_battery_percentage}% -> {session.target_battery_percentage}%" if session else "—"],
    ]
    tbl = Table(summary_data, colWidths=[5*cm, 11*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.4*cm))

    # Cost breakdown table
    story.append(Paragraph("Cost Breakdown", h2_style))
    tariff = float(session.applied_tariff) if session else 0.0
    energy_kwh = float(snapshot["energy_delivered_kwh"]) if snapshot else 0.0
    energy_cost = float(snapshot["energy_cost"]) if snapshot else 0.0
    idle_minutes = float(snapshot["idle_minutes"]) if snapshot else 0.0
    idle_fee = float(snapshot["idle_fee"]) if snapshot else 0.0
    total = float(invoice.total_amount)
    min_fee = float(station.minimum_session_fee) if station else 0.0
    session_cost = float(snapshot["total_cost"]) if snapshot else 0.0
    min_fee_adj = max(0.0, round(session_cost - (energy_cost + idle_fee), 2))
    penalties = max(0.0, round(total - session_cost, 2))

    cost_data = [
        ["Item", "Detail", "Amount (Rs.)"],
        ["Energy fee", f"{energy_kwh:.3f} kWh @ Rs.{tariff:.2f}/kWh", f"{energy_cost:.2f}"],
        ["Idle / overstay fee", f"{idle_minutes:.1f} billable min", f"{idle_fee:.2f}"],
    ]
    if min_fee_adj > 0:
        cost_data.append(["Minimum fee adjustment", "Station minimum session fee floor", f"{min_fee_adj:.2f}"])
    cost_data.append(["Penalties / Additional fees", "Station / operator penalty" if penalties > 0 else "None", f"{penalties:.2f}"])
    cost_data.append(["Total charged", "", f"{total:.2f}"])

    tbl2 = Table(cost_data, colWidths=[5*cm, 8*cm, 3*cm])
    tbl2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.whitesmoke, colors.white]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8f5e9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl2)
    story.append(Spacer(1, 0.3*cm))

    if min_fee > 0:
        story.append(Paragraph(
            f"<i>* A minimum session fee of Rs. {min_fee:.2f} applies at this station. "
            "If the energy cost was below this floor, the minimum fee was charged instead.</i>",
            ParagraphStyle("note", parent=normal, fontSize=8, textColor=colors.grey)
        ))


    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    status_text = f"<b>Status: {'PAID' if invoice.is_paid else 'UNPAID'}</b>"
    if invoice.is_paid and invoice.paid_at:
        status_text += f"  —  Paid on {paid_str}"
    story.append(Paragraph(status_text, ParagraphStyle("status", parent=normal, fontSize=10, spaceBefore=8)))

    doc.build(story)
    buf.seek(0)

    filename = f"electra-invoice-{inv_num}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/pay")
def pay_outstanding_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """FR-16 mock payment endpoint: the wallet is a single pooled balance, not
    earmarked per invoice, so an unpaid invoice means the settlement at session
    end left wallet_balance negative. Once the user tops up enough to clear
    that debt, every outstanding invoice is marked paid and the account
    unsuspends - there's no separate per-invoice amount to reconcile."""
    user = db.query(User).with_for_update().filter(User.user_id == current_user.user_id).first()
    if user.wallet_balance < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Wallet balance is still negative (₹{user.wallet_balance}). Top up at least ₹{-user.wallet_balance} before paying.",
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    unpaid = db.query(Invoice).filter(Invoice.user_id == current_user.user_id, Invoice.is_paid.is_(False)).with_for_update().all()
    for invoice in unpaid:
        invoice.is_paid = True
        invoice.paid_at = now

    user.is_suspended = False
    db.commit()
    return {"message": f"Settled {len(unpaid)} outstanding invoice(s)."}

