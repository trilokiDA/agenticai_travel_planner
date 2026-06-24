import io
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

def escape_ics_text(text: str) -> str:
    """Escapes special characters in ICS strings according to RFC 5545."""
    if not text:
        return ""
    # Escape backslashes, newlines, commas, and semicolons
    return text.replace('\\', '\\\\').replace('\n', '\\n').replace(',', '\\,').replace(';', '\\;')

def generate_ics(itinerary: Dict[str, Any], start_date_str: Optional[str]) -> str:
    """
    Generates an iCalendar (.ics) string for importing trip activities, flights, and stays.
    """
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        start_date = datetime.now().date()
        
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AI Travel Planner//NONSGML v1.0//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH"
    ]
    
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    destination = itinerary.get("destination", "Destination")
    currency = itinerary.get("currency", "USD")
    duration_days = int(itinerary.get("duration_days") or 1)
    
    # 1. Flights
    for idx, f in enumerate(itinerary.get("flights", [])):
        # Assume first flight is departure on Day 1, subsequent are return flights on final day
        is_return = idx > 0
        flight_day = duration_days if is_return else 1
        date_val = start_date + timedelta(days=flight_day - 1)
        
        date_str = date_val.strftime("%Y%m%d")
        next_date_str = (date_val + timedelta(days=1)).strftime("%Y%m%d")
        
        provider = f.get("provider", "Airline")
        origin = f.get("origin", "Origin")
        dest = f.get("destination", "Destination")
        price = f.get("price", 0.0)
        details = f.get("details", "")
        
        summary = f"Flight: {origin} to {dest} ({provider})"
        description = f"Flight details:\nProvider: {provider}\nRoute: {origin} -> {dest}\nPrice: {price} {currency}\n{details}"
        location = f"{origin} Airport"
        
        uid = f"{uuid.uuid4()}@aitravelplanner"
        
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART;VALUE=DATE:{date_str}",
            f"DTEND;VALUE=DATE:{next_date_str}",
            f"SUMMARY:{escape_ics_text(summary)}",
            f"DESCRIPTION:{escape_ics_text(description)}",
            f"LOCATION:{escape_ics_text(location)}",
            "END:VEVENT"
        ])
        
    # 2. Hotels (Single event covering check-in to check-out)
    for h in itinerary.get("hotels", []):
        checkin_date = start_date
        checkout_date = start_date + timedelta(days=duration_days)
        
        checkin_str = checkin_date.strftime("%Y%m%d")
        checkout_str = checkout_date.strftime("%Y%m%d")
        
        name = h.get("name", "Hotel")
        price_per_night = h.get("price_per_night", 0.0)
        total_price = h.get("total_price", 0.0)
        rating = h.get("rating", "")
        loc = h.get("location", "")
        
        summary = f"Stay at {name}"
        description = f"Hotel Booking Details:\nHotel: {name}\nPrice per night: {price_per_night} {currency}\nTotal price: {total_price} {currency}\nRating: {rating} stars\nLocation: {loc}"
        
        uid = f"{uuid.uuid4()}@aitravelplanner"
        
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART;VALUE=DATE:{checkin_str}",
            f"DTEND;VALUE=DATE:{checkout_str}",
            f"SUMMARY:{escape_ics_text(summary)}",
            f"DESCRIPTION:{escape_ics_text(description)}",
            f"LOCATION:{escape_ics_text(loc)}",
            "END:VEVENT"
        ])
        
    # 3. Activities
    for a in itinerary.get("activities", []):
        day_num = int(a.get("day_number") or 1)
        act_date = start_date + timedelta(days=day_num - 1)
        
        date_str = act_date.strftime("%Y%m%d")
        next_date_str = (act_date + timedelta(days=1)).strftime("%Y%m%d")
        
        name = a.get("name", "Activity")
        desc = a.get("description", "")
        cost = a.get("cost", 0.0)
        
        summary = f"Activity: {name}"
        description = f"Activity Details:\n{desc}\nCost: {cost} {currency}"
        
        uid = f"{uuid.uuid4()}@aitravelplanner"
        
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART;VALUE=DATE:{date_str}",
            f"DTEND;VALUE=DATE:{next_date_str}",
            f"SUMMARY:{escape_ics_text(summary)}",
            f"DESCRIPTION:{escape_ics_text(description)}",
            f"LOCATION:{escape_ics_text(destination)}",
            "END:VEVENT"
        ])
        
    lines.append("END:VCALENDAR")
    return "\n".join(lines)

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas renderer to display 'Page X of Y' page count dynamic text,
    plus decorative header and footer dividers.
    """
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        
        # Header (Only on Page 1+ - we draw header across all pages since it's a direct itinerary)
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawString(54, 755, "AI TRAVEL PLANNER ITINERARY")
        
        # Header line
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 747, 558, 747)
        
        # Footer
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(54, 35, "Generated with AI Travel Planner (HITL Edition)")
        
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 35, page_text)
        
        # Footer line
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)
        
        self.restoreState()

def generate_pdf(itinerary: Dict[str, Any], budget: float, currency: str, start_date_str: Optional[str]) -> bytes:
    """
    Generates a beautifully formatted, print-ready PDF itinerary of the trip details.
    """
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        start_date = datetime.now().date()
        
    duration = int(itinerary.get("duration_days") or 1)
    destination = itinerary.get("destination", "Destination")
    origin = itinerary.get("origin", "Origin")
    is_round_trip = itinerary.get("is_round_trip", True)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=65,
        bottomMargin=65
    )
    
    styles = getSampleStyleSheet()
    
    # Custom, premium styled ParagraphStyles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#1E3A8A"), # Deep Navy Blue
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#64748B"), # Slate Grey
        spaceAfter=15
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0F172A"), # Dark Charcoal
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    
    day_heading = ParagraphStyle(
        'DayHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor("#0284C7"), # Sky Blue
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#334155") # Muted Dark Slate
    )
    
    body_bold = ParagraphStyle(
        'DocBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10,
        textColor=colors.white
    )
    
    story = []
    
    # 1. Header Title & Subtitle
    story.append(Paragraph(f"Itinerary: {destination}", title_style))
    story.append(Paragraph(f"Created on {datetime.now().strftime('%B %d, %Y')} | Persistent Thread Plan Draft", subtitle_style))
    
    # 2. Metadata Info Card (2 columns, 4 rows)
    metadata_data = [
        [
            Paragraph(f"<b>Destination:</b> {destination}", body_style),
            Paragraph(f"<b>Total Budget:</b> {budget:,.2f} {currency}", body_style)
        ],
        [
            Paragraph(f"<b>Origin:</b> {origin}", body_style),
            Paragraph(f"<b>Estimated Cost:</b> {itinerary.get('total_cost', 0.0):,.2f} {currency}", body_style)
        ],
        [
            Paragraph(f"<b>Start Date:</b> {start_date.strftime('%B %d, %Y')}", body_style),
            Paragraph(f"<b>Trip Status:</b> {itinerary.get('status', 'Draft')}", body_style)
        ],
        [
            Paragraph(f"<b>Duration:</b> {duration} Days", body_style),
            Paragraph(f"<b>Trip Type:</b> {'Round Trip' if is_round_trip else 'One Way'}", body_style)
        ]
    ]
    metadata_table = Table(metadata_data, colWidths=[252, 252])
    metadata_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    story.append(metadata_table)
    story.append(Spacer(1, 15))
    
    # 3. Flights Section
    story.append(Paragraph("✈️ Flight Recommendations", section_heading))
    flights = itinerary.get("flights", [])
    if not flights:
        story.append(Paragraph("No flight recommendations booked or found for this itinerary.", body_style))
    else:
        flight_data = [[
            Paragraph("Provider", table_header_style),
            Paragraph("Route", table_header_style),
            Paragraph("Price", table_header_style),
            Paragraph("Details", table_header_style)
        ]]
        for f in flights:
            flight_data.append([
                Paragraph(f.get("provider", "N/A"), body_style),
                Paragraph(f"{f.get('origin', 'N/A')} → {f.get('destination', 'N/A')}", body_style),
                Paragraph(f"{currency} {f.get('price', 0.0):,.2f}", body_bold),
                Paragraph(f.get("details", "") or "No additional details available.", body_style)
            ])
        flight_table = Table(flight_data, colWidths=[110, 100, 80, 214])
        flight_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ]))
        story.append(flight_table)
    story.append(Spacer(1, 15))
    
    # 4. Hotels Section
    story.append(Paragraph("🏨 Hotel Stays", section_heading))
    hotels = itinerary.get("hotels", [])
    if not hotels:
        story.append(Paragraph("No hotel details booked or found for this itinerary.", body_style))
    else:
        hotel_data = [[
            Paragraph("Hotel Name", table_header_style),
            Paragraph("Location", table_header_style),
            Paragraph("Rating", table_header_style),
            Paragraph("Price/Night", table_header_style),
            Paragraph("Total Price", table_header_style)
        ]]
        for h in hotels:
            rating_str = f"⭐ {h.get('rating')}" if h.get("rating") else "N/A"
            hotel_data.append([
                Paragraph(h.get("name", "N/A"), body_style),
                Paragraph(h.get("location", "") or "N/A", body_style),
                Paragraph(rating_str, body_style),
                Paragraph(f"{currency} {h.get('price_per_night', 0.0):,.2f}", body_style),
                Paragraph(f"{currency} {h.get('total_price', 0.0):,.2f}", body_bold)
            ])
        hotel_table = Table(hotel_data, colWidths=[144, 130, 60, 80, 90])
        hotel_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ]))
        story.append(hotel_table)
    story.append(Spacer(1, 15))
    
    # 5. Daily Activities Section
    story.append(Paragraph("📅 Daily Schedule & Activities", section_heading))
    activities = itinerary.get("activities", [])
    activities_by_day = {}
    for a in activities:
        day_num = int(a.get("day_number") or 1)
        if day_num not in activities_by_day:
            activities_by_day[day_num] = []
        activities_by_day[day_num].append(a)
        
    for day_idx in range(1, duration + 1):
        day_acts = activities_by_day.get(day_idx, [])
        day_date = start_date + timedelta(days=day_idx - 1)
        day_date_str = day_date.strftime("%A, %b %d, %Y")
        
        day_story = []
        day_story.append(Paragraph(f"Day {day_idx} — {day_date_str}", day_heading))
        
        if not day_acts:
            day_story.append(Paragraph("No activities scheduled for this day.", body_style))
        else:
            act_data = [[
                Paragraph("Activity", table_header_style),
                Paragraph("Description", table_header_style),
                Paragraph("Cost", table_header_style)
            ]]
            for a in day_acts:
                cost_str = f"{currency} {a.get('cost', 0.0):,.2f}" if a.get("cost", 0.0) > 0 else "Free"
                act_data.append([
                    Paragraph(a.get("name", "N/A"), body_style),
                    Paragraph(a.get("description", "") or "No description provided.", body_style),
                    Paragraph(cost_str, body_bold)
                ])
            
            act_table = Table(act_data, colWidths=[130, 294, 80])
            act_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0284C7")),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ]))
            day_story.append(act_table)
            
        day_story.append(Spacer(1, 10))
        story.append(KeepTogether(day_story))
        
    # 6. Validation Notes Box
    notes = itinerary.get("validation_notes")
    if notes:
        story.append(Spacer(1, 15))
        validation_box = [
            Paragraph("Validation Notes & Feedback Warnings", ParagraphStyle(
                'ValTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor("#B45309")
            )),
            Spacer(1, 4),
            Paragraph(notes, ParagraphStyle(
                'ValBody', parent=body_style, fontSize=8, leading=10, textColor=colors.HexColor("#78350F")
            ))
        ]
        val_table = Table([[validation_box]], colWidths=[504])
        val_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FEF3C7")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#FDE68A")),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(KeepTogether([val_table]))
        
    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
