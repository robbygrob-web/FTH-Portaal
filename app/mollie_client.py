"""
Mollie API client helper.
"""
import os
import logging
from typing import Optional, Dict, Any
from mollie.api.client import Client as MollieClient

_LOG = logging.getLogger(__name__)


def get_mollie_client() -> MollieClient:
    """Haal Mollie client op met API key uit environment"""
    api_key = os.getenv("MOLLIE_API_KEY")
    if not api_key:
        raise ValueError("MOLLIE_API_KEY niet gevonden in environment variabelen")
    
    mollie_client = MollieClient()
    mollie_client.set_api_key(api_key)
    
    return mollie_client


def create_payment(
    amount: float,
    description: str,
    redirect_url: str,
    webhook_url: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Maak een Mollie payment aan.
    
    Args:
        amount: Bedrag in EUR (bijv. 25.50)
        description: Beschrijving van de betaling
        redirect_url: URL waar gebruiker naartoe wordt gestuurd na betaling
        webhook_url: URL waar Mollie webhook naar stuurt
        metadata: Extra metadata (bijv. order_id)
    
    Returns:
        Payment object van Mollie
    """
    mollie_client = get_mollie_client()
    
    payment = mollie_client.payments.create({
        "amount": {
            "currency": "EUR",
            "value": f"{amount:.2f}"
        },
        "description": description,
        "redirectUrl": redirect_url,
        "webhookUrl": webhook_url,
        "metadata": metadata
    })
    
    return {
        "id": payment.id,
        "status": payment.status,
        "checkout_url": payment.checkout_url,
        "amount": payment.amount,
        "description": payment.description
    }


def get_payment(payment_id: str) -> Dict[str, Any]:
    """
    Haal payment op van Mollie.
    
    Args:
        payment_id: Mollie payment ID
    
    Returns:
        Payment object van Mollie
    """
    mollie_client = get_mollie_client()
    
    payment = mollie_client.payments.get(payment_id)
    
    return {
        "id": payment.id,
        "status": payment.status,
        "checkout_url": payment.checkout_url,
        "amount": payment.amount,
        "description": payment.description,
        "metadata": payment.metadata
    }


def cancel_payment(payment_id: str) -> bool:
    """
    Annuleer een Mollie payment.
    
    Args:
        payment_id: Mollie payment ID
    
    Returns:
        True als succesvol geannuleerd, False anders
    """
    try:
        mollie_client = get_mollie_client()
        payment = mollie_client.payments.get(payment_id)
        
        # Probeer te annuleren (alleen mogelijk als status open/pending)
        if payment.status in ["open", "pending"]:
            payment.delete()
            return True
        else:
            _LOG.warning(f"Payment {payment_id} kan niet geannuleerd worden (status: {payment.status})")
            return False
    except Exception as e:
        _LOG.error(f"Fout bij annuleren Mollie payment {payment_id}: {e}", exc_info=True)
        return False
