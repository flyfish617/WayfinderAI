from app.services.unsplash_service import UnsplashService
from app.config import settings


if __name__ == "__main__":
    if not settings.UNSPLASH_ACCESS_KEY:
        print("请先在 .env 中配置 UNSPLASH_ACCESS_KEY")
    else:
        service = UnsplashService(access_key=settings.UNSPLASH_ACCESS_KEY)
        photos = service.search_photos("beijing", per_page=1)
        print(photos)
