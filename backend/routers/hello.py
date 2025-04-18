import logging
from fastapi import APIRouter
from ..models.common import HelloResponse

router = APIRouter()

@router.get("/hello/{name}", response_model=HelloResponse)
async def say_hello(name: str):
    """接收路径参数 name 并返回问候消息。"""
    logging.info(f"Received /hello/{name} request")
    return {"message": f"Hello, {name}"} 