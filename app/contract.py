"""Contract PDF generation module"""
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT


def generate_contract_pdf(partner_data: dict) -> bytes:
    """
    Generate contract PDF with partner data
    
    Args:
        partner_data: Dictionary containing:
            - name: Partner company name
            - street: Street address
            - zip: Postal code
            - city: City
            - vat: VAT number
            - peppol_endpoint: KvK number
    
    Returns:
        PDF as bytes
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                           rightMargin=20*mm, leftMargin=20*mm,
                           topMargin=20*mm, bottomMargin=20*mm)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor='black',
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor='black',
        spaceAfter=12,
        spaceBefore=12,
        alignment=TA_LEFT
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        textColor='black',
        spaceAfter=12,
        alignment=TA_LEFT
    )
    
    # Header
    elements.append(Paragraph("Samenwerkingsovereenkomst", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Friettruckhuren.nl - Partnerovereenkomst", heading_style))
    elements.append(Spacer(1, 20))
    
    # Date
    today = datetime.now().strftime("%d-%m-%Y")
    elements.append(Paragraph(f"Datum: {today}", normal_style))
    elements.append(Spacer(1, 20))
    
    # Partijen section
    elements.append(Paragraph("Partijen:", heading_style))
    elements.append(Paragraph("Friettruckhuren.nl, handelsnaam van Treatlab VOF", normal_style))
    elements.append(Paragraph("Thomas Edisonstraat 14, 3284WD Zuid-Beijerland", normal_style))
    elements.append(Paragraph("KvK: 77075382 | BTW: NL860892141B01", normal_style))
    elements.append(Paragraph("Vertegenwoordigd door: Robby Grob", normal_style))
    elements.append(Spacer(1, 12))
    
    # Partner data
    partner_name = partner_data.get('name', 'N/A')
    partner_street = partner_data.get('street', '')
    partner_zip = partner_data.get('zip', '')
    partner_city = partner_data.get('city', '')
    partner_vat = partner_data.get('vat', '')
    partner_kvk = partner_data.get('peppol_endpoint', '')
    
    # Build partner address
    partner_address_parts = []
    if partner_name:
        partner_address_parts.append(partner_name)
    if partner_street:
        partner_address_parts.append(partner_street)
    if partner_zip and partner_city:
        partner_address_parts.append(f"{partner_zip} {partner_city}")
    elif partner_zip:
        partner_address_parts.append(partner_zip)
    elif partner_city:
        partner_address_parts.append(partner_city)
    
    for part in partner_address_parts:
        elements.append(Paragraph(part, normal_style))
    
    if partner_kvk:
        elements.append(Paragraph(f"KvK: {partner_kvk}", normal_style))
    if partner_vat:
        elements.append(Paragraph(f"BTW: {partner_vat}", normal_style))
    
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("en", normal_style))
    elements.append(Spacer(1, 20))
    
    # Artikel 1 - Samenwerking
    elements.append(Paragraph("Artikel 1 - Samenwerking", heading_style))
    elements.append(Paragraph("• Friettruckhuren.nl exploiteert een platform waarop opdrachten voor frietcatering worden aangeboden.", normal_style))
    elements.append(Paragraph("• Partner kan via het partnerportaal opdrachten claimen.", normal_style))
    elements.append(Paragraph("• Partner voert geclaimde opdrachten zelfstandig uit en blijft verantwoordelijk voor de uitvoering.", normal_style))
    elements.append(Paragraph("• Friettruckhuren.nl verzorgt verkoop, marketing, communicatie met klanten en administratieve afhandeling.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 2 - Vergoeding
    elements.append(Paragraph("Artikel 2 - Vergoeding", heading_style))
    elements.append(Paragraph("• Partner ontvangt een vergoeding per uitgevoerde opdracht zoals vermeld in het partnerportaal.", normal_style))
    elements.append(Paragraph("• De vergoeding wordt bepaald op basis van de opdrachtgegevens en is exclusief BTW.", normal_style))
    elements.append(Paragraph("• Friettruckhuren.nl behoudt zich het recht voor om vergoedingen aan te passen met voorafgaande kennisgeving.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 3 - Betaling
    elements.append(Paragraph("Artikel 3 - Betaling", heading_style))
    elements.append(Paragraph("• Betalingen vinden plaats volgens de betaalcondities zoals vermeld in het partnerportaal.", normal_style))
    elements.append(Paragraph("• Voor zakelijke opdrachten geldt de betaaltermijn zoals overeengekomen in de opdracht.", normal_style))
    elements.append(Paragraph("• Partner dient een geldig IBAN-rekeningnummer te verstrekken voor betalingen.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 4 - Self-billing
    elements.append(Paragraph("Artikel 4 - Self-billing", heading_style))
    elements.append(Paragraph("• Friettruckhuren.nl verzorgt self-billing voor alle opdrachten.", normal_style))
    elements.append(Paragraph("• Partner ontvangt automatisch gegenereerde facturen via het partnerportaal.", normal_style))
    elements.append(Paragraph("• Partner dient alle benodigde gegevens correct en volledig aan te leveren voor self-billing.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 5 - No-show
    elements.append(Paragraph("Artikel 5 - No-show", heading_style))
    elements.append(Paragraph("• Bij no-show of niet-naleving van de opdracht kan Friettruckhuren.nl een boete opleggen.", normal_style))
    elements.append(Paragraph("• De hoogte van de boete wordt bepaald op basis van de schade die is geleden.", normal_style))
    elements.append(Paragraph("• Partner is verantwoordelijk voor tijdige communicatie bij wijzigingen of annuleringen.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 6 - Algemene voorwaarden
    elements.append(Paragraph("Artikel 6 - Algemene voorwaarden", heading_style))
    elements.append(Paragraph("• Op deze overeenkomst zijn de Algemene Partnervoorwaarden van Friettruckhuren.nl van toepassing.", normal_style))
    elements.append(Paragraph("• Deze voorwaarden zijn opgenomen in de bijlage en maken integraal deel uit van deze overeenkomst.", normal_style))
    elements.append(Spacer(1, 20))
    
    # Algemene Partnervoorwaarden
    elements.append(PageBreak())
    elements.append(Paragraph("Algemene Partnervoorwaarden", title_style))
    elements.append(Spacer(1, 20))
    
    # Artikel 1
    elements.append(Paragraph("Artikel 1 - Definities", heading_style))
    elements.append(Paragraph("In deze voorwaarden wordt verstaan onder: Platform: het digitale platform van Friettruckhuren.nl; Partner: de partij die via het platform opdrachten uitvoert; Opdracht: een concrete frietcatering opdracht zoals aangeboden via het platform.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 2
    elements.append(Paragraph("Artikel 2 - Toepasselijkheid", heading_style))
    elements.append(Paragraph("Deze voorwaarden zijn van toepassing op alle overeenkomsten tussen Friettruckhuren.nl en Partner, tenzij schriftelijk anders overeengekomen.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 3
    elements.append(Paragraph("Artikel 3 - Aanmelding en account", heading_style))
    elements.append(Paragraph("Partner dient zich aan te melden via het partnerportaal en een account aan te maken. Partner is verantwoordelijk voor de juistheid van de verstrekte gegevens en de vertrouwelijkheid van inloggegevens.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 4
    elements.append(Paragraph("Artikel 4 - Claimen van opdrachten", heading_style))
    elements.append(Paragraph("Partner kan opdrachten claimen via het partnerportaal. Een geclaimde opdracht is bindend en dient te worden uitgevoerd volgens de opdrachtspecificaties.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 5
    elements.append(Paragraph("Artikel 5 - Uitvoering opdrachten", heading_style))
    elements.append(Paragraph("Partner voert opdrachten zelfstandig uit en is verantwoordelijk voor de kwaliteit, veiligheid en tijdige uitvoering. Partner dient te beschikken over de benodigde vergunningen en verzekeringen.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 6
    elements.append(Paragraph("Artikel 6 - Kwaliteitseisen", heading_style))
    elements.append(Paragraph("Partner dient te voldoen aan alle geldende kwaliteitseisen en hygiënenormen. Friettruckhuren.nl behoudt zich het recht voor om kwaliteitscontroles uit te voeren.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 7
    elements.append(Paragraph("Artikel 7 - Verzekeringen", heading_style))
    elements.append(Paragraph("Partner dient te beschikken over een geldige aansprakelijkheidsverzekering en andere benodigde verzekeringen voor de uitvoering van opdrachten.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 8
    elements.append(Paragraph("Artikel 8 - Geheimhouding", heading_style))
    elements.append(Paragraph("Partner verplicht zich tot geheimhouding van alle vertrouwelijke informatie die hij in het kader van de samenwerking verwerft.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 9
    elements.append(Paragraph("Artikel 9 - Intellectueel eigendom", heading_style))
    elements.append(Paragraph("Alle intellectuele eigendomsrechten op het platform en de daarbij behorende materialen blijven eigendom van Friettruckhuren.nl.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 10
    elements.append(Paragraph("Artikel 10 - Aansprakelijkheid", heading_style))
    elements.append(Paragraph("Friettruckhuren.nl is niet aansprakelijk voor schade die Partner lijdt in verband met de uitvoering van opdrachten, tenzij sprake is van opzet of bewuste roekeloosheid.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 11
    elements.append(Paragraph("Artikel 11 - Schadevergoeding", heading_style))
    elements.append(Paragraph("Partner is aansprakelijk voor alle schade die voortvloeit uit de uitvoering van opdrachten en dient deze te vergoeden aan Friettruckhuren.nl of derden.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 12
    elements.append(Paragraph("Artikel 12 - Opzegging", heading_style))
    elements.append(Paragraph("Beide partijen kunnen deze overeenkomst opzeggen met een opzegtermijn van 30 dagen, tenzij anders overeengekomen.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 13
    elements.append(Paragraph("Artikel 13 - Wijzigingen", heading_style))
    elements.append(Paragraph("Wijzigingen in deze voorwaarden worden schriftelijk medegedeeld en treden in werking 30 dagen na kennisgeving, tenzij Partner bezwaar maakt.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 14
    elements.append(Paragraph("Artikel 14 - Geschillen", heading_style))
    elements.append(Paragraph("Geschillen worden in eerste instantie opgelost door middel van overleg. Indien dit niet tot een oplossing leidt, worden geschillen voorgelegd aan de bevoegde rechter.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 15
    elements.append(Paragraph("Artikel 15 - Toepasselijk recht", heading_style))
    elements.append(Paragraph("Op deze overeenkomst is Nederlands recht van toepassing.", normal_style))
    elements.append(Spacer(1, 12))
    
    # Artikel 16
    elements.append(Paragraph("Artikel 16 - Overige bepalingen", heading_style))
    elements.append(Paragraph("Indien een bepaling van deze voorwaarden nietig of vernietigbaar blijkt, blijven de overige bepalingen van kracht.", normal_style))
    elements.append(Spacer(1, 20))
    
    # Ondertekening
    elements.append(PageBreak())
    elements.append(Paragraph("Ondertekening", heading_style))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Deze overeenkomst treedt in werking op de datum van ondertekening door beide partijen.", normal_style))
    elements.append(Spacer(1, 30))
    
    # Signatures
    elements.append(Paragraph("Friettruckhuren.nl", heading_style))
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("_________________________", normal_style))
    elements.append(Paragraph("Robby Grob", normal_style))
    elements.append(Paragraph("Datum: _________________", normal_style))
    elements.append(Spacer(1, 30))
    
    elements.append(Paragraph(partner_name if partner_name else "Partner", heading_style))
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("_________________________", normal_style))
    elements.append(Paragraph("Naam: _________________", normal_style))
    elements.append(Paragraph("Datum: _________________", normal_style))
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
