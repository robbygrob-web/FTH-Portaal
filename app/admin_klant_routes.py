"""
Admin klant detail endpoints.
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor
from app.config import SESSION_SECRET
from app.admin_routes import verify_admin_session, get_database_url

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/klant", tags=["admin"])


@router.get("/{klant_id}", response_class=HTMLResponse)
async def klant_detail(request: Request, klant_id: str, verified: bool = Depends(verify_admin_session)):
    """Detail pagina voor een klant"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal klant op
        cur.execute("""
            SELECT id, naam, email, telefoon, adres, postcode, land
            FROM contacten
            WHERE id = %s
        """, (klant_id,))
        
        klant = cur.fetchone()
        if not klant:
            raise HTTPException(status_code=404, detail="Klant niet gevonden")
        
        # Haal orders op voor deze klant
        cur.execute("""
            SELECT 
                id,
                ordernummer,
                leverdatum,
                plaats,
                portaal_status,
                status,
                totaal_bedrag
            FROM orders
            WHERE klant_id = %s
            ORDER BY created_at DESC
        """, (klant_id,))
        
        orders = cur.fetchall()
        
        # Format leverdatum
        def format_datetime(dt):
            if not dt:
                return "-"
            if isinstance(dt, str):
                return dt[:16]
            return dt.strftime("%Y-%m-%d %H:%M")
        
        # Format status
        def format_portaal_status(status):
            status_map = {
                "nieuw": ("Nieuw", "#3498db"),
                "beschikbaar": ("Beschikbaar", "#27ae60"),
                "claimed": ("Geclaimd", "#e67e22"),
                "transfer": ("Transfer", "#9b59b6")
            }
            return status_map.get(status, (status, "#999"))
        
        def format_order_status(status):
            status_map = {
                "sent": ("Offerte", "#3498db"),
                "sale": ("Verkooporder", "#27ae60"),
                "draft": ("Concept", "#999")
            }
            return status_map.get(status, (status, "#999"))
        
        # Build orders table rows
        orders_rows = ""
        for order in orders:
            order_id = str(order.get("id"))
            ordernummer = order.get("ordernummer") or "-"
            leverdatum = format_datetime(order.get("leverdatum"))
            plaats = order.get("plaats") or "-"
            portaal_status_text, portaal_status_color = format_portaal_status(order.get("portaal_status", "nieuw"))
            order_status_text, order_status_color = format_order_status(order.get("status", "draft"))
            totaal = float(order.get("totaal_bedrag", 0))
            
            orders_rows += f"""
            <tr>
                <td><a href="/admin/order/{order_id}?token={SESSION_SECRET}" style="color:#333;text-decoration:none;font-weight:500;">{ordernummer}</a></td>
                <td>{leverdatum}</td>
                <td>{plaats}</td>
                <td><span style="color:{portaal_status_color};">{portaal_status_text}</span></td>
                <td><span style="color:{order_status_color};">{order_status_text}</span></td>
                <td>€ {totaal:,.2f}</td>
            </tr>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="nl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>FTH Admin - Klant</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: #fffdf2;
                    padding: 20px;
                }}
                .header {{
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header h1 {{
                    color: #333333;
                    margin-bottom: 10px;
                }}
                .back-link {{
                    color: #666;
                    text-decoration: none;
                    margin-bottom: 20px;
                    display: inline-block;
                }}
                .section {{
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .section h2 {{
                    color: #333333;
                    margin-bottom: 15px;
                    font-size: 20px;
                }}
                .info-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 15px;
                }}
                .info-item {{
                    padding: 10px;
                    background: #f9f9f9;
                    border-radius: 8px;
                }}
                .info-label {{
                    font-size: 12px;
                    color: #666;
                    margin-bottom: 4px;
                }}
                .info-value {{
                    font-size: 16px;
                    color: #333;
                    font-weight: 500;
                }}
                input[type="text"],
                input[type="email"] {{
                    width: 100%;
                    padding: 8px 12px;
                    border: 2px solid #e0e0e0;
                    border-radius: 6px;
                    font-size: 14px;
                    font-family: inherit;
                    transition: border-color 0.3s;
                }}
                input[type="text"]:focus,
                input[type="email"]:focus {{
                    outline: none;
                    border-color: #e2af13;
                }}
                .save-button {{
                    background: #fec82a;
                    color: #333333;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: 700;
                    cursor: pointer;
                    margin-top: 20px;
                }}
                .save-button:hover {{
                    background: #e2af13;
                }}
                form {{
                    margin-top: 10px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 15px;
                }}
                th {{
                    text-align: left;
                    padding: 12px;
                    background: #f5f5f5;
                    font-weight: 600;
                    color: #333;
                    border-bottom: 2px solid #e0e0e0;
                }}
                td {{
                    padding: 12px;
                    border-bottom: 1px solid #e0e0e0;
                }}
                tr:hover {{
                    background: #f9f9f9;
                }}
                .chat-section {{
                    margin-top: 20px;
                }}
                .chat-container {{
                    max-height: 500px;
                    overflow-y: auto;
                    display: flex;
                    flex-direction: column;
                    gap: 16px;
                    padding: 10px;
                }}
                .chat-loading, .chat-empty {{
                    text-align: center;
                    padding: 20px;
                    color: #999;
                }}
                .chat-message {{
                    display: flex;
                    flex-direction: column;
                }}
                .chat-message.inkomend {{
                    align-items: flex-start;
                }}
                .chat-message.uitgaand {{
                    align-items: flex-end;
                }}
                .chat-label {{
                    font-size: 11px;
                    color: #999;
                    margin-bottom: 3px;
                }}
                .chat-bubble {{
                    max-width: 70%;
                    padding: 10px 14px;
                    border-radius: 12px;
                    line-height: 1.5;
                    word-wrap: break-word;
                }}
                .chat-bubble.inkomend {{
                    background: #f5f5f5;
                    color: #333;
                }}
                .chat-bubble.uitgaand {{
                    background: #e8f4fd;
                    color: #333;
                }}
                .chat-bubble.placeholder {{
                    font-style: italic;
                    color: #999;
                }}
                .chat-time {{
                    font-size: 11px;
                    color: #999;
                    margin-top: 4px;
                }}
                .chat-message-expand {{
                    cursor: pointer;
                    user-select: none;
                    font-size: 12px;
                    color: #999;
                    margin-right: 8px;
                    transition: transform 0.2s;
                    display: inline-block;
                }}
                .chat-message.expanded .chat-message-expand {{
                    transform: rotate(90deg);
                }}
                .chat-message-preview {{
                    display: none;
                }}
                .chat-message.expanded .chat-message-preview {{
                    display: block;
                }}
                .chat-order-badge {{
                    display: inline-block;
                    margin-top: 6px;
                    font-size: 12px;
                    color: #3498db;
                    text-decoration: none;
                }}
                .chat-order-badge:hover {{
                    text-decoration: underline;
                }}
                .chat-input-area {{
                    margin-top: 15px;
                    padding-top: 15px;
                    border-top: 2px solid #e0e0e0;
                    display: flex;
                    gap: 10px;
                }}
                .chat-input {{
                    flex: 1;
                    padding: 10px;
                    border-radius: 8px;
                    border: 1px solid #ddd;
                    font-size: 14px;
                    resize: none;
                }}
                .chat-send-btn {{
                    padding: 10px 20px;
                    background: #fec82a;
                    border: none;
                    border-radius: 8px;
                    cursor: not-allowed;
                    opacity: 0.5;
                    font-weight: 600;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <a href="/admin?token={SESSION_SECRET}" class="back-link">← Terug naar dashboard</a>
                <h1>Klant: {klant.get('naam', 'N/A')}</h1>
            </div>
            
            <div class="section">
                <h2>Klantgegevens</h2>
                <form method="post" action="/admin/klant/{klant_id}?token={SESSION_SECRET}">
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="info-label">Bedrijfsnaam</div>
                            <input type="text" name="naam" value="{klant.get('naam') or ''}" />
                        </div>
                        <div class="info-item">
                            <div class="info-label">Email</div>
                            <input type="email" name="email" value="{klant.get('email') or ''}" />
                        </div>
                        <div class="info-item">
                            <div class="info-label">Telefoon</div>
                            <input type="text" name="telefoon" value="{klant.get('telefoon') or ''}" />
                        </div>
                        <div class="info-item">
                            <div class="info-label">Adres</div>
                            <input type="text" name="adres" value="{klant.get('adres') or ''}" />
                        </div>
                        <div class="info-item">
                            <div class="info-label">Postcode</div>
                            <input type="text" name="postcode" value="{klant.get('postcode') or ''}" />
                        </div>
                        <div class="info-item">
                            <div class="info-label">Land</div>
                            <input type="text" name="land" value="{klant.get('land') or ''}" />
                        </div>
                    </div>
                    <button type="submit" class="save-button">Opslaan</button>
                </form>
            </div>
            
            <div class="section">
                <h2>Orders</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Ordernummer</th>
                            <th>Leverdatum</th>
                            <th>Plaats</th>
                            <th>Status aanvraag</th>
                            <th>Status offerte</th>
                            <th>Totaalprijs</th>
                        </tr>
                    </thead>
                    <tbody>
                        {orders_rows if orders_rows else '<tr><td colspan="6" style="text-align:center;padding:20px;">Geen orders gevonden</td></tr>'}
                    </tbody>
                </table>
            </div>
            
            <div class="section chat-section" id="chatvenster" data-contact-id="{klant_id}">
                <h2>Berichten</h2>
                <div class="chat-container" id="chat-container">
                    <div class="chat-loading">Laden...</div>
                </div>
                <div class="chat-input-area">
                    <textarea class="chat-input" rows="2" placeholder="Agent koppeling komt hier..." disabled></textarea>
                    <button class="chat-send-btn" disabled>Verstuur</button>
                </div>
            </div>
            <script>
                (function() {{
                    const chatContainer = document.getElementById('chat-container');
                    const chatSection = document.getElementById('chatvenster');
                    const contactId = chatSection.dataset.contactId;
                    const token = new URLSearchParams(window.location.search).get('token');
                    
                    if (!token || !contactId) {{
                        chatContainer.innerHTML = '<div class="chat-empty">Geen toegang</div>';
                        return;
                    }}
                    
                    function escapeHtml(text) {{
                        if (!text) return '';
                        const div = document.createElement('div');
                        div.textContent = text;
                        return div.innerHTML;
                    }}
                    
                    function formatTime(dateString) {{
                        if (!dateString) return '';
                        const date = new Date(dateString);
                        const now = new Date();
                        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                        const yesterday = new Date(today);
                        yesterday.setDate(yesterday.getDate() - 1);
                        const messageDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
                        
                        const hours = String(date.getHours()).padStart(2, '0');
                        const minutes = String(date.getMinutes()).padStart(2, '0');
                        const timeStr = hours + ':' + minutes;
                        
                        if (messageDate.getTime() === today.getTime()) {{
                            return 'vandaag ' + timeStr;
                        }} else if (messageDate.getTime() === yesterday.getTime()) {{
                            return 'gisteren ' + timeStr;
                        }} else {{
                            const day = String(date.getDate()).padStart(2, '0');
                            const month = String(date.getMonth() + 1).padStart(2, '0');
                            const year = date.getFullYear();
                            return day + '-' + month + '-' + year + ' ' + timeStr;
                        }}
                    }}
                    
                    fetch('/admin/klant/communicatie/contact/' + encodeURIComponent(contactId) + '?token=' + encodeURIComponent(token))
                        .then(response => response.json())
                        .then(data => {{
                            if (!data.berichten || data.berichten.length === 0) {{
                                chatContainer.innerHTML = '<div class="chat-empty">Geen berichten</div>';
                                return;
                            }}
                            
                            let html = '';
                            
                            data.berichten.forEach(bericht => {{
                                const richting = bericht.richting || 'inkomend';
                                const isInkomend = richting === 'inkomend';
                                const isUitgaand = richting === 'uitgaand';
                                
                                // Bepaal body content (volgorde: body → preview → onderwerp → "(Geen inhoud)")
                                let bodyContent = '';
                                let isPlaceholder = false;
                                
                                if (bericht.body) {{
                                    bodyContent = bericht.body; // Raw HTML, geen escapeHtml
                                }} else if (bericht.preview) {{
                                    bodyContent = bericht.preview; // Raw HTML, geen escapeHtml
                                }} else if (bericht.onderwerp) {{
                                    bodyContent = escapeHtml(bericht.onderwerp); // Plain text, wel escapeHtml
                                    isPlaceholder = true;
                                }} else {{
                                    bodyContent = '(Geen inhoud)';
                                    isPlaceholder = true;
                                }}
                                
                                // Tijd formatteren
                                const tijd = formatTime(bericht.verzonden_op);
                                
                                // Label voor uitgaande berichten (template_naam → onderwerp → "Mail")
                                let labelHtml = '';
                                if (isUitgaand) {{
                                    const labelText = bericht.template_naam || bericht.onderwerp || 'Mail';
                                    labelHtml = '<div class="chat-label">' + escapeHtml(labelText) + '</div>';
                                }}
                                
                                // Order badge als order_id aanwezig
                                let orderBadgeHtml = '';
                                if (bericht.order_id) {{
                                    const orderLink = '/admin/order/' + bericht.order_id + '?token=' + encodeURIComponent(token);
                                    orderBadgeHtml = '<a href="' + orderLink + '" class="chat-order-badge">→ Order bekijken</a>';
                                }}
                                
                                // Build message HTML
                                html += '<div class="chat-message ' + richting + '">';
                                html += '<span class="chat-message-expand" onclick="event.stopPropagation(); window.toggleChatExpand(this)">▶</span>';
                                if (labelHtml) {{
                                    html += labelHtml;
                                }}
                                html += '<div class="chat-message-preview">';
                                html += '<div class="chat-bubble ' + richting + (isPlaceholder ? ' placeholder' : '') + '">';
                                html += bodyContent;
                                html += '</div>';
                                html += '</div>';
                                if (orderBadgeHtml) {{
                                    html += orderBadgeHtml;
                                }}
                                if (tijd) {{
                                    html += '<div class="chat-time">' + escapeHtml(tijd) + '</div>';
                                }}
                                html += '</div>';
                            }});
                            
                            chatContainer.innerHTML = html;
                            
                            // Scroll naar beneden
                            chatContainer.scrollTop = chatContainer.scrollHeight;
                        }})
                        .catch(error => {{
                            console.error('Fout bij ophalen berichten:', error);
                            chatContainer.innerHTML = '<div class="chat-empty">Fout bij laden berichten</div>';
                        }});
                    
                    window.toggleChatExpand = function(arrow) {{
                        const item = arrow.closest('.chat-message');
                        item.classList.toggle('expanded');
                        arrow.textContent = item.classList.contains('expanded') ? '▼' : '▶';
                    }};
                }})();
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except HTTPException:
        raise
    except Exception as e:
        _LOG.error(f"Fout bij ophalen klant detail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij ophalen klant: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/{klant_id}", response_class=HTMLResponse)
async def klant_update(
    request: Request,
    klant_id: str,
    naam: str = Form(None),
    email: str = Form(None),
    telefoon: str = Form(None),
    adres: str = Form(None),
    postcode: str = Form(None),
    land: str = Form(None),
    verified: bool = Depends(verify_admin_session)
):
    """Update klantgegevens"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        # Update klantgegevens
        cur.execute("""
            UPDATE contacten
            SET naam = COALESCE(%s, naam),
                email = COALESCE(%s, email),
                telefoon = COALESCE(%s, telefoon),
                adres = COALESCE(%s, adres),
                postcode = COALESCE(%s, postcode),
                land = COALESCE(%s, land),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (naam, email, telefoon, adres, postcode, land, klant_id))
        
        conn.commit()
        
        # Redirect terug naar klant detail pagina
        token = request.query_params.get("token", SESSION_SECRET)
        return RedirectResponse(url=f"/admin/klant/{klant_id}?token={token}", status_code=303)
        
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij updaten klant: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij updaten klant: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.get("/communicatie/contact/{contact_id}")
async def communicatie_contact(
    request: Request, 
    contact_id: str, 
    verified: bool = Depends(verify_admin_session)
):
    """Haal alle berichten op voor een specifiek contact"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal contactgegevens op
        cur.execute("""
            SELECT id, naam, email 
            FROM contacten 
            WHERE id = %s
        """, (contact_id,))
        
        contact = cur.fetchone()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact niet gevonden")
        
        # Haal alle berichten op voor dit contact
        cur.execute("""
            SELECT
                ml.id,
                ml.richting,
                ml.kanaal,
                ml.template_naam,
                ml.inhoud as body,
                ml.preview,
                ml.onderwerp,
                ml.verzonden_op,
                ml.order_id,
                ml.status,
                ml.naar,
                ml.email_van
            FROM mail_logs ml
            WHERE ml.ontvanger_id = %s
            ORDER BY ml.verzonden_op ASC NULLS LAST, ml.created_at ASC
        """, (contact_id,))
        
        berichten = cur.fetchall()
        
        # Converteer contact
        contact_data = {
            "id": str(contact.get("id")),
            "naam": contact.get("naam"),
            "email": contact.get("email")
        }
        
        # Converteer berichten naar dict lijst
        berichten_list = []
        for bericht in berichten:
            berichten_list.append({
                "id": str(bericht.get("id")),
                "richting": bericht.get("richting"),
                "kanaal": bericht.get("kanaal"),
                "template_naam": bericht.get("template_naam"),
                "body": bericht.get("body"),
                "preview": bericht.get("preview"),
                "onderwerp": bericht.get("onderwerp"),
                "verzonden_op": bericht.get("verzonden_op").isoformat() if bericht.get("verzonden_op") else None,
                "order_id": str(bericht.get("order_id")) if bericht.get("order_id") else None,
                "status": bericht.get("status"),
                "naar": bericht.get("naar"),
                "email_van": bericht.get("email_van")
            })
        
        return JSONResponse({
            "contact": contact_data,
            "berichten": berichten_list
        })
        
    except HTTPException:
        raise
    except Exception as e:
        _LOG.error(f"Fout bij ophalen contact berichten: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            cur.close()
            conn.close()
