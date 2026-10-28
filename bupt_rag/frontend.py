"""Serve the built Vue app without masking API or missing-asset errors."""

import re

from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        path = path.replace("\\", "/")
        if scope["method"] in {"GET", "HEAD"} and (
            path in {".", "", "documents", "knowledge", "lab"} or re.fullmatch(r"documents/[^/.]+", path)
        ):
            return FileResponse(self.directory / "index.html", headers={"Cache-Control": "no-cache"})
        return await super().get_response(path, scope)
