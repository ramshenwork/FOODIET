from pydantic import BaseModel


class QrOut(BaseModel):
    branch_code: str
    url: str
    svg: str
