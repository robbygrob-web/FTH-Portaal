"""Factuur PDF generation module"""
import os
from datetime import datetime
from decimal import Decimal
from io import BytesIO
import psycopg2
from psycopg2.extras import RealDictCursor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib import colors

# Bedrijfsgegevens constanten
BEDRIJFS_NAAM = "Friettruck-huren.nl"
BEDRIJFS_ADRES = "Thomas Edisonstraat 14, 3284WD Zuid-Beijerland"
BEDRIJFS_KVK = "77075382"
BEDRIJFS_BTW = "NL860892141B01"
BEDRIJFS_TELEFOON = "085-212 7601"
BEDRIJFS_REKENING = "NL91ABNA0417164300 t.n.v. Treatlab VOF"


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL niet gevonden in environment variabelen")
    return database_url


def generate_factuur_pdf(order_id: str) -> bytes:
    """
    Generate factuur PDF on-the-fly voor een order.
    
    Args:
        order_id: UUID van de order
        
    Returns:
        PDF as bytes
        
    Raises:
        ValueError: Als order niet gevonden wordt
    """
    database_url = get_database_url()
    
    # Database queries
    conn = None
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Query 1: Order + Klant gegevens
        cur.execute("""
            SELECT 
                o.id, o.ordernummer, o.leverdatum, o.plaats, 
                o.aantal_personen, o.aantal_kinderen, o.ordertype,
                c.id as klant_id, c.voornaam, c.naam as achternaam, 
                c.email, c.adres, c.postcode, c.land, c.btw_nummer
            FROM orders o
            LEFT JOIN contacten c ON o.klant_id = c.id
            WHERE o.id = %s;
        """, (order_id,))
        
        order_row = cur.fetchone()
        if not order_row:
            raise ValueError(f"Order {order_id} niet gevonden")
        
        # Query 2: Factuurnummer ophalen (als bestaat)
        cur.execute("""
            SELECT factuurnummer
            FROM facturen
            WHERE order_id = %s
            LIMIT 1;
        """, (order_id,))
        
        factuur_row = cur.fetchone()
        factuurnummer = factuur_row['factuurnummer'] if factuur_row else f"FTH-{order_row['ordernummer']}"
        
        # Query 3: Order artikelen
        cur.execute("""
            SELECT naam, aantal, prijs_incl
            FROM order_artikelen
            WHERE order_id = %s
            ORDER BY naam;
        """, (order_id,))
        
        artikelen_rows = cur.fetchall()
        
        # Query 4: Totaal bedrag berekenen
        cur.execute("""
            SELECT SUM(prijs_incl * aantal) as totaal
            FROM order_artikelen
            WHERE order_id = %s;
        """, (order_id,))
        
        totaal_row = cur.fetchone()
        totaal_incl_btw = Decimal(str(totaal_row['totaal'] or 0))
        
        # BTW berekening (9%)
        bedrag_excl_btw = totaal_incl_btw / Decimal('1.09')
        btw_bedrag = totaal_incl_btw - bedrag_excl_btw
        
        # Data structuur
        order_data = {
            'ordernummer': order_row['ordernummer'],
            'leverdatum': order_row['leverdatum'],
            'plaats': order_row['plaats'],
            'aantal_personen': order_row['aantal_personen'] or 0,
            'aantal_kinderen': order_row['aantal_kinderen'] or 0,
            'ordertype': order_row['ordertype'],
            'klant': {
                'voornaam': order_row['voornaam'],
                'achternaam': order_row['achternaam'],
                'email': order_row['email'],
                'adres': order_row['adres'],
                'postcode': order_row['postcode'],
                'land': order_row['land'],
                'btw_nummer': order_row['btw_nummer']
            },
            'factuurnummer': factuurnummer,
            'artikelen': [
                {
                    'naam': row['naam'],
                    'aantal': Decimal(str(row['aantal'])),
                    'prijs_incl': Decimal(str(row['prijs_incl']))
                }
                for row in artikelen_rows
            ],
            'totaal_incl_btw': totaal_incl_btw,
            'bedrag_excl_btw': bedrag_excl_btw,
            'btw_bedrag': btw_bedrag
        }
        
    finally:
        if conn:
            cur.close()
            conn.close()
    
    # PDF generatie
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor='black',
        spaceAfter=12,
        alignment=TA_LEFT
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor='black',
        spaceAfter=8,
        spaceBefore=12,
        alignment=TA_LEFT
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        textColor='black',
        spaceAfter=6,
        alignment=TA_LEFT
    )
    
    normal_right_style = ParagraphStyle(
        'CustomNormalRight',
        parent=normal_style,
        alignment=TA_RIGHT
    )
    
    bold_style = ParagraphStyle(
        'CustomBold',
        parent=normal_style,
        fontSize=12,
        fontName='Helvetica-Bold'
    )
    
    bold_right_style = ParagraphStyle(
        'CustomBoldRight',
        parent=bold_style,
        alignment=TA_RIGHT
    )
    
    # Header sectie (linksboven)
    elements.append(Paragraph(BEDRIJFS_NAAM, title_style))
    elements.append(Paragraph(BEDRIJFS_ADRES, normal_style))
    elements.append(Paragraph(f"KvK: {BEDRIJFS_KVK} | BTW: {BEDRIJFS_BTW}", normal_style))
    elements.append(Paragraph(f"Tel: {BEDRIJFS_TELEFOON}", normal_style))
    
    # Rekeningnummer alleen bij b2b
    if order_data['ordertype'] == 'b2b':
        elements.append(Paragraph(f"Rekeningnummer: {BEDRIJFS_REKENING}", normal_style))
    
    elements.append(Spacer(1, 20))
    
    # Factuur informatie (rechtsboven) - gebruik Table voor alignment
    factuur_info_data = [
        [Paragraph("FACTUUR", heading_style), ""],
        [Paragraph(f"Factuurnummer: {order_data['factuurnummer']}", normal_style), ""],
        [Paragraph(f"Factuurdatum: {datetime.now().strftime('%d-%m-%Y')}", normal_style), ""],
        [Paragraph(f"Ordernummer: {order_data['ordernummer']}", normal_style), ""],
    ]
    
    leverdatum_str = "Niet opgegeven"
    if order_data['leverdatum']:
        leverdatum_str = order_data['leverdatum'].strftime('%d-%m-%Y')
    factuur_info_data.append([Paragraph(f"Leverdatum: {leverdatum_str}", normal_style), ""])
    
    factuur_info_table = Table(factuur_info_data, colWidths=[120*mm, 50*mm])
    factuur_info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(factuur_info_table)
    elements.append(Spacer(1, 20))
    
    # Klant informatie (links, onder header)
    klant = order_data['klant']
    klant_naam = ""
    if klant['voornaam'] and klant['achternaam']:
        klant_naam = f"{klant['voornaam']} {klant['achternaam']}"
    elif klant['achternaam']:
        klant_naam = klant['achternaam']
    
    if klant_naam:
        elements.append(Paragraph(klant_naam, normal_style))
    
    if klant['adres']:
        elements.append(Paragraph(klant['adres'], normal_style))
    
    postcode_land = []
    if klant['postcode']:
        postcode_land.append(klant['postcode'])
    if klant['land']:
        postcode_land.append(klant['land'])
    if postcode_land:
        elements.append(Paragraph(' '.join(postcode_land), normal_style))
    
    # BTW nummer alleen tonen als het bestaat en niet leeg is
    if klant['btw_nummer'] and klant['btw_nummer'].strip():
        elements.append(Paragraph(f"BTW nummer: {klant['btw_nummer']}", normal_style))
    
    elements.append(Spacer(1, 20))
    
    # Artikelen tabel
    artikelen_data = [
        ['Omschrijving', 'Aantal', 'Prijs', 'Totaal']
    ]
    
    for artikel in order_data['artikelen']:
        totaal_per_regel = artikel['aantal'] * artikel['prijs_incl']
        artikelen_data.append([
            artikel['naam'],
            str(artikel['aantal']),
            f"€{artikel['prijs_incl']:.2f}",
            f"€{totaal_per_regel:.2f}"
        ])
    
    artikelen_table = Table(artikelen_data, colWidths=[100*mm, 20*mm, 25*mm, 25*mm])
    artikelen_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))
    elements.append(artikelen_table)
    elements.append(Spacer(1, 20))
    
    # Totaal sectie (rechts uitgelijnd)
    totaal_data = [
        [Paragraph("Subtotaal (excl BTW):", normal_style), Paragraph(f"€{order_data['bedrag_excl_btw']:.2f}", normal_right_style)],
        [Paragraph("BTW (9%):", normal_style), Paragraph(f"€{order_data['btw_bedrag']:.2f}", normal_right_style)],
        [Paragraph("Totaal (incl BTW):", bold_style), Paragraph(f"€{order_data['totaal_incl_btw']:.2f}", bold_right_style)],
    ]
    
    totaal_table = Table(totaal_data, colWidths=[120*mm, 50*mm])
    totaal_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(totaal_table)
    elements.append(Spacer(1, 30))
    
    # Footer
    elements.append(Paragraph("Bedankt voor uw bestelling!", normal_style))
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
