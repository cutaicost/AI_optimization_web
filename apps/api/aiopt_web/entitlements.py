"""Central plan definitions and organization authorization policy."""
from dataclasses import dataclass
from fastapi import Depends,HTTPException
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from .auth import require_operational_user
from .database import db_session
from .models import Organization,OrganizationMember,User

PLANS={
 "FREE":{"features":{"pricing_comparison","reports"},"limits":{"member_limit":1,"provider_limit":1,"telemetry_event_limit":100_000,"monthly_import_limit":2,"retention_days":30}},
 "PROFESSIONAL":{"features":{"live_telemetry","pricing_comparison","forecasting","simulation","anomaly_detection","efficiency_analysis","reports","data_export","budgets","gateway"},"limits":{"member_limit":5,"provider_limit":8,"telemetry_event_limit":1_000_000,"monthly_import_limit":25,"retention_days":90}},
 "BUSINESS":{"features":{"live_telemetry","pricing_comparison","forecasting","simulation","anomaly_detection","efficiency_analysis","reports","data_export","budgets","gateway","api_access","team_members","integrations","extended_retention","advanced_audit","policy_routing"},"limits":{"member_limit":25,"provider_limit":25,"telemetry_event_limit":10_000_000,"monthly_import_limit":250,"retention_days":365}},
 "ENTERPRISE":{"features":{"live_telemetry","pricing_comparison","forecasting","simulation","anomaly_detection","efficiency_analysis","reports","data_export","budgets","gateway","api_access","team_members","integrations","extended_retention","advanced_audit","sso","policy_routing"},"limits":{"member_limit":None,"provider_limit":None,"telemetry_event_limit":None,"monthly_import_limit":None,"retention_days":None}},
}
ROLE_PERMISSIONS={"OWNER":{"organization.manage","members.manage","membership.manage","providers.manage","security.manage","data.manage","configuration.manage","read"},"ADMIN":{"members.manage","providers.manage","data.manage","configuration.manage","read"},"ANALYST":{"analysis.use","read"},"VIEWER":{"read"}}

@dataclass(frozen=True)
class OrganizationContext: organization:Organization;membership:OrganizationMember;user:User

def ensure_default_organization(db:Session,user:User):
    membership=db.scalar(select(OrganizationMember).where(OrganizationMember.user_id==user.id,OrganizationMember.status=="ACTIVE").order_by(OrganizationMember.joined_at))
    if membership:return membership
    base=(user.organization or f"{user.display_name}'s Organization")[:120];slug=f"org-{user.id.casefold()}";org=Organization(name=base,slug=slug,created_by=user.id,plan_id="FREE");db.add(org);db.flush();membership=OrganizationMember(organization_id=org.id,user_id=user.id,role="OWNER");db.add(membership);db.flush();return membership

def organization_context(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    membership=ensure_default_organization(db,user);db.commit();return OrganizationContext(db.get(Organization,membership.organization_id),membership,user)

def require_permission(permission):
    def dependency(context:OrganizationContext=Depends(organization_context)):
        if permission not in ROLE_PERMISSIONS.get(context.membership.role,set()):raise HTTPException(403,"Organization permission required")
        return context
    return dependency

def entitlement(org:Organization,key):
    plan=PLANS.get(org.plan_id,PLANS["FREE"]);return key in plan["features"] or plan["limits"].get(key)
def plan_summary(org:Organization):
    plan=PLANS.get(org.plan_id,PLANS["FREE"]);return {"id":org.plan_id,"status":org.plan_status,"features":sorted(plan["features"]),"limits":plan["limits"]}
def enforce_limit(org:Organization,key,current:int,increment=1):
    limit=PLANS.get(org.plan_id,PLANS["FREE"])["limits"].get(key)
    if limit is not None and current+increment>limit:raise HTTPException(403,f"Organization {key} reached")
    return limit
