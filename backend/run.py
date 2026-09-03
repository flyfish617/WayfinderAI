import os

from app.config import settings

# HuggingFace 环境变量必须在导入 huggingface_hub / sentence_transformers 之前设置，
# 否则 huggingface_hub 在导入时已固化官方端点，国内直连会超时
if settings.HF_ENDPOINT:
    os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT
if settings.HF_HUB_OFFLINE:
    os.environ["HF_HUB_OFFLINE"] = str(settings.HF_HUB_OFFLINE)
if settings.HF_HUB_CACHE_DIR:
    os.environ["HF_HUB_CACHE_DIR"] = settings.HF_HUB_CACHE_DIR

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
