from aiogram import Router
from .base import router as base_router
from .auth import router as auth_router
from .settings import router as settings_router
from .repos import router as repos_router
from .actions import router as actions_router
from .push import router as push_router
from .server_setup import router as server_router
from .profile import router as profile_router
from .create import router as create_router
from .files import router as files_router # NEW

router = Router()

router.include_router(base_router)
router.include_router(auth_router)
router.include_router(settings_router)
router.include_router(repos_router)
router.include_router(actions_router)
router.include_router(push_router)
router.include_router(server_router)
router.include_router(profile_router)
router.include_router(create_router)
router.include_router(files_router) # NEW