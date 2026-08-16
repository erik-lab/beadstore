from fastapi import APIRouter, Depends

from app.core.security import get_api_client
from app.models.api_client import ApiClient
from app.schemas.api_client import ApiClientWhoAmI

# Deliberately no router-level `dependencies=` — every other router in this
# app gates on get_current_user (staff/Supabase); this one gates per-route
# on get_api_client instead, since its caller is a non-human credential, not
# a logged-in staff member. First real endpoint on that auth path: lets a
# future storefront/Etsy integration confirm its key works before anything
# else is built for it to call.
router = APIRouter(prefix="/api-access", tags=["api-access"])


@router.get("/whoami", response_model=ApiClientWhoAmI)
def whoami(client: ApiClient = Depends(get_api_client)):
    return client
