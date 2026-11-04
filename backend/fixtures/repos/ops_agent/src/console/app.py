"""Engineer console: audit log view and the kill switch. OIDC login required."""

from __future__ import annotations

import os

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, FastAPI, HTTPException, Request

from src.agent.killswitch import stop_and_rollback

app = FastAPI(title="Remedy console")
oauth = OAuth()
oauth.register(
    "corp", server_metadata_url=f"{os.environ['OIDC_ISSUER']}.well-known/openid-configuration"
)


def engineer(request: Request) -> str:
    user = request.session.get("user")
    if not user or "infra-engineering" not in user.get("groups", []):
        raise HTTPException(status_code=401, detail="sign in with the corporate account")
    return str(user["email"])


@app.post("/agent/stop")
def stop(who: str = Depends(engineer)) -> dict[str, str]:
    return {"status": stop_and_rollback(), "by": who}
