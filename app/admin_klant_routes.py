"""
Admin klant detail endpoints.
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
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
            SELECT id, naam, email, telefoon
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
            </style>
        </head>
        <body>
            <div class="header">
                <a href="/admin?token={SESSION_SECRET}" class="back-link">← Terug naar dashboard</a>
                <h1>Klant: {klant.get('naam', 'N/A')}</h1>
            </div>
            
            <div class="section">
                <h2>Klantgegevens</h2>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Naam</div>
                        <div class="info-value">{klant.get('naam') or '-'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Email</div>
                        <div class="info-value">{klant.get('email') or '-'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Telefoon</div>
                        <div class="info-value">{klant.get('telefoon') or '-'}</div>
                    </div>
                </div>
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
