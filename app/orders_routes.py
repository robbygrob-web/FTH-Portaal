"""
API routes voor orders.
"""
import os
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL niet gevonden in environment variabelen")
    return database_url


@router.get("/recent")
async def get_recent_orders():
    """
    Haal de laatste 10 orders op uit de database.
    Retourneert: id, aangemaakt_op (created_at), naam (contact), status, utm_source
    """
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal laatste 10 orders op met contact naam
        cur.execute("""
            SELECT 
                o.id,
                o.created_at as aangemaakt_op,
                o.ordernummer,
                o.status,
                o.portaal_status,
                o.utm_source,
                o.utm_medium,
                o.utm_campaign,
                o.plaats,
                o.aantal_personen,
                o.aantal_kinderen,
                o.totaal_bedrag,
                c.naam as contact_naam,
                c.email as contact_email
            FROM orders o
            LEFT JOIN contacten c ON o.klant_id = c.id
            ORDER BY o.created_at DESC
            LIMIT 10
        """)
        
        orders = cur.fetchall()
        
        # Converteer naar dict lijst voor JSON serialisatie
        result = []
        for order in orders:
            result.append({
                "id": str(order["id"]),
                "aangemaakt_op": order["aangemaakt_op"].isoformat() if order["aangemaakt_op"] else None,
                "ordernummer": order["ordernummer"],
                "status": order["status"],
                "portaal_status": order["portaal_status"],
                "naam": order["contact_naam"],
                "email": order["contact_email"],
                "utm_source": order["utm_source"],
                "utm_medium": order["utm_medium"],
                "utm_campaign": order["utm_campaign"],
                "plaats": order["plaats"],
                "aantal_personen": order["aantal_personen"],
                "aantal_kinderen": order["aantal_kinderen"],
                "totaal_bedrag": float(order["totaal_bedrag"]) if order["totaal_bedrag"] else 0.00
            })
        
        cur.close()
        
        return JSONResponse({
            "status": "success",
            "aantal": len(result),
            "orders": result
        })
        
    except Exception as e:
        _LOG.error(f"Fout bij ophalen recente orders: {e}", exc_info=True)
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=f"Fout bij ophalen orders: {str(e)}")
    finally:
        if conn:
            conn.close()
