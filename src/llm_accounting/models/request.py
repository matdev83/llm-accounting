from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

@dataclass
class APIRequest:
    model: str
    username: str
    caller_name: str
    input_tokens: int
    output_tokens: int
    cost: float
    timestamp: datetime
    id: Optional[int] = None # ID is optional for new requests, will be assigned by DB
