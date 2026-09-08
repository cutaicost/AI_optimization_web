"""Version-aware, provider-neutral Decimal token pricing."""
from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal
from sqlalchemy import or_,select
from .models import PriceOverride,PricingRecord

MILLION=Decimal("1000000")
@dataclass(frozen=True)
class CostResult:
    input_cost:Decimal;output_cost:Decimal;cached_input_cost:Decimal;total_cost:Decimal;pricing_record_id:str|None;pricing_source:str
class CostCalculator:
    def __init__(self,db,user_id=None):self.db=db;self.user_id=user_id;self.cache={}
    def _prices(self,provider,model):
        key=(provider.casefold(),model)
        if key not in self.cache:self.cache[key]=self.db.scalars(select(PricingRecord).where(PricingRecord.provider==key[0],PricingRecord.model==model).order_by(PricingRecord.effective_from.desc())).all()
        return self.cache[key]
    def calculate(self,provider,model,at,input_tokens,output_tokens,cached_input_tokens=0):
        if at.tzinfo is None:at=at.replace(tzinfo=timezone.utc)
        aware=lambda value:value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value
        override=self.db.scalar(select(PriceOverride).where(PriceOverride.user_id==self.user_id,PriceOverride.provider==provider.casefold(),PriceOverride.model==model)) if self.user_id else None
        price=next((p for p in self._prices(provider,model) if aware(p.effective_from)<=at and (p.effective_to is None or at<aware(p.effective_to))),None)
        if override:
            price=type("EffectivePrice",(),{"input_price":override.input_price,"output_price":override.output_price,"cached_input_price":None,"id":None})()
        if not price:return None
        cached=Decimal(cached_input_tokens);regular=Decimal(input_tokens)-cached
        if regular<0:raise ValueError("Cached input tokens cannot exceed input tokens")
        if cached and price.cached_input_price is None:return None
        input_cost=regular*Decimal(price.input_price)/MILLION;output_cost=Decimal(output_tokens)*Decimal(price.output_price)/MILLION;cached_cost=cached*Decimal(price.cached_input_price or 0)/MILLION
        return CostResult(input_cost,output_cost,cached_cost,input_cost+output_cost+cached_cost,price.id,"MANUAL_OVERRIDE" if override else price.provenance)
