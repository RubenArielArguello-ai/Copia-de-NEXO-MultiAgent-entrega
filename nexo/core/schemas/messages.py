from pydantic import BaseModel

class AgentMessage(BaseModel):
    """Base message structure between agents"""
    to: str
    from_agent: str
    action: str
    data: dict
    
class OrquestradorCommand(BaseModel):
    """Command structure sent by the Orquestador"""
    to: str
    action: str
    data: dict
    
class StatusUpdate(BaseModel):
    """Status update message format"""
    from_agent: str
    status: str
    details: dict
