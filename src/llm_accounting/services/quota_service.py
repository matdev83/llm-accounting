from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..models.limits import UsageLimit, LimitScope, LimitType, TimeInterval

class QuotaService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def check_quota(
        self,
        model: str,
        username: str,
        caller_name: str,
        input_tokens: int,
        cost: float = 0.0 # Add cost parameter
    ) -> Tuple[bool, Optional[str]]:
        # Check limits in hierarchical order
        checks = [
            self._check_model_limits,  # Model-specific limits first
            self._check_global_limits,
            self._check_user_limits,
            self._check_caller_limits,
            self._check_user_caller_limits
        ]
        
        for check in checks:
            allowed, message = check(model, username, caller_name, input_tokens, cost)
            if not allowed:
                return False, message
                
        return True, None

    def _check_global_limits(self, model: str, username: str, caller_name: str, input_tokens: int, cost: float) -> Tuple[bool, Optional[str]]:
        limits = self.db.query(UsageLimit).filter(
            UsageLimit.scope == LimitScope.GLOBAL.value
        ).all()
        return self._evaluate_limits(limits, model, username, caller_name, input_tokens, cost)

    def _check_model_limits(self, model: str, username: str, caller_name: str, input_tokens: int, cost: float) -> Tuple[bool, Optional[str]]:
        limits = self.db.query(UsageLimit).filter(
            UsageLimit.scope == LimitScope.MODEL.value,
            UsageLimit.model == model
        ).all()
        # Model limits apply to all users/callers for this model
        return self._evaluate_limits(limits, model, None, None, input_tokens, cost)

    def _check_user_limits(self, model: str, username: str, caller_name: str, input_tokens: int, cost: float) -> Tuple[bool, Optional[str]]:
        limits = self.db.query(UsageLimit).filter(
            UsageLimit.scope == LimitScope.USER.value,
            UsageLimit.username == username
        ).all()
        return self._evaluate_limits(limits, model, username, caller_name, input_tokens, cost)

    def _check_caller_limits(self, model: str, username: str, caller_name: str, input_tokens: int, cost: float) -> Tuple[bool, Optional[str]]:
        limits = self.db.query(UsageLimit).filter(
            UsageLimit.scope == LimitScope.CALLER.value,
            UsageLimit.caller_name == caller_name
        ).all()
        return self._evaluate_limits(limits, model, username, caller_name, input_tokens, cost)

    def _check_user_caller_limits(self, model: str, username: str, caller_name: str, input_tokens: int, cost: float) -> Tuple[bool, Optional[str]]:
        limits = self.db.query(UsageLimit).filter(
            UsageLimit.scope == LimitScope.CALLER.value,
            UsageLimit.username == username,
            UsageLimit.caller_name == caller_name
        ).all()
        return self._evaluate_limits(limits, model, username, caller_name, input_tokens, cost)

    def _evaluate_limits(self, limits, model, username, caller_name, input_tokens, cost):
        now = datetime.now(timezone.utc)
        for limit in limits:
            start_time = now - limit.time_delta()
            
            # Calculate current usage
            current_usage = self._get_usage(
                limit.limit_type,
                start_time,
                model=model,
                username=username,
                caller_name=caller_name
            )
            
            # Calculate potential usage including current request
            if limit.limit_type == LimitType.REQUESTS.value:
                potential_usage = current_usage + 1
            elif limit.limit_type == LimitType.INPUT_TOKENS.value:
                potential_usage = current_usage + input_tokens
            elif limit.limit_type == LimitType.COST.value:
                potential_usage = current_usage + cost
            else:
                raise ValueError(f"Unknown limit type encountered in _evaluate_limits: {limit.limit_type}")
            
            if potential_usage > limit.max_value:
                # Format max_value as integer if whole number, else keep decimal
                formatted_max = f"{float(limit.max_value):.2f}"
                return False, f"{limit.scope.upper()} limit: {formatted_max} {limit.limit_type} per {limit.interval_value} {limit.interval_unit}"
        
        return True, None

    def _get_usage(self, limit_type: str, start_time: datetime, 
                  model: Optional[str] = None,
                  username: Optional[str] = None,
                  caller_name: Optional[str] = None) -> float:
        from llm_accounting.models import APIRequest
        
        query = self.db.query(APIRequest).filter(
            APIRequest.timestamp >= start_time
        )
        
        if model:
            query = query.filter(APIRequest.model == model)
        if username:
            query = query.filter(APIRequest.username == username)
        if caller_name:
            query = query.filter(APIRequest.caller_name == caller_name)
            
        if limit_type == LimitType.REQUESTS.value:
            return query.count()
        elif limit_type == LimitType.INPUT_TOKENS.value:
            return float(query.with_entities(func.sum(APIRequest.input_tokens)).scalar() or 0)
        elif limit_type == LimitType.OUTPUT_TOKENS.value:
            return float(query.with_entities(func.sum(APIRequest.output_tokens)).scalar() or 0)
        elif limit_type == LimitType.COST.value:
            return float(query.with_entities(func.sum(APIRequest.cost)).scalar() or 0)
            
        raise ValueError(f"Unknown limit type: {limit_type}")
