"""
Mail routes voor test endpoints.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.mail import stuur_mail, haal_inkomende_mails
import logging

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/mail", tags=["mail"])


@router.get("/test")
async def test_mail():
    """
    Test endpoint om een testmail te sturen naar info@friettruck-huren.nl
    """
    try:
        test_email = "info@friettruck-huren.nl"
        test_onderwerp = "Test Email - FTH Portaal"
        test_inhoud = """
        <html>
            <body>
                <h1>Test Email</h1>
                <p>Dit is een test email van het FTH Portaal.</p>
                <p>Als je deze email ontvangt, werkt de mail functionaliteit correct.</p>
                <hr>
                <p><small>Verzonden via Gmail SMTP</small></p>
            </body>
        </html>
        """
        
        result = stuur_mail(
            naar=test_email,
            onderwerp=test_onderwerp,
            inhoud=test_inhoud,
            template_naam="test_email"
        )
        
        if result["success"]:
            return JSONResponse({
                "status": "success",
                "message": f"Test email verzonden naar {test_email}",
                "message_id": result["message_id"],
                "log_id": result["log_id"]
            })
        else:
            return JSONResponse(
                {
                    "status": "error",
                    "message": f"Kon test email niet verzenden: {result['error']}",
                    "error": result["error"]
                },
                status_code=500
            )
            
    except Exception as e:
        _LOG.error(f"Fout bij test mail endpoint: {e}", exc_info=True)
        return JSONResponse(
            {
                "status": "error",
                "message": f"Fout bij verzenden test email: {str(e)}"
            },
            status_code=500
        )


@router.get("/inkomend")
async def haal_inkomende_mails_endpoint():
    """
    Endpoint om nieuwe inkomende mails op te halen via Gmail API.
    Haalt ongelezen mails op en logt ze in mail_logs met richting='inkomend'.
    """
    try:
        result = haal_inkomende_mails()
        
        if result["success"]:
            return JSONResponse({
                "status": "success",
                "message": f"{result['aantal_verwerkt']} nieuwe mails verwerkt",
                "aantal_verwerkt": result["aantal_verwerkt"]
            })
        else:
            return JSONResponse(
                {
                    "status": "error",
                    "message": f"Kon inkomende mails niet ophalen: {result['error']}",
                    "error": result["error"]
                },
                status_code=500
            )
            
    except Exception as e:
        _LOG.error(f"Fout bij inkomende mails endpoint: {e}", exc_info=True)
        return JSONResponse(
            {
                "status": "error",
                "message": f"Fout bij ophalen inkomende mails: {str(e)}"
            },
            status_code=500
        )
