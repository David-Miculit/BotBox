from pydantic import BaseModel

class SearchRequest(BaseModel):
    body: str