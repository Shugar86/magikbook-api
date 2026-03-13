from pydantic import BaseModel

class GenerateRequest(BaseModel):
    category: str
    model: str
    style: str
    input: str
