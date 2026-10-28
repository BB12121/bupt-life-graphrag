"""CI-only real backend with an explicit encoder/source test double; no model scores."""

from pathlib import Path
from tempfile import TemporaryDirectory

from conftest import TestEncoder, reference_source

from bupt_rag.api import create_app
from bupt_rag.config import Settings
from bupt_rag.service import KnowledgeService

directory = TemporaryDirectory(prefix="bupt-e2e-")
service = KnowledgeService(Settings(data_dir=Path(directory.name)), reference_source(), TestEncoder())
service.sync()
app = create_app(service.settings, service)
