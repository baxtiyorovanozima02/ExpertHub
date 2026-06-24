from pydantic import BaseModel


class AdminStatsOut(BaseModel):
    total_users: int
    total_experts: int
    verified_experts: int
    total_categories: int
    total_documents: int