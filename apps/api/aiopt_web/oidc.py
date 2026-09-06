"""Vendor-neutral OpenID Connect authorization-code flow with PKCE."""
import base64,hashlib,re
from datetime import timedelta
from urllib.parse import urlencode
import httpx,jwt
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import RedirectResponse
from jwt import PyJWK
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth import CSRF_COOKIE,SESSION_COOKIE,audit,create_session
from .config import settings
from .database import db_session
from .models import OidcIdentity,OidcLoginState,User
from .security import digest,hash_password,opaque_token,utcnow

router=APIRouter(prefix="/api/v1/auth/oidc");ALGORITHMS={"RS256","RS384","RS512","ES256","ES384","ES512"}
def enabled():
    cfg=settings();return bool(cfg.oidc_issuer and cfg.oidc_client_id)
async def discovery():
    cfg=settings()
    if not enabled():raise HTTPException(404,"Enterprise identity is not configured")
    async with httpx.AsyncClient(timeout=10) as client:response=await client.get(f"{cfg.oidc_issuer}/.well-known/openid-configuration")
    response.raise_for_status();document=response.json()
    if document.get("issuer")!=cfg.oidc_issuer:raise HTTPException(502,"OIDC discovery issuer mismatch")
    for field in ("authorization_endpoint","token_endpoint","jwks_uri"):
        if not str(document.get(field,"")).startswith("https://") and cfg.environment=="production":raise HTTPException(502,"OIDC discovery endpoint is not HTTPS")
    return document
def validate_id_token(token,document,jwks,nonce=None):
    if not token:raise jwt.InvalidTokenError("ID token is missing")
    cfg=settings();header=jwt.get_unverified_header(token);algorithm=header.get("alg")
    if algorithm not in ALGORITHMS:raise jwt.InvalidAlgorithmError("Unsupported signing algorithm")
    candidates=[key for key in jwks.get("keys",[]) if key.get("kid")==header.get("kid")]
    if len(candidates)!=1:raise jwt.InvalidKeyError("Signing key was not found")
    claims=jwt.decode(token,PyJWK.from_dict(candidates[0]).key,algorithms=[algorithm],issuer=document["issuer"],audience=cfg.oidc_client_id,options={"require":["exp","iss","aud","sub"]})
    if nonce is not None and claims.get("nonce")!=nonce:raise jwt.InvalidTokenError("OIDC nonce mismatch")
    return claims
def mapped_role(claims):
    cfg=settings();value=claims
    for part in cfg.oidc_role_claim.split("."):value=value.get(part) if isinstance(value,dict) else None
    values=value if isinstance(value,list) else [value] if value else [];mapped={cfg.oidc_role_map.get(str(item),"") for item in values}
    return "ADMIN" if "ADMIN" in mapped else "ANALYST" if "ANALYST" in mapped else "VIEWER"
def set_cookies(response,raw,csrf):
    cfg=settings();common={"secure":cfg.cookie_secure,"samesite":"lax","path":"/"};response.set_cookie(SESSION_COOKIE,raw,httponly=True,max_age=cfg.session_ttl_seconds,**common);response.set_cookie(CSRF_COOKIE,csrf,httponly=False,max_age=cfg.session_ttl_seconds,**common)

@router.get("/login")
async def login(db:Session=Depends(db_session)):
    cfg=settings();document=await discovery();state=opaque_token();nonce=opaque_token();verifier=opaque_token();challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode();db.add(OidcLoginState(state_hash=digest(state),nonce=nonce,code_verifier=verifier,expires_at=utcnow()+timedelta(minutes=10)));db.commit();query=urlencode({"client_id":cfg.oidc_client_id,"response_type":"code","scope":"openid profile email","redirect_uri":cfg.oidc_redirect_uri,"state":state,"nonce":nonce,"code_challenge":challenge,"code_challenge_method":"S256"});return RedirectResponse(f"{document['authorization_endpoint']}?{query}")

@router.get("/callback")
async def callback(code:str=Query(""),state:str=Query(""),db:Session=Depends(db_session)):
    cfg=settings();login_state=db.get(OidcLoginState,digest(state)) if state else None
    if not code or not login_state or login_state.expires_at<utcnow():raise HTTPException(400,"OIDC login state is invalid or expired")
    document=await discovery()
    async with httpx.AsyncClient(timeout=10) as client:
        token_response=await client.post(document["token_endpoint"],data={"grant_type":"authorization_code","code":code,"redirect_uri":cfg.oidc_redirect_uri,"client_id":cfg.oidc_client_id,"client_secret":cfg.oidc_client_secret,"code_verifier":login_state.code_verifier});token_response.raise_for_status();tokens=token_response.json();keys=(await client.get(document["jwks_uri"])).json()
    try:claims=validate_id_token(tokens.get("id_token"),document,keys,login_state.nonce)
    except jwt.PyJWTError as error:raise HTTPException(401,"OIDC token validation failed") from error
    db.delete(login_state);identity=db.scalar(select(OidcIdentity).where(OidcIdentity.issuer==document["issuer"],OidcIdentity.subject==claims["sub"]));role=mapped_role(claims)
    if identity:user=db.get(User,identity.user_id);identity.last_login_at=utcnow();user.role=role
    else:
        email=str(claims.get("email") or f"{claims['sub']}@oidc.invalid")[:320];base=re.sub(r"[^a-zA-Z0-9_.-]","-",email.split("@",1)[0])[:30] or "oidc";username=base;suffix=1
        while db.scalar(select(User.id).where(User.username==username)):suffix+=1;username=f"{base[:34]}-{suffix}"
        user=User(username=username,email=email,display_name=str(claims.get("name") or username)[:100],password_hash=hash_password(opaque_token()),role=role);db.add(user);db.flush();db.add(OidcIdentity(issuer=document["issuer"],subject=claims["sub"],user_id=user.id,last_login_at=utcnow()))
    raw,csrf=create_session(db,user);user.last_login_at=utcnow();audit(db,"authentication.oidc",actor=user.id,resource_type="user",resource_id=user.id,role=role,issuer=document["issuer"]);db.commit();response=RedirectResponse("/app/overview");set_cookies(response,raw,csrf);return response
