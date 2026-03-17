from .auth import router as auth_router
from .core import router as core_router
from .files import router as files_router

__all__ = ["auth_router", "core_router", "files_router"]