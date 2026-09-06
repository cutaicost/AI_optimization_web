import csv,io,math
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends,HTTPException,Query,Response
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from .auth import audit,require_csrf,require_operational_user
from .database import db_session
from .models import Budget,ForecastRun,Integration,ScenarioRun,TelemetryEvent,User
from .schemas import BudgetIn,IntegrationIn,ScenarioIn
from .secrets_store import secret_store

router=APIRouter(prefix="/api/v1")
def owner(user):return TelemetryEvent.user_id==user.id

@router.post("/forecasts",status_code=201,dependencies=[Depends(require_csrf)])
def forecast(metric:str=Query("spend",pattern=r"^(spend|tokens|requests)$"),horizon:int=Query(30,ge=7,le=365),user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    expression={"spend":func.sum(TelemetryEvent.estimated_cost),"tokens":func.sum(TelemetryEvent.total_tokens),"requests":func.count()}[metric]
    rows=db.execute(select(func.date(TelemetryEvent.timestamp),expression).where(owner(user)).group_by(func.date(TelemetryEvent.timestamp)).order_by(func.date(TelemetryEvent.timestamp))).all()
    if len(rows)<7:raise HTTPException(422,"Not enough telemetry to generate a forecast")
    values=[float(x[1] or 0) for x in rows];window=values[-min(28,len(values)):];daily=sum(window)/len(window);variance=sum((x-daily)**2 for x in window)/len(window);margin=1.96*math.sqrt(variance)
    start=datetime.fromisoformat(str(rows[-1][0])).date();points=[{"date":(start+timedelta(days=i)).isoformat(),"expected":daily,"lower":max(0,daily-margin),"upper":daily+margin} for i in range(1,horizon+1)]
    result={"metric":metric,"horizon_days":horizon,"summary":{"expected":daily*horizon,"lower":max(0,daily-margin)*horizon,"upper":(daily+margin)*horizon},"forecast":points,"method":"Trailing observed daily mean with empirical 95% interval","guarantee":False}
    run=ForecastRun(user_id=user.id,organization_id=None,parameters={"metric":metric,"horizon":horizon},result=result,source_start=datetime.fromisoformat(str(rows[0][0])).replace(tzinfo=timezone.utc),source_end=datetime.fromisoformat(str(rows[-1][0])).replace(tzinfo=timezone.utc));db.add(run);db.flush();audit(db,"forecast.created",actor=user.id,resource_type="forecast",resource_id=run.id,metric=metric,horizon=horizon);db.commit();return {"id":run.id,**result}

@router.get("/forecasts/runs")
def forecast_runs(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(ForecastRun).where(ForecastRun.user_id==user.id).order_by(ForecastRun.created_at.desc()).limit(50)).all();return {"items":[{"id":x.id,"created_at":x.created_at,"parameters":x.parameters,"result":x.result} for x in rows]}

@router.get("/forecasts/runs/{run_id}")
def forecast_run(run_id:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=db.scalar(select(ForecastRun).where(ForecastRun.id==run_id,ForecastRun.user_id==user.id))
    if not row:raise HTTPException(404,"Forecast not found")
    return {"id":row.id,"created_at":row.created_at,"parameters":row.parameters,"result":row.result}

@router.get("/optimization")
def optimization(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    rows=db.execute(select(TelemetryEvent.application,TelemetryEvent.model,func.count(),func.sum(TelemetryEvent.estimated_cost),func.sum(TelemetryEvent.total_tokens)).where(owner(user)).group_by(TelemetryEvent.application,TelemetryEvent.model).order_by(func.sum(TelemetryEvent.estimated_cost).desc()).limit(20)).all();total=sum(float(x[3] or 0) for x in rows)
    items=[{"issue":"Cost concentration","application":a,"model":m,"requests":r,"current_spend":float(c or 0),"tokens":t or 0,"estimated_opportunity":None,"reason":"This workload is among the highest observed spend contributors. Validate quality and pricing before substitution.","basis":"Observed telemetry; savings not estimated without an equivalent-model price and quality constraint"} for a,m,r,c,t in rows if total and float(c or 0)/total>=.2]
    return {"recommendations":items,"summary":{"count":len(items),"estimated_savings":None},"method":"Deterministic observed-cost concentration; no LLM used"}

@router.get("/anomalies")
def anomalies(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    rows=db.execute(select(func.date(TelemetryEvent.timestamp),func.sum(TelemetryEvent.total_tokens),func.sum(TelemetryEvent.estimated_cost),func.count(),func.avg(TelemetryEvent.duration_ms)).where(owner(user)).group_by(func.date(TelemetryEvent.timestamp)).order_by(func.date(TelemetryEvent.timestamp))).all();findings=[]
    for index,row in enumerate(rows):
        if index<7:continue
        for pos,name in ((1,"tokens"),(2,"spend"),(3,"requests"),(4,"latency")):
            baseline=sum(float(x[pos] or 0) for x in rows[max(0,index-28):index])/len(rows[max(0,index-28):index]);observed=float(row[pos] or 0)
            if baseline>0 and observed>=baseline*2:findings.append({"severity":"HIGH" if observed>=baseline*3 else "MEDIUM","metric":name,"observed":observed,"baseline":baseline,"time":str(row[0]),"scope":"All owned telemetry"})
    return {"items":findings[-50:],"method":"Trailing 7–28 day ratio baseline"}

def budget_json(row,db,user):
    start=datetime.now(timezone.utc).replace(day=1,hour=0,minute=0,second=0,microsecond=0);spent=float(db.scalar(select(func.coalesce(func.sum(TelemetryEvent.estimated_cost),0)).where(owner(user),TelemetryEvent.timestamp>=start)) or 0);percent=spent/row.monthly_amount*100
    return {"id":row.id,"name":row.name,"amount":row.monthly_amount,"period":row.period,"warning_threshold":row.warning_threshold,"is_active":row.is_active,"spent":spent,"remaining":max(0,row.monthly_amount-spent),"used_percent":percent,"state":"OVER" if percent>=100 else "WARNING" if percent>=row.warning_threshold else "OK"}
@router.get("/budgets")
def budgets(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):return {"items":[budget_json(x,db,user) for x in db.scalars(select(Budget).where(Budget.user_id==user.id)).all()]}
@router.post("/budgets",status_code=201,dependencies=[Depends(require_csrf)])
def create_budget(payload:BudgetIn,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=Budget(user_id=user.id,name=payload.name,monthly_amount=payload.monthly_amount,period=payload.period,warning_threshold=payload.warning_threshold,is_active=payload.is_active);db.add(row);db.flush();audit(db,"budget.created",actor=user.id,resource_type="budget",resource_id=row.id);db.commit();return budget_json(row,db,user)
@router.patch("/budgets/{budget_id}",dependencies=[Depends(require_csrf)])
def update_budget(budget_id:str,payload:BudgetIn,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=db.scalar(select(Budget).where(Budget.id==budget_id,Budget.user_id==user.id))
    if not row:raise HTTPException(404,"Budget not found")
    for key,value in payload.model_dump().items():setattr(row,"monthly_amount" if key=="monthly_amount" else key,value)
    audit(db,"budget.updated",actor=user.id,resource_type="budget",resource_id=row.id);db.commit();return budget_json(row,db,user)
@router.delete("/budgets/{budget_id}",dependencies=[Depends(require_csrf)])
def delete_budget(budget_id:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=db.scalar(select(Budget).where(Budget.id==budget_id,Budget.user_id==user.id))
    if not row:raise HTTPException(404,"Budget not found")
    db.delete(row);audit(db,"budget.deleted",actor=user.id,resource_type="budget",resource_id=budget_id);db.commit();return {"deleted":budget_id}

@router.post("/scenarios",status_code=201,dependencies=[Depends(require_csrf)])
def scenario(payload:ScenarioIn,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    inputs=payload.model_dump();cost=payload.monthly_requests*(payload.input_tokens_per_request*payload.input_price_per_million+payload.output_tokens_per_request*payload.output_price_per_million)/1_000_000;result={"monthly_cost":cost,"annual_cost":cost*12,"monthly_tokens":payload.monthly_requests*(payload.input_tokens_per_request+payload.output_tokens_per_request),"labels":{"inputs":"USER-SUPPLIED ASSUMPTIONS","outputs":"CALCULATED","quality":"NOT EVALUATED"}};row=ScenarioRun(user_id=user.id,parameters=inputs,result=result);db.add(row);db.flush();audit(db,"scenario.executed",actor=user.id,resource_type="scenario",resource_id=row.id);db.commit();return {"id":row.id,**result}
@router.get("/scenarios")
def scenarios(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):return {"items":[{"id":x.id,"parameters":x.parameters,"result":x.result,"created_at":x.created_at} for x in db.scalars(select(ScenarioRun).where(ScenarioRun.user_id==user.id).order_by(ScenarioRun.created_at.desc())).all()]}
@router.get("/scenarios/{scenario_id}")
def scenario_detail(scenario_id:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=db.scalar(select(ScenarioRun).where(ScenarioRun.id==scenario_id,ScenarioRun.user_id==user.id))
    if not row:raise HTTPException(404,"Scenario not found")
    return {"id":row.id,"parameters":row.parameters,"result":row.result}

def report_data(db,user):
    row=db.execute(select(func.count(),func.coalesce(func.sum(TelemetryEvent.total_tokens),0),func.coalesce(func.sum(TelemetryEvent.estimated_cost),0),func.count(func.distinct(TelemetryEvent.model))).where(owner(user))).one();return {"requests":row[0],"tokens":row[1],"spend":float(row[2]),"models":row[3]}
@router.get("/reports/executive")
def report(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):audit(db,"report.exported",actor=user.id,resource_type="report",format="json");db.commit();return report_data(db,user)
def csv_safe(value):
    text=str(value);return "'"+text if text.startswith(("=","+","-","@","\t","\r")) else text
@router.get("/reports/executive.csv")
def report_csv(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    data=report_data(db,user);output=io.StringIO();writer=csv.writer(output);writer.writerow(["metric","value"])
    for key,value in data.items():writer.writerow([csv_safe(key),csv_safe(value)])
    audit(db,"report.exported",actor=user.id,resource_type="report",format="csv");db.commit();return Response(output.getvalue(),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=aiopt-report.csv"})

def integration_json(row):return {"id":row.id,"name":row.name,"kind":row.kind,"endpoint":row.configuration.get("endpoint"),"credential_configured":bool(row.secret_reference),"credential_reference":f"{row.secret_reference[:2]}***" if row.secret_reference else None,"created_at":row.created_at}
@router.get("/integrations")
def integrations(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):return {"items":[integration_json(x) for x in db.scalars(select(Integration).where(Integration.user_id==user.id)).all()],"secret_storage":"environment reference"}
@router.post("/integrations",status_code=201,dependencies=[Depends(require_csrf)])
def create_integration(payload:IntegrationIn,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=Integration(user_id=user.id,name=payload.name,kind=payload.kind,configuration={"endpoint":payload.endpoint},secret_reference=payload.secret_env_name);db.add(row);db.flush();audit(db,"integration.configured",actor=user.id,resource_type="integration",resource_id=row.id,kind=row.kind,credential_available=secret_store.exists(payload.secret_env_name) if payload.secret_env_name else False);db.commit();return integration_json(row)
@router.delete("/integrations/{integration_id}",dependencies=[Depends(require_csrf)])
def delete_integration(integration_id:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=db.scalar(select(Integration).where(Integration.id==integration_id,Integration.user_id==user.id))
    if not row:raise HTTPException(404,"Integration not found")
    db.delete(row);audit(db,"integration.deleted",actor=user.id,resource_type="integration",resource_id=integration_id);db.commit();return {"deleted":integration_id}
